import json
import os
from pathlib import Path

CONFIG_PATH = Path("drugs_config.json")
FALLBACK_PATH = Path("/tmp/drugs_config.json") if os.environ.get("VERCEL") else CONFIG_PATH

KV_URL = os.environ.get("KV_URL")

def get_redis_client():
    if not KV_URL:
        return None
    try:
        import redis
        return redis.from_url(KV_URL, decode_responses=True, ssl_cert_reqs="none")
    except Exception as e:
        print(f"Failed to initialize Redis: {e}")
        return None

def load_config() -> dict:
    r = get_redis_client()
    if r:
        try:
            raw = r.get("medication_config")
            if raw:
                return json.loads(raw)
            if CONFIG_PATH.exists():
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                r.set("medication_config", json.dumps(data, ensure_ascii=False))
                return data
            return {}
        except Exception as e:
            print(f"Redis load error: {e}")
            
    target_path = FALLBACK_PATH if FALLBACK_PATH.exists() else CONFIG_PATH
    if target_path.exists():
        with open(target_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_config(config: dict) -> None:
    r = get_redis_client()
    if r:
        try:
            r.set("medication_config", json.dumps(config, ensure_ascii=False))
            return
        except Exception as e:
            print(f"Redis save error: {e}")
            
    with open(FALLBACK_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)