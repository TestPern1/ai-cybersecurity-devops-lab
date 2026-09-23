"""Shared client for talking to a local, OpenAI-compatible LM Studio server.

Every agent in this lab goes through this one module to reach the model, so
the "local only, no external calls" constraint only has to be enforced and
reviewed in one place.
"""

from __future__ import annotations

import ipaddress
import os
from pathlib import Path
from urllib.parse import urlparse

import openai
from dotenv import load_dotenv

# Load the repo-root .env (agents/common/llm_client.py -> agents/common ->
# agents -> repo root) so running an agent directly (`python foo_agent.py`)
# picks up the same config as `docker compose --env-file .env`, instead of
# silently falling back to DEFAULT_BASE_URL below. override=False so a real
# exported env var still wins if you've set one manually.
load_dotenv(dotenv_path=Path(__file__).resolve().parents[2] / ".env", override=False)

DEFAULT_BASE_URL = "http://127.0.0.1:1234/v1"
DEFAULT_MODEL = "qwen2.5-7b-instruct"


def _is_local_only(base_url: str) -> bool:
    """True for literal loopback or an RFC1918 private address.

    Plain loopback (127.0.0.1/localhost) covers running the agents directly
    alongside LM Studio with no VM involved. A private address covers the
    VirtualBox VM setup (see docs/INSTALL.md), where LM Studio is reachable
    only via the host-only adapter's private subnet — not literal loopback,
    but still never routable beyond this one physical machine.
    """
    host = urlparse(base_url).hostname
    if host in ("localhost",):
        return True
    try:
        addr = ipaddress.ip_address(host)
    except ValueError:
        return False
    return addr.is_loopback or addr.is_private


def get_client() -> openai.OpenAI:
    base_url = os.environ.get("LM_STUDIO_BASE_URL", DEFAULT_BASE_URL)

    if not _is_local_only(base_url):
        raise ValueError(
            f"Refusing to configure a non-local LM_STUDIO_BASE_URL: {base_url!r}. "
            "This lab is designed to talk to a local-only model server (loopback or "
            "a private/RFC1918 address such as a VirtualBox host-only adapter), never "
            "a public address."
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
