import os
import time
import logging
import threading

from agent import Agent

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def launch_agent(host: str, port: int, team_name: str, unum: int):
    while True:
        try:
            agent = Agent(host, port, team_name, unum)
            agent.run()
        except Exception as e:
            logger.error(f"[Agente {unum}] Error inesperado: {e}")
            import traceback
            logger.error(traceback.format_exc())
        logger.info(f"[Agente {unum}] Reconectando en 3s...")
        time.sleep(3)


def main():
    host = os.getenv("SERVER_IP", "rcssserver")
    port = int(os.getenv("SERVER_PORT", "6000"))
    team_name = os.getenv("TEAM", "Team").capitalize()
    num_agents = int(os.getenv("NUM_AGENTS", "11"))

    logger.info(
        f"Lanzando {num_agents} agentes para equipo '{team_name}' → {host}:{port}"
    )

    training = os.getenv("TRAINING", "false").lower() == "true"
    if training:
        logger.info("MODO ENTRENAMIENTO ACTIVADO")

    threads = []
    for unum in range(1, num_agents + 1):
        time.sleep(0.15)
        t = threading.Thread(
            target=launch_agent,
            args=(host, port, team_name, unum),
            daemon=True,
            name=f"agente-{unum}",
        )
        t.start()
        threads.append(t)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Deteniendo agentes...")


if __name__ == "__main__":
    main()
