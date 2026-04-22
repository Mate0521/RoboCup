"""
Entrenador offline — aprende de archivos de log .rcg del servidor.

El servidor genera archivos .rcg automáticamente en cada partida.
Este script los parsea, extrae (estado, acción) y entrena el modelo
por imitación antes de conectar al servidor en vivo.

Uso:
  python src/ml/trainer.py --role forward --logs /path/to/logs/ --epochs 50

El entrenamiento offline es la fase 1. La fase 2 es el fine-tuning
online con OnlineTrainer durante la simulación.
"""

import os
import re
import argparse
import numpy as np
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger(__name__)


# ── Parser de archivos .rcg ───────────────────────────────────────────────────

class RCGParser:
    """
    Parsea archivos .rcg (RoboCup Game Log) para extraer
    estados y acciones de cada jugador por ciclo.

    Formato relevante del .rcg:
      (show T (ball (pos X Y) (vel VX VY)) (player "TEAM" N ...))
    """

    def parse_file(self, path: str) -> list[dict]:
        """
        Retorna lista de frames. Cada frame:
          time, ball_x, ball_y, ball_vx, ball_vy,
          players: [{team, unum, x, y, vx, vy, body_dir}]
        """
        frames = []
        with open(path, "r", errors="ignore") as f:
            for line in f:
                frame = self._parse_line(line.strip())
                if frame:
                    frames.append(frame)
        return frames

    def _parse_line(self, line: str) -> dict | None:
        if not line.startswith("(show"):
            return None

        t_m = re.search(r"\(show\s+(\d+)", line)
        if not t_m:
            return None
        time = int(t_m.group(1))

        # Balón
        ball_m = re.search(
            r"\(ball\s+\(pos\s+([\d\.\-]+)\s+([\d\.\-]+)\)\s*"
            r"\(vel\s+([\d\.\-]+)\s+([\d\.\-]+)\)", line
        )
        if not ball_m:
            return None

        frame = {
            "time":    time,
            "ball_x":  float(ball_m.group(1)),
            "ball_y":  float(ball_m.group(2)),
            "ball_vx": float(ball_m.group(3)),
            "ball_vy": float(ball_m.group(4)),
            "players": [],
        }

        # Jugadores
        for pm in re.finditer(
            r'\(player\s+"([^"]+)"\s+(\d+)\s+'
            r'\(pos\s+([\d\.\-]+)\s+([\d\.\-]+)\)\s*'
            r'\(vel\s+([\d\.\-]+)\s+([\d\.\-]+)\)\s*'
            r'\(body\s+([\d\.\-]+)\)', line
        ):
            frame["players"].append({
                "team":     pm.group(1),
                "unum":     int(pm.group(2)),
                "x":        float(pm.group(3)),
                "y":        float(pm.group(4)),
                "vx":       float(pm.group(5)),
                "vy":       float(pm.group(6)),
                "body_dir": float(pm.group(7)),
            })

        return frame


# ── Construcción del dataset ──────────────────────────────────────────────────

