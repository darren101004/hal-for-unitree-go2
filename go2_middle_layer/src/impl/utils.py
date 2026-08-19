import logging
import math
import time
from typing import List, Tuple, Optional, Dict, Any
from datetime import datetime, timedelta, timezone

import numpy as np
import pyrealsense2 as rs
import cv2

from utils.captioning import Captioner
from utils.yolov8.base import ObjectDetector


logger = logging.getLogger("Utils")
GMT_PLUS_7 = timezone(timedelta(hours=7))


def get_timestamp() -> str:
    return datetime.now(GMT_PLUS_7).strftime("%Y-%m-%d %H:%M:%S")


def estimate_position(
    distance: float,  # in millimeters
    depth_camera_coordinates: Tuple[
        int, int
    ],  # pixel coordinates in depth camera image
    camera_intrinsics: rs.intrinsics,
    theta: float = 0,  # in radians
) -> Tuple[float, float, float]:  # x, y, z in millimeters
    """
    Estimate the position of the object in the world coordinates.
    """
    u_depth, v_depth = depth_camera_coordinates

    x_temp = distance * (u_depth - camera_intrinsics.ppx) / camera_intrinsics.fx
    y_temp = distance * (v_depth - camera_intrinsics.ppy) / camera_intrinsics.fy
    z_temp = distance

    x_target = x_temp - 35  # Compensate 35mm offset on X axis
    y_target = -(z_temp * math.sin(theta) + y_temp * math.cos(theta))
    z_target = z_temp * math.cos(theta) + y_temp * math.sin(theta)
    return x_target, y_target, z_target


def get_angle_and_distance(x: float, y: float, z: float) -> Tuple[float, float]:
    distance = math.sqrt(x**2 + z**2)  # Using X-Z plane to calculate distance
    angle = math.degrees(math.atan2(abs(x), abs(z)))
    return distance, angle  # distance in millimeters, angle in degrees


def get_natural_language_description(
    objects: List[Dict[str, Any]],
    caption_info: Optional[Dict[str, Any]] = None,
    far_objects: List[Dict[str, Any]] = None,
) -> str:

    timestamp = get_timestamp()
    res = "At " + timestamp + ":\n"

    caption = caption_info["caption"] if caption_info else "No caption provided"
    if caption_info is not None:
        res += "The image is described as: " + caption + ".\n"

    if objects is not None and len(objects) > 0:
        res += (
            "Some objects which are closer to you are detected in the image. You can use these objects to "
            "estimate the position of the objects in the image."
        )
        cnt = 0
        for obj in objects:
            x, y, z = obj["coordinates"]
            distance, angle = get_angle_and_distance(x, y, z)
            distance = int(distance / 10)  # convert to centimeters
            is_left = x < 0
            res += f"\n{cnt + 1}. {obj['name']} at {distance} centimeters,"
            if abs(angle) > 85 or abs(angle) < 5:
                res += "directly in front of the center."
            else:
                res += f" {int(angle)} degrees to the {'left' if is_left else 'right'} of the center."
            cnt += 1

    if far_objects is not None and len(far_objects) > 0:
        far_objects_names = set([obj["name"] for obj in far_objects])
        res += (
            "\nIn the far range, there are some objects such as: "
            + ", ".join(far_objects_names)
            + "."
        )
    res += "\nNOTE: Some objects may be not detected correctly due to the limited field of view of the camera, and with any movement of the robot, must carefully consider the position of the objects for avoiding collisions."
    return res


