from pathlib import Path

from ultralytics import YOLO, YOLOWorld

import logging
import cv2
from PIL import Image
import time
import numpy as np

from utils.yolov8.base import ObjectDetector

logger = logging.getLogger("YOLOv8Detector")
DEFAULT_LOCAL_DETECTOR_MODEL_PATH = "resources/yolov8s.pt"


def _resolve_model_path(path: str) -> str:
    """Resolve relative model path to src/ directory."""
    p = Path(path)
    if p.is_absolute():
        return path
    src_dir = Path(__file__).resolve().parent.parent.parent
    return str((src_dir / path).resolve())


class YOLOv8Detector(ObjectDetector):
    def __init__(
        self, model_path: str = DEFAULT_LOCAL_DETECTOR_MODEL_PATH, custom_classes=None
    ):
        super().__init__()
        t0 = time.time()
        self.model_path = _resolve_model_path(model_path)
        self.custom_classes = custom_classes

        logger.info(f"Loading model from {self.model_path} ...")
        if custom_classes:
            self.model = YOLOWorld(self.model_path)
            logger.info(f"Using YOLOWorld model: {self.model}")
        else:
            self.model = YOLO(self.model_path)
            logger.info(f"Using YOLO model: {self.model}")
        logger.info(f"Model loaded in {time.time() - t0:.4f}s")

        default_classes = list(self.model.names.values())
        logger.debug(f"Default classes: {default_classes}")
        logger.debug(f"Custom classes: {self.class_names}")
        self.class_names = list(set(default_classes + self.class_names))
        if custom_classes is not None:
            self.class_names = self.class_names + list(custom_classes)
            self.model.set_classes(self.class_names)

    def __str__(self):
        return f"YOLOv8Detector(model_path={self.model_path}), class_names={self.class_names}"

    def detect_image(self, img: bytes | Image.Image | np.ndarray):
        logger.debug("Starting detection on image...")
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

        t0 = time.time()
        results = self.model(raw_img, stream=False)
        logger.debug(f"Detection done in {time.time() - t0:.4f}s")
        if not results or not hasattr(results[0], "boxes") or results[0].boxes is None:
            return None

        out = []
        boxes_obj = results[0].boxes.xyxyn.cpu().numpy().tolist()
        class_idx = results[0].boxes.cls.cpu().numpy().tolist()
        for box, class_idx in zip(boxes_obj, class_idx):
            class_name = (
                self.class_names[int(class_idx)]
                if int(class_idx) < len(self.class_names)
                else "unknown"
            )
            out.append({"name": class_name, "xyxyn": box})
        return out
