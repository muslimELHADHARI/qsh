import os
from dataclasses import dataclass

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF


@dataclass(slots=True)
class SessionKeys:
    encryption_key: bytes
    session_id: bytes
    salt: bytes


def derive_session_keys(shared_material: bytes, salt: bytes | None = None, key_length: int = 32) -> SessionKeys:
    if not shared_material:
        raise ValueError("shared_material must not be empty")
    use_salt = salt or os.urandom(16)
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=key_length + 16,
        salt=use_salt,
        info=b"qsh-session-derivation",
    )
    output = hkdf.derive(shared_material)
    return SessionKeys(output[:key_length], output[key_length:], use_salt)
