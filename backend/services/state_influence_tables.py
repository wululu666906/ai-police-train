"""Declarative tables for four-axis state influence (emotion / cooperation / risk / clarity)."""

from __future__ import annotations

from typing import Any

# Band thresholds: inclusive upper bound per tier name
BAND_THRESHOLDS: list[tuple[str, int]] = [
    ("very_low", 20),
    ("low", 40),
    ("mid", 60),
    ("high", 80),
    ("very_high", 100),
]

AXIS_EMOTION: dict[str, dict[str, Any]] = {
    "very_low": {
        "affect": "flat",
        "delivery": "fearful",
        "sentence_style": "broken",
        "max_sentences": 2,
        "tone_hint": "语气弱、害怕、反复请求保证，不敢展开。",
        "must_include": ["不确定", "我怕"],
        "must_avoid": ["攻击性反问", "长篇条理陈述"],
        "interruption_allowed": False,
    },
    "low": {
        "affect": "guarded",
        "delivery": "defensive",
        "sentence_style": "short",
        "max_sentences": 2,
        "tone_hint": "压抑、回避，先挡一句再观察民警态度。",
        "must_include": [],
        "must_avoid": ["主动全盘交代"],
        "interruption_allowed": False,
    },
    "mid": {
        "affect": "neutral",
        "delivery": "normal",
        "sentence_style": "normal",
        "max_sentences": 3,
        "tone_hint": "正常口语，可带轻微犹豫。",
        "must_include": [],
        "must_avoid": [],
        "interruption_allowed": False,
    },
    "high": {
        "affect": "agitated",
        "delivery": "angry",
        "sentence_style": "short",
        "max_sentences": 2,
        "tone_hint": "明显激动，带抱怨或反问，句子偏短。",
        "must_include": [],
        "must_avoid": ["冷静理性长分析"],
        "interruption_allowed": True,
    },
    "very_high": {
        "affect": "angry",
        "delivery": "angry",
        "sentence_style": "short",
        "max_sentences": 2,
        "tone_hint": "愤怒或强烈激动：短句、打断感、重复核心不满。",
        "must_include": ["你别", "凭什么"],
        "must_avoid": ["完整时间线", "主动自证全部细节"],
        "interruption_allowed": True,
    },
}

AXIS_COOPERATION: dict[str, dict[str, Any]] = {
    "very_low": {"disclosure_level": 0.12, "stance": "强烈对抗或冷拒，只答边缘信息。"},
    "low": {"disclosure_level": 0.25, "stance": "防御性强，倾向转移话题。"},
    "mid": {"disclosure_level": 0.45, "stance": "可给部分可验证细节。"},
    "high": {"disclosure_level": 0.65, "stance": "愿意补充时间线节点。"},
    "very_high": {"disclosure_level": 0.8, "stance": "较主动澄清误会或补充细节。"},
}

AXIS_RISK: dict[str, dict[str, Any]] = {
    "very_low": {"escalation_bias": 0.05, "hint": "可接受深入追问。"},
    "low": {"escalation_bias": 0.15, "hint": "对定性语言略敏感。"},
    "mid": {"escalation_bias": 0.35, "hint": "对命令式语气敏感。"},
    "high": {"escalation_bias": 0.6, "hint": "易出现边界警告或拒绝刺激追问。"},
    "very_high": {"escalation_bias": 0.85, "hint": "优先安全与边界，拒绝刺激性追问。"},
}

AXIS_CLARITY: dict[str, dict[str, Any]] = {
    "very_low": {
        "style": "broken",
        "hint": "表达破碎：跳题、断句、至少一次自我纠正。",
        "self_correction_min": 1,
    },
    "low": {"style": "fragmented", "hint": "顺序偶尔乱，细节缺失。", "self_correction_min": 0},
    "mid": {"style": "normal", "hint": "基本可懂。", "self_correction_min": 0},
    "high": {"style": "clear", "hint": "时间线较完整。", "self_correction_min": 0},
    "very_high": {
        "style": "structured",
        "hint": "可先…再…最后…结构化表达。",
        "self_correction_min": 0,
    },
}

