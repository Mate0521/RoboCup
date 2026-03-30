import socket
import time
import logging

logger = logging.getLogger(__name__)

SERVER_BUFFER = 8192


class RCSSClient:
    """Maneja la comunicación UDP con el rcssserver."""

    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.settimeout(3.0)
        self.server_addr = (host, port)
        self.connected = False

    def send(self, message: str):
        """Envía un mensaje al servidor. Los mensajes terminan en \x00."""
        data = (message + "\x00").encode("utf-8")
        self.socket.sendto(data, self.server_addr)
        logger.debug(f"SEND → {message}")

    def receive(self) -> str | None:
        """Recibe un mensaje del servidor. Retorna None si timeout."""
        try:
            data, addr = self.socket.recvfrom(SERVER_BUFFER)
            # El servidor responde desde un puerto diferente al 6000
            # Actualizamos la dirección del servidor para respuestas futuras
            self.server_addr = addr
            msg = data.decode("utf-8").rstrip("\x00").strip()
            logger.debug(f"RECV ← {msg}")
            return msg
        except socket.timeout:
            return None

    def init(self, team_name: str, version: int = 19) -> str | None:
        """
        Inicializa el agente con el servidor.
        Envía (init TeamName (version N)) y espera la respuesta.
        Retorna el mensaje de respuesta o None si falla.
        """
        msg = f"(init {team_name} (version {version}))"
        self.send(msg)
        response = self.receive()
        if response:
            self.connected = True
            logger.info(f"Init response: {response}")
        return response

    def close(self):
        self.socket.close()
        self.connected = False