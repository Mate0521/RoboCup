"""
Agent — orquesta el ciclo de vida de un agente individual.
Conecta, inicializa, y corre el loop de percepción-decisión-acción.
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
        self.perception = Perception()
        self.decision = DecisionMaker(self.perception)

        self._running = False

    def connect(self) -> bool:
        """Inicializa la conexión con el servidor. Retorna True si exitoso."""
        logger.info(f"[Agente {self.unum}] Conectando a {self.host}:{self.port}...")
        response = self.client.init(self.team_name)

        if not response:
            logger.error(f"[Agente {self.unum}] Sin respuesta del servidor.")
            return False

        parsed = parse(response)

        if parsed["type"] == "error":
            logger.error(f"[Agente {self.unum}] Error del servidor: {parsed['data']}")
            return False

        if parsed["type"] == "init":
            self.perception.update(parsed)
            assigned_unum = self.perception.state.unum
            side = self.perception.state.side
            logger.info(
                f"[Agente {self.unum}] Conectado — "
                f"equipo: {self.team_name} | lado: {side} | unum: {assigned_unum}"
            )
            return True

        logger.warning(f"[Agente {self.unum}] Respuesta inesperada: {response}")
        return False

    def run(self):
        """Loop principal del agente."""
        if not self.connect():
            return

        self._running = True
        logger.info(f"[Agente {self.unum}] Iniciando loop...")

        while self._running:
            # 1. Recibir mensajes del servidor
            message = self.client.receive()

            if message is None:
                continue

            # 2. Parsear y actualizar percepción
            parsed = parse(message)
            self.perception.update(parsed)

            # Solo actuar en mensajes sense_body (cada 100ms)
            if parsed["type"] != "sense_body":
                continue

            # 3. Decidir acción
            command = self.decision.decide()

            # 4. Enviar comando
            if command:
                self.client.send(command)

    def stop(self):
        self._running = False
        self.client.close()