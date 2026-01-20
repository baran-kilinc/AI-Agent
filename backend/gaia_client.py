import logging
import os
from typing import List

import httpx

logger = logging.getLogger(__name__)

DEFAULT_SYSTEM_PROMPT = (
    "You are a helpful assistant. Answer clearly and concisely, "
    "and ask follow-up questions when helpful."
)


def load_system_prompt() -> str:
    env_prompt = os.getenv("SYSTEM_PROMPT")
    if env_prompt:
        return env_prompt

    prompt_path = os.getenv("SYSTEM_PROMPT_PATH", "system_prompt.txt")
    if prompt_path and os.path.exists(prompt_path):
        try:
            with open(prompt_path, "r", encoding="utf-8") as handle:
                return handle.read().strip() or DEFAULT_SYSTEM_PROMPT
        except OSError as exc:
            logger.warning("Failed to read system prompt file: %s", exc)

    return DEFAULT_SYSTEM_PROMPT


def gaia_chat(messages: List[dict]) -> str:
    base_url = os.getenv("GAIA_BASE_URL")
    api_key = os.getenv("GAIA_API_KEY")
    model = os.getenv("GAIA_MODEL")

    if not base_url or not api_key or not model:
        logger.warning("GAIA API not configured; returning stub response.")
        return (
            "GAIA API is not configured. Please set GAIA_BASE_URL, "
            "GAIA_API_KEY, and GAIA_MODEL."
        )

    url = f"{base_url.rstrip('/')}/v1/chat/completions"
    payload = {"model": model, "messages": messages}
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as exc:
        logger.error("Unexpected GAIA response shape: %s", exc)
        return "Sorry, I received an unexpected response from the AI service."
    except httpx.HTTPError as exc:
        logger.error("GAIA API request failed: %s", exc)
        return "Sorry, the AI service is currently unavailable."
