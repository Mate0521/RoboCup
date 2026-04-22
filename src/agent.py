"""
Agent — ciclo de vida de un agente individual.
Cambios v3:
  - Llama decision.update_score() cuando el marcador cambia
  - Llama decision.notify_episode_end() al desconectarse
  - Detecta TIME_OVER para cerrar el episodio limpiamente
"""
import logging

from comunication.client import RCSSClient
from comunication.parser import parse
from modules.perception import Perception, PlayMode
from modules.decision import DecisionMaker

logger = logging.getLogger(__name__)


class Agent:
    def __init__(self, host: str, port: int, team_name: str, unum: int):
        self.host      = host
        self.port      = port
        self.team_name = team_name
        self.unum      = unum

        self.client     = RCSSClient(host, port)
        self.perception = Perception(team_name=team_name)
        self.decision   = DecisionMaker(self.perception, team_name=team_name)
        self._running   = False

        # Seguimiento del score para detectar cambios
        self._last_score_diff = 0.0

    def connect(self) -> bool:
        logger.info(f"[Agente {self.unum}] Conectando a {self.host}:{self.port}...")
        response = self.client.init(self.team_name)
        if not response:
            logger.error(f"[Agente {self.unum}] Sin respuesta del servidor.")
            return False

        parsed = parse(response)
        if parsed["type"] == "error":
            logger.error(f"[Agente {self.unum}] Error: {parsed['data']}")
            return False

        if parsed["type"] == "init":
            self.perception.update(parsed)
            logger.info(
                f"[Agente {self.unum}] Conectado — "
                f"lado: {self.perception.state.side} | "
                f"unum: {self.perception.state.unum}"
            )
            return True

        return False

    def run(self):
        if not self.connect():
            return

        self._running = True
        logger.info(f"[Agente {self.unum}] Loop iniciado.")

        try:
            while self._running:
                acted = False

                # Drenar TODOS los mensajes pendientes del buffer UDP
                for _ in range(30):
                    message = self.client.receive()
                    if message is None:
                        break

                    parsed = parse(message)
                    self.perception.update(parsed)

                    # Detectar fin de partido para cerrar episodio
                    if self.perception.state.play_mode == PlayMode.TIME_OVER:
                        self._on_episode_end()
                        self._running = False
                        break

                    # Actuar solo en sense_body (100ms del simulador)
                    if parsed["type"] == "sense_body" and not acted:
                        # Actualizar score_diff si cambió
                        current_score = self.perception.score_diff()
                        if current_score != self._last_score_diff:
                            self._last_score_diff = current_score
                            self.decision.update_score(current_score)

                        command = self.decision.decide()
                        if command:
                            self.client.send(command)
                        acted = True

        except Exception as e:
            logger.error(f"[Agente {self.unum}] Error en loop: {e}")
        finally:
            self._on_episode_end()

    def _on_episode_end(self):
        """Cierra el episodio limpiamente — guarda pesos si está entrenando."""
        try:
            if hasattr(self.decision, "notify_episode_end"):
                self.decision.notify_episode_end()
        except Exception as e:
            logger.warning(f"[Agente {self.unum}] Error al cerrar episodio: {e}")

    def stop(self):
        self._running = False
        self.client.close()