from app.agent.llm.anthropic import AnthropicProvider
from app.agent.llm.openai_compatible import OpenAICompatibleProvider


def create_llm_provider(settings, **overrides):
    provider = overrides.pop("provider", settings.llm_provider)
    if provider == "openai_compatible":
        return OpenAICompatibleProvider(
            api_key=overrides.pop("api_key", settings.llm_api_key),
            base_url=overrides.pop("base_url", settings.llm_base_url),
            model=overrides.pop("model", settings.llm_model),
            timeout=overrides.pop("timeout", settings.llm_timeout_seconds),
            max_tokens=overrides.pop("max_tokens", settings.llm_max_tokens),
        )
    return AnthropicProvider(
        api_key=overrides.pop("api_key", settings.anthropic_api_key),
        model=overrides.pop("model", settings.llm_model or settings.anthropic_model),
        timeout=overrides.pop("timeout", settings.llm_timeout_seconds),
        max_tokens=overrides.pop("max_tokens", settings.llm_max_tokens),
    )
