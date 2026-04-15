import base64
from getpass import getpass
import json
import socket
from pathlib import Path
from shlex import split as shlex_split

from config import AppConfig
from core.connection import recv_secure, send_secure
from protocol.handshake import client_handshake


def _send_request(sock: socket.socket, transport: object, payload: dict) -> dict:
    frame = transport.encrypt(json.dumps(payload).encode("utf-8"))
    send_secure(sock, frame)
    response = transport.decrypt(recv_secure(sock))
    return json.loads(response.decode("utf-8"))


def _authenticate(sock: socket.socket, transport: object, password: str) -> None:
    response = _send_request(sock, transport, {"action": "auth", "password": password})
    if response.get("type") != "AUTH_RESULT" or not response.get("ok"):
        if response.get("error") == "locked_out":
            raise RuntimeError(
                f"authentication failed: locked out, retry after {response.get('retry_after_seconds', '?')} seconds"
            )
        raise RuntimeError("authentication failed: invalid password")


class PersistentClientSession:
    def __init__(self, config: AppConfig, password: str, noise_rate: float = 0.0) -> None:
        self._config = config
        self._password = password
        self._noise_rate = noise_rate
        self._sock: socket.socket | None = None
        self._transport: object | None = None

    def connect(self) -> None:
        if self._sock is not None:
            return
        print(f"[QSH][Client] opening session to {self._config.host}:{self._config.port}")
        sock = socket.create_connection((self._config.host, self._config.port))
        transport = client_handshake(sock, self._config, noise_rate=self._noise_rate)
        _authenticate(sock, transport, self._password)
        self._sock = sock
        self._transport = transport
        print("[QSH][Client] secure session established and authenticated")

    def request(self, payload: dict) -> dict:
        if self._sock is None or self._transport is None:
            raise RuntimeError("session not connected")
        return _send_request(self._sock, self._transport, payload)

    def close(self) -> None:
        if self._sock is None or self._transport is None:
            return
        try:
            _send_request(self._sock, self._transport, {"action": "quit"})
        except Exception:
            pass
        self._sock.close()
        self._sock = None
        self._transport = None
        print("[QSH][Client] session closed")


def interactive_shell(config: AppConfig, password: str | None = None, noise_rate: float = 0.0) -> None:
    resolved_password = password or getpass("QSH password: ")
    session = PersistentClientSession(config, password=resolved_password, noise_rate=noise_rate)
    session.connect()
    print("[QSH][Client] type: shell <cmd> | upload <local> <remote> | download <remote> <local> | exit")
    while True:
        try:
            raw = input("qsh> ").strip()
        except (KeyboardInterrupt, EOFError):
            print()
            break
        if not raw:
            continue
        if raw in {"exit", "quit"}:
            break
        if raw == "help":
            print("shell <cmd>")
            print("upload <local_path> <remote_path>")
            print("download <remote_path> <local_path>")
            print("exit")
            continue
        try:
            parts = shlex_split(raw)
        except ValueError as exc:
            print(f"parse error: {exc}")
            continue
        command = parts[0]
        try:
            if command == "shell":
                if len(parts) < 2:
                    print("usage: shell <command>")
                    continue
                response = session.request({"action": "shell", "command": " ".join(parts[1:])})
                result = response["result"]
                print(f"exit={result['return_code']}")
                if result["stdout"]:
                    print("stdout:")
                    print(result["stdout"])
                if result["stderr"]:
                    print("stderr:")
                    print(result["stderr"])
            elif command == "upload":
                if len(parts) != 3:
                    print("usage: upload <local_path> <remote_path>")
                    continue
                content = base64.b64encode(Path(parts[1]).read_bytes()).decode("ascii")
                response = session.request({"action": "upload", "remote_path": parts[2], "content_b64": content})
                print(response)
            elif command == "download":
                if len(parts) != 3:
                    print("usage: download <remote_path> <local_path>")
                    continue
                response = session.request({"action": "download", "remote_path": parts[1]})
                Path(parts[2]).parent.mkdir(parents=True, exist_ok=True)
                Path(parts[2]).write_bytes(base64.b64decode(response["content_b64"].encode("ascii")))
                print(f"saved {parts[2]}")
            else:
                print(f"unknown command: {command}")
        except Exception as exc:
            print(f"request error: {exc}")
    session.close()


def run_shell(config: AppConfig, command: str, password: str, noise_rate: float = 0.0) -> dict:
    with socket.create_connection((config.host, config.port)) as sock:
        transport = client_handshake(sock, config, noise_rate=noise_rate)
        _authenticate(sock, transport, password)
        response = _send_request(sock, transport, {"action": "shell", "command": command})
        _send_request(sock, transport, {"action": "quit"})
        return response


def upload(config: AppConfig, local_path: str, remote_path: str, password: str, noise_rate: float = 0.0) -> dict:
    content = base64.b64encode(Path(local_path).read_bytes()).decode("ascii")
    with socket.create_connection((config.host, config.port)) as sock:
        transport = client_handshake(sock, config, noise_rate=noise_rate)
        _authenticate(sock, transport, password)
        response = _send_request(
            sock,
            transport,
            {"action": "upload", "remote_path": remote_path, "content_b64": content},
        )
        _send_request(sock, transport, {"action": "quit"})
        return response


def download(config: AppConfig, remote_path: str, local_path: str, password: str, noise_rate: float = 0.0) -> dict:
    with socket.create_connection((config.host, config.port)) as sock:
        transport = client_handshake(sock, config, noise_rate=noise_rate)
        _authenticate(sock, transport, password)
        response = _send_request(sock, transport, {"action": "download", "remote_path": remote_path})
        Path(local_path).parent.mkdir(parents=True, exist_ok=True)
        Path(local_path).write_bytes(base64.b64decode(response["content_b64"].encode("ascii")))
        _send_request(sock, transport, {"action": "quit"})
        return response
