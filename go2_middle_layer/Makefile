# GO2 Middle Layer - Makefile
# Requires: server running on port 8001 for MCP tests (except test-yolo)

PYTHON ?= python
PORT ?= 8001
TEST_URL ?= http://localhost:$(PORT)

.PHONY: help run run-bg kill-server test test-all test-sport test-sport-state \
	test-rpc-cam test-depth-cam test-local-cam test-speaker test-audio-capture \
	test-yolo run-sport run-sport-state run-rpc-cam run-depth-cam run-local-cam \
	run-speaker run-audio-capture run-yolo lint format clean install download-audio

help:
	@echo "GO2 Middle Layer - Available targets:"
	@echo ""
	@echo "  Server:"
	@echo "    run          - Run server (foreground, port $(PORT))"
	@echo "    run-bg       - Run server in background"
	@echo "    kill-server  - Kill process on port $(PORT)"
	@echo ""
	@echo "  Tests via pytest (server on port $(PORT) except test-yolo):"
	@echo "    test / test-all     - Run all tests"
	@echo "    test-sport          - Sport MCP tools"
	@echo "    test-sport-state    - Sport state"
	@echo "    test-rpc-cam        - RPC camera"
	@echo "    test-depth-cam      - Depth camera"
	@echo "    test-local-cam      - Local camera"
	@echo "    test-speaker        - Speaker/TTS"
	@echo "    test-audio-capture  - Audio capture"
	@echo "    test-yolo           - YOLO detector (no server)"
	@echo ""
	@echo "  Run tests as scripts (run-*):"
	@echo "    run-sport, run-sport-state, run-rpc-cam, run-depth-cam,"
	@echo "    run-local-cam, run-speaker, run-audio-capture, run-yolo"
	@echo ""
	@echo "  Code quality:"
	@echo "    lint         - Run ruff check"
	@echo "    format       - Run black + ruff format"
	@echo ""
	@echo "  Setup:"
	@echo "    install      - Install dependencies + pytest"
	@echo "    download-audio - Download pre-recorded WAV files for speaker"
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
# Tests (requires running server on port $(PORT) except test-yolo)
# Run from project root so src/ is importable
# -----------------------------------------------------------------------------
test test-all:
	$(PYTHON) -m pytest tests/ -v

test-sport:
	$(PYTHON) -m pytest tests/test_sport_mcp_tools.py -v

test-sport-state:
	$(PYTHON) -m pytest tests/test_sport_state.py -v

test-rpc-cam:
	$(PYTHON) -m pytest tests/test_rpc_cam_mcp_tools.py -v

test-depth-cam:
	$(PYTHON) -m pytest tests/test_depth_cam_mcp_tools.py -v

test-local-cam:
	$(PYTHON) -m pytest tests/test_local_cam_mcp_tools.py -v

test-speaker:
	$(PYTHON) -m pytest tests/test_speaker_mcp_tools.py -v

test-audio-capture:
	$(PYTHON) -m pytest tests/test_audio_capture_mcp_tools.py -v

test-yolo:
	$(PYTHON) -m pytest tests/test_yolo.py -v

# Run test files directly (scripts with __main__, no pytest)
run-sport:
	cd tests && $(PYTHON) test_sport_mcp_tools.py

run-sport-state:
	cd tests && $(PYTHON) test_sport_state.py

run-rpc-cam:
	cd tests && $(PYTHON) test_rpc_cam_mcp_tools.py

run-depth-cam:
	cd tests && $(PYTHON) test_depth_cam_mcp_tools.py

run-local-cam:
	cd tests && $(PYTHON) test_local_cam_mcp_tools.py

run-speaker:
	cd tests && $(PYTHON) test_speaker_mcp_tools.py

run-audio-capture:
	cd tests && $(PYTHON) test_audio_capture_mcp_tools.py

run-yolo:
	cd tests && $(PYTHON) test_yolo.py

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
install:
	pip install -r src/requirements.txt
	pip install pytest pytest-asyncio

download-audio:
	$(PYTHON) scripts/download_recorded_audio.py

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@echo "Cleaned cache files"
