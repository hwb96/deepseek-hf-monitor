# Changelog

All notable changes to this project will be documented in this file.

## [0.1.0] - 2026-03-01

### Added
- Added durable Hugging Face org monitor with baseline + incremental detection.
- Added email notification module with SMTP auto-detection.
- Added dual-source env loading (local `.env` + optional `EXTERNAL_ENV_FILE`).
- Added loop mode (`--loop`, `--interval-seconds`) for daemon runtime.
- Added heartbeat writer + healthcheck command for container probes.
- Added Dockerfile and docker-compose deployment artifacts.
- Added GitHub Actions CI workflow.
- Added `.env.example`, `Makefile`, and MIT license.
