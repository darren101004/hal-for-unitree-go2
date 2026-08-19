---
name: go2-audio-capture-mcp
description: Use the GO2 robot audio capture MCP to capture voice commands via microphone. Use when the user wants voice control—listen for hotword triggers and transcribe spoken commands (ASR).
---

# GO2 Audio Capture MCP Skill

Use this skill when working with the GO2 middle layer audio capture endpoint to capture voice commands from the microphone. The service uses hotword detection and Vosk ASR to transcribe spoken commands into text tasks.

## Endpoint

| Environment | URL |
|-------------|-----|
| Local | `http://localhost:8001/audio_capture/mcp` |
| Robot network | `http://172.168.20.189:8001/audio_capture/mcp` |

**MCP protocol:** HTTP POST with JSON-RPC. Client must accept `application/json` and `text/event-stream` in the `Accept` header.

## Tools

| Tool | Parameters | Description |
|------|-------------|-------------|
| `get_audio_tasks` | none | Return all voice tasks collected since the last call. Each task is a command spoken after the hotword or transcribed from external audio. The queue is drained on each call. |
| `transcribe_audio` | `audio_base64` (str, required), `audio_format` (str, default `"ogg"`) | Transcribe an external audio file (e.g. Telegram voice message). Accepts base64-encoded audio data. Transcribed text is appended to the task queue. Supported formats: ogg, wav, mp3, flac, webm. |
| `start_audio_background_capture` | none | Start the background audio capture loop (hotword detection + ASR) |
| `stop_audio_background_capture` | none | Stop the background audio capture loop |

## Response Format

`get_audio_tasks` returns a `Response` object:

```json
{
  "success": true,
  "message": "N pending task(s) retrieved.",
  "data": ["command1", "command2"],
  "code": 200,
  "extra_data": null
}
```

`transcribe_audio` returns a `Response` object:

```json
{
  "success": true,
  "message": "N sentence(s) transcribed.",
  "data": ["sentence1", "sentence2"],
  "code": 200,
  "extra_data": null
}
```

- `data` — list of transcribed command/sentence strings (empty list when no new tasks)
- `code: 200` — Success
- `code: 400` — Transcription failed (bad format, decode error, etc.)
- `code: 503` — Audio capture service unavailable (no microphone or Vosk not available)

## Usage Flow

### Microphone capture (hotword-based)

1. Call `start_audio_background_capture` to begin listening.
2. User says hotword (e.g. "hello"), then speaks a command.
3. Call `get_audio_tasks` to drain and retrieve pending commands.
4. Call `stop_audio_background_capture` when done.

### External audio transcription (e.g. Telegram voice)

1. Base64-encode the audio file (OGG, WAV, MP3, etc.).
2. Call `transcribe_audio` with the base64 string and format hint.
3. Transcribed sentences are returned immediately and also appended to the task queue.
4. Optionally call `get_audio_tasks` later to retrieve accumulated tasks.

> **Note:** `transcribe_audio` does not require a microphone — it only needs the Vosk model. It works even when mic initialization has failed.

## Configuration (Environment)

| Variable | Default | Description |
|----------|---------|-------------|
| `AUDIO_CAPTURE_DEVICE_ID` | `None` | Microphone device ID (system default if unset) |
| `AUDIO_CAPTURE_HOTWORDS` | `hello` | Comma-separated hotword(s) to trigger listening |
| `AUDIO_CAPTURE_PATIENCE` | `3` | Seconds of silence before ending a command session |
| `AUDIO_CAPTURE_MODEL_ID` | `vosk-model-small-en-us-0.15` | Vosk ASR model name |
| `AUDIO_CAPTURE_SAMPLE_RATE` | `16000` | Microphone sample rate in Hz |
| `AUDIO_CAPTURE_CHANNELS` | `1` | Microphone channel count |

## Service Availability

Check `GET /status` — `audio_capture` must be `available: true`. If `false`, the service uses a stub and returns empty tasks.

## Health Check

Verify the server is running: `GET http://localhost:8001/health` → `{"message": "OK"}`
