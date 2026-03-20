"""
Modified models.py for AidanBench that uses:
- Anthropic API (Bearer token auth) instead of OpenRouter
- sentence-transformers for local embeddings instead of OpenAI
"""
import json
import os
import urllib.request
from functools import lru_cache
from retry import retry
from sentence_transformers import SentenceTransformer

# Auth
BEARER_TOKEN = open('/home/claude/.claude/remote/.session_ingress_token').read().strip()
ANTHROPIC_BASE_URL = os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com")

# Map OpenRouter-style model names to Anthropic model IDs
# Also map o1-mini (judge model) to a fast Claude model
MODEL_MAP = {
    # OpenRouter format -> Anthropic API format
    "anthropic/claude-sonnet-4": "claude-sonnet-4-6",
    "anthropic/claude-sonnet-4:thinking": "claude-sonnet-4-6",
    "anthropic/claude-opus-4": "claude-opus-4-6",
    "anthropic/claude-3.5-sonnet": "claude-3-5-sonnet-20241022",
    "anthropic/claude-3-5-haiku-20241022": "claude-3-5-haiku-20241022",
    "anthropic/claude-3.7-sonnet": "claude-3-7-sonnet-20250219",
    # Judge model (o1-mini in original) -> fast Claude Haiku
    "o1-mini": "claude-haiku-4-5-20251001",
}

# Embedding model (loaded once)
_embed_model = None


def _get_embed_model():
    global _embed_model
    if _embed_model is None:
        _embed_model = SentenceTransformer('all-MiniLM-L6-v2')
    return _embed_model


def _resolve_model(model: str) -> str:
    """Map OpenRouter-style model names to Anthropic API model IDs."""
    return MODEL_MAP.get(model, model)


@retry(tries=3, delay=1, backoff=2)
def chat_with_model(prompt: str, model: str, max_tokens: int = 4000, temperature: float = 0) -> str:
    model_id = _resolve_model(model)
    data = json.dumps({
        "model": model_id,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": [{"role": "user", "content": prompt}]
    }).encode()

    req = urllib.request.Request(
        f"{ANTHROPIC_BASE_URL}/v1/messages",
        data=data,
        headers={
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
            "Authorization": f"Bearer {BEARER_TOKEN}"
        }
    )
    resp = urllib.request.urlopen(req, timeout=120)
    result = json.loads(resp.read())
    return result["content"][0]["text"]


@lru_cache(maxsize=10000)
@retry(tries=3, delay=1, backoff=2)
def embed(text: str) -> tuple:
    """Return embedding as tuple (hashable, for lru_cache compatibility)."""
    model = _get_embed_model()
    embedding = model.encode(text, normalize_embeddings=True)
    return tuple(embedding.tolist())
