from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

from deepseek_hf_monitor.config import AppConfig, load_config
from deepseek_hf_monitor.emailer import EmailNotifier

HF_API_URL = "https://huggingface.co/api/models"


class NewModelNotifier(Protocol):
    def send_new_models(self, author: str, new_model_ids: list[str]) -> bool: ...


@dataclass(frozen=True)
class CheckResult:
    status: str
    new_model_ids: list[str]
    current_model_ids: list[str]
    recovered_from_corruption: bool = False


@dataclass(frozen=True)
class CycleOutcome:
    exit_code: int
    result: CheckResult | None
    error: str = ""
    email_sent: bool = False


def fetch_models(author: str = "deepseek-ai", limit: int = 100, timeout: int = 15) -> list[dict[str, Any]]:
    query = urllib.parse.urlencode(
        {
            "author": author,
            "sort": "lastModified",
            "direction": "-1",
            "limit": limit,
        }
    )
    url = f"{HF_API_URL}?{query}"

    with urllib.request.urlopen(url, timeout=timeout) as response:
        payload = response.read().decode("utf-8")

    data = json.loads(payload)
    if not isinstance(data, list):
        raise ValueError("Hugging Face API 返回格式不是列表")

    return [item for item in data if isinstance(item, dict)]


def check_once(current_models: list[dict[str, Any]], state_file: Path, bootstrap_if_missing: bool = True) -> CheckResult:
    current_model_ids = _extract_model_ids(current_models)
    state_missing = not state_file.exists()
    known_model_ids, recovered = _load_known_model_ids(state_file)

    if recovered:
        _write_state(state_file, current_model_ids)
        return CheckResult(
            status="bootstrap",
            new_model_ids=[],
            current_model_ids=current_model_ids,
            recovered_from_corruption=True,
        )

    if state_missing and bootstrap_if_missing:
        _write_state(state_file, current_model_ids)
        return CheckResult(status="bootstrap", new_model_ids=[], current_model_ids=current_model_ids)

    new_model_ids = [model_id for model_id in current_model_ids if model_id not in known_model_ids]
    _write_state(state_file, current_model_ids)

    if new_model_ids:
        return CheckResult(
            status="new_models",
            new_model_ids=new_model_ids,
            current_model_ids=current_model_ids,
        )

    return CheckResult(status="no_change", new_model_ids=[], current_model_ids=current_model_ids)


def run_single_cycle(
    config: AppConfig,
    fetcher: Any = fetch_models,
    notifier: NewModelNotifier | None = None,
) -> CycleOutcome:
    _write_heartbeat(config.heartbeat_file)

    try:
        models = fetcher(author=config.hf_author, limit=config.hf_limit)
    except Exception as exc:  # noqa: BLE001
        return CycleOutcome(exit_code=1, result=None, error=f"拉取模型失败: {exc}")

    contains = config.contains.strip().lower()
    if contains:
        models = [m for m in models if contains in str(m.get("id", "")).lower()]

    result = check_once(
        current_models=models,
        state_file=config.state_file,
        bootstrap_if_missing=config.bootstrap_if_missing,
    )

    if result.status == "new_models":
        email_sent = False
        if notifier is not None:
            email_sent = notifier.send_new_models(config.hf_author, result.new_model_ids)
        return CycleOutcome(exit_code=2, result=result, email_sent=email_sent)

    return CycleOutcome(exit_code=0, result=result)


def run_loop(config: AppConfig, notifier: NewModelNotifier | None = None) -> int:
    while True:
        outcome = run_single_cycle(config=config, notifier=notifier)
        _print_outcome(outcome)
        try:
            time.sleep(config.check_interval_seconds)
        except KeyboardInterrupt:
            return 0


def _extract_model_ids(models: list[dict[str, Any]]) -> list[str]:
    model_ids: list[str] = []
    for model in models:
        model_id = str(model.get("id", "")).strip()
        if model_id:
            model_ids.append(model_id)
    return model_ids


