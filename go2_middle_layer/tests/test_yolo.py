import os
import sys
from typing import Any, Dict, List

import cv2
import numpy as np
import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_ROOT = os.path.join(PROJECT_ROOT, "src")
if SRC_ROOT not in sys.path:
    sys.path.append(SRC_ROOT)

from utils.yolov8.yolov8_remote_detector import RemoteYOLOv8Detector  # noqa: E402


DEFAULT_REMOTE_DETECTOR_URL = "https://956x9guslla3pa-64411556-8888.proxy.runpod.net/api/dl/yoloworld"
DL_API_KEY = "doggi-dl-aSmceRCKIltWclb0lEmnt8X4yWRrjpVjpPDcafeGDY6I5mGrsfDSEfdrhn6ohylIJhd34ZU_1_5Og6lXP9b-_g"


def _make_dummy_image(height: int = 100, width: int = 200) -> np.ndarray:
    """
    Create a dummy RGB image for testing.

    Args:
        height: Image height in pixels.
        width: Image width in pixels.

    Returns:
        Numpy RGB image array.
    """

    return np.zeros((height, width, 3), dtype=np.uint8)


def test_remote_yolov8_detector_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Verify that RemoteYOLOv8Detector sends the correct request and parses the response.

    The detector should:
    - Encode the image and send it as base64 to the configured URL.
    - Include the API key in the X-API-KEY header when provided.
    - Convert xywh detections to normalized xyxyn format.
    """

    captured: Dict[str, Any] = {}

    class DummyResponse:
        status_code = 200

        @staticmethod
        def json() -> List[Dict[str, Any]]:
            # Single detection centered in the image.
            return [
                {
                    "class_name": "person",
                    "xywh": [100.0, 50.0, 40.0, 20.0],
                }
            ]

    def fake_post(url: str, json: Dict[str, Any], headers: Dict[str, str], timeout: int) -> DummyResponse:  # type: ignore[override]
        captured["url"] = url
        captured["json"] = json
        captured["headers"] = headers
        captured["timeout"] = timeout
        return DummyResponse()

    monkeypatch.setattr(
        "src.utils.yolov8.yolov8_remote_detector.requests.post",
        fake_post,
    )

    detector = RemoteYOLOv8Detector(
        url=DEFAULT_REMOTE_DETECTOR_URL,
        custom_classes=["person", "chair", "mirror"],
        api_key=DL_API_KEY,
    )

    img = _make_dummy_image(height=100, width=200)
    detections = detector.detect_image(img)

    assert captured["url"] == DEFAULT_REMOTE_DETECTOR_URL
    assert captured["headers"]["X-API-KEY"] == DL_API_KEY
    assert "image_b64" in captured["json"]
    assert captured["json"]["classes"] == ["person", "chair", "mirror"]

    assert detections is not None
    assert len(detections) == 1
    det = detections[0]
    assert det["name"] == "person"

    # Expected normalized coordinates for xywh = [100, 50, 40, 20] on 200x100 image.
    expected_x1 = 0.4
    expected_y1 = 0.4
    expected_x2 = 0.6
    expected_y2 = 0.6

    x1, y1, x2, y2 = det["xyxyn"]
    assert pytest.approx(x1, rel=1e-6) == expected_x1
    assert pytest.approx(y1, rel=1e-6) == expected_y1
    assert pytest.approx(x2, rel=1e-6) == expected_x2
    assert pytest.approx(y2, rel=1e-6) == expected_y2


def test_remote_yolov8_detector_non_200_response(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Verify that RemoteYOLOv8Detector returns None on non-200 HTTP responses.
    """

    class DummyResponse:
        status_code = 500

        @staticmethod
        def json() -> List[Dict[str, Any]]:
            return []

        text = "server error"

    def fake_post(*_: Any, **__: Any) -> DummyResponse:  # type: ignore[override]
        return DummyResponse()

    monkeypatch.setattr(
        "src.utils.yolov8.yolov8_remote_detector.requests.post",
        fake_post,
    )

    detector = RemoteYOLOv8Detector(
        url=DEFAULT_REMOTE_DETECTOR_URL,
        custom_classes=["person", "chair", "mirror"],
        api_key=DL_API_KEY,
    )

    img = _make_dummy_image()
    detections = detector.detect_image(img)

    assert detections is None


def test_remote_yolov8_detector_with_real_image(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Verify that RemoteYOLOv8Detector can process a real JPEG image (img3.jpg).

    This test focuses on the image loading and encoding path while still
    mocking the remote HTTP call.
    """

    class DummyResponse:
        status_code = 200

        @staticmethod
        def json() -> List[Dict[str, Any]]:
            return []

    def fake_post(*_: Any, **__: Any) -> DummyResponse:  # type: ignore[override]
        return DummyResponse()

    monkeypatch.setattr(
        "utils.yolov8.yolov8_remote_detector.requests.post",
        fake_post,
    )

    detector = RemoteYOLOv8Detector(
        url="http://example.com/detect",
        custom_classes=["person", "chair", "mirror"],
        api_key="secret-key",
    )

    img_path = os.path.join(os.path.dirname(__file__), "img3.jpg")
    cv_img = cv2.imread(img_path)
    assert cv_img is not None, "Failed to load img3.jpg for YOLO test"

    # Use the raw numpy image to exercise the ndarray code path.
    detections = detector.detect_image(cv_img)

    # With DummyResponse.json() returning empty list, we expect empty detections.
    assert detections == []