import os
from enum import Enum
from typing import Optional

import numpy as np
from pydantic import BaseModel, model_validator


class SupportedLanguages(str, Enum):
    ARABIC_EGYPT = "ar-EG"
    GERMAN_GERMANY = "de-DE"
    ENGLISH_US = "en-US"
    SPANISH_US = "es-US"
    FRENCH_FRANCE = "fr-FR"
    HINDI_INDIA = "hi-IN"
    INDONESIAN_INDONESIA = "id-ID"
    ITALIAN_ITALY = "it-IT"
    JAPANESE_JAPAN = "ja-JP"
    KOREAN_KOREA = "ko-KR"
    PORTUGUESE_BRAZIL = "pt-BR"
    RUSSIAN_RUSSIA = "ru-RU"
    DUTCH_NETHERLANDS = "nl-NL"
    POLISH_POLAND = "pl-PL"
    THAI_THAILAND = "th-TH"
    TURKISH_TURKEY = "tr-TR"
    VIETNAMESE_VIETNAM = "vi-VN"
    ROMANIAN_ROMANIA = "ro-RO"
    UKRAINIAN_UKRAINE = "uk-UA"
    BENGALI_BANGLADESH = "bn-BD"
    ENGLISH_INDIA = "en-IN"
    MARATHI_INDIA = "mr-IN"
    TAMIL_INDIA = "ta-IN"
    TELUGU_INDIA = "te-IN"


class RecordedAudio(str, Enum):
    """Pre-recorded audio clips available on the robot."""

    BARK = "bark"
    HAPPY = "happy"
    SAD = "sad"
    ALERT = "alert"
    GREETING = "greeting"
    GOODBYE = "goodbye"
    ACKNOWLEDGE = "acknowledge"
    ERROR = "error"
    CONFUSED = "confused"


class RobotModality(str, Enum):
    TEXT = "text"
    VOICE = "voice"
    SILENT = "silent"


class DeviceModelType(str, Enum):
    MICROPHONE = "microphone"
    SPEAKER = "speaker"
    VIDEO = "video"
    ROBOT = "robot"
    OTHER = "other"


class IDeviceInfo(BaseModel):
    model_type: DeviceModelType
    device_id: int | str
    device_name: Optional[str] = None

    @model_validator(mode="after")
    def validate_device_id(self):
        if self.device_name is None:
            self.device_name = f"{self.model_type}_{os.urandom(2).hex()}"
        return self


class IDeviceResponse(BaseModel):
    success: bool = True


class AudioCaptureDeviceInfo(IDeviceInfo):
    model_type: DeviceModelType = DeviceModelType.MICROPHONE
    sample_rate: int = 16000


class AudioCaptureDeviceResponse(IDeviceResponse):
    # TODO: add necessary fields here
    pass


class SpeakerDeviceInfo(IDeviceInfo):
    model_type: DeviceModelType = DeviceModelType.SPEAKER
    sample_rate: int = 48000
    block_size: int = 1024
    channels: int = 1
    dtype: type = np.float32
    should_stop: bool = True


class SpeakerDeviceResponse(IDeviceResponse):
    # TODO: add necessary fields here
    pass
