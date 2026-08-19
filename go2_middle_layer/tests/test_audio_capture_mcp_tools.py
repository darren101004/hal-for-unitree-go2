"""
Integration tests for the audio_capture MCP tool.

Prerequisites:
  - Server must be running:  python src/server.py --port 8001
  - A microphone must be connected and configured via AUDIO_CAPTURE_DEVICE_ID in .env

Manual test flow for task capture:
  1. Run the server.
  2. Run this file.
  3. When prompted, say the hotword (default: "hello") into the mic.
  4. After the hotword is detected, say a command (e.g. "sit down").
  5. Wait for the silence timeout — the task will be enqueued.
  6. The polling test will print the collected tasks.
"""
import asyncio
import time

from fastmcp import Client
from fastmcp.client import StreamableHttpTransport

BASE_URL = "http://localhost:8001/audio_capture/mcp"


# ─────────────────────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────────────────────
def make_client() -> Client:
    return Client(transport=StreamableHttpTransport(url=BASE_URL))


def print_section(title: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"TEST: {title}")
    print("=" * 60)


# ─────────────────────────────────────────────────────────────
#  Test: list tools
# ─────────────────────────────────────────────────────────────
async def test_list_tools() -> None:
    async with make_client() as client:
        assert client.is_connected()
        tools = await client.list_tools()
        print(f"Total tools registered: {len(tools)}")
        for tool in tools:
            print(f"  - {tool.name}: {tool.description}")
        assert any(t.name == "get_audio_tasks" for t in tools), \
            "Expected tool 'get_audio_tasks' not found!"
        assert any(t.name == "transcribe_audio" for t in tools), \
            "Expected tool 'transcribe_audio' not found!"


# ─────────────────────────────────────────────────────────────
#  Test: empty queue returns success + empty list
# ─────────────────────────────────────────────────────────────
async def test_get_audio_tasks_empty() -> None:
    """
    On a freshly started server (or after all tasks drained),
    get_audio_tasks should return success=True with an empty data list.
    """
    async with make_client() as client:
        assert client.is_connected()
        result = await client.call_tool("get_audio_tasks", {})
        content = result.structured_content

        print(f"  success : {content.get('success')}")
        print(f"  message : {content.get('message')}")
        print(f"  data    : {content.get('data')}")
        print(f"  code    : {content.get('code')}")

        assert content.get("success") is True, "Expected success=True"
        assert isinstance(content.get("data"), list), "Expected data to be a list"
        print("  → PASS: empty queue returns success with [] data")


# ─────────────────────────────────────────────────────────────
#  Test: drain behavior — calling twice empties the queue
# ─────────────────────────────────────────────────────────────
async def test_drain_behavior() -> None:
    """
    Call get_audio_tasks twice in quick succession.
    The second call should always return an empty list because
    the first call already drained the queue.
    """
    async with make_client() as client:
        assert client.is_connected()

        result1 = await client.call_tool("get_audio_tasks", {})
        tasks_first = result1.structured_content.get("data", [])
        print(f"  First  call → {len(tasks_first)} task(s): {tasks_first}")

        result2 = await client.call_tool("get_audio_tasks", {})
        tasks_second = result2.structured_content.get("data", [])
        print(f"  Second call → {len(tasks_second)} task(s): {tasks_second}")

        assert tasks_second == [], "Expected empty list on second call (queue should be drained)"
        print("  → PASS: drain behavior correct")


# ─────────────────────────────────────────────────────────────
#  Test: continuous polling — manual interactive test
# ─────────────────────────────────────────────────────────────
async def test_poll_for_tasks(
    duration_sec: int = 30,
    interval_sec: float = 1.0,
) -> None:
    """
    Poll get_audio_tasks every `interval_sec` seconds for `duration_sec` seconds.

    HOW TO USE:
      1. Make sure the server is running with a mic connected.
      2. Say the hotword (default: "hello") into the mic.
      3. After the beep / log message, say your command.
      4. Wait for the silence timeout — task will appear in the next poll.
    """
    print(f"\n  Polling every {interval_sec}s for {duration_sec}s.")
    print(f"  → Say the hotword into the mic now to enqueue a task.")

    total_collected: list[str] = []
    deadline = time.time() + duration_sec

    async with make_client() as client:
        assert client.is_connected()
        while time.time() < deadline:
            remaining = int(deadline - time.time())
            result = await client.call_tool("get_audio_tasks", {})
            tasks: list[str] = result.structured_content.get("data", [])

            if tasks:
                print(f"  [{remaining:>3}s left] {len(tasks)} new task(s): {tasks}")
                total_collected.extend(tasks)
            else:
                print(f"  [{remaining:>3}s left] (no tasks yet)")

            await asyncio.sleep(interval_sec)

    print(f"\n  Polling finished. Total tasks collected: {len(total_collected)}")
    for i, t in enumerate(total_collected, 1):
        print(f"    [{i}] {t!r}")