def _load_known_model_ids(state_file: Path) -> tuple[set[str], bool]:
    if not state_file.exists():
        return set(), False

    try:
        raw = json.loads(state_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        _backup_corrupt_state_file(state_file)
        return set(), True

    if not isinstance(raw, dict):
        _backup_corrupt_state_file(state_file)
        return set(), True

    ids = raw.get("model_ids", [])
    if not isinstance(ids, list):
        _backup_corrupt_state_file(state_file)
        return set(), True

    return {str(model_id).strip() for model_id in ids if str(model_id).strip()}, False


def _backup_corrupt_state_file(state_file: Path) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = state_file.with_name(f"{state_file.stem}.corrupt-{stamp}{state_file.suffix}")
    suffix = 1
    while backup.exists():
        backup = state_file.with_name(f"{state_file.stem}.corrupt-{stamp}.{suffix}{state_file.suffix}")
        suffix += 1

    state_file.replace(backup)
    return backup


def _write_state(state_file: Path, model_ids: list[str]) -> None:
    state_file.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "model_ids": model_ids,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    state_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_heartbeat(heartbeat_file: Path) -> None:
    heartbeat_file.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "heartbeat_at": datetime.now(timezone.utc).isoformat(),
    }
    heartbeat_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _build_parser(defaults: AppConfig) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="监控 Hugging Face 组织是否出现新模型")
    parser.add_argument("--author", default=defaults.hf_author, help="Hugging Face 组织名")
    parser.add_argument("--limit", type=int, default=defaults.hf_limit, help="每次最多拉取的模型数量")
    parser.add_argument("--state-file", type=Path, default=defaults.state_file, help="状态文件路径")
    parser.add_argument("--heartbeat-file", type=Path, default=defaults.heartbeat_file, help="心跳文件路径")
    parser.add_argument("--contains", default=defaults.contains, help="仅保留模型 ID 中包含该子串的结果")
    parser.add_argument(
        "--bootstrap-if-missing",
        action=argparse.BooleanOptionalAction,
        default=defaults.bootstrap_if_missing,
        help="状态文件不存在时是否先建立基线",
    )
    parser.add_argument(
        "--interval-seconds",
        type=int,
        default=defaults.check_interval_seconds,
        help="循环模式轮询间隔（秒）",
    )
    parser.add_argument(
        "--loop",
        action="store_true",
        help="开启守护循环模式",
    )
    return parser


def _build_runtime_config(args: argparse.Namespace, base: AppConfig) -> AppConfig:
    return AppConfig(
        hf_author=args.author,
        hf_limit=max(1, int(args.limit)),
        check_interval_seconds=max(1, int(args.interval_seconds)),
        state_file=args.state_file,
        heartbeat_file=args.heartbeat_file,
        contains=args.contains,
        bootstrap_if_missing=bool(args.bootstrap_if_missing),
        email_sender=base.email_sender,
        email_sender_name=base.email_sender_name,
        email_password=base.email_password,
        email_receivers=base.email_receivers,
    )


def _build_notifier(config: AppConfig) -> EmailNotifier | None:
    if not (config.email_sender and config.email_password and config.email_receivers):
        return None
    return EmailNotifier(
        sender=config.email_sender,
        password=config.email_password,
        receivers=config.email_receivers,
        sender_name=config.email_sender_name,
    )


def _print_outcome(outcome: CycleOutcome) -> None:
    if outcome.error:
        print(f"[ERROR] {outcome.error}")
        return

    if outcome.result is None:
        print("[ERROR] 未获取到执行结果")
        return

    if outcome.result.status == "bootstrap":
        if outcome.result.recovered_from_corruption:
            print(f"[BOOTSTRAP] 状态文件损坏已恢复，重建基线（{len(outcome.result.current_model_ids)} 个模型）。")
        else:
            print(f"[BOOTSTRAP] 已建立基线，共 {len(outcome.result.current_model_ids)} 个模型。")
        return

    if outcome.result.status == "no_change":
        print(f"[OK] 无新增模型（当前 {len(outcome.result.current_model_ids)} 个）。")
        return

    print(f"[NEW] 发现 {len(outcome.result.new_model_ids)} 个新模型：")
    for model_id in outcome.result.new_model_ids:
        print(f"- {model_id}")

    if outcome.email_sent:
        print("[INFO] 邮件通知已发送。")
    else:
        print("[WARN] 邮件通知未发送（可能未配置或发送失败）。")


def main(argv: list[str] | None = None) -> int:
    base_config = load_config()
    parser = _build_parser(base_config)
    args = parser.parse_args(argv)
    runtime_config = _build_runtime_config(args, base_config)

    notifier = _build_notifier(runtime_config)

    if args.loop:
        return run_loop(config=runtime_config, notifier=notifier)

    outcome = run_single_cycle(config=runtime_config, notifier=notifier)
    _print_outcome(outcome)
    return outcome.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
