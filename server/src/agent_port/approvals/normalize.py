import hashlib
import json


def normalize_tool_args(args: dict) -> str:
    return json.dumps(args, sort_keys=True, separators=(",", ":"))


def hash_normalized_args(normalized: str) -> str:
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()
