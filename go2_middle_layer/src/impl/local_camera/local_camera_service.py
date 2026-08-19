import logging
import threading
import time
from typing import Optional, Tuple, Dict, Any
import cv2

from interfaces.camera import CameraService
import service_registry


logger = logging.getLogger("Camera:LocalCameraService")

LOCAL_CAMERA_WIDTH, LOCAL_CAMERA_HEIGHT = 1280, 720
LOCAL_CAMERA_FPS = 30


def resolve_camera_device_id(
    device_id: str | int | None, max_scan: int = 5
) -> str | int:
    """
    Validate and resolve a local camera device ID (OpenCV).

    - If device_id is None → scan indices 0..max_scan and pick the first available.
    - If device_id is provided but invalid/unavailable → log warning and scan.
    - If device_id is valid → return it unchanged.

    Raises RuntimeError if no camera is found anywhere in the scan range.
    """
    if isinstance(device_id, str) and device_id.isdigit():
        device_id = int(device_id)

    def _try_open(dev_id: str | int) -> bool:
        cap = cv2.VideoCapture(dev_id)
        opened = cap.isOpened()
        cap.release()
        return opened

    def _scan_first_available() -> int:
        for idx in range(max_scan):
            if _try_open(idx):
                logger.info("Auto-selected local camera device: [%d]", idx)
                return idx
        raise RuntimeError(
            f"No local camera found in device range [0..{max_scan - 1}]."
        )

    if device_id is None:
        logger.info("No camera device_id specified.")
        return _scan_first_available()

    if _try_open(device_id):
        return device_id

    logger.warning(
        "Camera device_id=%s is invalid or unavailable. Scanning for first available.",
        device_id,
    )
    return _scan_first_available()


class LocalCameraService(CameraService):
    """
    Background camera capture service.
    """

    def __init__(self, device_id: str | int | None) -> None:
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._latest_frame_lock = threading.Lock()
        self._latest_frame: Optional[Tuple[Dict[str, Any], bytes]] = None
        # self._device_id = resolve_camera_device_id(device_id)
        try:
            self._device_id = int(device_id)
        except ValueError:
            self._device_id = device_id

    def _capture_loop(self, fps: int) -> None:
        if fps <= 0:
            fps = 30

        try:
            self._cap = cv2.VideoCapture(self._device_id)
            if not self._cap.isOpened():
                self._cap.release()
                msg = f"Local camera device {self._device_id} not available"
                logger.warning("%s. Camera disabled.", msg)
                service_registry.register("local_camera", False, msg)
                return
        except Exception as e:
            msg = f"Failed to open local camera (device {self._device_id}): {e}"
            logger.warning("%s. Camera disabled.", msg)
            service_registry.register("local_camera", False, str(e))
            return

        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, LOCAL_CAMERA_WIDTH)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, LOCAL_CAMERA_HEIGHT)
        self._cap.set(cv2.CAP_PROP_FPS, LOCAL_CAMERA_FPS)

        w, h = self._cap.get(cv2.CAP_PROP_FRAME_WIDTH), self._cap.get(
            cv2.CAP_PROP_FRAME_HEIGHT
        )
        logger.info(f"Resolution of local camera: {w}x{h}")
        service_registry.register(
            "local_camera",
            True,
            extra_data={
                "device_id": self._device_id,
                "fps": fps,
                "resolution": f"{int(w)}x{int(h)}",
            },
        )
        self._fps = fps
        self._capture_interval_sec = 1.0 / fps

        logger.info("Starting camera background capture loop at %s FPS", fps)
        try:
            while not self._stop_event.is_set():
                ret, frame = self._cap.read()
                if not ret:
                    logger.warning("Failed to capture frame from camera")
                    time.sleep(self._capture_interval_sec)
                    continue

                success, encoded_image = cv2.imencode(
                    ".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85]
                )
                if not success:
                    logger.warning("Failed to encode frame to JPEG")
                    time.sleep(self._capture_interval_sec)
                    continue
                bytes_data = encoded_image.tobytes()
                with self._latest_frame_lock:
                    self._latest_frame = ({"message": "Success"}, bytes_data)

                time.sleep(self._capture_interval_sec)
        finally:
            self._cap.release()
            logger.info("Camera background capture loop stopped")

    def is_healthy(self) -> bool:
        """Return True if the capture thread is alive."""
        return self._thread is not None and self._thread.is_alive()

    def restart(self) -> None:
        """Stop and re-start the capture service."""
        fps = getattr(self, "_fps", 30)
        self.stop()
        self.start(fps=fps)

    def start(self, fps: int = 30) -> None:
        """
        Start the background capture thread if it is not already running.
        """
        if self._thread is not None and self._thread.is_alive():
            logger.debug("Camera background capture thread already running")
            return

        logger.info("Initializing camera for background capture")
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._capture_loop,
            args=(fps,),
            name="camera_capture_thread",
            daemon=True,
        )
        self._thread.start()

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
        Note: No description is supported for local camera.
        """
        with self._latest_frame_lock:
            return self._latest_frame
