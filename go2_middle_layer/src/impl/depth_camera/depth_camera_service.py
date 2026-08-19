import logging
import threading
import time
from typing import Optional, Tuple, Dict, Any

import numpy as np
import pyrealsense2 as rs
import cv2

from impl.utils import build_depth_frame_info
from interfaces.camera import CameraService
from utils.yolov8.yolov8_remote_detector import RemoteYOLOv8Detector
from utils.yolov8.base import ObjectDetector
from utils.captioning import Captioner
import service_registry

logger = logging.getLogger("Camera:DepthCamera")

DEPTH_CAMERA_WIDTH, DEPTH_CAMERA_HEIGHT = 640, 480
COLOR_CAMERA_WIDTH, COLOR_CAMERA_HEIGHT = 640, 480
DEFAULT_FPS = 30
DEPTH_CAMERA_MAX_FRAMES = 20


class DepthCameraService(CameraService):
    """
    Background depth camera capture service.
    """

    def __init__(self, config: dict = None) -> None:
        self._config = config
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

        self._latest_frame_lock = threading.Lock()
        self._latest_frame: Optional[rs.composite_frame] = None

        self._config_lock = threading.Lock()
        self._align: Optional[rs.align] = None
        self._pipeline: Optional[rs.pipeline] = None
        self._intr: Optional[rs.intrinsics] = None
        self._detector: Optional[ObjectDetector] = None
        self._captioner: Optional[Captioner] = None

    def _capture_loop(self, fps: int) -> None:
        """
        Background capture loop: update the latest depth camera frame into the buffer.
        """
        if fps <= 0:
            fps = DEFAULT_FPS
        depth_camera_capture_interval_sec = 1.0 / fps

        logger.info("Starting camera background capture loop at %s FPS", fps)
        try:
            frame_count = 0
            last_log_time = time.time()
            assert (
                self._pipeline is not None
            ), "Pipeline must be initialized before capture loop"
            pipeline = self._pipeline
            while not self._stop_event.is_set():
                start_time = time.time()
                frames = pipeline.wait_for_frames()

                if frames is not None:
                    #  Keeps the frame, so that other frames don't overwrite it.
                    with self._latest_frame_lock:
                        self._latest_frame = None
                        frames.keep()
                        self._latest_frame = frames

                frame_count += 1
                current_time = time.time()
                if current_time - last_log_time >= 1.0:
                    realtime_fps = frame_count / (current_time - last_log_time)
                    logger.debug("[Depth Camera] Real-time FPS: %.2f", realtime_fps)
                    frame_count = 0
                    last_log_time = current_time

                elapsed_time = current_time - start_time
                if elapsed_time < depth_camera_capture_interval_sec:
                    time.sleep(depth_camera_capture_interval_sec - elapsed_time)
        finally:
            logger.info("Camera background capture loop stopped")

    async def get_latest_distance_to_center(self) -> Optional[float]:
        """
        Get the latest distance to the center of the image. (in millimeters)
        """
        local_depth_image = None
        with self._latest_frame_lock:
            if self._latest_frame is None:
                return None
            local_depth_image = np.asanyarray(
                self._latest_frame.get_depth_frame().get_data()
            ).copy()
            
        frame_height, frame_width = (
            local_depth_image.shape[0],
            local_depth_image.shape[1],
        )
        v, u = frame_height // 2, frame_width // 2
        ker_height = int(frame_height * 0.75)
        ker_width = int(frame_width * 0.5)
        v_start = max(v - ker_height // 2, 0)
        v_end = min(v + ker_height // 2 + 1, frame_height)
        u_start = max(u - ker_width // 2, 0)
        u_end = min(u + ker_width // 2 + 1, frame_width)
        center_region = local_depth_image[v_start:v_end, u_start:u_end]
        valid_distances = center_region[center_region > 0]

        distance = None
        if valid_distances.size > 0:
            distance = np.percentile(valid_distances, 5)
        return distance

    def _save_depth_image(
        self, depth_image: np.ndarray, max_distance: int = 4000
    ) -> None:
        """
        Save the depth image to a file.
        """
        cliped_depth_image = np.clip(depth_image, 0, max_distance)
        depth_normalized_image = (cliped_depth_image / max_distance) * 255.0
        depth_u8 = depth_normalized_image.astype(np.uint8)
        cv2.imwrite("depth_image.png", depth_u8)

    async def get_latest_frame(
        self, need_description: bool = False
    ) -> Optional[Tuple[Dict[str, Any], bytes]]:
        """
        Get the latest frames from the depth camera buffer and convert to info + PNG image.
        Input:
        - need_description: bool, whether to include description in the info
        Output:
        - info: Dict[str, Any], information about the detected objects and natural language description are included if need_description is True
        - img_bytes: bytes, PNG image of the detected objects
        """
        local_latest_frame = None
        start_time0 = time.time()
        with self._latest_frame_lock:
            if self._latest_frame is None or self._align is None:
                return None
            local_latest_frame = self._latest_frame

        # raw_depth_image = np.asanyarray(local_latest_frame.get_depth_frame().get_data())
        # raw_color_image = np.asanyarray(local_latest_frame.get_color_frame().get_data())

        align_start_time = time.time()
        color_image, depth_image = self._align_frame(local_latest_frame)
        align_end_time = time.time()
        logger.info(f"[Depth Camera] Align time: {align_end_time - align_start_time}")
        # color_image = np.asanyarray(aligned_frames.get_color_frame().get_data())
        # depth_image = np.asanyarray(aligned_frames.get_depth_frame().get_data())
        # self._save_depth_image(depth_image)
        # end_time0 = time.time()

        # diff_depth_image = raw_depth_image - depth_image
        # diff_color_image = raw_color_image - color_image
        # logger.info(f"[Depth Camera] Diff depth image: {diff_depth_image.sum()}")
        # logger.info(f"[Depth Camera] Diff color image: {diff_color_image.sum()}")
        # logger.info(f"[Depth Camera] Get latest frame time: {end_time0 - start_time0}")

        start_time1 = time.time()
        if self._intr is None:
            logger.warning("Depth camera intrinsics not initialized yet")
            return None

        res = await build_depth_frame_info(
            color_image=color_image,
            depth_image=depth_image,
            intr=self._intr,
            detector=self._detector,
            captioner=self._captioner,
            need_description=need_description,
        )
        end_time1 = time.time()
        logger.debug(
            f"[Depth Camera] Total time to build info: {end_time1 - start_time1}"
        )

        logger.debug(
            f"[Depth Camera] Total time to get latest camera data: {end_time1 - start_time0}"
        )
        return res
    
    def _align_frame(self, frame: rs.composite_frame) -> Tuple[np.ndarray, np.ndarray]:
        """
        Align the frame using the align object.
        """
        aligned_frames = self._align.process(frame)
        color_image = np.asanyarray(aligned_frames.get_color_frame().get_data()).copy()
        depth_image = np.asanyarray(aligned_frames.get_depth_frame().get_data()).copy()
        return color_image, depth_image
    

    def is_healthy(self) -> bool:
        """Return True if the capture thread is alive and pipeline is active."""
        return (
            self._thread is not None
            and self._thread.is_alive()
            and self._pipeline is not None
        )

    def restart(self) -> None:
        """Stop and re-start the capture service."""
        fps = getattr(self, "_last_fps", DEFAULT_FPS)
        self.stop()
        self.start(fps=fps)

    def start(self, fps: int = DEFAULT_FPS) -> None:
        """
        Start the background capture thread if it is not already running.
        """
        with self._config_lock:
            if self._thread is not None and self._thread.is_alive():
                logger.debug("Depth camera background capture thread already running")
                return

            logger.info("Initializing Depth Camera for background capture")
            try:
                if fps <= 0:
                    fps = DEFAULT_FPS
                self._pipeline = rs.pipeline()
                realsense_config = rs.config()

                pipeline_wrapper = rs.pipeline_wrapper(self._pipeline)
                logger.debug("Pipeline wrapper: %s", pipeline_wrapper)
                pipeline_profile = realsense_config.resolve(pipeline_wrapper)
                logger.debug("Pipeline profile: %s", pipeline_profile)
                device = pipeline_profile.get_device()
                logger.debug("Device: %s", device)
                device_product_line = str(device.get_info(rs.camera_info.product_line))
                logger.debug("Device product line: %s", device_product_line)

                found_rgb = False
                for s in device.sensors:
                    logger.debug("Sensor: %s", s)
                    if s.get_info(rs.camera_info.name) == "RGB Camera":
                        found_rgb = True
                        break
                if not found_rgb:
                    msg = "Depth camera requires Color sensor (RGB Camera not found)"
                    logger.error(msg)
                    self._pipeline = None
                    service_registry.register("depth_camera", False, msg)
                    return

                realsense_config.enable_stream(
                    rs.stream.depth,
                    DEPTH_CAMERA_WIDTH,
                    DEPTH_CAMERA_HEIGHT,
                    rs.format.z16,
                    fps,
                )
                realsense_config.enable_stream(
                    rs.stream.color,
                    COLOR_CAMERA_WIDTH,
                    COLOR_CAMERA_HEIGHT,
                    rs.format.bgr8,
                    fps,
                )

                self._align = rs.align(rs.stream.color)
                profile = self._pipeline.start(realsense_config)
                logger.debug("Profile: %s", profile)

                self._intr = (
                    profile.get_stream(rs.stream.color)
                    .as_video_stream_profile()
                    .get_intrinsics()
                )
                logger.debug("Depth camera intrinsics: %s", self._intr)

                # YOLOv8Detector (default use remote)
                custom_classes: list[str] = []
                remote_detector_url = (
                    self._config["remote_detector_url"]
                    if self._config is not None
                    and "remote_detector_url" in self._config
                    else None
                )
                dl_api_key = (
                    self._config["dl_api_key"]
                    if self._config is not None and "dl_api_key" in self._config
                    else None
                )
                logger.debug("=========REMOTE DETECTOR INFO=========")
                logger.debug("Remote detector URL: %s", remote_detector_url)
                logger.debug("Depth camera config: %s", self._config)
                if dl_api_key is not None:
                    logger.debug(
                        "DL API key: %s", dl_api_key[:10] + "..." + dl_api_key[-10:]
                    )
                else:
                    logger.warning("DL API key: None")
                logger.debug("=========DEPTH CAMERA INFO=========")
                self._detector = RemoteYOLOv8Detector(
                    url=remote_detector_url,
                    custom_classes=custom_classes,
                    api_key=dl_api_key,
                )
                logger.debug("Detector: %s", self._detector)
                logger.debug("Captioner: %s", self._captioner)
            except Exception as e:
                logger.error("Failed to initialize depth camera: %s", e)
                self._pipeline = None
                self._align = None
                self._intr = None
                service_registry.register("depth_camera", False, str(e))
                return

            self._last_fps = fps

            with self._latest_frame_lock:
                self._latest_frame = None

            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._capture_loop,
                args=(fps,),
                name="depth_camera_capture_thread",
                daemon=True,
            )
            self._thread.start()
            service_registry.register(
                "depth_camera",
                True,
                extra_data={
                    "device_product_line": device_product_line,
                    "fps": fps,
                    "depth_resolution": f"{DEPTH_CAMERA_WIDTH}x{DEPTH_CAMERA_HEIGHT}",
                    "color_resolution": f"{COLOR_CAMERA_WIDTH}x{COLOR_CAMERA_HEIGHT}",
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

        with self._config_lock:
            if self._pipeline is not None:
                self._pipeline.stop()
            self._pipeline = None
            self._align = None
            self._intr = None
            self._detector = None
            self._captioner = None

        with self._latest_frame_lock:
            self._latest_frame = None
