from cryptography.hazmat.primitives import hashes


def sha256_hex(data: bytes) -> str:
    digest = hashes.Hash(hashes.SHA256())
    digest.update(data)
    return digest.finalize().hex()
