# deepseek-hf-monitor

![Python](https://img.shields.io/badge/Python-3.11%2B-blue)
![License](https://img.shields.io/badge/License-MIT-green.svg)
![uv](https://img.shields.io/badge/Package%20Manager-uv-7c3aed)

一键监控 DeepSeek 是否发新模型。这是一款 Hugging Face 模型更新监控工具，支持多组织订阅、邮件实时告警、Docker 一键部署。

## Features

- 增量监控：首次建立基线，后续只对新增模型告警
- 邮件通知：内置 SMTP 自动识别（QQ/163/Gmail/Outlook 等）
- 配置优先级：环境变量 > 本项目 `.env` > `EXTERNAL_ENV_FILE`
- 容器化运行：`docker compose` 常驻守护 + 自动重启
- 健康检查：heartbeat 文件用于容器探活

## Quick Start (Local)

```bash
cp .env.example .env
# 填写 EMAIL_SENDER / EMAIL_PASSWORD / EMAIL_RECEIVERS（可选）

uv sync --group dev
uv run deepseek-monitor
```

首次运行会建立基线（不报警）：

```text
[BOOTSTRAP] 已建立基线，共 N 个模型。
```

后续发现新增：

```text
[NEW] 发现 1 个新模型：
- deepseek-ai/DeepSeek-XXXX
[INFO] 邮件通知已发送。
```

## Run as Daemon

```bash
uv run deepseek-monitor --loop --interval-seconds 1800
```

## Docker Compose

```bash
cp .env.example .env
# 填写你的配置

docker compose up -d --build
docker compose logs -f monitor
```

停止：

```bash
docker compose down
```

## Reuse existing email config from another project

如果你已有另一个项目 `.env`（例如含 `EMAIL_SENDER` 等变量），可在本项目 `.env` 中设置：

```bash
EXTERNAL_ENV_FILE=/run/external/external.env
```

再在 `docker-compose.yml` 挂载该文件（示例已注释）。

## Environment Variables

| 变量 | 默认值 | 说明 |
|---|---|---|
| `HF_AUTHOR` | `deepseek-ai` | 监控的 Hugging Face 组织 |
| `HF_LIMIT` | `100` | 每次拉取模型数量上限 |
| `CONTAINS` | 空 | 仅保留模型 ID 包含该关键词 |
| `CHECK_INTERVAL_SECONDS` | `1800` | 循环模式检查间隔（秒） |
| `BOOTSTRAP_IF_MISSING` | `true` | 状态文件不存在时建立基线 |
| `STATE_FILE` | `state/models.json` | 状态文件路径 |
| `HEARTBEAT_FILE` | `state/heartbeat.json` | 心跳文件路径 |
| `EXTERNAL_ENV_FILE` | 空 | 外部 `.env`（最低优先级） |
| `EMAIL_SENDER` | 空 | 发件人邮箱 |
| `EMAIL_PASSWORD` | 空 | 邮箱授权码/密码 |
| `EMAIL_RECEIVERS` | 空 | 收件人（逗号分隔，留空默认发给发件人） |
| `EMAIL_SENDER_NAME` | `deepseek-hf-monitor` | 发件人名称 |
| `HEALTHCHECK_MAX_AGE_SECONDS` | `CHECK_INTERVAL_SECONDS*2+60` | 心跳最大年龄阈值 |

## CLI

```bash
# 单次检查
uv run deepseek-monitor

# 指定组织
uv run deepseek-monitor --author deepseek-ai

# 循环模式
uv run deepseek-monitor --loop --interval-seconds 1800

# 指定状态文件
uv run deepseek-monitor --state-file state/models.json

# 指定关键词过滤
uv run deepseek-monitor --contains v4
```

## Exit Codes

- `0`: 正常（建立基线或无新增）
- `2`: 发现新增模型（单次模式）
- `1`: 执行失败（例如网络错误）

## Development

```bash
make install
make test
make run
make run-loop
```

## Troubleshooting

- 邮件未发送：检查 `EMAIL_SENDER`、`EMAIL_PASSWORD`、`EMAIL_RECEIVERS`
- 容器 unhealthy：检查 `state/heartbeat.json` 是否持续更新
- 无法读取外部 env：确认挂载路径与 `EXTERNAL_ENV_FILE` 一致

## License

MIT
