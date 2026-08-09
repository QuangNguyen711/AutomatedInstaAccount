from __future__ import annotations

import asyncio
import io
import urllib.request

import cv2
import numpy as np
from PIL import Image
from ultralytics import YOLO

from backend.domain.ports.image_classifier_provider import ImageClassifierProvider

# best_cls.pt was trained on legacy/datasets/{bad_images,good_images}; ultralytics assigns
# class indices alphabetically by folder name, so index 0 = bad_images, 1 = good_images.
_GOOD_CLASS_INDEX = 1
_FETCH_TIMEOUT_S = 10
# Variance of the Laplacian is a standard cheap blur metric (low variance = few sharp edges =
# blurry); this threshold is an empirical starting point, not derived from this project's data.
_BLUR_VARIANCE_THRESHOLD = 100.0


class YoloClassifierProvider(ImageClassifierProvider):
    def __init__(
        self,
        weights_path: str,
        good_class_index: int = _GOOD_CLASS_INDEX,
        confidence_threshold: float = 0.5,
        blur_variance_threshold: float = _BLUR_VARIANCE_THRESHOLD,
    ):
        self._model = YOLO(weights_path)
        self._good_class_index = good_class_index
        self._confidence_threshold = confidence_threshold
        self._blur_variance_threshold = blur_variance_threshold

    async def is_good(self, image_url: str) -> bool:
        return await asyncio.to_thread(self._classify, image_url)

    def _classify(self, image_url: str) -> bool:
        try:
            image = self._fetch_image(image_url)
            if self._is_blurry(image):
                return False
            # Passing a PIL.Image (rather than the raw URL string) is deliberate: ultralytics
            # sniffs string sources by file extension, and Google's photo URLs have none —
            # it was misdetecting them as video streams and hanging forever waiting for frames.
            result = self._model(image, verbose=False)[0]
            top1 = int(result.probs.top1)
            confidence = float(result.probs.top1conf)
            return top1 == self._good_class_index and confidence >= self._confidence_threshold
        except Exception:
            # fail open: don't hide a photo just because fetch/classification broke
            return True

    def _is_blurry(self, image: Image.Image) -> bool:
        gray = np.array(image.convert("L"))
        variance = cv2.Laplacian(gray, cv2.CV_64F).var()
        return variance < self._blur_variance_threshold

    @staticmethod
    def _fetch_image(image_url: str) -> Image.Image:
        request = urllib.request.Request(image_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(request, timeout=_FETCH_TIMEOUT_S) as response:
            data = response.read()
        return Image.open(io.BytesIO(data)).convert("RGB")
