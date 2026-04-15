import os
import struct

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class AesGcmTransport:
    def __init__(self, key: bytes) -> None:
        self._aead = AESGCM(key)
        self._send_seq = 0
        self._recv_seq = 0

    def encrypt(self, payload: bytes) -> bytes:
        seq = self._send_seq
        self._send_seq += 1
        nonce = os.urandom(12)
        aad = struct.pack("!Q", seq)
        ciphertext = self._aead.encrypt(nonce, payload, aad)
        return struct.pack("!Q", seq) + nonce + struct.pack("!I", len(ciphertext)) + ciphertext

    def decrypt(self, frame: bytes) -> bytes:
        seq = struct.unpack("!Q", frame[:8])[0]
        if seq != self._recv_seq:
            raise ValueError(f"invalid sequence number: expected {self._recv_seq}, got {seq}")
        nonce = frame[8:20]
        ct_len = struct.unpack("!I", frame[20:24])[0]
        ciphertext = frame[24 : 24 + ct_len]
        aad = struct.pack("!Q", seq)
        plaintext = self._aead.decrypt(nonce, ciphertext, aad)
        self._recv_seq += 1
        return plaintext