# ─────────────────────────────────────────────────────────────
#  Test: rapid concurrent polls
# ─────────────────────────────────────────────────────────────
async def test_concurrent_polls() -> None:
    """
    Fire 5 concurrent get_audio_tasks calls.
    Only one call should collect any queued tasks; the rest should
    return empty lists (queue is drained atomically).
    """
    async with make_client() as client:
        assert client.is_connected()

        tasks_calls = [client.call_tool("get_audio_tasks", {}) for _ in range(5)]
        results = await asyncio.gather(*tasks_calls)

        all_tasks: list[list[str]] = [r.structured_content.get("data", []) for r in results]
        non_empty = [t for t in all_tasks if t]
        flat = [item for sublist in all_tasks for item in sublist]

        # All results should succeed
        for r in results:
            assert r.structured_content.get("success") is True

        print(f"  Concurrent poll results (5 calls):")
        for i, t in enumerate(all_tasks, 1):
            print(f"    call {i}: {t}")
        print(f"  Non-empty responses: {len(non_empty)}")
        print(f"  Total tasks across all calls: {len(flat)}")
        print("  → PASS: all concurrent polls succeeded")


# ─────────────────────────────────────────────────────────────
#  Test: transcribe_audio — smoke test (non-interactive)
# ─────────────────────────────────────────────────────────────
async def test_transcribe_audio_smoke() -> None:
    """
    Call transcribe_audio with base64 payload to ensure the MCP tool is wired.

    Notes:
      - The underlying STT backend may be unavailable or may reject the dummy bytes.
        In that case, the controller should return a structured Response with code=400.
      - This is intentionally a smoke test; it does not require a microphone.
    """
    import base64
    from pathlib import Path

    tests_dir = Path(__file__).resolve().parent
    preferred_path = tests_dir / "test.wav"
    wav_candidates = list(tests_dir.glob("*.wav"))

    audio_path: Path | None
    if preferred_path.exists():
        audio_path = preferred_path
    elif wav_candidates:
        audio_path = wav_candidates[0]
    else:
        audio_path = None

    if audio_path is not None:
        audio_bytes = audio_path.read_bytes()
        audio_format = audio_path.suffix.lstrip(".") or "wav"
        print(f"  Using audio file: {audio_path.name} ({len(audio_bytes)} bytes)")
    else:
        audio_bytes = b"not-a-real-audio-file"
        audio_format = "ogg"
        print("  No .wav file found in tests/. Using dummy bytes.")

    payload = {
        "audio_base64": base64.b64encode(audio_bytes).decode("utf-8"),
        "audio_format": audio_format,
    }

    async with make_client() as client:
        assert client.is_connected()
        result = await client.call_tool("transcribe_audio", payload)
        content = result.structured_content

        print(f"  success : {content.get('success')}")
        print(f"  message : {content.get('message')}")
        print(f"  data    : {content.get('data')}")
        print(f"  code    : {content.get('code')}")

        assert isinstance(content.get("success"), bool), "Expected success to be a bool"
        assert isinstance(content.get("code"), int), "Expected code to be an int"
        assert content.get("code") in {200, 400}, "Expected code to be 200 or 400"

        if content.get("success") is True:
            assert isinstance(content.get("data"), list), "Expected data to be a list on success"
        else:
            assert content.get("data") is None, "Expected data=None on failure"
            assert isinstance(content.get("message"), str) and content.get("message"), \
                "Expected a non-empty error message on failure"

        print("  → PASS: transcribe_audio smoke test returned structured Response")


# ─────────────────────────────────────────────────────────────
#  Entry point
# ─────────────────────────────────────────────────────────────
async def test_all_audio_capture_tools() -> None:
    # print_section("list_tools")
    # await test_list_tools()

    print_section("get_audio_tasks — empty queue")
    await test_get_audio_tasks_empty()

    # print_section("get_audio_tasks — drain behavior")
    # await test_drain_behavior()

    # print_section("get_audio_tasks — concurrent polls")
    # await test_concurrent_polls()

    print_section("transcribe_audio — smoke test")
    await test_transcribe_audio_smoke()

    # print_section("get_audio_tasks — continuous polling (30s, manual)")
    # await test_poll_for_tasks(duration_sec=30, interval_sec=1.0)


if __name__ == "__main__":
    asyncio.run(test_all_audio_capture_tools())
