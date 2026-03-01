from __future__ import annotations

import json
from pathlib import Path

from deepseek_hf_monitor.config import AppConfig
from deepseek_hf_monitor.monitor import check_once, run_single_cycle


class _FakeNotifier:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def send_new_models(self, author: str, new_model_ids: list[str]) -> bool:
        self.calls.append({"author": author, "new_model_ids": list(new_model_ids)})
        return True


def _write_state(path: Path, ids: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"model_ids": ids}, ensure_ascii=False, indent=2), encoding="utf-8")


def test_bootstrap_when_state_missing(tmp_path: Path) -> None:
    state_file = tmp_path / "state.json"

    result = check_once(
        current_models=[
            {"id": "deepseek-ai/DeepSeek-V3"},
            {"id": "deepseek-ai/DeepSeek-R1"},
        ],
        state_file=state_file,
        bootstrap_if_missing=True,
    )

    assert result.status == "bootstrap"
    assert result.new_model_ids == []
    assert state_file.exists()


def test_no_change_when_models_unchanged(tmp_path: Path) -> None:
    state_file = tmp_path / "state.json"
    _write_state(state_file, ["deepseek-ai/DeepSeek-V3"])

    result = check_once(
        current_models=[{"id": "deepseek-ai/DeepSeek-V3"}],
        state_file=state_file,
        bootstrap_if_missing=True,
    )

    assert result.status == "no_change"
    assert result.new_model_ids == []


def test_detects_new_models(tmp_path: Path) -> None:
    state_file = tmp_path / "state.json"
    _write_state(state_file, ["deepseek-ai/DeepSeek-V3"])

    result = check_once(
        current_models=[
            {"id": "deepseek-ai/DeepSeek-V4"},
            {"id": "deepseek-ai/DeepSeek-V3"},
        ],
        state_file=state_file,
        bootstrap_if_missing=True,
    )

    assert result.status == "new_models"
    assert result.new_model_ids == ["deepseek-ai/DeepSeek-V4"]


def test_state_corruption_backed_up_and_recovered(tmp_path: Path) -> None:
    state_file = tmp_path / "models.json"
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text("{bad-json", encoding="utf-8")

    result = check_once(
        current_models=[{"id": "deepseek-ai/DeepSeek-V3"}],
        state_file=state_file,
        bootstrap_if_missing=True,
    )

    assert result.status == "bootstrap"
    assert result.recovered_from_corruption is True
    backups = list(tmp_path.glob("models.corrupt-*.json"))
    assert len(backups) == 1


def test_run_single_cycle_api_error_does_not_overwrite_state(tmp_path: Path) -> None:
    state_file = tmp_path / "models.json"
    heartbeat_file = tmp_path / "heartbeat.json"
    _write_state(state_file, ["deepseek-ai/DeepSeek-V3"])
    before = state_file.read_text(encoding="utf-8")

    cfg = AppConfig(
        hf_author="deepseek-ai",
        hf_limit=100,
        check_interval_seconds=1800,
        state_file=state_file,
        heartbeat_file=heartbeat_file,
        contains="",
        bootstrap_if_missing=True,
        email_sender=None,
        email_sender_name="bot",
        email_password=None,
        email_receivers=[],
    )

    def _raise_fetch(*_args, **_kwargs):
        raise RuntimeError("network down")

    outcome = run_single_cycle(config=cfg, fetcher=_raise_fetch, notifier=None)

    assert outcome.exit_code == 1
    assert state_file.read_text(encoding="utf-8") == before
    assert heartbeat_file.exists()


def test_run_single_cycle_sends_email_on_new_models(tmp_path: Path) -> None:
    state_file = tmp_path / "models.json"
    heartbeat_file = tmp_path / "heartbeat.json"
    cfg = AppConfig(
        hf_author="deepseek-ai",
        hf_limit=100,
        check_interval_seconds=1800,
        state_file=state_file,
        heartbeat_file=heartbeat_file,
        contains="",
        bootstrap_if_missing=True,
        email_sender=None,
        email_sender_name="bot",
        email_password=None,
        email_receivers=[],
    )
    notifier = _FakeNotifier()

    first = run_single_cycle(
        config=cfg,
        fetcher=lambda *_args, **_kwargs: [{"id": "deepseek-ai/DeepSeek-V3"}],
        notifier=notifier,
    )
    second = run_single_cycle(
        config=cfg,
        fetcher=lambda *_args, **_kwargs: [
            {"id": "deepseek-ai/DeepSeek-V4"},
            {"id": "deepseek-ai/DeepSeek-V3"},
        ],
        notifier=notifier,
    )

    assert first.exit_code == 0
    assert second.exit_code == 2
    assert len(notifier.calls) == 1
    assert notifier.calls[0]["new_model_ids"] == ["deepseek-ai/DeepSeek-V4"]
