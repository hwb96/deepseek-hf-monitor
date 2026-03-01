from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path


def _parse_iso(ts: str) -> datetime:
    if ts.endswith("Z"):
        ts = ts[:-1] + "+00:00"
    parsed = datetime.fromisoformat(ts)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def check_heartbeat(heartbeat_file: Path, max_age_seconds: int) -> tuple[bool, str]:
    if not heartbeat_file.exists():
        return False, f"heartbeat 文件不存在: {heartbeat_file}"

    try:
        payload = json.loads(heartbeat_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False, "heartbeat 文件不是合法 JSON"

    heartbeat_at = payload.get("heartbeat_at") if isinstance(payload, dict) else None
    if not isinstance(heartbeat_at, str) or not heartbeat_at.strip():
        return False, "heartbeat_at 缺失"

    try:
        hb_time = _parse_iso(heartbeat_at)
    except ValueError:
        return False, "heartbeat_at 格式错误"

    age = (datetime.now(timezone.utc) - hb_time).total_seconds()
    if age <= max_age_seconds:
        return True, f"heartbeat 正常，age={int(age)}s"

    return False, f"heartbeat 超时，age={int(age)}s > {max_age_seconds}s"


def main(argv: list[str] | None = None) -> int:
    default_interval = int(os.getenv("CHECK_INTERVAL_SECONDS", "1800"))
    default_max_age = int(os.getenv("HEALTHCHECK_MAX_AGE_SECONDS", str(default_interval * 2 + 60)))
    default_file = Path(os.getenv("HEARTBEAT_FILE", "state/heartbeat.json"))

    parser = argparse.ArgumentParser(description="deepseek-hf-monitor heartbeat 健康检查")
    parser.add_argument("--heartbeat-file", type=Path, default=default_file)
    parser.add_argument("--max-age-seconds", type=int, default=default_max_age)
    args = parser.parse_args(argv)

    ok, message = check_heartbeat(args.heartbeat_file, args.max_age_seconds)
    print(message)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