# Cross-axis overrides: first match wins
COMBINATION_RULES: list[dict[str, Any]] = [
    {
        "when": {"emotion_min": "high", "risk_min": "high", "clarity_max": "low"},
        "override": {
            "primary_affect": "fearful",
            "delivery": "fearful",
            "sentence_style": "broken",
            "tone_hint": "高情绪+高风险+低清晰度：表现为害怕、慌乱、语无伦次，而非强硬对抗。",
            "must_include": ["我不确定", "怎么办"],
            "must_avoid": ["强硬顶撞", "条理清晰长段"],
        },
    },
    {
        "when": {"emotion_min": "high", "risk_min": "high", "clarity_min": "mid"},
        "override": {
            "primary_affect": "angry",
            "delivery": "angry",
            "sentence_style": "short",
            "tone_hint": "高情绪+高风险+表达尚清晰：表现为愤怒、对抗、短句顶回。",
            "must_include": [],
            "must_avoid": ["突然全面坦白"],
        },
    },
    {
        "when": {"emotion_max": "low", "cooperation_max": "low"},
        "override": {
            "primary_affect": "cold",
            "delivery": "defensive",
            "tone_hint": "低情绪+低配合：冷拒、敷衍，不展开。",
            "disclosure_level_cap": 0.2,
        },
    },
    {
        "when": {"cooperation_min": "high", "emotion_max": "mid"},
        "override": {
            "primary_affect": "cooperative",
            "delivery": "calm",
            "tone_hint": "配合升高：语气缓和，愿意补充可核实细节。",
        },
    },
]

TRIGGER_DELTAS: list[dict[str, Any]] = [
    {
        "id": "soft_contact",
        "pattern": r"(别急|慢慢说|不用着急|辛苦|先别慌|深呼吸|你先缓一下|先稳住)",
        "emotion": -7,
        "cooperation": 5,
        "risk": -5,
        "clarity": 2,
    },
    {
        "id": "empathy_validation",
        "pattern": r"(我理解|能理解|知道你着急|知道你害怕|你受委屈|先听你说|我在听|我会记录|我们会处理)",
        "emotion": -6,
        "cooperation": 5,
        "risk": -3,
        "clarity": 2,
    },
    {
        "id": "safety_reassurance",
        "pattern": r"(先保证安全|到安全位置|别靠近|先分开|保持距离|保护你|已经派警|民警.*路上|救护|120|安全位置)",
        "emotion": -5,
        "cooperation": 4,
        "risk": -7,
        "clarity": 2,
    },
    {
        "id": "procedural_explanation",
        "pattern": r"(我先核实|按流程|依法|先确认|再处理|方便回拨|给你回电|我这边记录|我们一步一步)",
        "emotion": -4,
        "cooperation": 4,
        "risk": -3,
        "clarity": 3,
    },
    {
        "id": "hard_pressure",
        "pattern": r"(快说|老实交代|别废话|是不是你干的|再不说|你必须)",
        "emotion": 6,
        "cooperation": -6,
        "risk": 6,
        "clarity": -3,
    },
    {
        "id": "fact_probe",
        "pattern": r"(时间|几点|地点|哪里|谁先|经过|当时|现场|看见|听见)",
        "emotion": 0,
        "cooperation": 2,
        "risk": -1,
        "clarity": 2,
    },
    {
        "id": "labeling",
        "pattern": r"(你就是|你肯定|故意|罪|违法)",
        "emotion": 8,
        "cooperation": -8,
        "risk": 8,
        "clarity": -4,
    },
]

ACTION_DELTAS: dict[str, dict[str, int]] = {
    "控制": {"emotion": 4, "cooperation": -4, "risk": 8, "clarity": -2},
    "强制": {"emotion": 5, "cooperation": -5, "risk": 7, "clarity": -2},
    "分离": {"emotion": -3, "cooperation": 2, "risk": -8, "clarity": 2},
    "隔离": {"emotion": -3, "cooperation": 2, "risk": -8, "clarity": 2},
    "安抚": {"emotion": -9, "cooperation": 7, "risk": -6, "clarity": 3},
    "解释": {"emotion": -5, "cooperation": 5, "risk": -3, "clarity": 3},
    "救助": {"emotion": -5, "cooperation": 4, "risk": -7, "clarity": 2},
    "警戒": {"emotion": 2, "cooperation": -2, "risk": 4, "clarity": 0},
}

MAX_DELTA_PER_TURN = 12
MAX_DELTA_FROM_CURRENT = 12
