"""LiteLLM wrapper client with dynamic fallback routing.

Implements provider abstraction across Google Gemini, OpenRouter, Groq, and Cerebras.
Also sets up tracing automatically if configured in settings.
"""

import logging
from typing import Any, Optional

import litellm

from common.config.settings import settings
from common.observability.logger import get_logger

logger = get_logger("litellm-client")

# Configure LiteLLM globally
litellm.telemetry = False


def truncate_messages(
    messages: list[dict[str, str]],
    model: str,
    limit: int
) -> list[dict[str, str]]:
    """Truncate conversation history to fit within a specific token limit.

    Preserves the system message (first message if role == 'system') and truncates
    the oldest intermediate user/assistant messages first.
    """
    if not messages:
        return []

    try:
        # Check if messages fit without truncation
        current_tokens = litellm.token_counter(model=model, messages=messages)
        if current_tokens <= limit:
            return messages
    except Exception:
        # If token counter fails, do not crash, just return messages
        return messages

    logger.warning(
        "Context size %d exceeds limit of %d tokens for model %s. Truncating messages...",
        current_tokens, limit, model
    )
    
    # Separate system message if present
    system_msg = None
    other_msgs = list(messages)
    if other_msgs and other_msgs[0].get("role") == "system":
        system_msg = other_msgs.pop(0)

    # Iteratively remove the oldest non-system message until it fits
    while len(other_msgs) > 1:
        other_msgs.pop(0)  # remove oldest message
        temp_messages = [system_msg] + other_msgs if system_msg else other_msgs
        try:
            tokens = litellm.token_counter(model=model, messages=temp_messages)
            if tokens <= limit:
                return temp_messages
        except Exception:
            break

    return [system_msg] + other_msgs if system_msg else other_msgs


async def completion_with_fallback(
    model: str = "gemini/gemini-3.5-flash",
    messages: list[dict[str, str]] = None,
    fallbacks: Optional[list[dict[str, Any]]] = None,
    **kwargs: Any,
) -> Any:
    """Execute LLM completion with automatic fallback support.

    If primary model fails (e.g. rate limit, quota, timeout), we will
    automatically try the fallback list in order, truncating the context
    if required for each specific model.

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

    # Enforce HTTPS on all outbound API bases for external providers
    import os
    for provider in ["GEMINI", "OPENROUTER", "GROQ", "CEREBRAS", "OPENAI"]:
        base_env = os.environ.get(f"{provider}_API_BASE")
        if base_env and not base_env.startswith("https://"):
            raise ValueError(f"Outbound API base for {provider} must use HTTPS, got: {base_env}")
    
    # Check if a custom api_base is passed in kwargs
    api_base_arg = kwargs.get("api_base")
    if api_base_arg and not api_base_arg.startswith("https://"):
        raise ValueError(f"Outbound API base must use HTTPS, got: {api_base_arg}")

    # 1. Resolve fallback chain dynamically from model registry if not provided
    if fallbacks is None:
        try:
            from common.models.registry import get_fallback_chain
            registry_fallbacks = await get_fallback_chain("completion")
            
            # Map fallback models to their respective API keys dynamically
            fallbacks = []
            for spec in registry_fallbacks:
                f_key = None
                if spec.provider == "gemini":
                    f_key = settings.GOOGLE_API_KEY
                elif spec.provider == "openrouter":
                    f_key = settings.OPENROUTER_API_KEY
                elif spec.provider == "groq":
                    f_key = settings.GROQ_API_KEY
                elif spec.provider == "cerebras":
                    f_key = settings.CEREBRAS_API_KEY
                elif spec.provider == "openai":
                    f_key = settings.OPENAI_API_KEY
                
                # Exclude the primary model from fallback to prevent duplication
                if spec.model_id != model:
                    # Resolve context limit
                    limit = spec.context_window or 8000
                    if "gemini-3.5" in spec.model_id or "gemini-3.1" in spec.model_id:
                        limit = 1000000
                    elif "70b" in spec.model_id or "235b" in spec.model_id:
                        limit = 32000

                    fallbacks.append({
                        "model": spec.model_id,
                        "api_key": f_key,
                        "context_window": limit
                    })
        except Exception as e:
            logger.warning("Failed to load completion fallback chain from registry: %s", e)
            # Use reasonable static fallbacks
            fallbacks = [
                {
                    "model": "groq/llama-3.3-70b-versatile",
                    "api_key": settings.GROQ_API_KEY,
                    "context_window": 32000
                },
                {
                    "model": "openrouter/google/gemini-3.5-flash:free",
                    "api_key": settings.OPENROUTER_API_KEY,
                    "context_window": 8000
                },
            ]

    # 2. Build ordered list of candidates to try (starting with primary model)
    primary_key = settings.GOOGLE_API_KEY
    if model.startswith("openrouter/"):
        primary_key = settings.OPENROUTER_API_KEY
    elif model.startswith("openai/"):
        primary_key = settings.OPENAI_API_KEY
    elif model.startswith("groq/"):
        primary_key = settings.GROQ_API_KEY
    elif model.startswith("cerebras/"):
        primary_key = settings.CEREBRAS_API_KEY

    primary_context = 1000000
    if "70b" in model or "235b" in model:
        primary_context = 32000
    elif "free" in model or "8b" in model:
        primary_context = 8000

    candidates = [
        {
            "model": model,
            "api_key": primary_key,
            "context_window": primary_context
        }
    ]
    for fb in fallbacks:
        candidates.append({
            "model": fb["model"],
            "api_key": fb["api_key"],
            "context_window": fb.get("context_window", 8000)
        })

    # 3. Iterate candidates in priority order
    last_error = None
    for candidate in candidates:
        cand_model = candidate["model"]
        api_key = candidate["api_key"]
        limit = candidate["context_window"]

        # Truncate context to model window limit using Pydantic schemas
        truncated_messages = truncate_messages(messages, cand_model, limit)

        logger.info("Attempting LiteLLM completion with model=%s (limit=%d tokens)", cand_model, limit)
        try:
            response = await litellm.acompletion(
                model=cand_model,
                messages=truncated_messages,
                api_key=api_key,
                timeout=60.0,  # Enforce strict LLM timeout of 60 seconds
                **kwargs,
            )

            # Log tokens for cost tracking
            usage = getattr(response, "usage", None)
            if usage:
                prompt_tokens = getattr(usage, "prompt_tokens", 0)
                completion_tokens = getattr(usage, "completion_tokens", 0)
                total_tokens = getattr(usage, "total_tokens", 0)
                logger.info(
                    "LiteLLM completion success: model=%s, prompt_tokens=%d, completion_tokens=%d, total_tokens=%d",
                    cand_model, prompt_tokens, completion_tokens, total_tokens
                )
            return response
        except Exception as e:
            logger.warning("Completion failed for model=%s: %s", cand_model, e)
            last_error = e
            continue

    logger.error("All completion attempts failed.")
    raise RuntimeError(f"LLM completion execution failed: {last_error}") from last_error
