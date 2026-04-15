from typing import Any, Callable


Handler = Callable[[dict[str, Any]], dict[str, Any]]


class HandlerRegistry:
    def __init__(self) -> None:
        self._handlers: dict[str, Handler] = {}

    def register(self, action: str, handler: Handler) -> None:
        self._handlers[action] = handler

    def get(self, action: str) -> Handler | None:
        return self._handlers.get(action)
from typing import Any, Callable


Handler = Callable[[dict[str, Any]], dict[str, Any]]


class HandlerRegistry:
    def __init__(self) -> None:
        self._handlers: dict[str, Handler] = {}

    def register(self, action: str, handler: Handler) -> None:
        self._handlers[action] = handler

    def get(self, action: str) -> Handler | None:
        return self._handlers.get(action)
