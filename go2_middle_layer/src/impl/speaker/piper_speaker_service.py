import asyncio
import logging
import threading
from typing import Optional

from impl.speaker.base import SyncSpeakerDeviceBase
from impl.speaker.tts import piper_tts_realtime
from models.response import Response
import service_registry

logger = logging.getLogger("Speaker:PiperSpeakerService")

SPEAKER_SAMPLE_RATE = 48000


class PiperSpeakerService(SyncSpeakerDeviceBase):
    """Speaker service using Piper TTS engine for offline text-to-speech."""

    def __init__(
        self,
        device_id: int | None = None,
        name: str | None = None,
        sample_rate: int = SPEAKER_SAMPLE_RATE,
        block_size: int = 1024,
        channels: int = 1,
        piper_model: str = "en_US-lessac-medium.onnx",
        volume: float = 1.0,
        fade_in_ms: int = 0,
        startup_delay_ms: int = 0,
        mixer_volume: int = 100,
    ):
        super().__init__(
            device_id,
            name,
            sample_rate,
            block_size,
            channels,
            volume=volume,
            fade_in_ms=fade_in_ms,
            startup_delay_ms=startup_delay_ms,
            mixer_volume=mixer_volume,
        )
        self.piper_model = piper_model
        self._voice = None
        self._voice_sample_rate: Optional[int] = None
        self._load_model()

        logger.info(
            "PiperSpeakerService initialized: device=%s, sr=%d, model=%s",
            self.device_id,
            self.sample_rate,
            self.piper_model,
        )

    def _load_model(self) -> None:
        try:
            from piper.voice import PiperVoice

            self._voice = PiperVoice.load(self.piper_model)
            self._voice_sample_rate = self._voice.config.sample_rate
            logger.info(
                "Piper model loaded: %s (sr=%d)",
                self.piper_model,
                self._voice_sample_rate,
            )
            service_registry.register(
                "speaker",
                True,
                extra_data={
                    "device_id": self.device_id,
                    "device_name": self.device_name,
                    "sample_rate": self.sample_rate,
                    "tts_engine": "piper",
                    "piper_model": self.piper_model,
                    "voice_sample_rate": self._voice_sample_rate,
                },
            )
        except Exception as e:
            logger.error("Failed to load Piper model '%s': %s", self.piper_model, e)
            self._voice = None
            service_registry.register(
                "speaker",
                False,
                f"Failed to load Piper model '{self.piper_model}': {e}",
            )

    def speak(self, text: str, interrupt: bool = False) -> Optional[Response]:
        logger.debug(f"Received text to speak out: {text}")

        if not isinstance(text, str) or text.strip() == "":
            logger.warning(f"Invalid text: type={type(text)}, value='{text}'")
            return Response(
                success=False,
                message=f"Invalid text: type={type(text)}, value='{text}'",
            )

        if self._voice is None:
            return Response(success=False, message="Piper model not loaded")

        self._add_new_task(
            piper_tts_realtime(
                text, target_sample_rate=self.sample_rate, model=self._voice
            ),
            interrupt,
        )

        return Response(success=True, message="Speech queued successfully")

    async def aspeak(
        self, text: str, interrupt: bool = False, timeout: float = 60.0
    ) -> Optional[Response]:
        logger.debug(f"Received text to speak out: {text}")

        if not isinstance(text, str) or text.strip() == "":
            logger.warning(f"Invalid text: type={type(text)}, value='{text}'")
            return Response(
                success=False,
                message=f"Invalid text: type={type(text)}, value='{text}'",
            )

        if self._voice is None:
            return Response(success=False, message="Piper model not loaded")

        task = self._add_new_task(
            piper_tts_realtime(
                text, target_sample_rate=self.sample_rate, model=self._voice
            ),
            interrupt,
        )

        try:
            await asyncio.wait_for(asyncio.shield(task), timeout=timeout)
        except asyncio.TimeoutError:
            self.interrupt_events.get(task, threading.Event()).set()
            try:
                await task
            except Exception:
                pass
            logger.warning("Speech timed out after %.0fs: '%s...'", timeout, text[:50])
            return Response(
                success=False, message=f"TTS timed out after {timeout:.0f}s"
            )
        except asyncio.CancelledError:
            logger.info("Speech interrupted: '%s...'", text[:50])
            return Response(success=False, message=f"Speech interrupted: '{text[:50]}'")

        return Response(success=True, message="Speech completed successfully")

    async def astart(self):
        logger.info(f"Starting piper speaker service with device_id={self.device_id}")

        self.running = True
