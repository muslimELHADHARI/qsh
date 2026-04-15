import socket
import struct
from typing import Any

from protocol.encoder import decode_json_packet, encode_json_packet


def recv_exact(sock: socket.socket, size: int) -> bytes:
    chunks: list[bytes] = []
    left = size
    while left > 0:
        data = sock.recv(left)
        if not data:
            raise ConnectionError("peer disconnected")
        chunks.append(data)
        left -= len(data)
    return b"".join(chunks)


def send_plain(sock: socket.socket, payload: dict[str, Any]) -> None:
    sock.sendall(encode_json_packet(payload))


def recv_plain(sock: socket.socket) -> dict[str, Any]:
    length = struct.unpack("!I", recv_exact(sock, 4))[0]
    return decode_json_packet(recv_exact(sock, length))


def send_secure(sock: socket.socket, frame: bytes) -> None:
    sock.sendall(struct.pack("!I", len(frame)) + frame)


def recv_secure(sock: socket.socket) -> bytes:
    length = struct.unpack("!I", recv_exact(sock, 4))[0]
    return recv_exact(sock, length)
