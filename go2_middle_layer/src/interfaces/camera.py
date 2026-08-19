from abc import ABC, abstractmethod
from typing import Optional, Tuple, Dict, Any


class CameraService(ABC):
    @abstractmethod
    def start(self, fps: int = 6) -> None:
        raise NotImplementedError

    @abstractmethod
    def stop(self) -> None:
        raise NotImplementedError

    @abstractmethod
    async def get_latest_frame(
        self, need_description: bool = False
    ) -> Optional[Tuple[Dict[str, Any], bytes]]:
        raise NotImplementedError
