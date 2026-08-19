import logging

from fastmcp import FastMCP

from models.response import Response
from usecases.audio_capture_controller import AudioCaptureController

logger = logging.getLogger("MCP:AudioCapture")

audio_capture_controller = AudioCaptureController()
mcp = FastMCP("audio_capture")


@mcp.tool(
    description=(
        "Return all voice tasks collected from the microphone since the last call. "
        "Each task is a command spoken by the user after the hotword trigger. "
        "The queue is drained on each call (tasks are consumed)."
    )
)
def get_audio_tasks() -> Response:
    return audio_capture_controller.get_pending_tasks()


@mcp.tool(
    description=(
        "Transcribe an audio file (e.g. voice message from Telegram). "
        "Accepts base64-encoded audio data and format hint. "
        "Transcribed text is appended to the task queue (retrievable via get_audio_tasks). "
        "Supported formats: ogg, wav, mp3, flac, webm. "
        "Returns an error response (code 504) if transcription does not complete within the timeout. "
        "When check_hotword=true, the response includes extra_data.hotword_detected (bool) "
        "indicating whether the transcribed text contains a configured hotword."
    )
)
async def transcribe_audio(
    audio_base64: str, audio_format: str = "ogg", check_hotword: bool = False
) -> Response:
    import base64

    audio_data = base64.b64decode(audio_base64)
    return await audio_capture_controller.transcribe_audio(
        audio_data, audio_format, check_hotword=check_hotword
    )


def start_audio_background_capture() -> None:
    return audio_capture_controller.start_background_capture()


def stop_audio_background_capture() -> None:
    return audio_capture_controller.stop_background_capture()


if __name__ == "__main__":
    mcp.run()
