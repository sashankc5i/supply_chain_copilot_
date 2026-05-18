"""Central LLM factory for the supply-chain copilot.

Every node that needs an LLM imports `get_llm()` from this module so the
Azure OpenAI config is read in exactly one place. Don't construct
`AzureChatOpenAI` directly inside node files -- it makes changing the
provider/model later a multi-file refactor.

Reads these env vars (from `.env` at the project root):
    AZURE_OPENAI_ENDPOINT
    AZURE_OPENAI_API_KEY
    AZURE_OPENAI_API_VERSION
    AZURE_OPENAI_DEPLOYMENT_NAME
"""
from __future__ import annotations

if __package__ in (None, ""):
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import os
from functools import lru_cache

from dotenv import load_dotenv
from langchain_openai import AzureChatOpenAI  # type: ignore[reportMissingImports]

load_dotenv()


@lru_cache(maxsize=4)
def get_llm(temperature: float = 0.0) -> AzureChatOpenAI:
    """Return a configured AzureChatOpenAI client.

    Cached per `temperature` so repeated calls reuse the same client/session.
    Use `temperature=0` for diagnose/recommend/critique calls (deterministic);
    use a small non-zero value only when intentional creativity is needed.
    """
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    api_key = os.getenv("AZURE_OPENAI_API_KEY")
    api_version = os.getenv("AZURE_OPENAI_API_VERSION")
    deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")

    missing = [n for n, v in {
        "AZURE_OPENAI_ENDPOINT": endpoint,
        "AZURE_OPENAI_API_KEY": api_key,
        "AZURE_OPENAI_API_VERSION": api_version,
        "AZURE_OPENAI_DEPLOYMENT_NAME": deployment,
    }.items() if not v]
    if missing:
        raise RuntimeError(
            f"Missing required env vars: {', '.join(missing)}. "
            "Add them to .env at the project root."
        )

    return AzureChatOpenAI(
        azure_endpoint=endpoint,
        api_key=api_key,
        api_version=api_version,
        azure_deployment=deployment,
        temperature=temperature,
    )


if __name__ == "__main__":
    llm = get_llm()
    print("LLM configured:", llm.deployment_name, "@", llm.azure_endpoint)
    print("Sanity check response:", llm.invoke("Reply with exactly: ok").content)
