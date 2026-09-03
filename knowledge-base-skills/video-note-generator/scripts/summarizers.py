#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
笔记摘要模块。

把 ASR 转写的口语化文本提炼成结构化知识点。
"""

import json
import os
import re
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional


class BaseSummarizer(ABC):
    """摘要器接口。"""

    @abstractmethod
    def summarize(self, notes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        输入 notes 列表，返回摘要后的结构化笔记。

        输出格式建议包含：
        - section: 小节标题
        - start_time / end_time: 时间范围
        - key_points: 要点列表
        - original_slides: 覆盖的原始 slide 编号
        """
        raise NotImplementedError


# 默认 ASR 常见口误修正表（可在子类中覆盖）
_DEFAULT_ASR_CORRECTIONS = {
    "伯尔巴迪": "Workbody",
    "webadi": "Workbody",
    "玩Body": "Workbody",
    "我Body": "Workbody",
    "民既论": "零基础",
    "直信流程": "执行流程",
    "集于AI": "基于 AI",
    "将AI": "去 AI 味",
    "去Ai位": "去 AI 味",
    "风模型": "AI 模型",
    "风位鞋": "AI 味",
    "可付钱": "可复现",
    "事务剧细": "事无巨细",
    "提示词起": "提示词写",
    "疯装": "封装",
    "文件家": "文件夹",
    "閱读": "阅读",
    "吸酿": "批量",
    "专金": "专业",
    "靠谷": "靠谱",
    "杂功": "杂工",
    "实上": "时长",
    "叛诺阿": "Hello",
    "和性能力": "核心能力",
    "直信": "执行",
    "集于": "基于",
    "将解": "讲解",
    "实践力": "实践案例",
    "降AI": "去 AI 味",
}


def clean_asr_text(text: str, corrections: Optional[Dict[str, str]] = None) -> str:
    """清洗 ASR 转写文本中的常见口误。"""
    corrections = corrections or _DEFAULT_ASR_CORRECTIONS
    for old, new in corrections.items():
        text = text.replace(old, new)
    return text


