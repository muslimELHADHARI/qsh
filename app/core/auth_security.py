from __future__ import annotations

import base64
import hashlib
import hmac
import os
import time
from dataclasses import dataclass


def hash_password(plain_password: str, iterations: int = 200_000, salt: bytes | None = None) -> str:
    use_salt = salt or os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", plain_password.encode("utf-8"), use_salt, iterations, dklen=32)
    return f"pbkdf2_sha256${iterations}${base64.b64encode(use_salt).decode('ascii')}${base64.b64encode(digest).decode('ascii')}"


def verify_password(plain_password: str, encoded_hash: str) -> bool:
    parts = encoded_hash.split("$", 3)
    if len(parts) != 4:
        raise ValueError("invalid password hash format: expected pbkdf2_sha256$<iter>$<salt_b64>$<digest_b64>")
    algorithm, iter_text, salt_b64, digest_b64 = parts
    if algorithm != "pbkdf2_sha256":
        raise ValueError(f"unsupported password hash algorithm: {algorithm}")
    iterations = int(iter_text)
    salt = base64.b64decode(salt_b64.encode("ascii"))
    expected = base64.b64decode(digest_b64.encode("ascii"))
    actual = hashlib.pbkdf2_hmac("sha256", plain_password.encode("utf-8"), salt, iterations, dklen=len(expected))
    return hmac.compare_digest(actual, expected)


@dataclass(slots=True)
class AuthState:
    failures: int = 0
    lockout_until: float = 0.0


class AuthGuard:
    def __init__(self, max_failures: int, lockout_seconds: int, throttle_base_seconds: float) -> None:
        self.max_failures = max_failures
        self.lockout_seconds = lockout_seconds
        self.throttle_base_seconds = throttle_base_seconds
        self._state_by_identity: dict[str, AuthState] = {}

    def _state(self, identity: str) -> AuthState:
        return self._state_by_identity.setdefault(identity, AuthState())

    def check_lockout(self, identity: str) -> tuple[bool, float]:
        state = self._state(identity)
        now = time.time()
        if state.lockout_until > now:
            return True, state.lockout_until - now
        return False, 0.0

    def register_failure(self, identity: str) -> tuple[float, bool]:
        state = self._state(identity)
        state.failures += 1
        throttle_seconds = self.throttle_base_seconds * (2 ** max(0, state.failures - 1))
        locked = False
        if state.failures >= self.max_failures:
            state.lockout_until = time.time() + self.lockout_seconds
            locked = True
        return throttle_seconds, locked

    def register_success(self, identity: str) -> None:
        state = self._state(identity)
        state.failures = 0
        state.lockout_until = 0.0
