import asyncio
import logging
from typing import Optional

from impl.speaker.base import AsyncSpeakerDeviceBase
from impl.speaker.tts import openai_tts_realtime
from models.response import Response
import service_registry


logger = logging.getLogger("Speaker:OpenAISpeakerService")

SPEAKER_SAMPLE_RATE = 48000
OPENAI_TTS_SAMPLE_RATE = 24000


class OpenAISpeakerService(AsyncSpeakerDeviceBase):
    """Speaker service using OpenAI TTS API for text-to-speech."""

    def __init__(
        self,
        device_id: int | None = None,
        sample_rate: int = SPEAKER_SAMPLE_RATE,
        block_size: int = 1024,
        channels: int = 1,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        tts_model: str = "gpt-4o-mini-tts",
        tts_voice: str = "coral",
        volume_rate: float = 2.0,
        name: str | None = None,
        chunk_write_timeout: float = 10.0,
        lock_acquire_timeout: float = 5.0,
        tts_speed: float = 1.5,
        tts_chunk_size: int = 2048,
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
            chunk_write_timeout=chunk_write_timeout,
            lock_acquire_timeout=lock_acquire_timeout,
            volume=volume,
            fade_in_ms=fade_in_ms,
            startup_delay_ms=startup_delay_ms,
            mixer_volume=mixer_volume,
        )
        self.tts_model = tts_model
        self.tts_voice = tts_voice
        self.volume_rate = volume_rate
        self.tts_speed = tts_speed
        self.tts_chunk_size = tts_chunk_size

        self._api_key = api_key
        self._base_url = base_url

        logger.info(
            "OpenAI TTS config: model=%s, voice=%s, speed=%.1f, volume_rate=%.1f",
            self.tts_model,
            self.tts_voice,
            self.tts_speed,
            self.volume_rate,
        )
        self.text_queue: asyncio.Queue[str] = asyncio.Queue()
        service_registry.register(
            "speaker",
            True,
            extra_data={
                "device_id": self.device_id,
                "device_name": self.device_name,
                "sample_rate": self.sample_rate,
                "tts_engine": "openai",
                "tts_model": self.tts_model,
                "tts_voice": self.tts_voice,
            },
        )

    def speak(self, text: str, interrupt: bool = False) -> Optional[Response]:
        logger.debug(f"Received text to speak out: {text}")

        if not isinstance(text, str) or text.strip() == "":
            logger.warning(f"Invalid text: type={type(text)}, value='{text}'")
            return Response(
                success=False,
                message=f"Invalid text: type={type(text)}, value='{text}'",
            )

        self._add_new_task(
            openai_tts_realtime(
                text,
                voice=self.tts_voice,
                api_key=self._api_key,
                base_url=self._base_url,
                tts_model=self.tts_model,
                speed=self.tts_speed,
                chunk_size=self.tts_chunk_size,
                volume_rate=self.volume_rate,
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

        task = self._add_new_task(
            openai_tts_realtime(
                text,
                voice=self.tts_voice,
                api_key=self._api_key,
                base_url=self._base_url,
                tts_model=self.tts_model,
                speed=self.tts_speed,
                chunk_size=self.tts_chunk_size,
                volume_rate=self.volume_rate,
            ),
            interrupt,
        )

        try:
            await asyncio.wait_for(asyncio.shield(task), timeout=timeout)
        except asyncio.TimeoutError:
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
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
        logger.info(f"Starting openai speaker service with device_id={self.device_id}")

        self.running = True
