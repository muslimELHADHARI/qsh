import socket
import os
import random

from config import AppConfig
from core.connection import recv_plain, send_plain
from crypto.bb84 import bits_to_bytes, generate_material, measure_material, measure_with_eve_intercept, sift_key
from crypto.cipher import AesGcmTransport
from crypto.kdf import derive_session_keys
from protocol.messages import BB84_CLIENT_DATA, BB84_RESULT, HELLO
from utils.logger import get_logger, log_event

logger = get_logger("qsh.qkd")


def client_handshake(conn: socket.socket, config: AppConfig, noise_rate: float = 0.0) -> AesGcmTransport:
    print("[QSH][QKD][Client] sending HELLO")
    send_plain(conn, {"type": HELLO, "protocol": "QSH-0.1"})
    sender = generate_material(config.bb84_bits)
    receiver_bases = generate_material(config.bb84_bits).bases
    print(f"[QSH][QKD][Client] preparing BB84 exchange with {config.bb84_bits} qubits")
    if config.eve_intercept_rate > 0:
        print(
            f"[QSH][QKD][Client] Eve enabled mode={config.eve_mode} "
            f"rate={config.eve_intercept_rate:.2f} bias={config.eve_basis_bias:.2f}"
        )
        measured, eve_stats = measure_with_eve_intercept(
            sender,
            receiver_bases,
            eve_intercept_rate=config.eve_intercept_rate,
            eve_mode=config.eve_mode,
            eve_basis_bias=config.eve_basis_bias,
            noise_rate=noise_rate,
        )
        log_event(
            logger,
            "eve_simulated",
            mode=eve_stats.mode,
            intercept_count=eve_stats.intercept_count,
            intercept_rate_observed=round(eve_stats.intercept_rate_observed, 4),
        )
    else:
        measured = measure_material(sender, receiver_bases, noise_rate=noise_rate)
        eve_stats = None
    salt = os.urandom(16)
    sample_count = min(config.bb84_sample_size, config.bb84_bits)
    sample_indexes = random.sample(range(config.bb84_bits), sample_count) if sample_count else []
    send_plain(
        conn,
        {
            "type": BB84_CLIENT_DATA,
            "bits": sender.bits,
            "bases": sender.bases,
            "receiver_bases": receiver_bases,
            "measured_bits": measured,
            "salt_hex": salt.hex(),
            "sample_indexes": sample_indexes,
            "eve_mode": eve_stats.mode if eve_stats else "none",
            "eve_intercept_count": eve_stats.intercept_count if eve_stats else 0,
            "eve_intercept_rate_observed": eve_stats.intercept_rate_observed if eve_stats else 0.0,
        },
    )
    result = recv_plain(conn)
    if result.get("type") != BB84_RESULT or not result.get("accepted"):
        raise RuntimeError(f"BB84 rejected: {result}")
    final = sift_key(
        sender.bits,
        sender.bases,
        measured,
        receiver_bases,
        config.bb84_sample_size,
        sample_indexes=sample_indexes,
    )
    if final.qber > config.bb84_qber_threshold:
        raise RuntimeError(f"local QBER too high: {final.qber}")
    sifted_rate = len(final.sifted_bits) / config.bb84_bits if config.bb84_bits else 0.0
    print(
        f"[QSH][QKD][Client] accepted qber={final.qber:.4f}, "
        f"sifted_bits={len(final.sifted_bits)}"
    )
    print(
        f"[QSH][QKD][Client][Report] sifted_rate={sifted_rate:.3f} "
        f"eve_mode={eve_stats.mode if eve_stats else 'none'} "
        f"eve_intercepts={eve_stats.intercept_count if eve_stats else 0} "
        f"eve_observed_rate={eve_stats.intercept_rate_observed if eve_stats else 0.0:.3f}"
    )
    log_event(
        logger,
        "client_qkd_report",
        qber=round(final.qber, 4),
        sifted_bits=len(final.sifted_bits),
        sifted_rate=round(sifted_rate, 4),
        eve_mode=eve_stats.mode if eve_stats else "none",
        eve_intercepts=eve_stats.intercept_count if eve_stats else 0,
    )
    shared = bits_to_bytes(final.sifted_bits)
    session = derive_session_keys(shared, salt=salt, key_length=config.aes_key_length)
    print(
        f"[QSH][Session][Client] session_id={session.session_id.hex()} "
        f"key_len={len(session.encryption_key)}"
    )
    return AesGcmTransport(session.encryption_key)


def server_handshake(conn: socket.socket, config: AppConfig) -> AesGcmTransport:
    hello = recv_plain(conn)
    if hello.get("type") != HELLO:
        raise ValueError("expected HELLO")
    print("[QSH][QKD][Server] HELLO received")
    payload = recv_plain(conn)
    if payload.get("type") != BB84_CLIENT_DATA:
        raise ValueError("expected BB84_CLIENT_DATA")
    print(
        f"[QSH][QKD][Server] BB84 payload received bits={len(payload['bits'])} "
        f"samples={len(payload.get('sample_indexes', []))}"
    )
    print(
        f"[QSH][QKD][Server] client_report eve_mode={payload.get('eve_mode', 'none')} "
        f"eve_intercepts={payload.get('eve_intercept_count', 0)} "
        f"eve_observed_rate={payload.get('eve_intercept_rate_observed', 0.0):.3f}"
    )
    log_event(
        logger,
        "server_qkd_client_report",
        eve_mode=payload.get("eve_mode", "none"),
        eve_intercepts=payload.get("eve_intercept_count", 0),
        eve_observed_rate=round(payload.get("eve_intercept_rate_observed", 0.0), 4),
    )
    final = sift_key(
        payload["bits"],
        payload["bases"],
        payload["measured_bits"],
        payload["receiver_bases"],
        config.bb84_sample_size,
        sample_indexes=payload.get("sample_indexes"),
    )
    if final.qber > config.bb84_qber_threshold:
        send_plain(conn, {"type": BB84_RESULT, "accepted": False, "qber": final.qber})
        raise ValueError(f"QBER too high: {final.qber}")
    sifted_rate = len(final.sifted_bits) / config.bb84_bits if config.bb84_bits else 0.0
    shared = bits_to_bytes(final.sifted_bits)
    keys = derive_session_keys(shared, salt=bytes.fromhex(payload["salt_hex"]), key_length=config.aes_key_length)
    print(
        f"[QSH][QKD][Server] accepted qber={final.qber:.4f}, "
        f"sifted_bits={len(final.sifted_bits)}"
    )
    print(f"[QSH][QKD][Server][Report] sifted_rate={sifted_rate:.3f} qber={final.qber:.4f}")
    log_event(
        logger,
        "server_qkd_report",
        qber=round(final.qber, 4),
        sifted_bits=len(final.sifted_bits),
        sifted_rate=round(sifted_rate, 4),
    )
    print(
        f"[QSH][Session][Server] session_id={keys.session_id.hex()} "
        f"key_len={len(keys.encryption_key)}"
    )
    send_plain(conn, {"type": BB84_RESULT, "accepted": True, "qber": final.qber, "session_id_hex": keys.session_id.hex()})
    return AesGcmTransport(keys.encryption_key)
