import logging
import threading
import time
from typing import Optional, Tuple, Dict, Any

from unitree_sdk2py.go2.video.video_client import VideoClient
from unitree_sdk2py.core.channel import ChannelFactoryInitialize

from interfaces.camera import CameraService
import service_registry


logger = logging.getLogger("Camera:RpcCameraService")


class RpcCameraService(CameraService):
    """
    Background camera capture service.
    """

    def __init__(self, network_interface: str) -> None:
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._latest_frame_lock = threading.Lock()
        self._latest_frame: Optional[Tuple[Dict[str, Any], bytes]] = None
        self._client: Optional[VideoClient] = None
        self._network_interface = network_interface

    def _capture_loop(self, fps: int) -> None:
        if fps <= 0:
            fps = 30
        capture_interval_sec = 1.0 / fps

        logger.info("Starting camera background capture loop at %s FPS", fps)
        try:
            assert (
                self._client is not None
            ), "VideoClient must be initialized before starting capture loop"
            client = self._client
            while not self._stop_event.is_set():
                start_time = time.time()
                code, data = client.GetImageSample()
                if code == 0 and data is not None:
                    try:
                        with self._latest_frame_lock:
                            self._latest_frame = ({"code": code}, bytes(data))
                    except Exception:
                        logger.exception("Failed to update latest camera frame buffer")
                else:
                    logger.warning(
                        "Failed to capture frame from camera. Code: %s", code
                    )

                elapsed = time.time() - start_time
                if elapsed < capture_interval_sec:
                    time.sleep(capture_interval_sec - elapsed)
        finally:
            logger.info("Camera background capture loop stopped")

    def is_healthy(self) -> bool:
        """Return True if the capture thread is alive."""
        return self._thread is not None and self._thread.is_alive()

    def restart(self) -> None:
        """Stop and re-start the capture service."""
        fps = getattr(self, "_last_fps", 30)
        self.stop()
        self.start(fps=fps)

    def start(self, fps: int = 30) -> None:
        """
        Start the background capture thread if it is not already running.
        """
        if self._thread is not None and self._thread.is_alive():
            logger.debug("Camera background capture thread already running")
            return

        logger.info("Initializing VideoClient for background capture")

        try:
            ChannelFactoryInitialize(0, self._network_interface)
            client = VideoClient()
            client.SetTimeout(3.0)
            client.Init()
            self._client = client
        except Exception as e:
            logger.error("Failed to initialize RPC camera: %s", e)
            service_registry.register("rpc_camera", False, str(e))
            return

        self._last_fps = fps

        with self._latest_frame_lock:
            self._latest_frame = None

        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._capture_loop,
            args=(fps,),
            name="camera_capture_thread",
            daemon=True,
        )
        self._thread.start()
        service_registry.register(
            "rpc_camera",
            True,
            extra_data={
                "network_interface": self._network_interface,
                "fps": fps,
            },
        )

    def stop(self) -> None:
        """Stop the background capture thread if it is running."""
        if self._thread is None:
            return

        logger.info("Stopping camera background capture thread")
        self._stop_event.set()
        self._thread.join(timeout=2.0)
        self._thread = None

    async def get_latest_frame(
        self, need_description: bool = False
    ) -> Optional[Tuple[Dict[str, Any], bytes]]:
        """
        Return the latest frame in the buffer.
        Note: No description is supported for RPC camera.
        """
        with self._latest_frame_lock:
            return self._latest_frame
