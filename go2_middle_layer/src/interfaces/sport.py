from abc import ABC, abstractmethod
from models.sport_request import SportRequest
from models.response import Response


class SportService(ABC):
    @abstractmethod
    def handle(self, request: SportRequest) -> Response:
        pass
