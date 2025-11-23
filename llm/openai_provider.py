# llm/openai_provider.py
import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
_api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=_api_key)

def openai_generate(messages, model="gpt-4.1-mini", max_tokens=512, temperature=0.2):
    # messages: list of {"role":"system"/"user"/"assistant","content": "..."}
    resp = client.responses.create(
    model=model,
    input=messages,
    max_output_tokens=max_tokens,
    temperature=temperature
)

    # extract text in a safe way
    out = ""
    for item in resp.output:
        if hasattr(item, "content"):
            for c in item.content:
                if getattr(c, "text", None):
                    out += c.text
    return out
