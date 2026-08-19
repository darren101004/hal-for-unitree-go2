from typing import Optional
from dependency_injector.wiring import Provide, inject
from dependencies import Go2MiddleLayerContainer

from interfaces.state import StateService
from models.response import Response
from models.state import RobotState
import service_registry


class StateController:
    # Keep echo implementation for reference only.
    # Runtime is currently forced to ROS2 service.
    #
    # @inject
    # async def get_latest_state_using_echo(
    #     self,
    #     state_service: StateService = Provide[
    #         Go2MiddleLayerContainer.state_service_using_echo
    #     ],
    # ) -> Response:
    #     """
    #     Get the latest state from background buffer using ros2 echo state service.
    #     """
    #     reason = service_registry.get_unavailable_reason("state_echo")
    #     if reason:
    #         return Response(
    #             success=False,
    #             message=f"State service (echo) not available: {reason}",
    #             data=None,
    #             code=503,
    #         )
    #
    #     state: Optional[RobotState] = state_service.get_latest_state()
    #     if state is None:
    #         return Response(
    #             success=False,
    #             message="No state available yet. State service using ros2 echo on terminal is not running.",
    #             data=None,
    #             code=425,
    #         )
    #     return Response(
    #         success=True,
    #         message="State captured successfully from state service using ros2 echo on terminal",
    #         data=state,
    #         code=200,
    #     )

    @inject
    async def get_latest_state_using_ros2(
        self,
        state_service: StateService = Provide[
            Go2MiddleLayerContainer.state_service_using_ros2
        ],
    ) -> Response:
        """
        Get the latest state from the ros2 subscriber node.
        """
        reason = service_registry.get_unavailable_reason("state_ros2")
        if reason:
            return Response(
                success=False,
                message=f"State service (ROS2 node) not available: {reason}",
                data=None,
                code=503,
            )

        state: Optional[RobotState] = state_service.get_latest_state()
        if state is None:
            return Response(
                success=False,
                message="No state available yet. State service using ros2 subscriber node is not running.",
                data=None,
                code=425,
            )
        return Response(
            success=True,
            message="State captured successfully from state service using ros2 subscriber node",
            data=state,
            code=200,
        )

    @inject
    def start_state_service(
        self,
        # state_service_using_echo: StateService = Provide[
        #     Go2MiddleLayerContainer.state_service_using_echo
        # ],
        state_service: StateService = Provide[
            Go2MiddleLayerContainer.state_service_using_ros2
        ],
    ) -> None:
        """Start the ROS2 state service."""
        # state_service_using_echo.start()
        state_service.start()

    @inject
    def stop_state_service(
        self,
        # state_service_using_echo: StateService = Provide[
        #     Go2MiddleLayerContainer.state_service_using_echo
        # ],
        state_service: StateService = Provide[
            Go2MiddleLayerContainer.state_service_using_ros2
        ],
    ) -> None:
        """Stop the ROS2 state service."""
        # state_service_using_echo.stop()
        state_service.stop()
