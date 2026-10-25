"""Thin Groq wrapper with retry/backoff for rate limits."""
import random
import time
from typing import Iterator

from . import config


class LLMError(Exception):
    pass


_client = None


def _get_client():
    global _client
    if not config.GROQ_API_KEY or config.GROQ_API_KEY.startswith("your_"):
        raise LLMError("GROQ_API_KEY is not set. Copy .env.example to .env and add your key.")
    if _client is None:
        from groq import Groq

        _client = Groq(api_key=config.GROQ_API_KEY, max_retries=0)
    return _client


def _with_retry(fn, attempts: int = 6):
    import groq

    delay = 2.0
    for attempt in range(attempts):
        try:
            return fn()
        except groq.RateLimitError as e:
            if attempt == attempts - 1:
                raise LLMError("Groq rate limit reached. Wait a minute and try again.") from e
            retry_after = None
            try:
                retry_after = float(e.response.headers.get("retry-after"))
            except Exception:
                pass
            time.sleep((retry_after or delay) + random.random())
            delay = min(delay * 2, 60)
        except (groq.APIConnectionError, groq.InternalServerError) as e:
            if attempt == attempts - 1:
                raise LLMError(f"Could not reach Groq: {e}") from e
            time.sleep(delay)
            delay = min(delay * 2, 30)
        except groq.AuthenticationError as e:
            raise LLMError("Groq rejected the API key. Check GROQ_API_KEY in .env.") from e
        except groq.APIStatusError as e:
            if e.status_code == 413:
                raise LLMError("Request too large for your Groq plan. Lower NOTES_MAX_TOKENS "
                               "or CHUNK_TOKENS in .env and restart.") from e
            raise LLMError(f"Groq error {e.status_code}: {e.message}") from e


REASONING_HEADROOM = 1500  # reasoning models spend part of max_tokens thinking


def _params(messages: list[dict], max_tokens: int, temperature: float) -> dict:
    params = {"model": config.GROQ_MODEL, "messages": messages,
              "max_tokens": max_tokens, "temperature": temperature}
    if config.GROQ_MODEL.startswith("openai/gpt-oss"):
        params["reasoning_effort"] = config.REASONING_EFFORT
        params["max_tokens"] = max_tokens + REASONING_HEADROOM
    return params


def complete(messages: list[dict], max_tokens: int = 2048, temperature: float = 0.3) -> str:
    client = _get_client()
    resp = _with_retry(lambda: client.chat.completions.create(**_params(messages, max_tokens, temperature)))
    return resp.choices[0].message.content or ""


def stream(messages: list[dict], max_tokens: int = 1500, temperature: float = 0.3) -> Iterator[str]:
    client = _get_client()
    resp = _with_retry(lambda: client.chat.completions.create(
        **_params(messages, max_tokens, temperature), stream=True))
    for event in resp:
        delta = event.choices[0].delta.content if event.choices else None
        if delta:
            yield delta
