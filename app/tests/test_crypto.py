from crypto.cipher import AesGcmTransport
from crypto.kdf import derive_session_keys


def test_encrypted_roundtrip():
    keys = derive_session_keys(b"01234567" * 8)
    sender = AesGcmTransport(keys.encryption_key)
    receiver = AesGcmTransport(keys.encryption_key)
    payload = b"hello qsh"
    frame = sender.encrypt(payload)
    assert receiver.decrypt(frame) == payload
