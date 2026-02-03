import logging
import os
from typing import List

import httpx

logger = logging.getLogger(__name__)

DEFAULT_SYSTEM_PROMPT = (
    "You are a helpful assistant. Answer clearly and concisely, "
    "and ask follow-up questions when helpful."
)

DEFAULT_MODEL = "openai/gpt-4o"
DEFAULT_CERT_FILE = "BMW_Trusted_Certificates_Latest.pem"


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


def _resolve_verify_path(cert_path: str | None) -> str | bool:
    if not cert_path:
        return False
    return cert_path if os.path.exists(cert_path) else False


def bmw_chat(messages: List[dict]) -> str:
    api_url = os.getenv("BMW_API_URL", "https://api.gcp.cloud.bmw/llmapi/v1/chat/completions")
    api_token = os.getenv("BMW_API_TOKEN")
    client_id = os.getenv("BMW_CLIENT_ID")
    model = os.getenv("BMW_MODEL", DEFAULT_MODEL)
    cert_file = os.getenv("BMW_CERT_FILE", DEFAULT_CERT_FILE)

    if not api_token or not client_id:
        logger.warning("BMW API not configured; returning stub response.")
        return (
            "BMW API is not configured. Please set BMW_API_TOKEN and BMW_CLIENT_ID."
        )

    payload = {"model": model, "messages": messages}
    headers = {
        "Authorization": f"Bearer {api_token}",
        "x-apikey": client_id,
        "Content-Type": "application/json",
    }
    verify = _resolve_verify_path(cert_file)

    try:
        with httpx.Client(timeout=30.0, verify=verify) as client:
            response = client.post(api_url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as exc:
        logger.error("Unexpected BMW response shape: %s", exc)
        return "Sorry, I received an unexpected response from the AI service."
    except httpx.HTTPError as exc:
        logger.error("BMW API request failed: %s", exc)
        return "Sorry, the AI service is currently unavailable."
