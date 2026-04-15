from dataclasses import dataclass
import os


@dataclass(slots=True)
class AppConfig:
    host: str = "127.0.0.1"
    port: int = 8022
    bb84_bits: int = 512
    bb84_sample_size: int = 32
    bb84_qber_threshold: float = 0.18
    aes_key_length: int = 32
    command_timeout: int = 20
    server_password: str = os.getenv("QSH_SERVER_PASSWORD", "qsh123")
    server_password_hash: str | None = os.getenv("QSH_SERVER_PASSWORD_HASH")
    password_hash_iterations: int = 200_000
    auth_max_failures: int = 5
    auth_lockout_seconds: int = 180
    auth_throttle_base_seconds: float = 0.75
    eve_intercept_rate: float = 0.0
    eve_mode: str = "random"
    eve_basis_bias: float = 0.5
    log_file: str = os.getenv("QSH_LOG_FILE", "logs/qsh.log")
