"""LiteLLM wrapper client with dynamic fallback routing.

Implements provider abstraction across Google Gemini and OpenRouter free-tier.
Also sets up tracing automatically if configured in settings.
"""

from typing import Any, Optional

import litellm
from litellm import completion

from common.config.settings import settings
from common.observability.logger import get_logger

logger = get_logger("litellm-client")

# Configure LiteLLM globally
litellm.telemetry = False

# Configure fallback list based on settings
DEFAULT_FALLBACKS = [
    {"model": "openrouter/google/gemini-2.5-flash:free", "api_key": settings.OPENROUTER_API_KEY},
    {"model": "openrouter/meta-llama/llama-3-8b-instruct:free", "api_key": settings.OPENROUTER_API_KEY},
]


async def completion_with_fallback(
    model: str = "gemini/gemini-1.5-flash",
    messages: list[dict[str, str]] = None,
    fallbacks: Optional[list[dict[str, Any]]] = None,
    **kwargs: Any,
) -> Any:
    """Execute LLM completion with automatic fallback support.

    If primary model fails (e.g. rate limit, quota, timeout), LiteLLM will
    automatically try the fallback list in order.

    Args:
        model: Primary model name.
        messages: List of message dicts.
        fallbacks: Optional list of fallback specifications.
        **kwargs: Additional parameters passed to completion.

    Returns:
        LiteLLM completion response object.
    """
    if messages is None:
        messages = []

    # Map primary API keys
    api_key = settings.GOOGLE_API_KEY
    if model.startswith("openrouter/"):
        api_key = settings.OPENROUTER_API_KEY
    elif model.startswith("openai/"):
        api_key = settings.OPENAI_API_KEY

    # Use default fallbacks if not provided
    if fallbacks is None:
        fallbacks = DEFAULT_FALLBACKS

    # Prepare fallback params
    litellm_fallbacks = []
    for f in fallbacks:
        litellm_fallbacks.append(f["model"])
        # Register keys dynamically for fallback models
        if f["model"].startswith("openrouter/"):
            litellm.api_key = f["api_key"]
        elif f["model"].startswith("gemini/"):
            litellm.api_key = f.get("api_key", settings.GOOGLE_API_KEY)

    logger.debug("Executing completion with model=%s, fallbacks=%s", model, litellm_fallbacks)

    try:
        # litellm completion supports fallbacks natively
        response = await litellm.acompletion(
            model=model,
            messages=messages,
            api_key=api_key,
            fallbacks=litellm_fallbacks,
            **kwargs,
        )
        return response
    except Exception as e:
        logger.error("All completion attempts failed: %s", e)
        raise RuntimeError("LLM completion execution failed") from e
