from typing import Optional
from dependency_injector.wiring import Provide, inject
from dependencies import Go2MiddleLayerContainer

from interfaces.state import StateService
from models.response import Response
from models.state import RobotState
import service_registry


class StateController:
    @inject
    async def get_latest_state(
        self,
        state_service: StateService = Provide[Go2MiddleLayerContainer.state_service],
    ) -> Response:
        """
        Get the latest state read from DDS by the SDK subscriber.
        """
        reason = service_registry.get_unavailable_reason("state")
        if reason:
            return Response(
                success=False,
                message=f"State service not available: {reason}",
                data=None,
                code=503,
            )

        state: Optional[RobotState] = state_service.get_latest_state()
        if state is None:
            return Response(
                success=False,
                message="No state available yet. No packet received from the robot.",
                data=None,
                code=425,
            )
        return Response(
            success=True,
            message="State captured successfully from the SDK state service",
            data=state,
            code=200,
        )

    @inject
    def start_state_service(
        self,
        state_service: StateService = Provide[Go2MiddleLayerContainer.state_service],
    ) -> None:
        """Start the SDK state service."""
        state_service.start()

    @inject
    def stop_state_service(
        self,
        state_service: StateService = Provide[Go2MiddleLayerContainer.state_service],
    ) -> None:
        """Stop the SDK state service."""
        state_service.stop()
