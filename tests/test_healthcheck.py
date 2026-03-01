from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from deepseek_hf_monitor.healthcheck import check_heartbeat


def _write_heartbeat(path: Path, ts: datetime) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"heartbeat_at": ts.isoformat()}), encoding="utf-8")


def test_heartbeat_is_healthy_when_recent(tmp_path: Path) -> None:
    heartbeat_file = tmp_path / "heartbeat.json"
    _write_heartbeat(heartbeat_file, datetime.now(timezone.utc) - timedelta(seconds=20))

    ok, _ = check_heartbeat(heartbeat_file=heartbeat_file, max_age_seconds=120)
    assert ok is True


def test_heartbeat_is_unhealthy_when_too_old(tmp_path: Path) -> None:
    heartbeat_file = tmp_path / "heartbeat.json"
    _write_heartbeat(heartbeat_file, datetime.now(timezone.utc) - timedelta(seconds=500))

    ok, _ = check_heartbeat(heartbeat_file=heartbeat_file, max_age_seconds=120)
    assert ok is False
