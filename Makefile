.PHONY: install test run run-loop docker-up docker-down docker-logs

install:
	uv sync --group dev

test:
	uv run pytest -q

run:
	uv run deepseek-monitor

run-loop:
	uv run deepseek-monitor --loop

docker-up:
	docker compose up -d --build

docker-down:
	docker compose down

docker-logs:
	docker compose logs -f monitor
