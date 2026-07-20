"""Single-use, replay-safe confirmation tokens."""
import hashlib
import json
import time
import threading
from dataclasses import dataclass, field
from typing import Any

from nexus.core.interfaces import ActionPlan


@dataclass
class ConfirmationStore:
    ttl_seconds: int = 120
    _clock: callable = time.time
    _lock: threading.RLock = field(default_factory=threading.RLock, repr=False)
    _tokens: dict[str, dict[str, Any]] = field(default_factory=dict, repr=False)

    def _plan_hash(self, plan: ActionPlan) -> str:
        """Deterministic hash of the plan content (excluding reasoning)."""
        # Use only action_type, target, and params (sorted)
        data = {
            "action_type": plan.action_type,
            "target": plan.target,
            "params": plan.params,
        }
        # Sort keys for stability
        json_str = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(json_str.encode("utf-8")).hexdigest()

    def issue(self, plan: ActionPlan) -> str:
        """Create a new confirmation token bound to the plan's content hash."""
        token_id = hashlib.sha256(f"{self._clock()}{plan.action_type}{self._plan_hash(plan)}".encode()).hexdigest()[:16]
        content_hash = self._plan_hash(plan)
        with self._lock:
            self._tokens[token_id] = {
                "content_hash": content_hash,
                "issued_at": self._clock(),
                "used": False,
            }
        return token_id

    def redeem(self, token_id: str, plan: ActionPlan) -> bool:
        """
        Redeem token if it matches the plan's content hash, is not expired, and unused.
        Returns True on success, False otherwise.
        """
        with self._lock:
            token = self._tokens.get(token_id)
            if token is None:
                return False
            if token["used"]:
                return False
            if self._clock() - token["issued_at"] > self.ttl_seconds:
                del self._tokens[token_id]
                return False

            content_hash = self._plan_hash(plan)
            if content_hash != token["content_hash"]:
                return False

            token["used"] = True
            return True

    def cleanup_expired(self) -> None:
        """Remove expired tokens (called periodically or during redemption)."""
        now = self._clock()
        with self._lock:
            expired = [tid for tid, data in self._tokens.items() if now - data["issued_at"] > self.ttl_seconds]
            for tid in expired:
                del self._tokens[tid]