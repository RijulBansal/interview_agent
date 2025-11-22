# llm/llm_providers.py
from llm.openai_provider import openai_generate
import os

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai")  # "openai" or "local"

def generate_response(messages, **kwargs):
    if LLM_PROVIDER == "openai":
        return openai_generate(messages, **kwargs)
    elif LLM_PROVIDER == "local":
        # TODO: implement local provider (Ollama / HTTP to local server)
        return "LOCAL_PROVIDER_NOT_IMPLEMENTED"
    else:
        raise ValueError("Unknown LLM_PROVIDER")
