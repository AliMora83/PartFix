"""Provider switch. ask(prompt, images) -> text; every call logged to logs/usage.jsonl."""
import base64
import json
import mimetypes
import os
import time
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
LOG_PATH = ROOT / "logs" / "usage.jsonl"

load_dotenv(ROOT / ".env")

META_BASE_URL = "https://api.meta.ai/v1"
DEFAULT_MODELS = {
    "meta": "muse-spark-1.3",
    "baseten": "meta-models/muse-spark-open-1026",
}


def _data_url(path):
    mime = mimetypes.guess_type(str(path))[0] or "image/jpeg"
    b64 = base64.b64encode(Path(path).read_bytes()).decode()
    return f"data:{mime};base64,{b64}"


def _log(model, usage, latency):
    LOG_PATH.parent.mkdir(exist_ok=True)
    rec = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "provider": os.environ.get("PROVIDER", "meta"),
        "model": model,
        "input_tokens": getattr(usage, "prompt_tokens", None),
        "output_tokens": getattr(usage, "completion_tokens", None),
        "latency_s": round(latency, 3),
    }
    with LOG_PATH.open("a") as f:
        f.write(json.dumps(rec) + "\n")
    return rec


def _chat(base_url, api_key, model, messages):
    from openai import OpenAI

    client = OpenAI(base_url=base_url, api_key=api_key)
    t0 = time.monotonic()
    resp = client.chat.completions.create(model=model, messages=messages)
    rec = _log(model, resp.usage, time.monotonic() - t0)
    return resp.choices[0].message.content or "", rec


def ask(prompt, images=(), history=None):
    """Send prompt (+ image paths) to the configured provider.

    history: optional prior messages (list of role/content dicts) to continue a chat.
    Returns (text, usage_record).
    """
    provider = os.environ.get("PROVIDER", "meta")
    model = os.environ.get("MODEL") or DEFAULT_MODELS.get(provider)
    content = [{"type": "text", "text": prompt}]
    for img in images:
        content.append({"type": "image_url", "image_url": {"url": _data_url(img)}})
    messages = list(history or []) + [{"role": "user", "content": content}]

    if provider == "meta":
        return _chat(META_BASE_URL, os.environ["MODEL_API_KEY"], model, messages)
    if provider == "baseten":
        # OpenAI-compatible chat completions; confirm base URL in Baseten dashboard.
        base = os.environ["BASETEN_BASE_URL"]
        return _chat(base, os.environ["BASETEN_API_KEY"], model, messages)
    if provider == "modal":
        raise NotImplementedError("modal provider not implemented yet")
    raise ValueError(f"unknown PROVIDER: {provider}")
