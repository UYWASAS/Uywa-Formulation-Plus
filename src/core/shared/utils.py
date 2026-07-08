import json
import os
from datetime import date


def safe_float(val, default=0.0):
    try:
        if isinstance(val, str):
            val = val.replace(",", ".")
        return float(val)
    except Exception:
        return default


def normalize_requirement_bound(val):
    bound = safe_float(val, 0)
    return bound if bound > 0 else 0.0


def profile_filename(user: dict) -> str:
    name = str(user.get("name", "user")).strip().replace(" ", "_")
    return f"{name}_profile.json"


def load_profile(user: dict) -> dict:
    filename = profile_filename(user)

    if os.path.exists(filename):
        try:
            with open(filename, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
        except Exception:
            pass

    return {
        "name": user.get("name", "Usuario"),
        "premium": bool(user.get("premium", False)),
        "last_cost": None,
        "num_saved": 0,
        "updated_at": date.today().isoformat(),
    }


def save_profile(user: dict, profile: dict):
    filename = profile_filename(user)
    payload = dict(profile)
    payload["updated_at"] = date.today().isoformat()

    with open(filename, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
