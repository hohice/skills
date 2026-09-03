#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
智能双轨视频笔记生成器 (Intelligent Dual-Track Video Note Generator)

Phase 1: 轻量级字幕探测
    使用 Playwright 拦截视频页面网络请求，尝试获取原生 CC / UP主 字幕 JSON。

Phase 2: 重量级兜底处理
    若 Phase 1 失败，使用 yt-dlp 下载视频，并行执行 Whisper ASR 与 pHash 视觉
    PPT 翻页检测，并将两者时间对齐生成结构化笔记。

Phase 3: 学习笔记生成
    使用 LLM/规则摘要把口语化 ASR 文本提炼成结构化知识点，
    默认输出为「单文件 OKF 文档（嵌入截图）」，也可选择「OKF v0.2 笔记包」或「单文件 PDF 讲义」。
"""

import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import imagehash
import imageio_ffmpeg

# Whisper 调用 ffmpeg 命令时需要它在 PATH 中
_ffmpeg_bin = imageio_ffmpeg.get_ffmpeg_exe()
_ffmpeg_dir = os.path.dirname(_ffmpeg_bin)
if _ffmpeg_dir and os.path.exists(_ffmpeg_dir):
    os.environ["PATH"] = _ffmpeg_dir + os.pathsep + os.environ.get("PATH", "")
    # imageio_ffmpeg 提供的二进制文件名带平台后缀，Whisper 只认 "ffmpeg"
    _ffmpeg_link = os.path.join(_ffmpeg_dir, "ffmpeg")
    if not shutil.which("ffmpeg") and not os.path.exists(_ffmpeg_link):
        os.symlink(_ffmpeg_bin, _ffmpeg_link)

import whisper
from PIL import Image
from moviepy import VideoFileClip
from playwright.sync_api import sync_playwright

import frame_selector
import summarizers

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

try:
    import yt_dlp
except ImportError:  # pragma: no cover
    yt_dlp = None


# OKF note-taking skill CLI helper path (sibling skill directory)
_OKF_SKILL_DIR = Path(__file__).resolve().parent.parent.parent / "okf-note-taking"
OKF_NOTES_CLI = _OKF_SKILL_DIR / "scripts" / "okf_notes.py"


def _load_okf_notes() -> Any:
    """Load the okf-note-taking helper module without relying on sys.path."""
    spec = importlib.util.spec_from_file_location("okf_notes", OKF_NOTES_CLI)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载 OKF 笔记模块：{OKF_NOTES_CLI}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


okf_notes = _load_okf_notes()


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _safe_filename(name: str) -> str:
    """把标题转换成可用的文件名，保留中文等 Unicode 字符。"""
    name = name.strip().replace(" ", "-")
    # 移除常见文件系统危险字符和控制字符
    name = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "", name)
    # 合并连续连字符/下划线
    name = re.sub(r"[-_]+", "-", name)
    name = name.strip("-")
    # 限制长度，避免文件名过长
    return name[:80].lower() or "note"


def _build_concept_document(meta: Dict[str, Any], body: str = "") -> str:
    """把 frontmatter 和 body 组装成完整 OKF 概念文档。

    实际序列化逻辑复用 okf-note-taking/scripts/okf_notes.py 中的实现，
    保证两个 skill 产出的 frontmatter 风格一致。
    """
    return okf_notes.build_concept_document(meta, body, flow_style=False)


class VideoNoteGenerator:
    """
    双轨视频笔记生成器。

    优先尝试低成本的在线字幕提取；失败时自动降级到高成本的本地 ASR + 视觉分析。
    最终通过摘要生成结构化学习笔记，默认输出单文件 OKF 文档（嵌入截图），也支持 OKF v0.2 笔记包或单文件 PDF 讲义。
    """

    def __init__(
        self,
        video_url: str,
        output_path: Optional[str] = None,
        browser_data_dir: str = "./browser_data",
        whisper_model: str = "base",
        slide_hash_threshold: int = 5,
        sample_interval: int = 1,
        headless: bool = True,
        subtitle_timeout: int = 10,
        download_dir: str = "./downloads",
        summarizer_method: str = "rule",
        output_format: str = "okf-doc",
        notes_dir: Optional[str] = None,
        frame_selector_method: str = "visual",
        screenshot_dir: str = "./screenshots",
        reuse_existing: bool = False,
        granularity: str = "video",
    ):
        self.video_url = video_url
        self.output_path = output_path
        self.browser_data_dir = browser_data_dir
        self.whisper_model = whisper_model
        self.slide_hash_threshold = slide_hash_threshold
        self.sample_interval = sample_interval
        self.headless = headless
        self.subtitle_timeout = subtitle_timeout
        self.download_dir = download_dir
        self.summarizer_method = summarizer_method
        self.output_format = output_format.lower()
        self.frame_selector_method = frame_selector_method
        self.screenshot_dir = Path(screenshot_dir)
        self.reuse_existing = reuse_existing
        self.granularity = granularity.lower()
        self._notes_dir_override = notes_dir

        self.subtitle_data: Optional[List[Dict[str, Any]]] = None
        self.video_path: Optional[str] = None
        self.video_title: Optional[str] = None

        # 派生输出路径，在获取到视频标题后解析
        self.summary_path: Optional[str] = None
        self.pdf_path: Optional[str] = None
        self.llm_prompt_path: Optional[str] = None
        self.okf_bundle_dir: Optional[Path] = None
        self.okf_doc_path: Optional[Path] = None
        self.okf_doc_assets_dir: Optional[Path] = None

        self._summarizer: Optional[summarizers.BaseSummarizer] = None
        self._frame_selector: Optional[frame_selector.BaseFrameSelector] = None

    # 浏览器 Cookie 候选（按 macOS 常见程度排列）
    _BROWSER_COOKIE_CANDIDATES: List[Tuple[str, Optional[str]]] = [
        ("safari", None),
        ("chrome", None),
        ("edge", None),
        ("firefox", None),
    ]

    def _get_video_title(self) -> str:
        """从视频页面或 yt-dlp 元数据获取视频标题。

        对 Bilibili 等站点，无 Cookie 时可能 412，因此会依次尝试默认请求头
        及各浏览器 Cookie，直到成功获取标题。
        """
        if self.video_title is not None:
            return self.video_title

        def _try_title(opts: Dict[str, Any]) -> Optional[str]:
            if yt_dlp is None:
                return None
            try:
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(self.video_url, download=False)
                    title = info.get("title", "").strip()
                    if title and not title.lower().startswith("http"):
                        return title
            except Exception:
                pass
            return None

        base_opts: Dict[str, Any] = {
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "headers": {
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/127.0.0.0 Safari/537.36"
                ),
                "Referer": (
                    "https://www.bilibili.com/"
                    if "bilibili" in self.video_url.lower()
                    else self.video_url
                ),
            },
        }

        title = _try_title(base_opts)
        if title:
            self.video_title = title
            return title

        for browser_name, profile in self._BROWSER_COOKIE_CANDIDATES:
            opts = dict(base_opts)
            opts["cookiesfrombrowser"] = (browser_name, profile)
            title = _try_title(opts)
            if title:
                print(f"[*] 使用 {browser_name} Cookie 获取到视频标题：{title}")
                self.video_title = title
                return title

        # 兜底：从 URL 提取一个可读名称
        self.video_title = _safe_filename(self.video_url).replace("-", " ").title() or "Video Notes"
        return self.video_title

    def _resolve_output_paths(self, title: str) -> None:
        """根据视频标题或用户指定路径解析所有输出文件路径。"""
        if self.output_path is None:
            base = _safe_filename(title) or "notes"
            self.output_path = base + ".json"

        output_base = Path(self.output_path).with_suffix("")
        self.summary_path = str(output_base) + "_summary.json"
        self.pdf_path = str(output_base) + "_study_notes.pdf"
        self.llm_prompt_path = str(output_base) + "_llm_prompt.md"
        self.okf_bundle_dir = (
            Path(self._notes_dir_override)
            if self._notes_dir_override
            else Path(str(output_base) + "_notes")
        )
        self.okf_doc_path = Path(str(output_base) + "_okf.md")
        self.okf_doc_assets_dir = Path(str(output_base) + "_okf_assets")

    def _get_summarizer(self) -> summarizers.BaseSummarizer:
        if self._summarizer is None:
            self._summarizer = summarizers.create_summarizer(self.summarizer_method)
        return self._summarizer

    def _get_frame_selector(self) -> frame_selector.BaseFrameSelector:
        if self._frame_selector is None:
            self._frame_selector = frame_selector.create_frame_selector(
                self.frame_selector_method
            )
        return self._frame_selector

    # ==================== Phase 1: 字幕探测 ====================

    def _check_subtitle(self, page) -> bool:
        """尝试拦截页面中的字幕 JSON 数据。

        对不支持或响应慢的视频站点（如 YouTube），探测失败不会阻断流程，
        调用方会降级到本地 ASR + 视觉检测。
        """

        def handle_response(response):
            if self.subtitle_data is not None:
                return

            url = response.url.lower()
            content_type = response.headers.get("content-type", "").lower()

            # 启发式规则：URL 包含 subtitle 且返回 JSON
            if "subtitle" not in url or "json" not in content_type:
                return

            try:
                data = response.json()
            except Exception:
                return

            # 兼容两种常见格式：{"body": [...]} 或直接 [...]
            if isinstance(data, dict) and isinstance(data.get("body"), list):
                self.subtitle_data = data["body"]
            elif isinstance(data, list):
                self.subtitle_data = data

        page.on("response", handle_response)
        try:
            # 对 YouTube 等站点，networkidle 可能永远等不到，使用 load 更宽松
            page.goto(
                self.video_url,
                wait_until="load",
                timeout=max(self.subtitle_timeout * 1000, 15000),
            )
        except Exception as exc:
            print(f"[!] 字幕探测页面加载失败：{exc}", file=sys.stderr)
            return False

        # 等待字幕接口返回数据
        deadline = time.time() + self.subtitle_timeout
        while time.time() < deadline and self.subtitle_data is None:
            time.sleep(0.5)

        return self.subtitle_data is not None

    def _format_subtitle_notes(self) -> List[Dict[str, Any]]:
        """将原生字幕统一为最终输出结构。"""
        notes: List[Dict[str, Any]] = []
        for i, item in enumerate(self.subtitle_data or []):
            content = item.get("content", "")
            if isinstance(content, dict):
                content = content.get("text", "")
            start = item.get("from", item.get("start", 0.0))
            notes.append(
                {
                    "slide": i + 1,
                    "time": float(start),
                    "content": str(content).strip(),
                }
            )
        return notes

    # ==================== Phase 2: 兜底处理 ====================

    def _download_video(self) -> str:
        """使用 yt-dlp 下载视频源文件，若已存在则直接复用。

        对 Bilibili 等需要登录态或反爬的站点，会尝试从浏览器读取 Cookie、
        设置常见请求头，并在失败时重试。若最终仍失败但本地有同名缓存，
        则回退使用缓存文件。
        """
        if yt_dlp is None:
            raise RuntimeError(
                "yt-dlp 未安装，无法执行兜底下载。请运行：pip install yt-dlp"
            )

        os.makedirs(self.download_dir, exist_ok=True)

        base_opts: Dict[str, Any] = {
            "format": "bestvideo[height<=720][vcodec^=avc1]+bestaudio[ext=m4a]/best[height<=720]",
            "outtmpl": os.path.join(self.download_dir, "%(id)s.%(ext)s"),
            "merge_output_format": "mp4",
            "ffmpeg_location": imageio_ffmpeg.get_ffmpeg_exe(),
            "quiet": False,
            "no_warnings": False,
            "noplaylist": True,
            "headers": {
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/127.0.0.0 Safari/537.36"
                ),
                "Referer": (
                    "https://www.bilibili.com/"
                    if "bilibili" in self.video_url.lower()
                    else self.video_url
                ),
            },
        }

        last_exc: Optional[Exception] = None
        info: Optional[Dict[str, Any]] = None
        video_path: Optional[str] = None

        # 先不带 Cookie 尝试，再依次尝试各浏览器 Cookie
        attempts: List[Optional[Tuple[str, Optional[str]]]] = [None] + self._BROWSER_COOKIE_CANDIDATES
        for attempt in attempts:
            ydl_opts = dict(base_opts)
            if attempt is not None:
                browser_name, profile = attempt
                ydl_opts["cookiesfrombrowser"] = (browser_name, profile)
                print(f"[*] 尝试使用 {browser_name} 浏览器 Cookie 下载...")

            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(self.video_url, download=False)
                    video_path = ydl.prepare_filename(info)

                    if os.path.exists(video_path):
                        print(f"[*] 检测到已下载视频，直接复用：{video_path}")
                    else:
                        print("[*] 开始下载视频...")
                        ydl.download([self.video_url])

                    if os.path.exists(video_path):
                        self.video_path = video_path
                        return video_path
            except Exception as exc:
                last_exc = exc
                print(f"[!] 本次下载尝试失败：{exc}", file=sys.stderr)
                # 若目标文件已部分生成，清理掉，避免下次误判为"已存在"
                if video_path and os.path.exists(video_path):
                    try:
                        os.remove(video_path)
                    except OSError:
                        pass
                continue

        # 所有尝试都失败：若本地有同视频 ID 的缓存文件则回退使用
        if info is not None:
            fallback_path = yt_dlp.YoutubeDL(base_opts).prepare_filename(info)
            if os.path.exists(fallback_path):
                print(f"[!] 下载均失败，回退使用本地缓存：{fallback_path}")
                self.video_path = fallback_path
                return fallback_path

        raise RuntimeError(
            f"视频下载失败，已尝试默认请求头及浏览器 Cookie：{last_exc}"
        ) from last_exc

    def _transcribe_audio(self, video_path: str) -> List[Dict[str, Any]]:
        """使用 OpenAI Whisper 转写视频音频。"""
        print(f"[*] 加载 Whisper 模型：{self.whisper_model}")
        model = whisper.load_model(self.whisper_model)
        print("[*] 开始音频转写（首次使用会自动下载模型）...")
        result = model.transcribe(video_path, verbose=False)
        return result.get("segments", [])

    def _detect_slide_changes(self, video_path: str) -> List[float]:
        """使用 pHash 检测 PPT/Keynote 翻页节点。"""
        print("[*] 开始视觉 PPT 翻页检测...")
        clip = VideoFileClip(video_path)
        timestamps: List[float] = [0.0]
        prev_hash = None

        try:
            duration = int(clip.duration)
            for t in range(0, duration, self.sample_interval):
                frame = clip.get_frame(t)
                current_hash = imagehash.phash(Image.fromarray(frame))
                if (
                    prev_hash is not None
                    and abs(current_hash - prev_hash) > self.slide_hash_threshold
                ):
                    timestamps.append(float(t))
                prev_hash = current_hash
        finally:
            clip.close()

        return timestamps

    def _align_notes(
        self,
        transcript: List[Dict[str, Any]],
        slide_timestamps: List[float],
    ) -> List[Dict[str, Any]]:
        """将 ASR 文本片段按 PPT 翻页时间对齐。"""
        notes: List[Dict[str, Any]] = []
        for i, start_t in enumerate(slide_timestamps):
            end_t = (
                slide_timestamps[i + 1]
                if i + 1 < len(slide_timestamps)
                else float("inf")
            )
            texts: List[str] = []
            for seg in transcript:
                seg_start = seg.get("start", 0.0)
                if start_t <= seg_start < end_t:
                    texts.append(seg.get("text", ""))
            notes.append(
                {
                    "slide": i + 1,
                    "time": start_t,
                    "content": "".join(texts).strip(),
                }
            )
        return notes

    def _fallback_asr_and_ppt(self) -> List[Dict[str, Any]]:
        """Phase 2 兜底：下载视频后并行 ASR + 视觉检测。"""
        print("[*] 未检测到原生字幕，启动 ASR + PPT 视觉检测...")

        video_path = self._download_video()
        print(f"[*] 视频已下载：{video_path}")

        # 并行执行音频转写与视觉检测，最大化利用 CPU/GPU 资源
        with ThreadPoolExecutor(max_workers=2) as executor:
            future_transcript = executor.submit(self._transcribe_audio, video_path)
            future_slides = executor.submit(self._detect_slide_changes, video_path)

            transcript = future_transcript.result()
            slide_timestamps = future_slides.result()

        return self._align_notes(transcript, slide_timestamps)

    # ==================== Phase 3: 智能学习笔记 ====================

    def _summarize_notes(self, notes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """把口语化笔记提炼成结构化知识点。"""
        print(f"[*] 使用 {self.summarizer_method} 摘要器提炼知识点...")
        summarizer = self._get_summarizer()
        return summarizer.summarize(notes)

    # ==================== OKF v0.2 笔记包输出 ====================

    def _video_source_id(self) -> str:
        """为视频来源生成一个稳定的 ASCII 标识符。"""
        return hashlib.sha256(self.video_url.encode("utf-8")).hexdigest()[:12]

    def _run_okf_cli(self, args: List[str], cwd: Optional[Path] = None) -> None:
        """调用 okf-note-taking skill 的 CLI helper。"""
        if not OKF_NOTES_CLI.exists():
            raise RuntimeError(f"未找到 OKF 笔记 CLI：{OKF_NOTES_CLI}")

        cmd = [sys.executable, str(OKF_NOTES_CLI)] + args
        try:
            subprocess.run(cmd, cwd=cwd, check=True)
        except subprocess.CalledProcessError as exc:
            print(f"[!] OKF CLI 调用失败：{' '.join(cmd)}\n{exc}", file=sys.stderr)

    def _init_okf_bundle(self) -> None:
        """初始化 OKF v0.2 笔记包目录结构。"""
        self.okf_bundle_dir.mkdir(parents=True, exist_ok=True)
        if not (self.okf_bundle_dir / "index.md").exists():
            bundle_name = self.video_title or "Video Notes"
            self._run_okf_cli(
                ["init", str(self.okf_bundle_dir), "--name", bundle_name]
            )
        else:
            print(f"[*] 检测到已有 OKF 笔记包，直接复用：{self.okf_bundle_dir}")

    def _write_reference_note(self) -> Path:
        """写入视频来源参考笔记。"""
        ref_dir = self.okf_bundle_dir / "references"
        ref_dir.mkdir(parents=True, exist_ok=True)
        ref_path = ref_dir / "video-source.md"

        ref_title = self.video_title or "Video Source"
        meta: Dict[str, Any] = {
            "type": "Reference",
            "title": ref_title,
            "description": f"Source video: {self.video_url}",
            "resource": self.video_url,
            "tags": ["video-source"],
            "status": "draft",
            "generated": {"by": "kimi-code-cli", "at": _now_iso()},
        }

        body = f"""# Summary

