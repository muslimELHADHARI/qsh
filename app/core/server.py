import json
import socket
import threading
import time
from typing import Any

from agent.executor import execute_shell
from agent.file_transfer import read_file_b64, write_file_b64
from config import AppConfig
from core.auth_security import AuthGuard, hash_password, verify_password
from core.connection import recv_secure, send_secure
from protocol.handshake import server_handshake
from utils.logger import get_logger, log_event

ACTIVE_SESSIONS = {}
ACTIVE_SESSIONS_LOCK = threading.Lock()

def _handle(payload: dict[str, Any], config: AppConfig) -> dict[str, Any]:
    action = payload.get("action")
    if action == "shell":
        return {"type": "SHELL_RESULT", "result": execute_shell(payload["command"], timeout=config.command_timeout)}
    if action == "upload":
        write_file_b64(payload["remote_path"], payload["content_b64"])
        return {"type": "UPLOAD_RESULT", "ok": True, "path": payload["remote_path"]}
    if action == "download":
        return {"type": "DOWNLOAD_RESULT", "ok": True, "path": payload["remote_path"], "content_b64": read_file_b64(payload["remote_path"])}
    if action == "quit":
        return {"type": "BYE"}
    return {"type": "ERROR", "message": f"unknown action: {action}"}

def _handle_client(conn, addr, session_label, config, auth_guard, password_hash, admin_password_hash):
    logger = get_logger("qsh.server")
    client_id = str(addr[0])
    print(f"[QSH][Session][{session_label}] connection from {addr}")
    log_event(logger, "session_open", session=session_label, client=client_id, addr=addr)
    
    with ACTIVE_SESSIONS_LOCK:
        ACTIVE_SESSIONS[session_label] = {"ip": client_id, "socket": conn, "is_admin": False, "start": time.time()}

    with conn:
        try:
            transport = server_handshake(conn, config)
            print(f"[QSH][Session][{session_label}] secure channel active")
            log_event(logger, "secure_channel_active", session=session_label, client=client_id)
            authenticated = False
            is_admin = False
            while True:
                request = json.loads(transport.decrypt(recv_secure(conn)).decode("utf-8"))
                action = request.get("action")
                print(f"[QSH][Session][{session_label}] action={action}")
                log_event(logger, "request_received", session=session_label, client=client_id, action=action)
                if not authenticated:
                    if action == "auth":
                        locked, remaining = auth_guard.check_lockout(client_id)
                        if locked:
                            response = {
                                "type": "AUTH_RESULT",
                                "ok": False,
                                "error": "locked_out",
                                "retry_after_seconds": round(remaining, 2),
                            }
                            log_event(
                                logger,
                                "auth_locked",
                                session=session_label,
                                client=client_id,
                                retry_after_seconds=round(remaining, 2),
                            )
                        else:
                            provided = request.get("password", "")
                            try:
                                if admin_password_hash and verify_password(provided, admin_password_hash):
                                    authenticated = True
                                    is_admin = True
                                    with ACTIVE_SESSIONS_LOCK:
                                        ACTIVE_SESSIONS[session_label]["is_admin"] = True
                                    response = {"type": "AUTH_RESULT", "ok": True}
                                else:
                                    authenticated = verify_password(provided, password_hash)
                                    response = {"type": "AUTH_RESULT", "ok": authenticated}
                            except ValueError:
                                authenticated = False
                                response = {"type": "AUTH_RESULT", "ok": False, "error": "server_hash_invalid"}
                        if authenticated:
                            auth_guard.register_success(client_id)
                            print(f"[QSH][Session][{session_label}] authentication success")
                            log_event(logger, "auth_success", session=session_label, client=client_id)
                        else:
                            delay_seconds, now_locked = auth_guard.register_failure(client_id)
                            print(f"[QSH][Session][{session_label}] authentication failed")
                            log_event(
                                logger,
                                "auth_failure",
                                session=session_label,
                                client=client_id,
                                now_locked=now_locked,
                                throttle_seconds=round(delay_seconds, 2),
                            )
                            if delay_seconds > 0:
                                time.sleep(delay_seconds)
                    elif action == "quit":
                        response = {"type": "BYE"}
                    else:
                        response = {"type": "ERROR", "message": "authenticate first"}
                else:
                    if action == "shell":
                        log_event(logger, "command_execute", session=session_label, client=client_id, command=request.get("command", ""))
                    if action in {"upload", "download"}:
                        log_event(
                            logger,
                            "file_action",
                            session=session_label,
                            client=client_id,
                            action=action,
                            remote_path=request.get("remote_path", ""),
                        )
                    
                    if action == "list_sessions":
                        if is_admin:
                            sessions_data = {}
                            with ACTIVE_SESSIONS_LOCK:
                                for s_id, s_info in ACTIVE_SESSIONS.items():
                                    sessions_data[s_id] = {"ip": s_info["ip"], "is_admin": s_info["is_admin"]}
                            response = {"type": "ADMIN_RESULT", "action": "list_sessions", "sessions": sessions_data}
                        else:
                            response = {"type": "ERROR", "message": "admin privilege required"}
                    elif action == "kill_session":
                        if is_admin:
                            target = request.get("target")
                            with ACTIVE_SESSIONS_LOCK:
                                target_session = ACTIVE_SESSIONS.get(target)
                            if target_session:
                                try:
                                    target_session["socket"].close()
                                except Exception:
                                    pass
                                response = {"type": "ADMIN_RESULT", "action": "kill_session", "ok": True}
                            else:
                                response = {"type": "ERROR", "message": f"session {target} not found"}
                        else:
                            response = {"type": "ERROR", "message": "admin privilege required"}
                    else:
                        response = _handle(request, config)

                send_secure(conn, transport.encrypt(json.dumps(response).encode("utf-8")))
                if response["type"] == "BYE":
                    print(f"[QSH][Session][{session_label}] closed by client")
                    log_event(logger, "session_close", session=session_label, client=client_id, reason="client_quit")
                    break
                if response.get("type") == "AUTH_RESULT" and not response.get("ok"):
                    print(f"[QSH][Session][{session_label}] closing after auth failure")
                    log_event(logger, "session_close", session=session_label, client=client_id, reason="auth_failure")
                    break
        except Exception as exc:
            print(f"[QSH][Session][{session_label}] error: {exc!r}")
            log_event(logger, "session_error", session=session_label, client=client_id, error=repr(exc))
        finally:
            with ACTIVE_SESSIONS_LOCK:
                ACTIVE_SESSIONS.pop(session_label, None)

