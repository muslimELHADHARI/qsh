from typing import Any

from server.dispatcher import dispatch
from server.registry import HandlerRegistry


def route(payload: dict[str, Any], registry: HandlerRegistry) -> dict[str, Any]:
    return dispatch(payload, registry)
