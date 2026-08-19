from abc import ABC, abstractmethod
from typing import Optional
from models.state import RobotState


class StateService(ABC):
    @abstractmethod
    def start(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def stop(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def get_latest_state(self) -> Optional[RobotState]:
        raise NotImplementedError
