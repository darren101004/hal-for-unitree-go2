---
name: go2-speaker-mcp
description: Use the GO2 robot speaker MCP to make the robot speak, play pre-recorded audio, or stop speaking. Use when the user wants the robot to say something, bark, play a sound, greet, say goodbye, or stop talking.
---

# GO2 Speaker MCP Skill

Use this skill when working with the GO2 middle layer speaker endpoint to control the robot's text-to-speech (TTS) and pre-recorded audio playback.

## Endpoint

| Environment | URL |
|-------------|-----|
| Local | `http://localhost:8001/speaker/mcp` |
| Robot network | `http://172.168.20.189:8001/speaker/mcp` |

**MCP protocol:** HTTP POST with JSON-RPC. Client must accept `application/json` and `text/event-stream` in the `Accept` header.

## Tools

| Tool | Parameters | Description |
|------|-------------|-------------|
| `speak_text` | `text: str`, `interrupt: bool` (default `false`) | Speak the given text aloud using TTS. Set `interrupt=true` to stop current audio first |
| `recorded_audio_speak` | `audio_name: str`, `interrupt: bool` (default `false`) | Play a pre-recorded clip. Values: `bark`, `happy`, `sad`, `alert`, `greeting`, `goodbye`, `acknowledge`, `error`, `confused` |
| `stop_speaking` | none | Stop all currently playing audio immediately |

## Response Format

All tools return a `Response` object:

```json
{
  "success": true,
  "message": "...",
  "data": null,
  "code": 200,
  "extra_data": null
}
```

- `code: 200` — Success
- `code: 400` — Client error (e.g. invalid audio name, empty text)
- `code: 425` — Not ready (e.g. TTS engine unavailable)

## Usage Examples

| User intent | Tool call |
|-------------|-----------|
| "Say hello" | `speak_text(text="Hello!")` |
| "Bark!" | `recorded_audio_speak(audio_name="bark")` |
| "Stop talking" | `stop_speaking()` |
| "Say goodbye and wave" | `speak_text(text="Goodbye!")` then use go2-sport tools |
| "Interrupt and say urgent" | `speak_text(text="Urgent!", interrupt=true)` |
| "Play greeting sound" | `recorded_audio_speak(audio_name="greeting")` |

## Configuration (Environment)

| Variable | Default | Description |
|----------|---------|-------------|
| `SPEAKER_TTS_ENGINE` | `openai` | TTS engine: `openai` or `piper` |
| `OPENAI_API_KEY` | — | Required for OpenAI TTS |
| `TTS_MODEL` | `gpt-4o-mini-tts` | OpenAI TTS model |
| `TTS_VOICE` | `coral` | OpenAI voice name |
| `SPEAKER_AUDIO_DIR` | `resources/sound/dog` | Directory for pre-recorded `.wav` files |

## Downloading Audio Files

Run `python scripts/download_recorded_audio.py` (requires py7zr) or `make download-audio`. Extracts from OpenGameArt dog.7z pack. Use `--force` to replace, `--fallback` if py7zr unavailable.

## Health Check

Verify the server is running: `GET http://localhost:8001/health` → `{"message": "OK"}`
