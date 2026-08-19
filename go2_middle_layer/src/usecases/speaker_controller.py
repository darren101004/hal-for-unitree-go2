import logging
import os

from dependency_injector.wiring import Provide, inject

from dependencies import Go2MiddleLayerContainer
from impl.speaker.models import RecordedAudio
from interfaces.speaker import SpeakerService
from models.response import Response
import service_registry

logger = logging.getLogger("UseCase:SpeakerController")


class SpeakerController:

    @inject
    async def speak_text(
        self,
        text: str,
        interrupt: bool = False,
        speaker_service: SpeakerService = Provide[
            Go2MiddleLayerContainer.speaker_service
        ],
    ) -> Response:
        reason = service_registry.get_unavailable_reason("speaker")
        if reason:
            return Response(
                success=False,
                message=f"Speaker service not available: {reason}",
                code=503,
            )
        return await speaker_service.aspeak(text, interrupt=interrupt)

    @inject
    async def play_recorded_audio(
        self,
        audio_name: RecordedAudio,
        times: int = 1,
        interrupt: bool = False,
        speaker_service: SpeakerService = Provide[
            Go2MiddleLayerContainer.speaker_service
        ],
        audio_dir: str = Provide[Go2MiddleLayerContainer.config.speaker.audio_dir],
    ) -> Response:
        file_path = os.path.join(audio_dir, f"{audio_name.value}.wav")
        if not os.path.isfile(file_path):
            return Response(
                success=False,
                message=f"Audio file not found: {file_path}. "
                f"Valid names: {[e.value for e in RecordedAudio]}",
            )
        return await speaker_service.aplay_file(
            file_path, times=times, interrupt=interrupt
        )

    @inject
    async def interrupt(
        self,
        speaker_service: SpeakerService = Provide[
            Go2MiddleLayerContainer.speaker_service
        ],
    ) -> Response:
        speaker_service.interrupt_all_task()
        return Response(success=True, message="All speaker tasks interrupted")

    @inject
    def warm_up(
        self,
        speaker_service: SpeakerService = Provide[
            Go2MiddleLayerContainer.speaker_service
        ],
    ) -> None:
        """Force lazy DI instantiation so the service registers its availability status."""
        pass
