"""
Agent — ciclo de vida de un agente individual.
Fix principal: el loop ahora procesa TODOS los mensajes pendientes
antes de decidir, evitando que el agente se quede quieto.
"""
import logging
import time

from comunication.client import RCSSClient
from comunication.parser import parse
from modules.perception import Perception
from modules.decision import DecisionMaker

logger = logging.getLogger(__name__)


class Agent:
    def __init__(self, host: str, port: int, team_name: str, unum: int):
        self.host = host
        self.port = port
        self.team_name = team_name
        self.unum = unum

        self.client = RCSSClient(host, port)
        self.perception = Perception(team_name=team_name)
        self.decision = DecisionMaker(self.perception, team_name=team_name)
        self._running = False

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
                f"lado: {self.perception.state.side} | unum: {self.perception.state.unum}"
            )
            return True

        return False

    def run(self):
        if not self.connect():
            return

        self._running = True
        logger.info(f"[Agente {self.unum}] Loop iniciado.")

        while self._running:
            # Drenar todos los mensajes pendientes del buffer UDP.
            # Importante: actualizar percepción con TODOS los mensajes (see + sense_body),
            # pero solo enviar UN comando por ciclo (cuando llega sense_body).
            # Esto evita saturar el servidor con comandos y perder información visual.
            acted = False
            for _ in range(30):  # max 30 msgs por ciclo (defensivo)
                message = self.client.receive()
                if message is None:
                    break

                parsed = parse(message)
                self.perception.update(parsed)

                # Actuar en sense_body (señal de sincronía con el simulador, cada 100ms)
                # Solo actuamos una vez por ciclo aunque lleguen varios sense_body
                if parsed["type"] == "sense_body" and not acted:
                    command = self.decision.decide()
                    if command:
                        self.client.send(command)
                    acted = True

            # Si no llegó ningún sense_body en este ciclo (buffer vacío),
            # no bloqueamos — el timeout de 0.08s en el socket ya es suficiente.

    def stop(self):
        self._running = False
        self.client.close()