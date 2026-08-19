import logging
import os
import subprocess
from dataclasses import dataclass

import numpy as np
import sounddevice as sd
import soundfile as sf
import soxr
from google import genai
from google.genai.types import HttpOptions
from openai import AsyncOpenAI, OpenAI
from piper.voice import PiperVoice

from impl.speaker.models import SupportedLanguages


logger = logging.getLogger("TTS")


@dataclass
class SpeechData:
    data: bytes
    sample_rate: int
    codec: str | None = None
    is_part: bool = False


async def gemini_tts(
    tts_prompt: str,
    language_code: SupportedLanguages = SupportedLanguages.ENGLISH_US,
    api_key: str | None = None,
    base_url: str | None = None,
    tts_model: str = "gemini-2.5-flash-preview-tts",
) -> SpeechData | None:
    client = genai.Client(
        api_key=api_key,
        http_options=HttpOptions(base_url=base_url, api_version="v1alpha"),
    )

    logger.debug(f"TTS: {tts_prompt}")

    try:
        response = await client.aio.models.generate_content(
            model=tts_model,
            contents=tts_prompt,
            config=genai.types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=genai.types.SpeechConfig(
                    language_code=language_code,
                    voice_config=genai.types.VoiceConfig(
                        prebuilt_voice_config=genai.types.PrebuiltVoiceConfig(
                            voice_name="Achird"
                        )
                    ),
                ),
            ),
        )

        mimetype = response.candidates[0].content.parts[0].inline_data.mime_type

        if not mimetype or not mimetype.startswith("audio/"):
            logger.error(f"Unexpected MIME type: {mimetype}")
            return None

        properties_list = [mimetype.split("=") for mimetype in mimetype.split(";")[1:]]

        properties = {
            property[0]: property[1]
            for property in properties_list
            if len(property) == 2
        }

        sample_rate = int(properties.get("rate", "16000") or "16000")
        codec = properties.get("codec", "pcm")

        return SpeechData(
            data=response.candidates[0].content.parts[0].inline_data.data,
            sample_rate=sample_rate,
            codec=codec,
        )

    except Exception as e:
        logger.error(f"Error generating audio with Gemini API: {e};", exc_info=True)
        return None


class Resampler:
    """Optimized resampler for 24kHz -> 48kHz (exact 2x)"""

    def __init__(self, input_rate=24000, output_rate=48000, volume_rate=1.0):
        self.input_rate = input_rate
        self.output_rate = output_rate
        self.volume_rate = volume_rate
        self.ratio = output_rate / input_rate
        logger.info(
            "Resampler: %d Hz -> %d Hz (ratio: %.2f)",
            input_rate,
            output_rate,
            self.ratio,
        )

        # Keep previous sample for interpolation continuity
        self.prev_sample = 0.0

    def process(self, pcm16_bytes: bytes) -> np.ndarray:
        if len(pcm16_bytes) == 0:
            return np.array([], dtype=np.float32)

        # Convert int16 to float32 [-1, 1]
        samples = (
            np.frombuffer(pcm16_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        )
        upsampled = soxr.resample(samples, self.input_rate, self.output_rate)
        upsampled = (upsampled * self.volume_rate).clip(-1, 1)

        # if len(samples) == 0:
        #     return np.array([], dtype=np.float32)

        # # Simple and fast 2x upsampling with linear interpolation
        # output_len = len(samples) * 2
        # upsampled = np.zeros(output_len, dtype=np.float32)

        # # First sample uses previous chunk's last sample
        # upsampled[0] = (self.prev_sample + samples[0]) * 0.5
        # upsampled[1] = samples[0]

        # # Interleave original samples and interpolated values
        # for i in range(1, len(samples)):
        #     upsampled[i * 2] = (samples[i - 1] + samples[i]) * 0.5  # Interpolated
        #     upsampled[i * 2 + 1] = samples[i]  # Original

        # # Save last sample for next chunk
        # self.prev_sample = samples[-1]

        return upsampled


async def openai_tts_realtime(
    text: str,
    voice: str = "coral",
    api_key: str | None = None,
    base_url: str | None = None,
    tts_model: str = "gpt-4o-mini-tts",
    speed: float = 1.5,
    chunk_size: int = 2048,
    volume_rate: float = 2.0,
):

    logger.info("Starting TTS for text: '%s...'", text[:50])
    resampler = Resampler(input_rate=24000, output_rate=48000, volume_rate=volume_rate)

    logger.debug("=========OPENAI INFO=========")
    logger.debug("API key: %s", api_key[:10] + "..." + api_key[-10:])
    logger.debug("Base URL: %s", base_url)
    logger.debug("=========OPENAI INFO=========")
    client = AsyncOpenAI(
        api_key=api_key,
        base_url=base_url,
    )

    logger.debug("Requesting TTS from OpenAI by model: %s", tts_model)
    chunk_count = 0
    async with client.audio.speech.with_streaming_response.create(
        model=tts_model,
        voice=voice,
        input=text,
        response_format="pcm",
        instructions="Speak in professional tone",
        speed=speed,
    ) as response:
        # Larger chunks = fewer iterations = less overhead
        async for chunk in response.iter_bytes(chunk_size=chunk_size):
            if not chunk:
                continue

            # Resample 24kHz -> 48kHz
            resampled = resampler.process(chunk)

            if len(resampled) > 0:
                chunk_count += 1
                yield resampled.reshape(-1, 1)

        logger.info("TTS completed. Total chunks: %d", chunk_count)


def piper_tts_realtime(
    text: str,
    target_sample_rate=48000,
    white_buffer_seconds: float = 0.5,
    model: PiperVoice = None,
):
    logger.info("Starting TTS for text: '%s...'", text[:50])

    logger.info("Using Piper model: %s", model)
    if white_buffer_seconds > 0:
        silence = np.zeros(
            int(white_buffer_seconds * target_sample_rate), dtype=np.float32
        )
    else:
        silence = None

    chunk_count = 0
    for chunk in model.synthesize(text):
        resampled = soxr.resample(
            chunk.audio_float_array, model.config.sample_rate, target_sample_rate
        )
        if len(resampled) > 0:
            if chunk_count == 0 and silence is not None:
                yield silence.reshape(-1, 1)

            chunk_count += 1
            yield resampled.reshape(-1, 1)

    logger.info("TTS completed. Total chunks: %d", chunk_count)


async def openai_tts_into_file(
    text: str,
    voice: str = "coral",
    api_key: str | None = None,
    base_url: str | None = None,
    tts_model: str = "gpt-4o-mini-tts",
):
    client = OpenAI(
        api_key=api_key,
        base_url=base_url,
    )
    with client.audio.speech.with_streaming_response.create(
        model=tts_model,
        voice=voice,
        input=text,
        response_format="wav",
    ) as response:
        response.stream_to_file("tts_24k.wav")
        # 2. Upsample 24k → 48k
        result = subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                "tts_24k.wav",
                "-af",
                "aresample=48000",
                "tts_48k.wav",
            ],
            capture_output=True,
            text=True,
        )
        logger.debug(f"FFmpeg result: {result.stdout}")
        logger.debug(f"FFmpeg error: {result.stderr}")

        # 3. Play
        sd.default.device = 0
        sd.default.latency = "high"
        sd.default.blocksize = 2048
        audio, sr = sf.read("tts_48k.wav", dtype="float32")
        sd.play(audio, 48000)
        sd.wait()

        # 4. Cleanup
        os.remove("tts_24k.wav")
        os.remove("tts_48k.wav")
        logger.info("TTS into file finished.")
