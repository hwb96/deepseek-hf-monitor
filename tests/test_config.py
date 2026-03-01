from __future__ import annotations

from pathlib import Path

from deepseek_hf_monitor.config import load_config


def _write_env(path: Path, data: dict[str, str]) -> None:
    content = "\n".join(f"{k}={v}" for k, v in data.items()) + "\n"
    path.write_text(content, encoding="utf-8")


def test_load_config_precedence_env_over_local_over_external(tmp_path: Path) -> None:
    external = tmp_path / "external.env"
    local = tmp_path / ".env"

    _write_env(
        external,
        {
            "HF_AUTHOR": "external-author",
            "EMAIL_SENDER": "external@example.com",
            "EMAIL_PASSWORD": "external-pass",
        },
    )

    _write_env(
        local,
        {
            "EXTERNAL_ENV_FILE": str(external),
            "HF_AUTHOR": "local-author",
            "EMAIL_SENDER": "local@example.com",
            "EMAIL_PASSWORD": "local-pass",
            "EMAIL_RECEIVERS": "a@example.com,b@example.com",
            "CHECK_INTERVAL_SECONDS": "900",
        },
    )

    cfg = load_config(
        project_root=tmp_path,
        environ={
            "HF_AUTHOR": "env-author",
            "EMAIL_SENDER_NAME": "Env Name",
        },
    )

    assert cfg.hf_author == "env-author"
    assert cfg.email_sender == "local@example.com"
    assert cfg.email_password == "local-pass"
    assert cfg.email_receivers == ["a@example.com", "b@example.com"]
    assert cfg.email_sender_name == "Env Name"
    assert cfg.check_interval_seconds == 900


def test_load_config_defaults_when_no_files(tmp_path: Path) -> None:
    cfg = load_config(project_root=tmp_path, environ={})

    assert cfg.hf_author == "deepseek-ai"
    assert cfg.hf_limit == 100
    assert cfg.check_interval_seconds == 1800
    assert cfg.state_file == Path("state/models.json")
    assert cfg.heartbeat_file == Path("state/heartbeat.json")
