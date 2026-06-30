.PHONY: install test status audit upload clean
install:
	pip install -r requirements.txt && python -m playwright install chromium
test:
	python3 -m pytest tests/ -q
status:
	cd agent-harness/cli_anything && python3 -m auto_youtube.auto_youtube_cli status
audit:
	cd agent-harness/cli_anything && python3 -m auto_youtube.auto_youtube_cli audit-studio
clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null; true
