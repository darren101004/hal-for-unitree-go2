"""
Stub implementation of AudioCaptureService when sounddevice/vosk are not available
or when the audio device fails. Use this to run the server without a microphone.
"""

import logging

from interfaces.audio import AudioCaptureService

logger = logging.getLogger("AudioCapture:AudioCaptureServiceStub")


class AudioCaptureServiceStub(AudioCaptureService):
    """
    No-op audio capture service when microphone is not available.
    """

    def __init__(
        self,
        device_id: int | str | None = None,
        hotwords: list[str] | None = None,
        patience: int = 3,
        model_id: str = "",
        sample_rate: int = 16000,
        channels: int = 1,
        name: str | None = None,
        **kwargs: object,
    ) -> None:
        self._device_id = device_id
        logger.warning(
            "Audio capture disabled: sounddevice/vosk not available or device %s failed. "
            "Install sounddevice and vosk to enable voice commands.",
            device_id,
        )

    def is_healthy(self) -> bool:
        """Stub is never healthy — audio device not available."""
        return False

    def restart(self) -> None:
        """No-op for stub."""
        pass

    def start(self) -> None:
        """No-op when audio capture is not available."""
        pass

    def stop(self) -> None:
        """No-op when audio capture is not available."""
        pass

    def get_pending_tasks(self) -> list[str]:
        """Return empty list when audio capture is not available."""
        return []

    def transcribe_audio(self, audio_data: bytes, audio_format: str) -> list[str]:
        """Return empty list when audio capture is not available."""
        return []
