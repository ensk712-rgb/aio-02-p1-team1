"""승인이 필요한 Tool 호출을 Redis에 TTL로 보관합니다.

`docs/04_pending-action-and-confirmation.md`와 같은 계약입니다: 한 번 `consume()`하면
사라지고, 확인 시점에 자연어를 다시 해석하지 않습니다.
"""

import json
from uuid import uuid4

import redis

from app.core.config import settings

_client = redis.from_url(settings.redis_url, decode_responses=True)


def _key(action_id: str) -> str:
    return f"ranger:pending_action:{action_id}"


def create(tool_name: str, arguments: dict, summary: str) -> dict:
    action_id = uuid4().hex[:12]
    payload = {"action_id": action_id, "tool_name": tool_name, "arguments": arguments, "summary": summary}
    _client.setex(_key(action_id), settings.pending_action_ttl_seconds, json.dumps(payload, ensure_ascii=False))
    return payload


def consume(action_id: str) -> dict | None:
    key = _key(action_id)
    raw = _client.get(key)
    if raw is None:
        return None
    _client.delete(key)
    return json.loads(raw)
