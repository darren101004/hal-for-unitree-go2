from abc import ABC, abstractmethod


class AudioCaptureService(ABC):
    @abstractmethod
    def start(self) -> None:
        """Start the background audio capture loop (hotword detection + task listening)."""
        raise NotImplementedError

    @abstractmethod
    def stop(self) -> None:
        """Stop the background audio capture loop."""
        raise NotImplementedError

    @abstractmethod
    def get_pending_tasks(self) -> list[str]:
        """
        Drain and return all voice tasks collected since the last call.
        Each task is a transcribed command spoken after a hotword trigger.
        """
        raise NotImplementedError

    @abstractmethod
    def transcribe_audio(self, audio_data: bytes, audio_format: str) -> list[str]:
        """
        Transcribe raw audio data (e.g. from Telegram voice message).

        audio_data: raw bytes of audio file (OGG, WAV, etc.)
        audio_format: file format hint (e.g. "ogg", "wav")
        Returns list of transcribed sentences.
        Also appends results to the pending tasks queue.
        """
        raise NotImplementedError

    @abstractmethod
    def check_hotwords(self, text: str) -> bool:
        """Check if transcribed text contains any configured hotword."""
        raise NotImplementedError
