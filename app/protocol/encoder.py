import json
import struct
from typing import Any


def encode_json_packet(data: dict[str, Any]) -> bytes:
    payload = json.dumps(data).encode("utf-8")
    return struct.pack("!I", len(payload)) + payload


def decode_json_packet(payload: bytes) -> dict[str, Any]:
    return json.loads(payload.decode("utf-8"))
