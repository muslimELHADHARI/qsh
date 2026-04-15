from dataclasses import dataclass

from crypto.cipher import AesGcmTransport
from crypto.kdf import SessionKeys


@dataclass(slots=True)
class Session:
    keys: SessionKeys
    transport: AesGcmTransport
