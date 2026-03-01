from __future__ import annotations

from deepseek_hf_monitor.emailer import EmailNotifier, resolve_smtp_config


class _FakeSMTPBase:
    def __init__(self) -> None:
        self.logged_in = None
        self.sent = False
        self.tls_started = False
        self.closed = False

    def login(self, sender: str, password: str) -> None:
        self.logged_in = (sender, password)

    def send_message(self, _msg: object) -> None:
        self.sent = True

    def quit(self) -> None:
        self.closed = True


class _FakeSMTPSSL(_FakeSMTPBase):
    def __init__(self, server: str, port: int, timeout: int) -> None:
        super().__init__()
        self.server = server
        self.port = port
        self.timeout = timeout


class _FakeSMTP(_FakeSMTPBase):
    def __init__(self, server: str, port: int, timeout: int) -> None:
        super().__init__()
        self.server = server
        self.port = port
        self.timeout = timeout

    def starttls(self) -> None:
        self.tls_started = True


def test_resolve_smtp_config_known_domain() -> None:
    cfg = resolve_smtp_config("user@qq.com")
    assert cfg.server == "smtp.qq.com"
    assert cfg.port == 465
    assert cfg.use_ssl is True


def test_resolve_smtp_config_unknown_domain_fallback() -> None:
    cfg = resolve_smtp_config("user@example.org")
    assert cfg.server == "smtp.example.org"
    assert cfg.port == 465
    assert cfg.use_ssl is True


def test_send_new_models_uses_configured_sender(monkeypatch) -> None:
    smtp_instances: list[_FakeSMTPSSL] = []

    def _fake_ssl(server: str, port: int, timeout: int) -> _FakeSMTPSSL:
        inst = _FakeSMTPSSL(server, port, timeout)
        smtp_instances.append(inst)
        return inst

    monkeypatch.setattr("deepseek_hf_monitor.emailer.smtplib.SMTP_SSL", _fake_ssl)

    notifier = EmailNotifier(
        sender="sender@qq.com",
        password="pwd",
        receivers=["a@example.com"],
        sender_name="Monitor Bot",
    )

    ok = notifier.send_new_models(
        author="deepseek-ai",
        new_model_ids=["deepseek-ai/DeepSeek-V4"],
    )

    assert ok is True
    assert len(smtp_instances) == 1
    assert smtp_instances[0].logged_in == ("sender@qq.com", "pwd")
    assert smtp_instances[0].sent is True
