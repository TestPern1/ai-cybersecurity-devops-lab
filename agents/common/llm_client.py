"""Shared client for talking to a local, OpenAI-compatible LM Studio server.

Every agent in this lab goes through this one module to reach the model, so
the "local only, no external calls" constraint only has to be enforced and
reviewed in one place.
"""

from __future__ import annotations

import os

import openai

DEFAULT_BASE_URL = "http://127.0.0.1:1234/v1"
DEFAULT_MODEL = "qwen2.5-7b-instruct"


def get_client() -> openai.OpenAI:
    base_url = os.environ.get("LM_STUDIO_BASE_URL", DEFAULT_BASE_URL)

    if not base_url.startswith("http://127.0.0.1") and not base_url.startswith("http://localhost"):
        raise ValueError(
            f"Refusing to configure a non-loopback LM_STUDIO_BASE_URL: {base_url!r}. "
            "This lab is designed to talk to a local model server only."
        )

    return openai.OpenAI(
        base_url=base_url,
        # LM Studio does not check this value; it only needs to be a non-empty
        # string to satisfy the OpenAI SDK. It is not a real credential.
        api_key=os.environ.get("LM_STUDIO_API_KEY", "lm-studio"),
    )


def get_model_name() -> str:
    return os.environ.get("LM_STUDIO_MODEL", DEFAULT_MODEL)


def ask(system_prompt: str, user_prompt: str, *, temperature: float = 0.1) -> str:
    client = get_client()
    response = client.chat.completions.create(
        model=get_model_name(),
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=temperature,
    )
    return response.choices[0].message.content or ""
