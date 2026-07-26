"""
Storage abstraction layer for Medication Summary.

- Local (default): reads/writes drugs_config.json
- Redis (when KV_URL env var is set): uses Vercel KV via Redis protocol

To switch to Redis:
  1. Provision a Vercel KV database
  2. Set KV_URL in your Vercel project environment variables
  3. Redeploy — no code changes needed
"""

import json
import os
from pathlib import Path

CONFIG_PATH = Path("drugs_config.json")

# Attempt to load Redis only if KV_URL is set
KV_URL = os.environ.get("KV_URL")
redis_client = None

if KV_URL:
    try:
        import redis.asyncio as aioredis
        redis_client = aioredis.from_url(KV_URL, decode_responses=True)
    except Exception:
        redis_client = None

REDIS_KEY = "medication_config"


def load_config() -> dict:
    """Load the drug config from local JSON or Redis."""
    if redis_client is not None:
        # In-memory fallback during async gaps: use sync Redis
        import redis as sync_redis
        r = sync_redis.from_url(KV_URL, decode_responses=True)
        raw = r.get(REDIS_KEY)
        if raw:
            return json.loads(raw)
        # Seed from local file if Redis is empty
        if CONFIG_PATH.exists():
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            r.set(REDIS_KEY, json.dumps(data, ensure_ascii=False))
            return data
        return {}
    # Local file fallback
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_config(config: dict) -> None:
    """Persist the drug config to local JSON or Redis."""
    if redis_client is not None:
        import redis as sync_redis
        r = sync_redis.from_url(KV_URL, decode_responses=True)
        r.set(REDIS_KEY, json.dumps(config, ensure_ascii=False))
    else:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
