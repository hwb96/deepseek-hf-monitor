from __future__ import annotations

import smtplib
from dataclasses import dataclass
from datetime import datetime
from email.header import Header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr

SMTP_CONFIGS = {
    "qq.com": {"server": "smtp.qq.com", "port": 465, "ssl": True},
    "foxmail.com": {"server": "smtp.qq.com", "port": 465, "ssl": True},
    "163.com": {"server": "smtp.163.com", "port": 465, "ssl": True},
    "126.com": {"server": "smtp.126.com", "port": 465, "ssl": True},
    "gmail.com": {"server": "smtp.gmail.com", "port": 587, "ssl": False},
    "outlook.com": {"server": "smtp-mail.outlook.com", "port": 587, "ssl": False},
    "hotmail.com": {"server": "smtp-mail.outlook.com", "port": 587, "ssl": False},
    "live.com": {"server": "smtp-mail.outlook.com", "port": 587, "ssl": False},
    "sina.com": {"server": "smtp.sina.com", "port": 465, "ssl": True},
    "sohu.com": {"server": "smtp.sohu.com", "port": 465, "ssl": True},
    "aliyun.com": {"server": "smtp.aliyun.com", "port": 465, "ssl": True},
    "139.com": {"server": "smtp.139.com", "port": 465, "ssl": True},
}


@dataclass(frozen=True)
class SmtpConfig:
    server: str
    port: int
    use_ssl: bool


def resolve_smtp_config(sender: str) -> SmtpConfig:
    domain = sender.split("@")[-1].lower().strip()
    cfg = SMTP_CONFIGS.get(domain)
    if cfg:
        return SmtpConfig(server=str(cfg["server"]), port=int(cfg["port"]), use_ssl=bool(cfg["ssl"]))
    return SmtpConfig(server=f"smtp.{domain}", port=465, use_ssl=True)


class EmailNotifier:
    def __init__(
        self,
        *,
        sender: str,
        password: str,
        receivers: list[str],
        sender_name: str = "deepseek-hf-monitor",
    ) -> None:
        self.sender = sender
        self.password = password
        self.receivers = receivers
        self.sender_name = sender_name

    @property
    def enabled(self) -> bool:
        return bool(self.sender and self.password and self.receivers)

    def send_new_models(self, author: str, new_model_ids: list[str]) -> bool:
        if not self.enabled:
            return False

        today = datetime.now().strftime("%Y-%m-%d")
        subject = f"[deepseek-hf-monitor] {author} 新模型提醒 ({len(new_model_ids)}) - {today}"
        lines = [
            f"监控组织: {author}",
            "",
            "发现新增模型:",
        ]
        for model_id in new_model_ids:
            lines.append(f"- {model_id} (https://huggingface.co/{model_id})")
        lines.extend([
            "",
            f"组织主页: https://huggingface.co/{author}",
        ])
        body = "\n".join(lines)
        return self.send_email(subject=subject, body=body)

    def send_email(self, *, subject: str, body: str) -> bool:
        if not self.enabled:
            return False

        msg = MIMEMultipart("alternative")
        msg["Subject"] = Header(subject, "utf-8")
        msg["From"] = formataddr((self.sender_name, self.sender))
        msg["To"] = ", ".join(self.receivers)

        msg.attach(MIMEText(body, "plain", "utf-8"))
        html = body.replace("\n", "<br>")
        msg.attach(MIMEText(f"<html><body>{html}</body></html>", "html", "utf-8"))

        smtp_cfg = resolve_smtp_config(self.sender)

        try:
            if smtp_cfg.use_ssl:
                server = smtplib.SMTP_SSL(smtp_cfg.server, smtp_cfg.port, timeout=30)
            else:
                server = smtplib.SMTP(smtp_cfg.server, smtp_cfg.port, timeout=30)
                server.starttls()

            server.login(self.sender, self.password)
            server.send_message(msg)
            server.quit()
            return True
        except Exception:
            return False
