from __future__ import annotations

import importlib
import logging
from pathlib import Path

from dependency_injector import containers, providers
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


def _lazy_class(
    module_path: str, class_name: str, fallback: tuple[str, str] | None = None
):
    """Return a factory that lazily imports and instantiates *class_name* from *module_path*.

    When the factory is called with ``(**kwargs)`` it:
    1. Imports the module (only on first call — Python caches it).
    2. Gets the class.
    3. Returns ``cls(**kwargs)``.

    If *fallback* is provided as ``(module, class)`` and the primary import
    raises ``ImportError`` / ``Exception``, the fallback is used instead (stub pattern).
    """

    _resolved_cls: list = []  # mutable cache shared across calls

    def _factory(*args, **kwargs):
        if not _resolved_cls:
            try:
                mod = importlib.import_module(module_path)
                _resolved_cls.append(getattr(mod, class_name))
            except (ImportError, Exception) as exc:
                if fallback is None:
                    raise
                logger.info(
                    "Could not import %s.%s (%s), falling back to %s.%s",
                    module_path,
                    class_name,
                    exc,
                    fallback[0],
                    fallback[1],
                )
                mod = importlib.import_module(fallback[0])
                _resolved_cls.append(getattr(mod, fallback[1]))
        return _resolved_cls[0](*args, **kwargs)

    return _factory


class ServiceSettings(BaseSettings):
    STATE_SERVICE_MODE: str = Field(default="ros2")
    STATE_TOPIC: str = Field(default="/lf/sportmodestate")
    STATE_LOWSTATE_TOPIC: str = Field(default="/lowstate")
    STATE_LOWSTATE_MIN_UPDATE_INTERVAL_SEC: float = Field(default=120.0)
    # Ethernet interface connected to the robot. On the OrangePi board the
    # Allwinner dwmac-sunxi driver names it "end0" — there is no "eth0".
    STATE_NETWORK_INTERFACE: str = Field(default="end0")

    DEVICE_WATCHER_ENABLED: bool = Field(
        default=True, description="Enable device watcher for auto-recovery"
    )
    DEVICE_WATCHER_POLL_INTERVAL: float = Field(
        default=5.0, description="Seconds between health checks"
    )
    DEVICE_WATCHER_BASE_BACKOFF: float = Field(
        default=2.0, description="Base backoff in seconds for retry delay"
    )
    DEVICE_WATCHER_MAX_BACKOFF: float = Field(
        default=120.0, description="Max backoff cap in seconds"
    )
    DEVICE_WATCHER_MAX_RETRIES: int = Field(
        default=5, description="Max restart attempts per service (0=unlimited)"
    )
    DEVICE_WATCHER_INITIAL_GRACE_PERIOD: float = Field(
        default=10.0, description="Seconds to wait before first health check"
    )

    model_config = SettingsConfigDict(
        env_prefix="",
        env_file=[
            str(Path(__file__).resolve().parent.parent.parent / ".env"),
            ".env",
        ],
        env_file_encoding="utf-8",
        extra="ignore",
    )


class Go2MiddleLayerContainer(containers.DeclarativeContainer):
    config = providers.Configuration()

    # --- Lazy factories: modules are imported only when the singleton is first accessed ---

    sport_service = providers.Singleton(
        _lazy_class(
            "impl.sdk_sport.sdk_sport_service",
            "SdkSportService",
            fallback=("impl.sdk_sport.sdk_sport_service_stub", "SdkSportServiceStub"),
        ),
        network_interface=config.state.network_interface,
    )

    state_service_using_ros2 = providers.Singleton(
        _lazy_class(
            "impl.state.ros2_state_service",
            "Ros2SportStateService",
            fallback=(
                "impl.state.ros2_state_service_stub",
                "Ros2SportStateServiceStub",
            ),
        ),
        sport_topic=config.state.topic,
        lowstate_topic=config.state.lowstate_topic,
        lowstate_min_update_interval_sec=config.state.lowstate_min_update_interval_sec,
    )

    device_watcher_service = providers.Singleton(
        _lazy_class(
            "impl.device_watcher.device_watcher_service", "DeviceWatcherService"
        ),
        poll_interval=config.device_watcher.poll_interval,
        base_backoff=config.device_watcher.base_backoff,
        max_backoff=config.device_watcher.max_backoff,
        max_retries=config.device_watcher.max_retries,
        initial_grace_period=config.device_watcher.initial_grace_period,
    )


_container = None


def init_container() -> Go2MiddleLayerContainer:
    global _container
    if _container:
        return _container

    settings = ServiceSettings()
    container = Go2MiddleLayerContainer()
    container.config.from_dict(
        {
            "state": {
                "mode": settings.STATE_SERVICE_MODE,
                "topic": settings.STATE_TOPIC,
                "lowstate_topic": settings.STATE_LOWSTATE_TOPIC,
                "lowstate_min_update_interval_sec": settings.STATE_LOWSTATE_MIN_UPDATE_INTERVAL_SEC,
                "network_interface": settings.STATE_NETWORK_INTERFACE,
            },
            "device_watcher": {
                "enabled": settings.DEVICE_WATCHER_ENABLED,
                "poll_interval": settings.DEVICE_WATCHER_POLL_INTERVAL,
                "base_backoff": settings.DEVICE_WATCHER_BASE_BACKOFF,
                "max_backoff": settings.DEVICE_WATCHER_MAX_BACKOFF,
                "max_retries": settings.DEVICE_WATCHER_MAX_RETRIES,
                "initial_grace_period": settings.DEVICE_WATCHER_INITIAL_GRACE_PERIOD,
            },
        }
    )

    _container = container
    return container