async def build_depth_frame_info(
    color_image: np.ndarray,
    depth_image: np.ndarray,
    intr: rs.intrinsics,
    detector: Optional[ObjectDetector] = None,
    captioner: Optional[Captioner] = None,
    need_description: bool = False,
) -> Optional[Tuple[Dict[str, Any], bytes]]:
    """
    Input:
    - color_image: np.ndarray, BGR image (height, width, 3)
    - depth_image: np.ndarray, depth in millimeters (height, width)
    - intr: rs.intrinsics, camera intrinsics
    - detector: ObjectDetector, object detector
    - captioner: Captioner, image captioner
    Output:
    - info: Dict[str, Any], information about the detected objects
    - img_bytes: bytes, PNG image of the detected objects
    """
    from asyncio import gather, to_thread




    # color_rgb_image = color_image[:, :, ::-1]
    # img_pil = Image.fromarray(color_rgb_image)

    # DETECT OBJECTS AND CAPTION IMAGE
    detected_objects: List[Dict[str, Any]] = []
    caption_info: Optional[Dict[str, Any]] = None

    start_time = time.time()
    if not need_description:
        success, img_bytes = cv2.imencode(
            ".jpg", color_image, [cv2.IMWRITE_JPEG_QUALITY, 85]
        )
        if not success:
            logger.error("[Depth Camera] Failed to encode image")
            return None
        img_bytes = img_bytes.tobytes()
        info: Dict[str, Any] = {
            "success": True,
            "message": "Successfully captured a frame from depth camera",
            "data": {},
        }
        return info, img_bytes
    tasks = []
    if detector is not None:
        tasks.append(to_thread(detector.detect_image, color_image))
    if captioner is not None:
        tasks.append(to_thread(captioner.caption_image, color_image))

    if tasks:
        results = await gather(*tasks)
        if len(results) == 0:
            logger.error("[Depth Camera] No results from tasks")
            return None
        if detector is not None and captioner is not None:
            detected_objects, caption_info = results
            logger.debug(
                "Detecting objects and captioning image using detector: %s and captioner: %s",
                detector,
                captioner,
            )
            logger.debug("Detected objects: %d", len(detected_objects))
            logger.debug("Caption: %s", caption_info)
        elif detector is not None:
            detected_objects = results[0]
        elif captioner is not None:
            caption_info = results[0]

    end_time = time.time()
    logger.debug(
        f"[Depth Camera] Detect objects and caption image time: {end_time - start_time}"
    )

    detected_objects_local = detected_objects
    caption_info_local = caption_info
    color_image_local = color_image
    intr_local = intr

    def _compute_description_and_encode() -> Optional[Tuple[Dict[str, Any], bytes]]:
        processed_objects: List[Dict[str, Any]] = []
        far_objects: List[Dict[str, Any]] = []

        height, width = depth_image.shape[0], depth_image.shape[1]
        if detected_objects_local is not None:
            logger.debug(
                "[Depth Camera] Detected %d objects",
                len(detected_objects_local),
            )
            for detected_object in detected_objects_local:
                x_min_norm, y_min_norm, x_max_norm, y_max_norm = detected_object[
                    "xyxyn"
                ]
                x_min, x_max = int(x_min_norm * width), int(x_max_norm * width)
                y_min, y_max = int(y_min_norm * height), int(y_max_norm * height)
                x_min, y_min = max(0, x_min), max(0, y_min)
                x_max, y_max = min(width - 1, x_max), min(height - 1, y_max)

                u_depth, v_depth = int((x_min + x_max) / 2), int((y_min + y_max) / 2)

                start_cv = time.time()
                roi = depth_image[y_min:y_max, x_min:x_max].astype(np.float32)
                roi[roi < 0] = 0

                wo, ho = x_max - x_min, y_max - y_min
                kernel_w, kernel_h = max(1, wo // 4), max(1, ho // 4)

                mean_depth_map = cv2.boxFilter(
                    src=roi,
                    ddepth=-1,
                    ksize=(kernel_w, kernel_h),
                    normalize=True,
                    borderType=cv2.BORDER_REFLECT_101,
                )
                sampled_depths = mean_depth_map[::kernel_h, ::kernel_w]
                valid_depths = sampled_depths[sampled_depths > 0]

                if valid_depths.size == 0:
                    dist_to_object = float(depth_image[v_depth, u_depth])
                else:
                    dist_to_object = float(np.min(valid_depths))

                logger.debug(
                    "[Depth Camera] Valid depths using CV filter: %s in %s seconds",
                    dist_to_object,
                    time.time() - start_cv,
                )

                if dist_to_object > 6000:
                    far_objects.append(detected_object)
                    continue

                x, y, z = estimate_position(
                    dist_to_object, (u_depth, v_depth), intr_local
                )
                processed_objects.append(
                    {
                        "name": detected_object["name"],
                        "xyxyn": detected_object["xyxyn"],
                        "xyxy": (x_min, y_min, x_max, y_max),
                        "distance_to_object": int(dist_to_object),
                        "coordinates": [x, y, z],
                    }
                )

            processed_objects.sort(key=lambda obj: obj["distance_to_object"])

            unique_counts: dict[str, int] = {}
            for obj in processed_objects:
                base_name = obj["name"]
                if base_name in unique_counts:
                    unique_counts[base_name] += 1
                    obj["name"] = f"{base_name}_{unique_counts[base_name]}"
                else:
                    unique_counts[base_name] = 1
                    obj["name"] = f"{base_name}_1"
        else:
            logger.debug("[Depth Camera] No objects detected.")

        success, out_img_bytes = cv2.imencode(
            ".jpg",
            color_image_local,
            [cv2.IMWRITE_JPEG_QUALITY, 85],
        )
        if not success:
            logger.error("[Depth Camera] Failed to encode image")
            return None

        img_bytes = out_img_bytes.tobytes()
        natural_language_description = get_natural_language_description(
            processed_objects, caption_info_local, far_objects
        )

        info: Dict[str, Any] = {
            "success": True,
            "message": "Successfully captured a frame from depth camera",
            "data": {
                "objects": processed_objects,
                "natural_language_description": natural_language_description,
            },
        }
        return info, img_bytes

    return await to_thread(_compute_description_and_encode)
