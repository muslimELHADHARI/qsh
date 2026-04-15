from typing import Any

from agent.executor import execute_shell
from agent.file_transfer import read_file_b64, write_file_b64
from config import AppConfig
from protocol.messages import BYE, DOWNLOAD_RESULT, ERROR, SHELL_RESULT, UPLOAD_RESULT
from server.registry import HandlerRegistry


def build_registry(config: AppConfig) -> HandlerRegistry:
    registry = HandlerRegistry()

    def shell_handler(payload: dict[str, Any]) -> dict[str, Any]:
        return {"type": SHELL_RESULT, "result": execute_shell(payload["command"], timeout=config.command_timeout)}

    def upload_handler(payload: dict[str, Any]) -> dict[str, Any]:
        write_file_b64(payload["remote_path"], payload["content_b64"])
        return {"type": UPLOAD_RESULT, "ok": True, "path": payload["remote_path"]}

    def download_handler(payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "type": DOWNLOAD_RESULT,
            "ok": True,
            "path": payload["remote_path"],
            "content_b64": read_file_b64(payload["remote_path"]),
        }

    def quit_handler(payload: dict[str, Any]) -> dict[str, Any]:
        _ = payload
        return {"type": BYE}

    registry.register("shell", shell_handler)
    registry.register("upload", upload_handler)
    registry.register("download", download_handler)
    registry.register("quit", quit_handler)
    return registry


def dispatch(payload: dict[str, Any], registry: HandlerRegistry) -> dict[str, Any]:
    action = payload.get("action")
    handler = registry.get(action)
    if handler is None:
        return {"type": ERROR, "message": f"unknown action: {action}"}
    return handler(payload)
