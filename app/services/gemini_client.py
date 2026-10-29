"""
The ONE place that calls Gemini (text and audio both come through here).

Why it exists: Gemini regularly answers "503 UNAVAILABLE - high demand" for a while, and the free
tier has small daily quotas per model. Instead of showing a resident an error, we:
  * retry briefly when the failure looks temporary (500/502/503/504, timeouts, dropped connections)
  * switch to the next model when this one is retired (404) or its quota is used up (429)
  * give up immediately on our own mistakes (bad key, bad request) — retrying can't fix those
"""
import time

from flask import current_app
from google import genai
from google.genai import errors, types

RETRY_SAME_MODEL = {500, 502, 503, 504}   # temporary, server-side
NEXT_MODEL_ONLY = {404, 429}              # model retired / this model's quota exhausted


class GeminiNotConfigured(Exception):
    """GEMINI_API_KEY missing — the route turns this into a clean 503."""


class GeminiCallFailed(Exception):
    """Every attempt failed. The message lists what happened on each model."""


def _models_to_try() -> list:
    primary = current_app.config.get("GEMINI_MODEL", "gemini-3.5-flash")
    fallbacks = current_app.config.get("GEMINI_FALLBACK_MODELS", [])
    seen, ordered = set(), []
    for name in [primary, *fallbacks]:
        if name and name not in seen:
            seen.add(name)
            ordered.append(name)
    return ordered


def generate(contents, config=None) -> str:
    """Returns Gemini's text answer. Raises GeminiNotConfigured or GeminiCallFailed."""
    cfg = current_app.config
    api_key = cfg.get("GEMINI_API_KEY")
    if not api_key:
        raise GeminiNotConfigured("GEMINI_API_KEY is not set in .env")

    retries = max(1, int(cfg.get("GEMINI_RETRIES_PER_MODEL", 2)))
    timeout_ms = int(cfg.get("GEMINI_TIMEOUT_SECONDS", 30)) * 1000
    client = genai.Client(api_key=api_key, http_options=types.HttpOptions(timeout=timeout_ms))

    log = []
    models = _models_to_try()
    for index, model in enumerate(models):
        for attempt in range(1, retries + 1):
            try:
                response = client.models.generate_content(model=model, contents=contents, config=config)
            except errors.APIError as exc:
                code = exc.code
                log.append(f"{model}: {code} {getattr(exc, 'status', '') or ''}".strip())
                if code in RETRY_SAME_MODEL:
                    if attempt < retries:
                        time.sleep(1.5 * attempt)   # 1.5s, then 3s ...
                        continue
                    break                            # retries used up -> next model
                if code in NEXT_MODEL_ONLY:
                    break                            # retrying this model can't help
                raise GeminiCallFailed("; ".join(log) + f" — {getattr(exc, 'message', exc)}") from exc
            except Exception as exc:                 # timeouts, dropped connections: treat as temporary
                log.append(f"{model}: {type(exc).__name__}")
                if attempt < retries:
                    time.sleep(1.5 * attempt)
                    continue
                break
            else:
                if index > 0 or attempt > 1:
                    current_app.logger.warning("Gemini answered via %s (attempt %d) after: %s", model, attempt, "; ".join(log))
                return (response.text or "").strip()

    raise GeminiCallFailed("; ".join(log) or "no model configured")
