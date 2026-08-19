import logging
from PIL import Image
import numpy as np
import base64
import requests

import cv2

from utils.yolov8.base import ObjectDetector

logger = logging.getLogger("RemoteYOLOv8Detector")


class RemoteYOLOv8Detector(ObjectDetector):
    def __init__(self, url: str = None, custom_classes=None, api_key: str = None):
        super().__init__()
        self.url = url
        self.custom_classes = custom_classes
        self.class_names = list(set(self.class_names + custom_classes))
        self._api_key = api_key

    def detect_image(self, img: bytes | Image.Image | np.ndarray) -> list[dict]:
        img_height = img_width = None

        raw_img = None
        if isinstance(img, np.ndarray):
            raw_img = img
        elif isinstance(img, Image.Image):
            raw_img = np.array(img.convert("RGB"))[:, :, ::-1]
        elif isinstance(img, bytes):
            raw_img = np.frombuffer(img, np.uint8)
            raw_img = cv2.imdecode(raw_img, cv2.IMREAD_COLOR)
        else:
            raise ValueError(f"Invalid image type: {type(img)}")

        img_height, img_width = raw_img.shape[:2]
        success, encoded_img = cv2.imencode(
            ".jpg", raw_img, [cv2.IMWRITE_JPEG_QUALITY, 85]
        )
        if not success:
            logger.error("[Remote YOLOv8 Detector] Failed to encode image")
            return None
        bytes_img = encoded_img.tobytes()
        img_b64 = base64.b64encode(bytes_img).decode("utf-8")

        # Hardcoded classes as requested by prompt
        payload = {
            "image_b64": img_b64,
            "classes": ["person", "chair", "mirror"],
        }
        logger.debug(
            f"Sending payload to {self.url} with {len(payload['classes'])} classes"
        )
        headers = {"X-API-KEY": self._api_key}
        try:
            response = requests.post(self.url, json=payload, headers=headers, timeout=5)
        except requests.exceptions.Timeout:
            logger.error(f"Timeout when requesting {self.url}")
            return None
        except Exception as e:
            logger.error(f"Error when requesting {self.url}: {e}")
            return None
        logger.debug(f"Response from {self.url}: {response}")
        if response.status_code != 200:
            logger.error(
                f"Error detecting image: {response.status_code} {response.text}"
            )
            return None
        struct_content = response.json()
        out = []
        for item in struct_content:
            name = item["class_name"]
            xc, yc, w, h = item["xywh"]
            x1 = (xc - w / 2) / img_width
            y1 = (yc - h / 2) / img_height
            x2 = (xc + w / 2) / img_width
            y2 = (yc + h / 2) / img_height
            xyxyn = [x1, y1, x2, y2]

            out.append(
                {
                    "name": name,
                    "xyxyn": xyxyn,
                }
            )
        return out

    def __str__(self):
        return f"RemoteYOLOv8Detector(url={self.url}, custom_classes={self.custom_classes})"
