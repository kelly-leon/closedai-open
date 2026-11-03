import anthropic
from collections.abc import Iterator
from typing import Any


class AnthropicProvider:
    def __init__(self, api_key: str, model: str, timeout: int = 60, max_tokens: int = 1024) -> None:
        self.model = model
        self.max_tokens = max_tokens
        self.client = anthropic.Anthropic(api_key=api_key, timeout=timeout)

    def stream_turn(self, system: str, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> Iterator[dict[str, Any]]:
        with self.client.messages.stream(
            model=self.model, max_tokens=self.max_tokens, system=system, tools=tools, messages=messages,
        ) as stream:
            usage_input = usage_output = 0
            tool_calls: dict[int, dict[str, str]] = {}
            for event in stream:
                event_type = getattr(event, "type", "")
                if event_type == "content_block_delta":
                    delta = getattr(event, "delta", None)
                    if getattr(delta, "type", "") == "text_delta":
                        yield {"text_delta": getattr(delta, "text", "")}
                elif event_type == "message_delta":
                    usage = getattr(event, "usage", None)
                    usage_output = getattr(usage, "output_tokens", usage_output) or usage_output
                elif event_type == "message_start":
                    usage = getattr(getattr(event, "message", None), "usage", None)
                    usage_input = getattr(usage, "input_tokens", 0) or 0
            message = stream.get_final_message()
            for block in getattr(message, "content", []) or []:
                if getattr(block, "type", "") == "tool_use":
                    yield {"tool_call": {"id": block.id, "name": block.name, "args": block.input}}
            yield {"usage": {"input_tokens": usage_input, "output_tokens": getattr(message.usage, "output_tokens", usage_output) or usage_output}}
            yield {"stop_reason": getattr(message, "stop_reason", None)}

    def complete(self, system: str, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None = None) -> tuple[str, list[dict[str, Any]], int, int]:
        response = self.client.messages.create(model=self.model, max_tokens=self.max_tokens, system=system,
                                               tools=tools or [], messages=messages)
        text = "".join(getattr(block, "text", "") for block in response.content if getattr(block, "type", "") == "text")
        calls = [{"id": block.id, "name": block.name, "args": block.input}
                 for block in response.content if getattr(block, "type", "") == "tool_use"]
        usage = getattr(response, "usage", None)
        return text, calls, getattr(usage, "input_tokens", 0) or 0, getattr(usage, "output_tokens", 0) or 0
