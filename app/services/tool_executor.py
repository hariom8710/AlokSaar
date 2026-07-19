"""
Tool Executor — the layer that actually calls the LLM (Gemini by default,
Anthropic as a fallback).
"""
import os

DEFAULT_MAX_TOKENS = 1024
VISUALIZATION_MAX_TOKENS = 3072


def get_provider() -> str:
    return os.getenv("LLM_PROVIDER", "gemini").lower()


def call_gemini(system_prompt: str, messages: list, max_tokens: int = DEFAULT_MAX_TOKENS) -> str:
    from google import genai
    from google.genai import types

    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not set. Get a free key at "
            "https://aistudio.google.com/apikey and add it to your .env file."
        )
    client = genai.Client(api_key=api_key)
    model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    contents = [
        types.Content(
            role=("model" if m["role"] == "assistant" else "user"),
            parts=[types.Part(text=m["content"])],
        )
        for m in messages
    ]

    response = client.models.generate_content(
        model=model,
        contents=contents,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            max_output_tokens=max_tokens,
        ),
    )
    text = response.text or ""

    try:
        finish_reason = response.candidates[0].finish_reason
        if finish_reason is not None and str(finish_reason).upper().endswith("MAX_TOKENS") and not text.strip():
            raise RuntimeError(
                "Gemini's response was cut off (hit the token limit) before "
                "producing any output. Try a simpler/shorter request."
            )
    except (IndexError, AttributeError):
        pass

    return text


def call_anthropic(system_prompt: str, messages: list, max_tokens: int = DEFAULT_MAX_TOKENS) -> str:
    from anthropic import Anthropic

    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set. Add it to your .env file to enable "
            "the AI assistant (see .env.example)."
        )
    client = Anthropic(api_key=api_key)
    model = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")

    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system_prompt,
        messages=messages,
    )
    return "".join(block.text for block in response.content if block.type == "text")


def generate_response(system_prompt: str, messages: list, max_tokens: int = DEFAULT_MAX_TOKENS) -> str:
    provider = get_provider()
    if provider == "gemini":
        return call_gemini(system_prompt, messages, max_tokens=max_tokens)
    elif provider == "anthropic":
        return call_anthropic(system_prompt, messages, max_tokens=max_tokens)
    else:
        raise RuntimeError(f"Unknown LLM_PROVIDER '{provider}' — use 'gemini' or 'anthropic'.")