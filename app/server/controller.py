import json
import socket

from config import AppConfig
from core.connection import recv_secure, send_secure
from protocol.handshake import server_handshake
from server.dispatcher import build_registry, dispatch


def run_server(config: AppConfig) -> None:
    registry = build_registry(config)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.bind((config.host, config.port))
        server.listen(5)
        print(f"[QSH] listening on {config.host}:{config.port}")
        while True:
            conn, addr = server.accept()
            print(f"[QSH] connection from {addr}")
            with conn:
                try:
                    transport = server_handshake(conn, config)
                    while True:
                        frame = recv_secure(conn)
                        payload = json.loads(transport.decrypt(frame).decode("utf-8"))
                        response = dispatch(payload, registry)
                        send_secure(conn, transport.encrypt(json.dumps(response).encode("utf-8")))
                        if response.get("type") == "BYE":
                            break
                except Exception as exc:
                    print(f"[QSH] session error: {exc}")
