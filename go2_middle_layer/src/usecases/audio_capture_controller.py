import asyncio

from dependency_injector.wiring import Provide, inject

from dependencies import Go2MiddleLayerContainer
from interfaces.audio import AudioCaptureService
from models.response import Response
import service_registry


_audio_transcribe_semaphores: dict[int, asyncio.Semaphore] = {}


def _get_audio_transcribe_semaphore(max_concurrency: int) -> asyncio.Semaphore:
    """
    Return a process-wide semaphore to limit concurrent audio transcription.

    Args:
        max_concurrency: Maximum number of concurrent transcriptions allowed.
    """
    value = max(1, int(max_concurrency))
    sem = _audio_transcribe_semaphores.get(value)
    if sem is None:
        sem = asyncio.Semaphore(value)
        _audio_transcribe_semaphores[value] = sem
    return sem


class AudioCaptureController:

    @inject
    def get_pending_tasks(
        self,
        audio_service: AudioCaptureService = Provide[
            Go2MiddleLayerContainer.audio_capture_service
        ],
    ) -> Response:
        """
        Drain and return all voice tasks received since the last call.
        """
        reason = service_registry.get_unavailable_reason("audio_capture")
        if reason:
            return Response(
                success=False,
                message=f"Audio capture not available: {reason}",
                data=None,
                code=503,
            )

        tasks = audio_service.get_pending_tasks()
        return Response(
            success=True,
            message=f"{len(tasks)} pending task(s) retrieved.",
            data=tasks,
            code=200,
        )

    @inject
    async def transcribe_audio(
        self,
        audio_data: bytes,
        audio_format: str,
        check_hotword: bool = False,
        audio_service: AudioCaptureService = Provide[
            Go2MiddleLayerContainer.audio_capture_service
        ],
        transcribe_max_concurrency: int = Provide[
            Go2MiddleLayerContainer.config.audio_capture.transcribe_max_concurrency
        ],
    ) -> Response:
        """
        Transcribe external audio data (e.g. Telegram voice message).

        This is async to avoid blocking the MCP server event loop.
        Timeout is enforced by the active audio capture service via `TRANSCRIBE_TIMEOUT`.
        A timeout returns `code=504`.

        When check_hotword=True, the response includes extra_data with
        hotword_detected (bool) and matched_hotword (str|None).
        """
        try:
            sem = _get_audio_transcribe_semaphore(transcribe_max_concurrency)
            async with sem:
                sentences = await audio_service._transcribe_async(
                    audio_data, audio_format
                )

            extra_data = None
            if check_hotword:
                full_text = " ".join(sentences).strip()
                hotword_detected = audio_service.check_hotwords(full_text)
                extra_data = {"hotword_detected": hotword_detected}

            return Response(
                success=True,
                message=f"{len(sentences)} sentence(s) transcribed.",
                data=sentences,
                code=200,
                extra_data=extra_data,
            )
        except asyncio.TimeoutError:
            return Response(
                success=False,
                message=(
                    f"Transcription timed out after "
                    f"{audio_service.TRANSCRIBE_TIMEOUT:.0f}s. "
                    "Audio may be too long or the transcription engine is unavailable."
                ),
                data=None,
                code=504,
            )
        except Exception as e:
            return Response(
                success=False,
                message=str(e),
                data=None,
                code=400,
            )

    @inject
    def start_background_capture(
        self,
        audio_service: AudioCaptureService = Provide[
            Go2MiddleLayerContainer.audio_capture_service
        ],
    ) -> None:
        audio_service.start()

    @inject
    def stop_background_capture(
        self,
        audio_service: AudioCaptureService = Provide[
            Go2MiddleLayerContainer.audio_capture_service
        ],
    ) -> None:
        audio_service.stop()