def frames_to_dataset(frames: list[dict], role: str,
                      target_team: str = "") -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Convierte frames del .rcg en arrays (X, y_action, y_params).

    La acción se infiere comparando la posición del jugador entre
    frames consecutivos (imitación comportamental):
      - Si se movió >0.5 unidades hacia el balón → MOVE_TO_BALL → DASH
      - Si el balón cambió velocidad bruscamente → KICK
      - Si giró >10° → TURN
      - Si no hizo nada relevante → STAY
    """
    from ml.model import (
        ACTION_TURN_LEFT, ACTION_TURN_RIGHT,
        ACTION_DASH, ACTION_KICK, ACTION_STAY
    )
    from util.field_constants import (
        normalize_x, normalize_y, normalize_dist,
        normalize_angle, normalize_stamina,
        FIELD_HALF_LEN, FIELD_HALF_WID,
    )

    X, y_act, y_par = [], [], []

    for i in range(len(frames) - 1):
        curr = frames[i]
        nxt  = frames[i + 1]

        for player in curr["players"]:
            if target_team and player["team"] != target_team:
                continue

            unum = player["unum"]

            # Encontrar el mismo jugador en el siguiente frame
            next_player = next(
                (p for p in nxt["players"]
                 if p["unum"] == unum and p["team"] == player["team"]),
                None,
            )
            if not next_player:
                continue

            # ── Construir vector de estado simplificado ─────────────────────
            # (versión aproximada desde datos del .rcg, sin sense_body completo)
            px, py = player["x"], player["y"]
            bx, by = curr["ball_x"], curr["ball_y"]

            ball_dist  = ((bx - px)**2 + (by - py)**2) ** 0.5
            ball_angle = 0.0  # aproximado — no tenemos la orientación exacta

            state_vec = np.zeros(58, dtype=np.float32)
            state_vec[0] = normalize_dist(ball_dist)
            state_vec[6] = normalize_x(px)
            state_vec[7] = normalize_y(py)
            state_vec[10] = normalize_dist(
                (player["vx"]**2 + player["vy"]**2)**0.5, max_dist=3.0
            )

            # ── Inferir acción ───────────────────────────────────────────────
            dx = next_player["x"] - px
            dy = next_player["y"] - py
            moved = (dx**2 + dy**2) ** 0.5

            ball_speed_change = abs(
                (nxt["ball_vx"]**2 + nxt["ball_vy"]**2)**0.5 -
                (curr["ball_vx"]**2 + curr["ball_vy"]**2)**0.5
            )

            dir_change = abs(next_player["body_dir"] - player["body_dir"])

            # Heurística de acción
            if ball_speed_change > 0.5 and ball_dist < 2.0:
                action = ACTION_KICK
                params = np.array([0.0, 1.0, 0.0], dtype=np.float32)
            elif moved > 0.3:
                action = ACTION_DASH
                params = np.array([0.0, min(1.0, moved * 2), 0.0], dtype=np.float32)
            elif dir_change > 10:
                action = ACTION_TURN_LEFT if dx < 0 else ACTION_TURN_RIGHT
                params = np.array([dir_change / 180.0, 0.0, 0.0], dtype=np.float32)
            else:
                action = ACTION_STAY
                params = np.zeros(3, dtype=np.float32)

            X.append(state_vec)
            y_act.append(action)
            y_par.append(params)

    if not X:
        return np.zeros((0, 58)), np.zeros(0, dtype=int), np.zeros((0, 3))

    return np.stack(X), np.array(y_act, dtype=np.int32), np.stack(y_par)


# ── Script de entrenamiento ───────────────────────────────────────────────────

def train_offline(role: str, logs_dir: str, epochs: int = 50,
                  batch_size: int = 64, lr: float = 1e-3):
    """
    Entrena el modelo para un rol usando archivos .rcg.
    """
    from ml.model import AgentBrain, compile_model

    logger.info(f"Entrenamiento offline — rol: {role}")

    # Cargar y parsear logs
    parser = RCGParser()
    all_frames = []
    log_files = [f for f in os.listdir(logs_dir) if f.endswith(".rcg")]

    if not log_files:
        logger.error(f"No se encontraron archivos .rcg en {logs_dir}")
        return

    for fname in log_files:
        path = os.path.join(logs_dir, fname)
        logger.info(f"Parseando {fname}...")
        frames = parser.parse_file(path)
        all_frames.extend(frames)
        logger.info(f"  → {len(frames)} frames")

    logger.info(f"Total frames: {len(all_frames)}")

    # Construir dataset
    X, y_act, y_par = frames_to_dataset(all_frames, role)
    if len(X) == 0:
        logger.error("Dataset vacío — sin datos para entrenar.")
        return

    logger.info(f"Dataset: {len(X)} muestras | acciones: {np.bincount(y_act)}")

    # Crear y compilar modelo
    brain = AgentBrain(role, training=True)
    compile_model(brain.model, learning_rate=lr)

    # Entrenar
    history = brain.model.fit(
        X,
        {"action_probs": y_act, "action_params": y_par},
        epochs=epochs,
        batch_size=batch_size,
        validation_split=0.1,
        verbose=1,
    )

    # Guardar pesos
    brain.save_weights()
    logger.info(f"Pesos guardados para rol '{role}'.")

    return history


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Entrenamiento offline RoboCup")
    ap.add_argument("--role",   required=True,
                    choices=["goalkeeper", "defender", "midfielder", "forward"])
    ap.add_argument("--logs",   required=True, help="Directorio con archivos .rcg")
    ap.add_argument("--epochs", type=int, default=50)
    ap.add_argument("--lr",     type=float, default=1e-3)
    args = ap.parse_args()

    train_offline(args.role, args.logs, args.epochs, lr=args.lr)