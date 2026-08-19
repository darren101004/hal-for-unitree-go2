import logging

from fastmcp import FastMCP

from impl.speaker.models import RecordedAudio
from models.response import Response
from usecases.speaker_controller import SpeakerController

logger = logging.getLogger("MCP:Speaker")

mcp = FastMCP("speaker")

speaker_controller = SpeakerController()


@mcp.tool(
    description="Speak the given text out loud using TTS (text-to-speech). The robot will convert the text into speech and play it through its speaker. Set interrupt=True to stop any currently playing audio before speaking."
)
async def speak_text(text: str, interrupt: bool = False) -> Response:
    return await speaker_controller.speak_text(text, interrupt=interrupt)


@mcp.tool(
    description="Play a pre-recorded audio clip through the robot's speaker. Available clips: bark, happy, sad, alert, greeting, goodbye, acknowledge, error, confused. Set times=N to play the clip N times. Set interrupt=True to stop any currently playing audio before playing."
)
async def recorded_audio_speak(
    audio_name: RecordedAudio, times: int = 1, interrupt: bool = False
) -> Response:
    return await speaker_controller.play_recorded_audio(
        audio_name, times=times, interrupt=interrupt
    )


@mcp.tool(description="Stop all currently playing audio immediately.")
async def stop_speaking() -> Response:
    return await speaker_controller.interrupt()


def start_speaker_service() -> None:
    """Force lazy DI instantiation so the speaker service registers its availability."""
    speaker_controller.warm_up()


if __name__ == "__main__":
    mcp.run()
