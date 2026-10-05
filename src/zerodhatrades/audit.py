"""Append-only JSONL audit trail of every signal, decision and order."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path


class AuditLog:
    def __init__(self, log_dir: str | Path):
        self.dir = Path(log_dir)
        self.dir.mkdir(parents=True, exist_ok=True)

    def write(self, event: str, now: datetime, **fields) -> None:
        path = self.dir / f"audit-{now.date().isoformat()}.jsonl"
        rec = {"ts": now.isoformat(), "event": event, **fields}
        with open(path, "a") as f:
            f.write(json.dumps(rec, default=str) + "\n")