Source video URL: {self.video_url}

# Notes

This reference is linked from topic notes generated from the video.
"""
        ref_path.write_text(_build_concept_document(meta, body), encoding="utf-8")
        print(f"[✔] 参考笔记已生成：{ref_path}")
        return ref_path

    def _collect_transcript_for_section(
        self, section: Dict[str, Any], notes: List[Dict[str, Any]]
    ) -> str:
        """收集属于某一小节的原始转写文本。"""
        start_t = float(section.get("start_time", 0.0))
        end_t = float(section.get("end_time", start_t))
        texts: List[str] = []
        for note in notes:
            t = float(note.get("time", 0.0))
            if start_t <= t <= end_t:
                content = str(note.get("content", "")).strip()
                if content:
                    texts.append(content)
        return " ".join(texts).strip()

    def _capture_section_frame(
        self,
        start_t: float,
        end_t: float,
        dest_path: Path,
    ) -> bool:
        """从视频 [start_t, end_t] 区间选取最佳帧并保存为 JPEG。

        Args:
            start_t: 区间开始时间（秒）。
            end_t: 区间结束时间（秒），可为 inf 表示取到视频结尾。
            dest_path: 图片保存路径。

        Returns:
            成功保存返回 True，否则 False。
        """
        if not self.video_path or not os.path.exists(self.video_path):
            return False
        try:
            clip = VideoFileClip(self.video_path)
            video_duration = float(clip.duration or 0)
            clip.close()
        except Exception:
            return False
        if video_duration <= 0 or start_t >= video_duration:
            return False

        select_start_t = max(0.0, start_t)
        select_end_t = min(end_t, video_duration)
        try:
            selector = self._get_frame_selector()
            best = selector.select(
                self.video_path,
                start_time=select_start_t,
                end_time=select_end_t,
                sample_count=5,
            )
            if best:
                _, best_img = best
                dest_path.parent.mkdir(parents=True, exist_ok=True)
                best_img.convert("RGB").save(dest_path, "JPEG", quality=90)
                return True
        except Exception:
            pass
        return False

    def _write_topic_notes(
        self, summary: List[Dict[str, Any]], notes: List[Dict[str, Any]]
    ) -> List[Path]:
        """把每个摘要小节写入为 OKF 主题笔记。"""
        topics_dir = self.okf_bundle_dir / "topics"
        topics_dir.mkdir(parents=True, exist_ok=True)
        source_id = self._video_source_id()
        source_link = "/references/video-source.md"

        written: List[Path] = []
        seen_slugs: set[str] = set()

        for idx, section in enumerate(summary, start=1):
            title = (
                str(section.get("section", f"Section {idx}")).strip()
                or f"Section {idx}"
            )

            base_slug = _safe_filename(title)
            slug = base_slug
            counter = 1
            while slug in seen_slugs:
                slug = f"{base_slug}-{counter}"
                counter += 1
            seen_slugs.add(slug)
            note_path = topics_dir / f"{slug}.md"

            start_t = float(section.get("start_time", 0.0))
            end_t = float(section.get("end_time", start_t))
            start_min, start_sec = divmod(int(start_t), 60)
            end_min, end_sec = divmod(int(end_t), 60)
            time_str = (
                f"{start_min:02d}:{start_sec:02d} - {end_min:02d}:{end_sec:02d}"
            )

            summary_text = str(section.get("summary", "")).strip()
            key_points = section.get("key_points", [])
            if not isinstance(key_points, list):
                key_points = []
            transcript = self._collect_transcript_for_section(section, notes)

            # 智能选图：截图存到 assets/topics/<slug>/，正文用相对路径引用
            img_path = (
                self.okf_bundle_dir / "assets" / "topics" / slug
                / f"section_{idx:03d}.jpg"
            )
            img_rel: Optional[str] = None
            if self._capture_section_frame(start_t, end_t, img_path):
                img_rel = Path(
                    os.path.relpath(img_path, note_path.parent)
                ).as_posix()

            meta: Dict[str, Any] = {
                "type": "Note",
                "title": title,
                "description": summary_text[:120]
                + ("..." if len(summary_text) > 120 else ""),
                "resource": self.video_url,
                "tags": ["video-notes"],
                "status": "draft",
                "generated": {"by": "kimi-code-cli", "at": _now_iso()},
                "sources": [
                    {
                        "id": source_id,
                        "resource": self.video_url,
                        "title": "Video Source",
                        "author": "unknown",
                        "last_modified": _now_iso(),
                    }
                ],
            }
            if img_rel:
                meta["assets"] = [
                    "/" + img_path.relative_to(self.okf_bundle_dir).as_posix()
                ]

            body_lines = [
                "# Summary",
                "",
                f"本小节内容整理自视频 [^{source_id}]。",
                "",
                summary_text,
                "",
            ]
            if img_rel:
                body_lines.extend(
                    [
                        f"![{title}]({img_rel})",
                        "",
                        f"*视频画面 @ {time_str}*",
                        "",
                    ]
                )
            body_lines.extend(["# Key points", ""])
            for point in key_points:
                body_lines.append(f"- {point}")
            if not key_points:
                body_lines.append("- (no key points extracted)")
            body_lines.extend(
                [
                    "",
                    "# Transcript",
                    "",
                    transcript or "(no transcript available)",
                    "",
                    "# Source",
                    "",
                    f"[^{source_id}]: {self.video_url} (time: {time_str})",
                    "",
                    "# Related notes",
                    "",
                    f"- [Video Source]({source_link})",
                    "",
                ]
            )
            body = "\n".join(body_lines)

            note_path.write_text(
                _build_concept_document(meta, body), encoding="utf-8"
            )
            print(f"[✔] 主题笔记已生成：{note_path}")
            written.append(note_path)

        return written

    def _write_single_topic_note(
        self, summary: List[Dict[str, Any]], notes: List[Dict[str, Any]]
    ) -> Path:
        """把整个视频整理成一个 OKF 主题笔记（video 粒度）。"""
        topics_dir = self.okf_bundle_dir / "topics"
        topics_dir.mkdir(parents=True, exist_ok=True)
        source_id = self._video_source_id()
        source_link = "/references/video-source.md"

        title = self.video_title or "Video Notes"
        slug = _safe_filename(title)
        note_path = topics_dir / f"{slug}.md"
        counter = 1
        original_slug = slug
        while note_path.exists():
            slug = f"{original_slug}-{counter}"
            note_path = topics_dir / f"{slug}.md"
            counter += 1

        # 整体时间范围
        if summary:
            start_t = float(summary[0].get("start_time", 0.0))
            end_t = float(summary[-1].get("end_time", start_t))
        else:
            start_t = 0.0
            end_t = 0.0
        start_min, start_sec = divmod(int(start_t), 60)
        end_min, end_sec = divmod(int(end_t), 60)
        time_str = f"{start_min:02d}:{start_sec:02d} - {end_min:02d}:{end_sec:02d}"

        # 聚合整体摘要和要点
        overall_summary_parts: List[str] = []
        all_key_points: List[str] = []
        for section in summary:
            section_summary = str(section.get("summary", "")).strip()
            if section_summary:
                overall_summary_parts.append(section_summary)
            section_points = section.get("key_points", [])
            if isinstance(section_points, list):
                all_key_points.extend(section_points)

        overall_summary = " ".join(overall_summary_parts).strip()
        seen_points: set[str] = set()
        unique_key_points: List[str] = []
        for point in all_key_points:
            if point not in seen_points:
                seen_points.add(point)
                unique_key_points.append(point)
                if len(unique_key_points) >= 5:
                    break

        # 收集完整转写
        full_transcript_parts: List[str] = []
        for note in notes:
            content = str(note.get("content", "")).strip()
            if content:
                full_transcript_parts.append(content)
        full_transcript = " ".join(full_transcript_parts).strip()

        meta: Dict[str, Any] = {
            "type": "Note",
            "title": title,
            "description": overall_summary[:120]
            + ("..." if len(overall_summary) > 120 else ""),
            "resource": self.video_url,
            "tags": ["video-notes"],
            "status": "draft",
            "generated": {"by": "kimi-code-cli", "at": _now_iso()},
            "sources": [
                {
                    "id": source_id,
                    "resource": self.video_url,
                    "title": "Video Source",
                    "author": "unknown",
                    "last_modified": _now_iso(),
                }
            ],
        }

        body_lines = [
            "# Summary",
            "",
            f"本笔记整理自视频 [^{source_id}]。",
            "",
            overall_summary or "(no summary available)",
            "",
            "# Key points",
            "",
        ]
        if unique_key_points:
            for point in unique_key_points:
                body_lines.append(f"- {point}")
        else:
            body_lines.append("- (no key points extracted)")

        body_lines.extend(["", "# Sections", ""])

        # 各小节截图统一存到 assets/topics/<slug>/，正文用相对路径引用
        assets_dir = self.okf_bundle_dir / "assets" / "topics" / slug
        asset_paths: List[str] = []

        for idx, section in enumerate(summary, start=1):
            section_title = (
                str(section.get("section", f"Section {idx}")).strip()
                or f"Section {idx}"
            )
            sec_start_t = float(section.get("start_time", 0.0))
            sec_end_t = float(section.get("end_time", sec_start_t))
            sec_start_min, sec_start_sec = divmod(int(sec_start_t), 60)
            sec_end_min, sec_end_sec = divmod(int(sec_end_t), 60)
            sec_time_str = f"{sec_start_min:02d}:{sec_start_sec:02d} - {sec_end_min:02d}:{sec_end_sec:02d}"
            section_summary = str(section.get("summary", "")).strip()
            section_points = section.get("key_points", [])
            if not isinstance(section_points, list):
                section_points = []

            # 智能选图
            img_path = assets_dir / f"section_{idx:03d}.jpg"
            img_rel: Optional[str] = None
            if self._capture_section_frame(sec_start_t, sec_end_t, img_path):
                img_rel = Path(
                    os.path.relpath(img_path, note_path.parent)
                ).as_posix()
                asset_paths.append(
                    "/" + img_path.relative_to(self.okf_bundle_dir).as_posix()
                )

            body_lines.extend(
                [
                    f"## {idx}. {section_title}",
                    "",
                    f"**时间：** {sec_time_str}",
                    "",
                ]
            )
            if img_rel:
                body_lines.extend(
                    [
                        f"![{section_title}]({img_rel})",
                        "",
                        f"*视频画面 @ {sec_time_str}*",
                        "",
                    ]
                )
            if section_summary:
                body_lines.extend(["### Summary", "", section_summary, ""])
            if section_points:
                body_lines.extend(["### Key points", ""])
                for point in section_points:
                    body_lines.append(f"- {point}")
                body_lines.append("")

        body_lines.extend(
            [
                "",
                "# Transcript",
                "",
                full_transcript or "(no transcript available)",
                "",
                "# Source",
                "",
                f"[^{source_id}]: {self.video_url} (time: {time_str})",
                "",
                "# Related notes",
                "",
                f"- [Video Source]({source_link})",
                "",
            ]
        )

        if asset_paths:
            meta["assets"] = asset_paths

        body = "\n".join(body_lines)
        note_path.write_text(
            _build_concept_document(meta, body), encoding="utf-8"
        )
        print(f"[✔] 主题笔记已生成：{note_path}")
        return note_path

    def _generate_okf_notes(
        self, summary: List[Dict[str, Any]], notes: List[Dict[str, Any]]
    ) -> Path:
        """生成 OKF v0.2 笔记包。"""
        print("[*] 开始生成 OKF v0.2 笔记包...")
        self._init_okf_bundle()
        self._write_reference_note()

        if self.granularity == "section":
            self._write_topic_notes(summary, notes)
        else:
            self._write_single_topic_note(summary, notes)

        # 更新索引与日志
        self._run_okf_cli(["index", "--regenerate"], cwd=self.okf_bundle_dir)
        if self.granularity == "section":
            log_message = f"Generated sectioned notes from {self.video_url}"
        else:
            log_message = f"Generated single video note from {self.video_url}"
        self._run_okf_cli(
            ["log", log_message],
            cwd=self.okf_bundle_dir,
        )

        print(f"[✔] OKF 笔记包已生成：{self.okf_bundle_dir}")
        return self.okf_bundle_dir

    # ==================== 单文件 OKF 文档输出 ====================

    def _generate_okf_doc(
        self,
        summary: List[Dict[str, Any]],
        notes: List[Dict[str, Any]],
    ) -> Path:
        """生成一份嵌入截图的完整 OKF 文档（单 markdown 文件）。"""
        print("[*] 开始生成单文件 OKF 学习文档...")
        self.okf_doc_assets_dir.mkdir(parents=True, exist_ok=True)

        has_video = bool(self.video_path and os.path.exists(self.video_path))
        if not has_video:
            print("[!] 视频文件不存在，OKF 文档将只包含文字，不包含截图")

        # 获取视频实际时长
        video_duration = 0.0
        if has_video and self.video_path:
            try:
                clip = VideoFileClip(self.video_path)
                video_duration = float(clip.duration or 0)
                clip.close()
            except Exception:
                video_duration = 0.0

        source_id = self._video_source_id()

        # 文档 frontmatter
        first_summary = str(summary[0].get("summary", "")).strip() if summary else ""
        doc_title = self.video_title or "视频学习笔记"
        meta: Dict[str, Any] = {
            "type": "Note",
            "title": doc_title,
            "description": first_summary[:160] + ("..." if len(first_summary) > 160 else ""),
            "resource": self.video_url,
            "tags": ["video-notes", "study-guide"],
            "status": "draft",
            "generated": {"by": "kimi-code-cli", "at": _now_iso()},
            "sources": [
                {
                    "id": source_id,
                    "resource": self.video_url,
                    "title": doc_title,
                    "author": "unknown",
                    "last_modified": _now_iso(),
                }
            ],
        }

        doc_lines = [
            "# Summary",
            "",
            f"本笔记整理自视频[^{source_id}]。",
            "",
            f"共 {len(summary)} 个小节，按时间顺序组织，每个小节包含要点、摘要、截图和原始转写。",
            "",
            "# Sections",
            "",
        ]

        # 记录截图资源路径，用于写入 frontmatter assets
        asset_paths: List[str] = []

        for idx, section in enumerate(summary, start=1):
            title = (
                str(section.get("section", f"Section {idx}")).strip()
                or f"Section {idx}"
            )
            start_t = float(section.get("start_time", 0.0))
            end_t = float(section.get("end_time", start_t))
            start_min, start_sec = divmod(int(start_t), 60)
            end_min, end_sec = divmod(int(end_t), 60)
            time_str = (
                f"{start_min:02d}:{start_sec:02d} - {end_min:02d}:{end_sec:02d}"
            )

            summary_text = str(section.get("summary", "")).strip()
            key_points = section.get("key_points", [])
            if not isinstance(key_points, list):
                key_points = []
            transcript = self._collect_transcript_for_section(section, notes)

            doc_lines.extend([
                f"## {idx}. {title}",
                "",
                f"**时间：** {time_str}",
                "",
            ])

            # 截图
            img_rel = None
            if has_video and video_duration > 0 and start_t < video_duration:
                mid_t = (max(0.0, start_t) + min(end_t, video_duration)) / 2
                img_filename = f"section_{idx:03d}_{int(mid_t):04d}.jpg"
                img_path = self.okf_doc_assets_dir / img_filename
                if self._capture_section_frame(start_t, end_t, img_path):
                    img_rel = str(
                        Path(self.okf_doc_assets_dir.name) / img_filename
                    )
                    asset_paths.append(
                        "/" + str(Path(self.okf_doc_assets_dir.name) / img_filename)
                    )

            if img_rel:
                doc_lines.extend([
                    f"![{title}]({img_rel})",
                    "",
                    f"*视频画面 @ {time_str}*",
                    "",
                ])

            # 要点
            if key_points:
                doc_lines.extend(["### Key points", ""])
                for point in key_points:
                    doc_lines.append(f"- {point}")
                doc_lines.append("")

            # 摘要
            if summary_text:
                doc_lines.extend([
                    "### Summary",
                    "",
                    summary_text,
                    "",
                ])

            # 转写
            if transcript:
                doc_lines.extend([
                    "### Transcript",
                    "",
                    f"> {transcript[:500]}{'...' if len(transcript) > 500 else ''}",
                    "",
                ])

            doc_lines.append("---")
            doc_lines.append("")

        # 来源
        doc_lines.extend([
            "# Source",
            "",
            f"[^{source_id}]: {self.video_url}",
            "",
        ])

        if asset_paths:
            meta["assets"] = asset_paths

        doc_body = "\n".join(doc_lines)
        self.okf_doc_path.write_text(
            _build_concept_document(meta, doc_body), encoding="utf-8"
        )
        print(f"[✔] 单文件 OKF 学习文档已生成：{self.okf_doc_path}")
        return self.okf_doc_path

    # ==================== PDF 讲义输出 ====================

    def _generate_study_pdf(
        self,
        summary: List[Dict[str, Any]],
        notes: List[Dict[str, Any]],
    ) -> None:
        """把摘要后的结构化笔记生成为「内容讲解 + 智能选图」的学习笔记 PDF。"""
        try:
            from fpdf import FPDF
        except ImportError:
            print("[!] 未安装 fpdf2，跳过 PDF 生成。可运行：pip install fpdf2")
            return

        has_video = bool(self.video_path and os.path.exists(self.video_path))
        if not has_video:
            print("[!] 视频文件不存在，PDF 将只包含文字，不包含截图")

        # 中文字体：优先 macOS 自带字体
        font_candidates = [
            "/Library/Fonts/Arial Unicode.ttf",
            "/System/Library/Fonts/STHeiti Medium.ttc",
            "/System/Library/Fonts/STHeiti Light.ttc",
        ]
        font_path = None
        for c in font_candidates:
            if os.path.exists(c):
                font_path = c
                break
        if not font_path:
            print("[!] 未找到中文字体，跳过 PDF 生成")
            return

        self.screenshot_dir.mkdir(exist_ok=True)

        class _PDF(FPDF):
            def header(self):
                if self.page_no() > 1:
                    self.set_font("ArialUnicode", "", 9)
                    self.set_text_color(128, 128, 128)
                    self.set_x(self.l_margin)
                    self.cell(0, 10, "智能视频学习笔记", align="C")
                    self.ln(5)

            def footer(self):
                self.set_y(-15)
                self.set_font("ArialUnicode", "", 9)
                self.set_text_color(128, 128, 128)
                self.set_x(self.l_margin)
                self.cell(0, 10, f"第 {self.page_no()} 页", align="C")

        pdf = _PDF()
        pdf.add_font("ArialUnicode", "", font_path)
        pdf.add_font("ArialUnicode", "B", font_path)
        pdf.set_auto_page_break(auto=True, margin=20)

        # 封面
        pdf.add_page()
        pdf.set_font("ArialUnicode", "B", 22)
        pdf.set_text_color(30, 64, 175)
        pdf.set_y(80)
        pdf.set_x(pdf.l_margin)
        pdf.cell(0, 15, "智能视频学习笔记", align="C")
        pdf.ln(12)
        pdf.set_font("ArialUnicode", "", 11)
        pdf.set_text_color(80, 80, 80)
        pdf.set_x(pdf.l_margin)
        pdf.cell(0, 10, f"来源：{self.video_url}", align="C")
        pdf.ln(8)
        pdf.set_x(pdf.l_margin)
        pdf.cell(0, 10, "整理方式：字幕/ASR 转写 + LLM 摘要 + 智能选图", align="C")

        selector = self._get_frame_selector() if has_video else None

        # 获取视频实际时长，用于把截图采样范围限制在有效区间内
        video_duration = 0.0
        if has_video and self.video_path:
            try:
                clip = VideoFileClip(self.video_path)
                video_duration = float(clip.duration or 0)
                clip.close()
            except Exception:
                video_duration = 0.0

        for idx, section in enumerate(summary, start=1):
            pdf.add_page()

            start_t = float(section.get("start_time", 0.0))
            end_t = float(section.get("end_time", start_t))
            start_min, start_sec = divmod(int(start_t), 60)
            end_min, end_sec = divmod(int(end_t), 60)
            time_str = f"{start_min:02d}:{start_sec:02d} - {end_min:02d}:{end_sec:02d}"

            # 截图采样区间不能超过视频实际时长
            select_start_t = max(0.0, start_t)
            select_end_t = end_t
            if video_duration > 0:
                select_end_t = min(end_t, video_duration)

            # 小节标题
            pdf.set_font("ArialUnicode", "B", 14)
            pdf.set_text_color(30, 64, 175)
            pdf.set_x(pdf.l_margin)
            pdf.cell(0, 10, f"{idx}. {section.get('section', '未命名小节')}")
            pdf.ln(10)

            # 时间范围
            pdf.set_font("ArialUnicode", "", 10)
            pdf.set_text_color(100, 100, 100)
            pdf.set_x(pdf.l_margin)
            pdf.cell(0, 7, f"时间：{time_str}")
            pdf.ln(9)

            # 核心要点
            key_points = section.get("key_points", [])
            if key_points:
                pdf.set_font("ArialUnicode", "B", 11)
                pdf.set_text_color(0, 0, 0)
                pdf.set_x(pdf.l_margin)
                pdf.cell(0, 8, "核心要点")
                pdf.ln(9)
                for point in key_points:
                    pdf.set_font("ArialUnicode", "", 10)
                    pdf.set_text_color(40, 40, 40)
                    pdf.set_x(pdf.l_margin + 5)
                    pdf.multi_cell(0, 7, f"• {point}")
                    pdf.ln(1)
                pdf.ln(3)

            # 摘要
            summary_text = section.get("summary", "").strip()
            if summary_text:
                pdf.set_font("ArialUnicode", "B", 11)
                pdf.set_text_color(0, 0, 0)
                pdf.set_x(pdf.l_margin)
                pdf.cell(0, 8, "内容摘要")
                pdf.ln(9)
                pdf.set_font("ArialUnicode", "", 10)
                pdf.set_text_color(60, 60, 60)
                pdf.set_x(pdf.l_margin)
                pdf.multi_cell(0, 7, summary_text)
                pdf.ln(5)

            if (
                not has_video
                or selector is None
                or video_duration <= 0
                or select_start_t >= video_duration
            ):
                continue

            # 智能选图（仅在视频有效时长范围内采样）
            mid_t = (select_start_t + select_end_t) / 2
            img_path = self.screenshot_dir / f"section_{idx:03d}_{int(mid_t):04d}.jpg"
            try:
                best = selector.select(
                    self.video_path,
                    start_time=select_start_t,
                    end_time=select_end_t,
                    sample_count=5,
                )
                if best:
                    _, best_img = best
                    best_img.convert("RGB").save(img_path, "JPEG", quality=90)
                else:
                    continue
            except Exception:
                continue

            available_height = pdf.h - pdf.b_margin - pdf.get_y()
            img_width = 170
            img_height = img_width * 9 / 16
            if available_height < img_height + 15:
                pdf.add_page()

            pdf.set_font("ArialUnicode", "", 9)
            pdf.set_text_color(100, 100, 100)
            pdf.set_x(pdf.l_margin)
            pdf.cell(0, 6, f"视频画面 @ {time_str}")
            pdf.ln(6)
            pdf.image(str(img_path), x=20, w=img_width)

        pdf.output(self.pdf_path)
        print(f"[✔] 学习笔记 PDF 已生成：{self.pdf_path}")

    # ==================== 统一入口 ====================

    def generate(self) -> Dict[str, Any]:
        """
        执行完整的双轨提取流程，并保存结果到文件。

        Returns:
            包含原始笔记、摘要笔记和输出路径的字典。
        """
        # 先获取视频标题，并据此解析输出路径
        video_title = self._get_video_title()
        self._resolve_output_paths(video_title)
        print(f"[*] 视频标题：{video_title}")
        print(f"[*] 输出前缀：{Path(self.output_path).with_suffix('')}")

        # 如果开启复用且 notes.json 已存在，跳过 Phase 1/2
        if self.reuse_existing and os.path.exists(self.output_path):
            print(f"[*] 检测到已有笔记，直接复用：{self.output_path}")
            with open(self.output_path, "r", encoding="utf-8") as f:
                final_data = json.load(f)

            # PDF / OKF 文档 / OKF 笔记包模式下需要视频文件用于截图
            if self.output_format in ("pdf", "okf-doc", "okf") and not self.video_path:
                self._download_video()
        else:
            # Phase 1：轻量级字幕探测
            has_subtitle = False
            try:
                with sync_playwright() as p:
                    browser = p.chromium.launch_persistent_context(
                        self.browser_data_dir,
                        headless=self.headless,
                    )
                    page = browser.pages[0] if browser.pages else browser.new_page()
                    try:
                        has_subtitle = self._check_subtitle(page)
                    finally:
                        browser.close()
            except Exception as exc:
                print(f"[!] 字幕探测阶段出现异常：{exc}", file=sys.stderr)
                has_subtitle = False

            # Phase 2：重量级兜底（仅在 Phase 1 失败时执行）
            if has_subtitle:
                print("[✔] 成功获取原生字幕！")
                final_data = self._format_subtitle_notes()
            else:
                print("[!] 未检测到字幕，转入本地 ASR + 视觉处理...")
                final_data = self._fallback_asr_and_ppt()

            # 统一输出原始笔记
            Path(self.output_path).parent.mkdir(parents=True, exist_ok=True)
            with open(self.output_path, "w", encoding="utf-8") as f:
                json.dump(final_data, f, ensure_ascii=False, indent=2)
            print(f"[✔] 笔记已生成：{self.output_path}（共 {len(final_data)} 页）")

        # 生成给 LLM/Agent 的摘要 prompt 上下文
        prompt = summarizers.build_llm_summary_prompt(final_data)
        with open(self.llm_prompt_path, "w", encoding="utf-8") as f:
            f.write(prompt)
        print(f"[✔] LLM 摘要提示已生成：{self.llm_prompt_path}")

        # Phase 3：摘要 + 选定格式输出
        if self.reuse_existing and os.path.exists(self.summary_path):
            print(f"[*] 检测到已有摘要，直接复用：{self.summary_path}")
            with open(self.summary_path, "r", encoding="utf-8") as f:
                summary_data = json.load(f)
        else:
            summary_data = self._summarize_notes(final_data)
            with open(self.summary_path, "w", encoding="utf-8") as f:
                json.dump(summary_data, f, ensure_ascii=False, indent=2)
            print(f"[✔] 知识点摘要已生成：{self.summary_path}（共 {len(summary_data)} 节）")

        result: Dict[str, Any] = {
            "notes": final_data,
            "summary": summary_data,
            "output_path": self.output_path,
            "summary_path": self.summary_path,
            "llm_prompt_path": self.llm_prompt_path,
        }

        if self.output_format == "pdf":
            self._generate_study_pdf(summary_data, final_data)
            result["pdf_path"] = self.pdf_path
        elif self.output_format == "okf-doc":
            okf_doc = self._generate_okf_doc(summary_data, final_data)
            result["okf_doc_path"] = str(okf_doc)
        else:
            okf_bundle = self._generate_okf_notes(summary_data, final_data)
            result["okf_bundle_dir"] = str(okf_bundle)

        return result


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="智能双轨视频笔记生成器",
    )
    parser.add_argument("url", help="视频 URL")
    parser.add_argument("output", nargs="?", default=None, help="输出 JSON 路径（默认使用视频标题命名）")
    parser.add_argument(
        "--reuse-existing",
        action="store_true",
        help="复用已存在的 notes.json，跳过字幕探测和 ASR",
    )
    parser.add_argument(
        "--summarizer-method",
        default="rule",
        choices=["rule"],
        help="摘要器方法（默认 rule，LLM 摘要通过生成的 prompt 文件由调用方实现）",
    )
    parser.add_argument(
        "--output-format",
        default="okf-doc",
        choices=["okf", "okf-doc", "pdf"],
        help="最终笔记输出格式：okf-doc（单文件 OKF 文档，嵌入截图，默认）、okf（OKF v0.2 笔记包）或 pdf（单文件 PDF 讲义）",
    )
    parser.add_argument(
        "--frame-selector-method",
        default="visual",
        choices=["visual", "ocr"],
        help="PDF / okf-doc 模式下的智能选图方法（默认 visual）",
    )
    parser.add_argument(
        "--whisper-model",
        default="base",
        help="Whisper 模型大小（默认 base）",
    )
    parser.add_argument(
        "--notes-dir",
        default=None,
        help="OKF 模式下笔记包输出目录（默认 <output>_notes）",
    )
    parser.add_argument(
        "--granularity",
        default="video",
        choices=["video", "section"],
        help="OKF 笔记包模式下的文档粒度：video（整视频一个主题文档，默认）或 section（每个摘要小节一个主题文档）",
    )

    args = parser.parse_args()

    generator = VideoNoteGenerator(
        video_url=args.url,
        output_path=args.output,
        summarizer_method=args.summarizer_method,
        output_format=args.output_format,
        frame_selector_method=args.frame_selector_method,
        whisper_model=args.whisper_model,
        notes_dir=args.notes_dir,
        reuse_existing=args.reuse_existing,
        granularity=args.granularity,
    )
    generator.generate()


if __name__ == "__main__":
    main()
