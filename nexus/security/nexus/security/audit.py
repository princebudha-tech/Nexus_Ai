"""Append-only audit log with JSON lines."""
import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from nexus.core.interfaces import ActionPlan, GuardrailDecision, GuardrailResult


class AuditLogger:
    def __init__(self, log_path: str | Path) -> None:
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def log_decision(self, result: GuardrailResult) -> None:
        """Write one JSON line per guardrail decision."""
        entry = {
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            "decision": result.decision.value,
            "reason": result.reason,
            "action_type": result.plan.action_type,
            "target": result.plan.target,
            "params": result.plan.params,
            "requested_by_agent": result.plan.requested_by_agent,
        }
        if result.confirmation_id:
            entry["confirmation_id"] = result.confirmation_id

        with self._lock:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, default=str) + "\n")