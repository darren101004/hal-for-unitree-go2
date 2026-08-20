# GO2 Sport Control - Makefile
# Requires: server running on port 8001 for MCP tests

PYTHON ?= python
PORT ?= 8001
TEST_URL ?= http://localhost:$(PORT)

.PHONY: help run run-bg kill-server test test-all test-sport test-sport-state \
	run-sport run-sport-state lint format clean install

help:
	@echo "GO2 Sport Control - Available targets:"
	@echo ""
	@echo "  Server:"
	@echo "    run          - Run server (foreground, port $(PORT))"
	@echo "    run-bg       - Run server in background"
	@echo "    kill-server  - Kill process on port $(PORT)"
	@echo ""
	@echo "  Tests via pytest (server must be running on port $(PORT)):"
	@echo "    test / test-all     - Run all tests"
	@echo "    test-sport          - Sport MCP tools"
	@echo "    test-sport-state    - Sport state"
	@echo ""
	@echo "  Run tests as scripts (run-*):"
	@echo "    run-sport, run-sport-state"
	@echo ""
	@echo "  Code quality:"
	@echo "    lint         - Run ruff check"
	@echo "    format       - Run black + ruff format"
	@echo ""
	@echo "  Setup:"
	@echo "    install      - Install Python dependencies"
	@echo "    clean        - Remove __pycache__, .pytest_cache"

# -----------------------------------------------------------------------------
# Server
# -----------------------------------------------------------------------------
run:
	$(PYTHON) src/server.py --port $(PORT)

run-bg:
	$(PYTHON) src/server.py --port $(PORT) &
	@echo "Server started in background. Use 'make kill-server' to stop."

kill-server:
	@lsof -ti :$(PORT) | xargs kill -9 2>/dev/null && echo "Killed process on port $(PORT)" || echo "No process on port $(PORT)"

# -----------------------------------------------------------------------------
# Tests (requires running server on port $(PORT))
# Run from project root so src/ is importable
# -----------------------------------------------------------------------------
test test-all:
	$(PYTHON) -m pytest tests/ -v

test-sport:
	$(PYTHON) -m pytest tests/test_sport_mcp_tools.py -v

test-sport-state:
	$(PYTHON) -m pytest tests/test_sport_state.py -v

# Run test files directly (scripts with __main__, no pytest)
run-sport:
	cd tests && $(PYTHON) test_sport_mcp_tools.py

run-sport-state:
	cd tests && $(PYTHON) test_sport_state.py

# -----------------------------------------------------------------------------
# Code quality
# -----------------------------------------------------------------------------
lint:
	ruff check src/

format:
	black src/
	ruff check src/ --fix

# -----------------------------------------------------------------------------
# Setup
# -----------------------------------------------------------------------------
# NOTE: unitree_sdk2_python and the CycloneDDS C library are NOT installed here.
# See README.md — they need CYCLONEDDS_HOME and a source build.
install:
	pip install -r src/requirements.txt

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@echo "Cleaned cache files"
