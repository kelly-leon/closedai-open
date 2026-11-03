import json
from collections.abc import Iterator
from typing import Any

from openai import OpenAI


def tool_schema(tool: dict[str, Any]) -> dict[str, Any]:
    return {"type": "function", "function": {
        "name": tool["name"],
        "description": tool.get("description", ""),
        "parameters": tool.get("input_schema", {"type": "object", "properties": {}}),
    }}


class OpenAICompatibleProvider:
    def __init__(self, api_key: str, base_url: str, model: str, timeout: int = 60, max_tokens: int = 1024) -> None:
        self.model = model
        self.max_tokens = max_tokens
        self.client = OpenAI(api_key=api_key, base_url=base_url, timeout=timeout)

    def stream_turn(self, system: str, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> Iterator[dict[str, Any]]:
        translated = [{"role": "system", "content": system}, *messages]
        stream = self.client.chat.completions.create(
            model=self.model, messages=translated, tools=[tool_schema(tool) for tool in tools],
            tool_choice="auto", max_tokens=self.max_tokens, stream=True, stream_options={"include_usage": True},
        )
        calls: dict[int, dict[str, str]] = {}
        input_tokens = output_tokens = 0
        for chunk in stream:
            usage = getattr(chunk, "usage", None)
            if usage:
                input_tokens = getattr(usage, "prompt_tokens", 0) or 0
                output_tokens = getattr(usage, "completion_tokens", 0) or 0
            choice = chunk.choices[0] if chunk.choices else None
            if not choice:
                continue
            delta = choice.delta
            if getattr(delta, "content", None):
                yield {"text_delta": delta.content}
            for fragment in getattr(delta, "tool_calls", None) or []:
                index = fragment.index
                call = calls.setdefault(index, {"id": "", "name": "", "arguments": ""})
                call["id"] += fragment.id or ""
                if fragment.function:
                    call["name"] += fragment.function.name or ""
                    call["arguments"] += fragment.function.arguments or ""
            stop_reason = getattr(choice, "finish_reason", None)
            if stop_reason == "tool_calls":
                for call in calls.values():
                    yield {"tool_call": {"id": call["id"], "name": call["name"], "args": call["arguments"]}}
            if stop_reason:
                yield {"stop_reason": stop_reason}
        yield {"usage": {"input_tokens": input_tokens, "output_tokens": output_tokens}}

    def complete(self, system: str, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None = None) -> tuple[str, list[dict[str, Any]], int, int]:
        kwargs: dict[str, Any] = {"model": self.model, "messages": [{"role": "system", "content": system}, *messages],
                                  "max_tokens": self.max_tokens}
        if tools:
            kwargs.update(tools=[tool_schema(tool) for tool in tools], tool_choice="auto")
        response = self.client.chat.completions.create(**kwargs)
        choice = response.choices[0]
        text = choice.message.content or ""
        calls = []
        for call in choice.message.tool_calls or []:
            calls.append({"id": call.id, "name": call.function.name, "args": call.function.arguments})
        usage = getattr(response, "usage", None)
        return text, calls, getattr(usage, "prompt_tokens", 0) or 0, getattr(usage, "completion_tokens", 0) or 0
