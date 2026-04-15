import time

from core.auth_security import AuthGuard, hash_password, verify_password


def test_password_hash_verify_roundtrip():
    encoded = hash_password("secret-123", iterations=50_000)
    assert verify_password("secret-123", encoded)
    assert not verify_password("wrong", encoded)


def test_auth_guard_lockout():
    guard = AuthGuard(max_failures=2, lockout_seconds=1, throttle_base_seconds=0.0)
    locked, _ = guard.check_lockout("client-a")
    assert not locked

    delay, locked_now = guard.register_failure("client-a")
    assert delay == 0.0
    assert not locked_now

    _, locked_now = guard.register_failure("client-a")
    assert locked_now

    locked, remaining = guard.check_lockout("client-a")
    assert locked
    assert remaining > 0

    time.sleep(1.05)
    locked, _ = guard.check_lockout("client-a")
    assert not locked
