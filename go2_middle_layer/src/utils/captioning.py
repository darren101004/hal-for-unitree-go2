from abc import ABC, abstractmethod
from PIL import Image
import numpy as np
import requests
import base64
import cv2
import logging

logger = logging.getLogger("RemoteCaptioner")
DEFAULT_REMOTE_CAPTIONER_URL = "http://14.225.217.119:8182/oai-caption"


INSTRUCTION_PROMPT = "'Describe the image in detail, including the objects and their positions. Ignore any blur or unclear parts"


class Captioner(ABC):
    @abstractmethod
    def caption_image(self, img: bytes | Image.Image | np.ndarray) -> str:
        pass


class RemoteCaptioner(Captioner):
    def __init__(
        self,
        url: str = DEFAULT_REMOTE_CAPTIONER_URL,
        instruction_prompt: str = INSTRUCTION_PROMPT,
    ):
        self.url = url
        self.instruction_prompt = instruction_prompt

    def caption_image(self, img: bytes | Image.Image | np.ndarray) -> str:
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

        success, encoded_img = cv2.imencode(
            ".jpg", raw_img, [cv2.IMWRITE_JPEG_QUALITY, 85]
        )
        if not success:
            logger.error("[Remote YOLOv8 Detector] Failed to encode image")
            return []
        bytes_img = encoded_img.tobytes()
        img_base64 = base64.b64encode(bytes_img).decode("utf-8")

        payload = {
            "image_b64": img_base64,
            "instruct": self.instruction_prompt,
        }
        response = requests.post(self.url, json=payload)
        logger.debug(f"Response from {self.url}: {response}")
        if response.status_code != 200:
            logger.error(
                f"Error captioning image: {response.status_code} {response.text}"
            )
            return None

        return response.json()

    def __str__(self):
        return f"RemoteCaptioner(url={self.url}"