def start(config: AppConfig) -> None:
    logger = get_logger("qsh.server")
    auth_guard = AuthGuard(
        max_failures=config.auth_max_failures,
        lockout_seconds=config.auth_lockout_seconds,
        throttle_base_seconds=config.auth_throttle_base_seconds,
    )
    password_hash = config.server_password_hash or hash_password(
        config.server_password,
        iterations=config.password_hash_iterations,
    )
    # Validate hash format at startup to fail fast with explicit message.
    try:
        verify_password("__qsh_self_test__", password_hash)
    except ValueError as exc:
        raise ValueError(
            "Invalid --server-password-hash format. Generate a valid hash with: "
            "'python app/main.py hash-password --value \"<password>\"'"
        ) from exc

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.bind((config.host, config.port))
        server.listen(5)
        print(f"[QSH] listening on {config.host}:{config.port}")
        log_event(
            logger,
            "server_listen",
            host=config.host,
            port=config.port,
            auth_max_failures=config.auth_max_failures,
            auth_lockout_seconds=config.auth_lockout_seconds,
        )
        session_counter = 0
        while True:
            try:
                conn, addr = server.accept()
                session_counter += 1
                session_label = f"S{session_counter:04d}"
                thread = threading.Thread(
                    target=_handle_client,
                    args=(conn, addr, session_label, config, auth_guard, password_hash, config.admin_password_hash),
                    daemon=True,
                )
                thread.start()
            except Exception as e:
                print(f"[QSH] accept error: {e}")
