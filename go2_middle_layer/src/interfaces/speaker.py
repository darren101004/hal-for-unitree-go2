from abc import ABC, abstractmethod
from typing import Optional

from models.response import Response


class SpeakerService(ABC):
    @abstractmethod
    def speak(self, text: str, interrupt: bool = False) -> Optional[Response]:
        """Speak the given text (sync, fire-and-forget)."""
        raise NotImplementedError

    @abstractmethod
    async def aspeak(self, text: str, interrupt: bool = False) -> Optional[Response]:
        """Speak the given text (async, waits until finished)."""
        raise NotImplementedError

    @abstractmethod
    def play_file(
        self, file_path: str, times: int = 1, interrupt: bool = False
    ) -> Optional[Response]:
        """Play audio from a file (sync, fire-and-forget)."""
        raise NotImplementedError

    @abstractmethod
    async def aplay_file(
        self, file_path: str, times: int = 1, interrupt: bool = False
    ) -> Optional[Response]:
        """Play audio from a file (async, waits until finished)."""
        raise NotImplementedError

    @abstractmethod
    def interrupt_all_task(self) -> None:
        """Interrupt all currently playing audio tasks."""
        raise NotImplementedError