class RuleBasedSummarizer(BaseSummarizer):
    """
    基于规则的摘要器。

    适合没有 LLM API 的场景：合并相邻短句、提取小节标题、整理要点。
    """

    def __init__(
        self,
        max_gap: float = 8.0,
        min_group_chars: int = 40,
        max_group_chars: int = 160,
    ):
        self.max_gap = max_gap
        self.min_group_chars = min_group_chars
        self.max_group_chars = max_group_chars

    def _extract_title(self, texts: List[str]) -> str:
        """从合并文本中提取标题：选择长度适中的第一句，过滤常见口头禅。"""
        merged = " ".join(texts).strip()
        merged = clean_asr_text(merged)
        if not merged:
            return "未命名小节"

        # 过滤纯问候/互动句
        noise_patterns = ["大家好", "哈喽", "哈喽啊", "朋友们", "三连", "点赞", "收藏"]
        for pattern in noise_patterns:
            if pattern in merged and len(merged) < 25:
                return "课程要点"

        # 按常见分隔符拆分，找第一个长度适中的句子作为标题
        sentences = [s.strip() for s in re.split(r"[。！？\n]", merged) if s.strip()]
        for sentence in sentences:
            if 12 <= len(sentence) <= 45:
                return sentence

        # 兜底：截取前 28 字
        return (merged[:28] + "...") if len(merged) > 28 else merged

    def _split_key_points(self, text: str) -> List[str]:
        """把清洗后的合并文本拆成若干精炼要点句。"""
        text = clean_asr_text(text)
        # 先按句号、感叹号、问号、分号拆分
        raw = [s.strip() for s in re.split(r"[。！？；]", text) if s.strip()]

        # 对过长的子句再按逗号拆分，得到更细的候选
        candidates: List[str] = []
        for sentence in raw:
            if len(sentence) <= 90:
                candidates.append(sentence)
            else:
                parts = [p.strip() for p in sentence.split("，") if len(p.strip()) > 10]
                candidates.extend(parts)

        # 优先选择长度适中、包含核心关键词的片段
        keywords = ["skill", "workbody", "ai", "工具", "使用", "原因", "作用", "结果", "流程", "模板", "稳定"]
        scored = []
        for sentence in candidates:
            length = len(sentence)
            if length < 12 or length > 70:
                continue
            keyword_score = sum(1 for kw in keywords if kw.lower() in sentence.lower())
            # 短句优先，有核心词的加分
            score = keyword_score * 10 + max(0, 70 - length)
            scored.append((score, sentence))

        # 按原始出现顺序排列，保持语义连贯
        selected = [s for _, s in sorted(scored, reverse=True, key=lambda x: x[0])]
        return selected[:3]  # 每小节最多 3 个要点

    def summarize(self, notes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not notes:
            return []

        groups: List[List[Dict[str, Any]]] = []
        current_group: List[Dict[str, Any]] = [notes[0]]
        current_chars = len(str(notes[0].get("content", "")))

        for note in notes[1:]:
            content = str(note.get("content", "")).strip()
            if not content:
                continue

            prev = current_group[-1]
            gap = float(note.get("time", 0)) - float(prev.get("time", 0))
            would_exceed = current_chars + len(content) > self.max_group_chars

            # 合并条件：间隔小、当前组还不够长、不会超长
            if gap <= self.max_gap and current_chars < self.min_group_chars and not would_exceed:
                current_group.append(note)
                current_chars += len(content)
            else:
                groups.append(current_group)
                current_group = [note]
                current_chars = len(content)

        if current_group:
            groups.append(current_group)

        result: List[Dict[str, Any]] = []
        for group in groups:
            contents = [str(n.get("content", "")).strip() for n in group if str(n.get("content", "")).strip()]
            if not contents:
                continue

            full_text = clean_asr_text(" ".join(contents))
            start_time = float(group[0].get("time", 0))
            end_time = float(group[-1].get("time", 0))

            result.append({
                "section": self._extract_title(contents),
                "start_time": round(start_time, 2),
                "end_time": round(end_time, 2),
                "key_points": self._split_key_points(full_text),
                "summary": full_text[:220] + ("..." if len(full_text) > 220 else ""),
                "original_slides": [int(n.get("slide", 0)) for n in group],
            })

        return result


def build_llm_summary_prompt(notes: List[Dict[str, Any]]) -> str:
    """
    为调用方（如 Code Agent）生成一段可直接喂给 LLM 的上下文 prompt。

    调用方读取该 prompt 后，使用自身的大模型能力生成 JSON 摘要，
    并将结果保存为 `{output}_summary.json`。
    """
    text = "\n".join(
        f"[{n.get('time', 0):.1f}s] {n.get('content', '')}"
        for n in notes
        if str(n.get("content", "")).strip()
    )
    return f"""你是一位优秀的学习笔记整理助手。请根据以下视频 ASR 转写文本，提炼成结构化的学习笔记。

要求：
1. 将内容划分为 3-8 个小节，每个小节有一个清晰的标题
2. 每个小节包含：时间范围、3-5 个核心要点、一段 50-100 字的摘要
3. 去除口头禅、互动话术和重复内容，修正 ASR 口误（如"伯尔巴迪"应为"Workbody"、"将AI"应为"去 AI 味"）
4. 保留专业术语和关键概念
5. 输出必须是合法的 JSON 数组，格式如下，不要包含任何 markdown 代码块标记：

[
  {{
    "section": "小节标题",
    "start_time": 0.0,
    "end_time": 30.0,
    "key_points": ["要点1", "要点2"],
    "summary": "摘要内容",
    "original_slides": [1, 2, 3]
  }}
]

以下是转写文本：
{text}
"""


def create_summarizer(method: str = "rule") -> BaseSummarizer:
    """工厂函数，按名称创建摘要器。"""
    method = method.lower()
    if method == "rule":
        return RuleBasedSummarizer()
    raise ValueError(f"不支持的摘要方法：{method}，当前仅支持 rule（LLM 摘要通过 prompt 文件由调用方实现）")
