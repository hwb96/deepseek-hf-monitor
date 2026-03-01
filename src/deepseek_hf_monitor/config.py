from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from dotenv import dotenv_values


_TRUE_VALUES = {"1", "true", "yes", "on"}
_FALSE_VALUES = {"0", "false", "no", "off"}


@dataclass(frozen=True)
class AppConfig:
    hf_author: str
    hf_limit: int
    check_interval_seconds: int
    state_file: Path
    heartbeat_file: Path
    contains: str
    bootstrap_if_missing: bool
    email_sender: str | None
    email_sender_name: str
    email_password: str | None
    email_receivers: list[str]


def _read_env_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}

    raw = dotenv_values(path)
    return {
        key: str(value)
        for key, value in raw.items()
        if key and value is not None and str(value).strip() != ""
    }


def _parse_bool(value: str | None, *, default: bool) -> bool:
    if value is None:
        return default
    lowered = value.strip().lower()
    if lowered in _TRUE_VALUES:
        return True
    if lowered in _FALSE_VALUES:
        return False
    return default


def _parse_int(value: str | None, *, default: int, minimum: int) -> int:
    if value is None:
        return default
    try:
        parsed = int(value)
    except ValueError:
        return default
    return max(parsed, minimum)


def _parse_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def load_config(
    project_root: Path | None = None,
    environ: Mapping[str, str] | None = None,
) -> AppConfig:
    root = project_root or Path.cwd()
    env_map: dict[str, str] = dict(environ) if environ is not None else dict(os.environ)

    local_env = _read_env_file(root / ".env")
    external_candidate = env_map.get("EXTERNAL_ENV_FILE") or local_env.get("EXTERNAL_ENV_FILE", "")
    external_env: dict[str, str] = {}
    if external_candidate:
        external_env = _read_env_file(Path(external_candidate).expanduser())

    merged: dict[str, str] = {}
    merged.update(external_env)
    merged.update(local_env)
    merged.update(env_map)

    sender = merged.get("EMAIL_SENDER")
    receivers = _parse_csv(merged.get("EMAIL_RECEIVERS"))
    if sender and not receivers:
        receivers = [sender]

    return AppConfig(
        hf_author=merged.get("HF_AUTHOR", "deepseek-ai"),
        hf_limit=_parse_int(merged.get("HF_LIMIT"), default=100, minimum=1),
        check_interval_seconds=_parse_int(
            merged.get("CHECK_INTERVAL_SECONDS"),
            default=1800,
            minimum=1,
        ),
        state_file=Path(merged.get("STATE_FILE", "state/models.json")),
        heartbeat_file=Path(merged.get("HEARTBEAT_FILE", "state/heartbeat.json")),
        contains=merged.get("CONTAINS", "").strip(),
        bootstrap_if_missing=_parse_bool(
            merged.get("BOOTSTRAP_IF_MISSING"),
            default=True,
        ),
        email_sender=sender,
        email_sender_name=merged.get("EMAIL_SENDER_NAME", "deepseek-hf-monitor"),
        email_password=merged.get("EMAIL_PASSWORD"),
        email_receivers=receivers,
    )
