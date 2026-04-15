import argparse
from getpass import getpass

from config import AppConfig
from core.auth_security import hash_password
from core.client import download, interactive_shell, run_shell, upload
from core.server import start
from utils.logger import configure_logging, get_logger, log_event


def main() -> None:
    parser = argparse.ArgumentParser(description="QSH - quantum-inspired secure shell")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8022, type=int)
    parser.add_argument("--noise-rate", default=0.0, type=float)
    parser.add_argument("--eve-rate", default=0.0, type=float, help="Eve intercept-resend probability [0..1]")
    parser.add_argument("--eve-mode", default="random", choices=["random", "biased"], help="Eve basis strategy")
    parser.add_argument("--eve-bias", default=0.5, type=float, help="When eve-mode=biased, probability Eve picks X basis")
    parser.add_argument("--password", default=None, help="Client password for encrypted auth step")
    parser.add_argument("--server-password", default=None, help="Password stored on server side")
    parser.add_argument("--server-password-hash", default=None, help="PBKDF2 encoded hash; overrides plain server password")
    parser.add_argument("--auth-max-failures", type=int, default=5)
    parser.add_argument("--auth-lockout-seconds", type=int, default=180)
    parser.add_argument("--auth-throttle-base", type=float, default=0.75)
    parser.add_argument("--log-file", default="logs/qsh.log")
    sub = parser.add_subparsers(dest="role", required=True)

    sub.add_parser("server")
    shell = sub.add_parser("shell")
    shell.add_argument("command")
    sub.add_parser("session")
    up = sub.add_parser("upload")
    up.add_argument("local_path")
    up.add_argument("remote_path")
    down = sub.add_parser("download")
    down.add_argument("remote_path")
    down.add_argument("local_path")
    hash_parser = sub.add_parser("hash-password")
    hash_parser.add_argument("--value", default=None, help="Password value. If omitted, prompt securely.")

    args = parser.parse_args()
    config = AppConfig(host=args.host, port=args.port)
    config.log_file = args.log_file
    configure_logging(log_file=config.log_file)
    logger = get_logger("qsh.main")
    if args.server_password is not None:
        config.server_password = args.server_password
    if args.server_password_hash is not None:
        config.server_password_hash = args.server_password_hash
    config.auth_max_failures = max(1, args.auth_max_failures)
    config.auth_lockout_seconds = max(1, args.auth_lockout_seconds)
    config.auth_throttle_base_seconds = max(0.0, args.auth_throttle_base)
    config.eve_intercept_rate = max(0.0, min(1.0, args.eve_rate))
    config.eve_mode = args.eve_mode
    config.eve_basis_bias = max(0.0, min(1.0, args.eve_bias))
    log_event(
        logger,
        "startup_config",
        host=config.host,
        port=config.port,
        eve_rate=config.eve_intercept_rate,
        eve_mode=config.eve_mode,
        log_file=config.log_file,
    )

    if args.role == "server":
        print("[QSH][Server] password auth enabled")
        start(config)
    elif args.role == "shell":
        password = args.password or getpass("QSH password: ")
        result = run_shell(config, args.command, password=password, noise_rate=args.noise_rate)
        shell_result = result["result"]
        print(f"exit={shell_result['return_code']}")
        if shell_result["stdout"]:
            print("stdout:")
            print(shell_result["stdout"])
        if shell_result["stderr"]:
            print("stderr:")
            print(shell_result["stderr"])
    elif args.role == "upload":
        password = args.password or getpass("QSH password: ")
        print(upload(config, args.local_path, args.remote_path, password=password, noise_rate=args.noise_rate))
    elif args.role == "download":
        password = args.password or getpass("QSH password: ")
        print(download(config, args.remote_path, args.local_path, password=password, noise_rate=args.noise_rate))
    elif args.role == "session":
        interactive_shell(config, password=args.password, noise_rate=args.noise_rate)
    elif args.role == "hash-password":
        raw = args.value or getpass("Password to hash: ")
        print(hash_password(raw, iterations=config.password_hash_iterations))


if __name__ == "__main__":
    main()
