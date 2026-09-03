#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
智能选图模块。

为每个笔记片段从视频中挑选一张最具信息量的画面。
"""

import os
from abc import ABC, abstractmethod
from typing import List, Optional, Tuple

import imagehash
import numpy as np
from PIL import Image


def _frame_at_time(video_path: str, t: float) -> Image.Image:
    """使用 moviepy 获取指定时间点的帧，自动限制在视频有效时长内。"""
    from moviepy import VideoFileClip

    clip = VideoFileClip(video_path)
    try:
        duration = float(clip.duration or 0)
        if duration > 0:
            # 留出少量边界，避免 moviepy 在最后一帧处回退警告
            t = max(0.0, min(t, duration - 0.05))
        frame = clip.get_frame(t)
    finally:
        clip.close()
    return Image.fromarray(frame)


def _brightness_variance(img: Image.Image) -> float:
    """计算图像亮度方差，方差越大通常画面内容越丰富。"""
    gray = img.convert("L")
    arr = np.array(gray, dtype=np.float32)
    return float(np.var(arr))


class BaseFrameSelector(ABC):
    """帧选择器接口。"""

    @abstractmethod
    def select(
        self,
        video_path: str,
        start_time: float,
        end_time: float,
        sample_count: int = 5,
    ) -> Optional[Tuple[float, Image.Image]]:
        """
        从 [start_time, end_time] 区间中选择最佳帧。

        Returns:
            (best_time, best_image) 或 None。
        """
        raise NotImplementedError


class VisualChangeSelector(BaseFrameSelector):
    """
    基于画面变化和亮度方差选择最佳帧。

    适合 PPT/教程类视频：画面切换处往往对应新的知识点。
    """

    def __init__(self, change_weight: float = 1.0, variance_weight: float = 0.001):
        self.change_weight = change_weight
        self.variance_weight = variance_weight

    def select(
        self,
        video_path: str,
        start_time: float,
        end_time: float,
        sample_count: int = 5,
    ) -> Optional[Tuple[float, Image.Image]]:
        if not os.path.exists(video_path):
            return None

        duration = end_time - start_time
        if duration <= 0:
            sample_times = [start_time]
        else:
            sample_times = [
                start_time + duration * i / (sample_count - 1)
                for i in range(sample_count)
            ]

        candidates: List[Tuple[float, Image.Image, float]] = []
        prev_hash = None

        for t in sample_times:
            try:
                img = _frame_at_time(video_path, t)
            except Exception:
                continue

            current_hash = imagehash.phash(img)
            change_score = 0
            if prev_hash is not None:
                change_score = abs(current_hash - prev_hash)
            variance_score = _brightness_variance(img)

            score = self.change_weight * change_score + self.variance_weight * variance_score
            candidates.append((t, img, score))
            prev_hash = current_hash

        if not candidates:
            return None

        # 选择综合评分最高的帧
        best = max(candidates, key=lambda x: x[2])
        return best[0], best[1]


class OCRFrameSelector(BaseFrameSelector):
    """
    基于 OCR 文字数量选择最佳帧。

    需要安装可选依赖：
        pip install easyocr

    有文字的帧（如 PPT 页面、代码界面）通常信息量更大。
    """

    def __init__(self, reader=None):
        self.reader = reader
        if self.reader is None:
            try:
                import easyocr

                self.reader = easyocr.Reader(["ch_sim", "en"], gpu=False)
            except Exception as exc:
                raise RuntimeError(
                    "OCRFrameSelector 需要 easyocr，请运行：pip install easyocr"
                ) from exc

    def _text_score(self, img: Image.Image) -> int:
        """返回画面中检测到的文字字符总数。"""
        result = self.reader.readtext(np.array(img))
        return sum(len(item[1]) for item in result)

    def select(
        self,
        video_path: str,
        start_time: float,
        end_time: float,
        sample_count: int = 5,
    ) -> Optional[Tuple[float, Image.Image]]:
        if not os.path.exists(video_path):
            return None

        duration = end_time - start_time
        if duration <= 0:
            sample_times = [start_time]
        else:
            sample_times = [
                start_time + duration * i / (sample_count - 1)
                for i in range(sample_count)
            ]

        candidates: List[Tuple[float, Image.Image, int]] = []
        for t in sample_times:
            try:
                img = _frame_at_time(video_path, t)
                score = self._text_score(img)
                candidates.append((t, img, score))
            except Exception:
                continue

        if not candidates:
            return None

        best = max(candidates, key=lambda x: x[2])
        return best[0], best[1]


def create_frame_selector(method: str = "visual") -> BaseFrameSelector:
    """工厂函数，按名称创建帧选择器。"""
    method = method.lower()
    if method == "visual":
        return VisualChangeSelector()
    if method == "ocr":
        return OCRFrameSelector()
    raise ValueError(f"不支持的选图方法：{method}，可选 visual/ocr")
