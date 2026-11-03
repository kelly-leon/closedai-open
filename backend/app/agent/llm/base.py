from abc import ABC, abstractmethod
from collections.abc import Iterator
from typing import Any


class BaseLLMProvider(ABC):
    @abstractmethod
    def stream_turn(self, system: str, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> Iterator[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def complete(self, system: str, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None = None) -> tuple[str, list[dict[str, Any]], int, int]:
        raise NotImplementedError
