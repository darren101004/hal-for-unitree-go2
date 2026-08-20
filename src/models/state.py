from typing import TypedDict, List, Any, Dict
from enum import Enum

from pydantic import BaseModel, Field


class TimeSpecDict(TypedDict):
    sec: int  # int32
    nanosec: int  # uint32


class IMUStateDict(TypedDict):
    quaternion: List[float]  # float32[4]
    gyroscope: List[float]  # float32[3]
    accelerometer: List[float]  # float32[3]
    rpy: List[float]  # float32[3] - Roll, Pitch, Yaw
    temperature: int  # int8


class SportModeStateDict(TypedDict):
    stamp: TimeSpecDict  # TimeSpec
    error_code: int  # uint32
    imu_state: IMUStateDict  # IMUState
    mode: int  # uint8
    progress: float  # float32
    gait_type: int  # uint8
    foot_raise_height: float  # float32
    position: List[float]  # float32[3]
    body_height: float  # float32
    velocity: List[float]  # float32[3]
    yaw_speed: float  # float32
    range_obstacle: List[float]  # float32[4]
    foot_force: List[int]  # int16[4]
    foot_position_body: List[float]  # float32[12]
    foot_speed_body: List[float]  # float32[12]


class RobotState(BaseModel):
    """
    Combined robot state returned by state services.
    - sportmodestate: parsed from `/lf/sportmodestate`
    - lowstate: parsed from lowstate topic
    """

    sportmodestate: Dict[str, Any] = Field(default_factory=dict)
    lowstate: Dict[str, Any] = Field(default_factory=dict)


class SportModeEnum(Enum):
    IDLE = 0
    STANDING = 1
    WALKING_VEL = 2
    WALKING_POS = 3
    WALKING_PATH = 4
    STAND_DOWN = 5
    STAND_UP = 6
    DAMPING = 7
    RECOVERY = 8
    BACKFLIP = 9
    JUMP_YAW = 10
    STRAIGHT_HAND = 11
    DANCE1 = 12
    DANCE2 = 13


class GaitTypeEnum(Enum):
    IDLE = 0  # Idle.
    TROT_WALKING = 1  # Trot walking.
    TROT_RUNNING = 2  # Trot running.
    STAIRS_CLIMBING = 3  # Stairs climbing.
    TROT_OBSTACLE = 4  # Trot obstacle.
