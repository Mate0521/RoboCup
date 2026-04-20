import re
import logging

logger = logging.getLogger(__name__)


def parse(message: str) -> dict:
    """
    Parsea cualquier mensaje del servidor y retorna un dict con:
        type  → tipo del mensaje (hear, see, sense_body, init, error, etc.)
        raw   → mensaje original
        data  → contenido parseado (depende del tipo)
    """
    if not message:
        return {"type": "empty", "raw": message, "data": {}}

    msg_type = _get_type(message)

    parsers = {
        "init":       _parse_init,
        "see":        _parse_see,
        "sense_body": _parse_sense_body,
        "hear":       _parse_hear,
        "server_param": _parse_generic,
        "player_param": _parse_generic,
        "player_type":  _parse_generic,
        "error":      _parse_error,
        "warning":    _parse_warning,
        "ok":         _parse_generic,
    }

    parser_fn = parsers.get(msg_type, _parse_generic)
    data = parser_fn(message)

    return {"type": msg_type, "raw": message, "data": data}


def _get_type(message: str) -> str:
    m = re.match(r"\((\w+)", message)
    return m.group(1) if m else "unknown"


def _parse_init(message: str) -> dict:
    """(init Side Unum PlayMode)"""
    m = re.match(r"\(init\s+(\w+)\s+(\d+)\s+(\w+)\)", message)
    if m:
        return {"side": m.group(1), "unum": int(m.group(2)), "play_mode": m.group(3)}
    return {"raw": message}


def _parse_see(message: str) -> dict:
    """
    Extrae objetos visibles del mensaje see.
    Retorna lista de objetos con nombre y datos de distancia/ángulo.
    """
    objects = []
    # Cada objeto visible: ((nombre) dist ang ...)
    pattern = re.compile(r"\(\(([^)]+)\)\s*([\d\.\-\s]*)\)")
    for match in pattern.finditer(message):
        name = match.group(1).strip()
        values = match.group(2).strip().split()
        obj = {"name": name}
        if len(values) >= 2:
            try:
                obj["distance"]    = float(values[0])
                obj["angle"]       = float(values[1])
                # dist_change y dir_change (velocidad del objeto)
                if len(values) >= 4:
                    obj["dist_change"] = float(values[2])
                    obj["dir_change"]  = float(values[3])
            except ValueError:
                pass
        objects.append(obj)

    # Extraer timestamp
    t = re.match(r"\(see\s+(\d+)", message)
    return {"time": int(t.group(1)) if t else None, "objects": objects}


def _parse_sense_body(message: str) -> dict:
    """Extrae stamina, velocidad, ángulo del cuerpo y dirección absoluta."""
    data = {}
    t = re.match(r"\(sense_body\s+(\d+)", message)
    if t:
        data["time"] = int(t.group(1))

    stamina = re.search(r"\(stamina\s+([\d\.]+)\s+([\d\.]+)", message)
    if stamina:
        data["stamina"]  = float(stamina.group(1))
        data["effort"]   = float(stamina.group(2))

    speed = re.search(r"\(speed\s+([\d\.]+)\s+([\d\.\-]+)", message)
    if speed:
        data["speed"]       = float(speed.group(1))
        data["speed_angle"] = float(speed.group(2))

    head = re.search(r"\(head_angle\s+([\d\.\-]+)", message)
    if head:
        data["head_angle"] = float(head.group(1))

    # body_direction: el servidor envía (body_angle <deg>) en sense_body
    # Este es el ángulo ABSOLUTO del cuerpo en el campo — la fuente de verdad.
    # Sin esto, body_direction solo viene de notify_turn() y se desincroniza.
    body = re.search(r"\(body_angle\s+([\d\.\-]+)", message)
    if body:
        data["body_dir"] = float(body.group(1))

    # Fallback: algunos servidores usan (dir <x> <y>)
    if "body_dir" not in data:
        dir_m = re.search(r"\(dir\s+([\d\.\-]+)", message)
        if dir_m:
            data["body_dir"] = float(dir_m.group(1))

    return data


def _parse_hear(message: str) -> dict:
    """(hear Time Sender Message)"""
    m = re.match(r"\(hear\s+(\d+)\s+(\S+)\s+(.*)\)", message)
    if m:
        return {"time": int(m.group(1)), "sender": m.group(2), "message": m.group(3)}
    return {"raw": message}


def _parse_error(message: str) -> dict:
    m = re.match(r"\(error\s+(.*)\)", message)
    return {"message": m.group(1) if m else message}


def _parse_warning(message: str) -> dict:
    m = re.match(r"\(warning\s+(.*)\)", message)
    return {"message": m.group(1) if m else message}


def _parse_generic(message: str) -> dict:
    return {"raw": message}