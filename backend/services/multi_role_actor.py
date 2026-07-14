"""Per-role actor: each selected character generates 1-8 utterances with own persona."""

from __future__ import annotations

import json
import hashlib
import re
from typing import Any, Optional

import models
from .case_knowledge_service import load_case_knowledge_bundle
from .llm_provider import create_json_chat_completion, extract_message_text, get_chat_model
from .rag_service import RUNTIME_RETRIEVAL_LIBRARIES, rag_service
from .persona_engine import (
    analyze_dialogue_momentum,
    build_persona_profile,
    build_role_script,
    format_persona_block,
)
from .state_influence_engine import (
    apply_delivery_from_contract,
    build_state_contract,
    enrich_momentum_with_axis_deltas,
    format_state_contract_block,
)
from .canonical_facts_service import (
    extract_canonical_facts,
    format_canonical_facts_block,
    format_peer_utterances_block,
    merge_role_knows_facts,
)
from .dialogue_sanitize_service import sanitize_utterances
from .human_reaction_engine import (
    choose_role_reaction,
    format_actor_reaction_block,
    merge_reaction_delta,
    reaction_preface,
)
from .multi_role_service import _build_history_block, _role_display_name

ROLE_ACTOR_PROMPT = """
你正在扮演警情训练场景中的角色「{role_name}」，根据导演编排意图说出台词。

【导演编排】
- 互动模式：{interaction_mode}
- 你的参与方式：{participation}
- 本次连续发言最多 {utterance_count} 条台词（可少于该数，不可超过）；多条之间学员无需回复，你应顺着同一段思路往下说
- 发言意图：{intent}
- 触发原因：{trigger_reason}

【场景】{scene_name}  阶段：{current_stage}
【学员刚才说】{user_text}

【你的人设与状态】
{persona_block}

【当前角色大脑 / 身体绑定（最高优先级，不得借给其他角色）】
{role_brain_block}

【身份锚点（最高优先级，不得违反）】
{identity_anchor_block}

【本轮表现契约（必须严格遵守）】
{state_contract_block}

【真人化反应策略（必须体现）】
{human_reaction_block}

【案件基准事实（全角色必须一致，不得互相矛盾）】
{canonical_facts_block}

【案件库与角色剧本库】
{case_knowledge_block}

【知识库实时召回（法律法规 / SOP / 教学资料）】
{retrieved_knowledge_block}

【你掌握的事实边界】
已知：{knows_facts}
不可透露：{hidden_truths}
不知道：{does_not_know}

【本轮已发言角色（勿与其时间/地点说法矛盾）】
{peer_utterances_block}

【近期对话】
{history_block}

【视角约束】
{perspective_hint}

要求：
1. 一次生成 utterances 数组，含 1 到 utterance_count 条连续台词；每条对应界面一个气泡，条与条之间是同一角色接着说完，不是等学员回话再说下一句。
2. 生成前必须先读【当前角色大脑 / 身体绑定】、【学员刚才说】、【近期对话】、【案件库与角色剧本库】和【本轮已发言角色】；如果你是第二个开口的人，必须像已经听见前一个角色发言一样回应或补充，不能无视前文。
3. 必须符合你的人设、情绪、配合度；不能串戏、不能全知。
4. 严禁用第一人称「我」冒充学员点名的其他角色作答；若你是证人/家属且学员在问别人，请用第三人称转述你观察到的情况。
5. 若 participation=interrupt，第一句可带打断感；若 calm_scene 模式，情绪应略有缓和但仍保角色性格。
6. 若你是违法嫌疑人、配合度较低、lying_ability 较高，且 hidden_truths 不为空：初期不要主动承认 hidden_truths，可用淡化、推责、记不清、反问来回避；只有当学员明确追问证据、监控、证人、伤情、时间线矛盾时，才允许部分改口或松动。
7. 若学员只是笼统问“具体点/说清楚”，不要自动交代所有事实；应反问其要问时间、地点、谁先动手、证据还是伤情。
8. 若学员拿出证据或指出矛盾，回复中应体现被击中的心理变化：停顿、犹豫、缩小说法、改口一小步，而不是突然完整认罪。
9. 必须优先回应【学员刚才说】这一句；【近期对话】只能作为背景，不能把历史里的问题说成学员本轮刚问的问题。
10. 如果学员刚才是在告知、安抚、说明已采取措施（例如“已经叫救护车/已经通知/请稍等”），应回应这项措施是否让你安心、是否继续催促、需要什么确认；不得说“你们光问”“你刚才问这些”“你不是问了吗”等把历史追问当成本轮提问的话。
11. 人设配置（如核心顾虑、当前诉求、触发点）仅用于决定语气与反应，禁止在台词中念出字段名、配置原文或「我最怕的就是XXX」这类说明书句式；把担心融入自然口语。
12. 被问时间、地点时，若【案件基准事实】或【已知】中有标准答案，必须与其一致；证人可说「大概/记不清」，但不得换成不同路口或相差超过1小时的时间。
13. 严格遵守【视角约束】中的身份边界：若提示你是旁观者/证人，禁止用第一人称「我」替被问对象回答经历。
14. delivery 取值及含义：
    - normal：平常语气
    - angry：愤怒、激动
    - anxious：焦急、不安
    - sad：委屈、低落
    - defensive：防御、辩解
    - calm：冷静、缓和
    - hesitant：犹豫、吞吞吐吐
15. new_fact_revealed 只有在本轮确实新增了一条关键事实时才填写该事实文本，否则填 null。
16. state_delta 是四个轴的变化量（范围-15 到 +15），不是绝对值；没有明显变化时写 0，不要整条不填。
17. 注意：以下输出格式中的值为示例（delivery、数字等），请根据角色状态和本轮互动动态决定，不要照搬。只输出 JSON：
18. 若【真人化反应策略】要求你回避、沉默、争执、转移或求保护，要通过自然口语表现出来；不要直接说“我是争执型/回避型”。
19. 如果本轮已有人先发言，必须像听见了对方的话一样回应：同意、反驳、补充、纠正、沉默回避均可，但不能无视明显冲突；但不要把前一个角色没有说过的话强行安到对方头上。
20. 角色身份、职业/案件角色、亲属关系、社会关系和称谓必须以【身份锚点】为准；不确定时只说姓名或“对方”，禁止自编哥哥/弟弟、父母子女、夫妻、朋友、同事、邻居、证人/嫌疑人/被害人等身份。
21. 若你指责“对方诬赖/栽赃/让你背锅/他说你动手”，必须能在【学员刚才说】或最近 2 条对方发言里找到依据；找不到依据时改为回答学员当前问题。
22. 如果你前几轮已经围绕同一件事抱怨或辩解过，本轮除非学员继续明确追问这件事，否则必须切换：回答学员当前问点、补充一个尚未说清的新细节、或反问民警下一步要核实哪项，不能继续抓着旧争点打转。
23. 你不是一个共享演员在临时换皮；你是【当前角色大脑 / 身体绑定】里的唯一角色。其他角色的话只是你听到的外部声音，不能变成你的身份、记忆、经历或第一人称立场。

{{
  "utterances": [
    {{"content": "第一句台词", "delivery": "angry"}},
    {{"content": "第二句台词", "delivery": "normal"}}
  ],
  "inner_thought": "心理活动",
  "state_delta": {{"emotion": 0, "cooperation": 0, "risk": 0, "clarity": 0}},
  "new_fact_revealed": null
}}
"""


def _text(value: Any) -> str:
    return str(value or "").strip()


def _format_facts(value: Any) -> str:
    if isinstance(value, list):
        return "、".join(_text(item) for item in value if _text(item)) or "（无）"
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return "、".join(_text(item) for item in parsed if _text(item)) or "（无）"
        except Exception:
            pass
        return value or "（无）"
    return "（无）"


def _safe_json_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if not isinstance(value, str) or not value.strip():
        return {}
    try:
        parsed = json.loads(value)
    except Exception:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _safe_case_structured(case: Optional[models.Case]) -> dict[str, Any]:
    return _safe_json_dict(getattr(case, "structured_data", None))


_IDENTITY_TERMS = (
    "哥哥",
    "弟弟",
    "姐姐",
    "妹妹",
    "兄弟",
    "姐妹",
    "父亲",
    "母亲",
    "爸爸",
    "妈妈",
    "儿子",
    "女儿",
    "丈夫",
    "妻子",
    "老公",
    "老婆",
    "叔叔",
    "阿姨",
    "舅舅",
    "姑姑",
    "伯父",
    "伯母",
    "侄子",
    "侄女",
    "外甥",
    "外甥女",
    "亲戚",
    "家属",
    "朋友",
    "同事",
    "邻居",
    "同学",
    "证人",
    "目击者",
    "旁观者",
    "嫌疑人",
    "违法嫌疑人",
    "被害人",
    "受害人",
    "报警人",
    "当事人",
    "民警",
    "警察",
    "辅警",
    "保安",
    "店员",
    "老板",
    "司机",
    "乘客",
    "医生",
    "护士",
    "老师",
    "学生",
    "房东",
    "租客",
)


def _format_identity_anchor(role: models.Role, case: Optional[models.Case], profile: dict[str, Any]) -> str:
    meta = _safe_json_dict(getattr(role, "persona_meta", None))
    structured = _safe_case_structured(case)
    fact_sheet = structured.get("fact_sheet") if isinstance(structured.get("fact_sheet"), dict) else {}
    relationships = fact_sheet.get("relationships") or structured.get("relationships") or []
    role_name = _role_display_name(role)
    lines = [
        f"- 当前发言人姓名：{role_name}",
        f"- 当前发言人角色类型：{_text(getattr(role, 'role_type', '')) or '相关人员'}",
    ]
    if _text(getattr(role, "person_id", "")):
        lines.append(f"- 当前发言人 person_id：{_text(getattr(role, 'person_id', ''))}")
    for key, label in (
        ("identity", "人设身份"),
        ("role", "人设角色"),
        ("self_image", "自我定位"),
    ):
        if _text(meta.get(key)):
            lines.append(f"- {label}：{_text(meta.get(key))}")
    direct_links = (profile.get("relationship_map") or {}).get("direct_links") or []
    if direct_links:
        lines.append(f"- 与他人的案件关系：{'；'.join(str(item) for item in direct_links[:6])}")
    relation_rows: list[str] = []
    for item in relationships:
        if not isinstance(item, dict):
            continue
        from_name = _text(item.get("from"))
        to_name = _text(item.get("to"))
        relation = _text(item.get("relation"))
        if role_name in {from_name, to_name} and (from_name or to_name or relation):
            relation_rows.append(f"{from_name or '?'} -> {to_name or '?'}：{relation or '关系待核实'}")
    if relation_rows:
        lines.append(f"- 原始关系记录：{'；'.join(relation_rows[:6])}")
    lines.append("- 身份规则：亲属、朋友、同事、邻居、证人、嫌疑人、被害人、报警人、民警等身份/关系，只有本锚点明确支持时才可使用；否则只用姓名或“对方”。")
    lines.append("- 禁止把其他人的身份、排行、关系、职业、案件角色或经历说成自己的第一人称经历。")
    return "\n".join(lines)


def _role_brain_signature(role: models.Role, case: Optional[models.Case], scene: Optional[models.Scene], script: str) -> str:
    raw = "|".join(
        [
            _text(getattr(role, "id", "")),
            _role_display_name(role),
            _text(getattr(role, "person_id", "")),
            _text(getattr(role, "role_type", "")),
            _text(getattr(case, "id", "")) if case else "",
            _text(getattr(scene, "id", "")) if scene else "",
            _text(script)[:1200],
        ]
    )
    return hashlib.sha1(raw.encode("utf-8", errors="ignore")).hexdigest()[:16]


def _identity_terms_from_text(text: str) -> list[str]:
    return [term for term in _IDENTITY_TERMS if term in _text(text)]


def _allowed_identity_terms_for_role(role: models.Role, identity_anchor: str, profile: dict[str, Any]) -> list[str]:
    evidence_lines: list[str] = []
    for line in identity_anchor.splitlines():
        clean = _text(line)
        if not clean or clean.startswith("- 身份规则") or clean.startswith("- 禁止"):
            continue
        evidence_lines.append(clean)

    role_type = _text(getattr(role, "role_type", ""))
    if any(token in role_type for token in ("嫌疑", "违法", "主犯", "从犯", "嫌疑对象")):
        evidence_lines.append("嫌疑人 违法嫌疑人 当事人")
    if any(token in role_type for token in ("证人", "目击", "旁观")):
        evidence_lines.append("证人 目击者 旁观者")
    if any(token in role_type for token in ("被害", "受害")):
        evidence_lines.append("被害人 受害人 当事人")
    if "报警" in role_type:
        evidence_lines.append("报警人 当事人")
    if any(token in role_type for token in ("民警", "警察", "辅警")):
        evidence_lines.append("民警 警察 辅警")

    direct_links = (profile.get("relationship_map") or {}).get("direct_links") or []
    evidence_lines.extend(str(item) for item in direct_links[:8])
    return sorted(set(_identity_terms_from_text("\n".join(evidence_lines))))


def _build_role_brain(
    *,
    role: models.Role,
    case: Optional[models.Case],
    scene: Optional[models.Scene],
    profile: Optional[dict[str, Any]] = None,
    script: str = "",
    history: Optional[list[Any]] = None,
    previous_brain: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    profile = profile or build_persona_profile(role, case, scene)
    script = script or build_role_script(role, case, scene, profile)
    identity_anchor = _format_identity_anchor(role, case, profile)
    previous = previous_brain if isinstance(previous_brain, dict) else {}
    role_id = getattr(role, "id", None)
    role_name = _role_display_name(role)
    role_type = _text(getattr(role, "role_type", ""))
    person_id = _text(getattr(role, "person_id", ""))
    recent_self_utterances = _recent_role_contents(history or [], role)
    last_topics = list(previous.get("last_topics") or [])
    for content in recent_self_utterances:
        topic = _topic_label(content)
        if topic:
            last_topics.append(topic)
    allowed_identity_terms = _allowed_identity_terms_for_role(role, identity_anchor, profile)
    return {
        **previous,
        "brain_id": f"role:{role_id or role_name}",
        "role_id": role_id,
        "role_name": role_name,
        "person_id": person_id,
        "role_type": role_type,
        "brain_signature": _role_brain_signature(role, case, scene, script),
        "identity_anchor": identity_anchor,
        "allowed_identity_terms": allowed_identity_terms,
        "known_facts": merge_role_knows_facts(role, case),
        "hidden_truths": _format_facts(getattr(role, "hidden_truths", [])),
        "does_not_know": _format_facts(getattr(role, "does_not_know", [])),
        "script_excerpt": _text(script)[:1600],
        "last_self_utterances": recent_self_utterances[-4:] or list(previous.get("last_self_utterances") or [])[-4:],
        "last_topics": last_topics[-8:],
    }


def _format_role_brain_block(role_brain: dict[str, Any]) -> str:
    brain = role_brain if isinstance(role_brain, dict) else {}
    lines = [
        f"- brain_id：{_text(brain.get('brain_id')) or '未绑定'}",
        f"- 这颗大脑只属于：{_text(brain.get('role_name')) or '当前角色'}",
        f"- 身体/姓名：{_text(brain.get('role_name')) or '当前角色'}",
        f"- person_id：{_text(brain.get('person_id')) or '未配置'}",
        f"- 案件角色：{_text(brain.get('role_type')) or '相关人员'}",
        f"- 剧本签名：{_text(brain.get('brain_signature')) or '未生成'}",
        "- 第一人称“我”只能指向这具身体和这个姓名，不能指向其他任何角色。",
        "- 其他角色发言只属于外部声音；你可以回应、反驳、补充，但不能继承对方身份、关系、记忆或经历。",
    ]
    allowed_terms = brain.get("allowed_identity_terms") if isinstance(brain.get("allowed_identity_terms"), list) else []
    lines.append(f"- 可使用身份/关系称谓：{'、'.join(_text(item) for item in allowed_terms if _text(item)) or '无明确称谓，优先说姓名或“对方”'}")
    last_topics = brain.get("last_topics") if isinstance(brain.get("last_topics"), list) else []
    if last_topics:
        lines.append(f"- 你最近已说过的话题：{'、'.join(_text(item) for item in last_topics[-4:] if _text(item))}")
    last_self = brain.get("last_self_utterances") if isinstance(brain.get("last_self_utterances"), list) else []
    if last_self:
        lines.append(f"- 你自己最近说过：{' / '.join(_text(item)[:80] for item in last_self[-2:] if _text(item))}")
    script_excerpt = _text(brain.get("script_excerpt"))
    if script_excerpt:
        lines.append(f"- 你的专属剧本摘录：{script_excerpt}")
    return "\n".join(lines)


def _update_role_brain_after_output(
    role_brain: dict[str, Any],
    utterances: list[dict[str, str]],
    user_text: str,
) -> dict[str, Any]:
    brain = dict(role_brain or {})
    topics = list(brain.get("last_topics") or [])
    user_topic = _topic_label(user_text)
    if user_topic:
        topics.append(user_topic)
    self_utterances = list(brain.get("last_self_utterances") or [])
    for item in utterances or []:
        content = _text(item.get("content") if isinstance(item, dict) else item)
        if not content:
            continue
        self_utterances.append(content)
        topic = _topic_label(content)
        if topic:
            topics.append(topic)
    brain["last_topics"] = topics[-8:]
    brain["last_self_utterances"] = self_utterances[-4:]
    return brain



def _clamp_delta(value: Any, low: int = -15, high: int = 15) -> int:
    try:
        numeric = int(value)
    except (TypeError, ValueError):
        return 0
    return max(low, min(high, numeric))


def _looks_like_question(text: str) -> bool:
    if not text:
        return False
    return bool(re.search(r"[？?]|吗|么|什么|哪里|哪儿|几点|多久|是否|有没有|为什么|怎么|能不能", text))


def _acknowledges_action(text: str) -> bool:
    if not text:
        return False
    return bool(re.search(r"已经|已|马上|正在|通知|叫.*救护车|救护车|120|请稍等|稍等|安排|派人|到场", text))


def _sanitize_utterances_for_last_user(utterances: list[dict[str, str]], user_text: str) -> list[dict[str, str]]:
    """Keep role replies anchored to the latest learner message, not stale history."""
    if _looks_like_question(user_text) or not _acknowledges_action(user_text):
        return utterances

    stale_question_patterns = (
        "你们别光问",
        "你们就光问",
        "光问这些",
        "你刚才问",
        "你们刚才问",
        "你不是问",
        "倒是问",
    )
    sanitized: list[dict[str, str]] = []
    replaced = False
    for item in utterances:
        content = _text(item.get("content"))
        if any(pattern in content for pattern in stale_question_patterns):
            if not replaced:
                sanitized.append(
                    {
                        "content": "那你们帮我确认一下，救护车到底什么时候能到？人现在还在这儿，我心里没底。",
                        "delivery": item.get("delivery") or "anxious",
                    }
                )
                replaced = True
            continue
        sanitized.append(item)
    return sanitized or utterances


def _recent_dialogue_text(history: list[Any], limit: int = 4) -> str:
    lines: list[str] = []
    for message in history[-limit:]:
        role = _text(getattr(message, "role", ""))
        speaker = _text(getattr(message, "speaker_name", ""))
        content = _text(getattr(message, "content", ""))
        if not content:
            continue
        if speaker:
            lines.append(f"{speaker}: {content}")
        else:
            lines.append(f"{role}: {content}")
    return "\n".join(lines)


def _topic_label(text: str) -> str:
    content = _text(text)
    if not content:
        return ""
    topic_map = [
        ("身份", ("身份", "你是谁", "叫什么", "关系", "哥哥", "弟弟", "姐姐", "妹妹", "你哥", "你弟", "你姐", "你妹", "亲属")),
        ("时间", ("时间", "几点", "什么时候", "多久", "何时")),
        ("地点", ("地点", "哪里", "哪儿", "位置", "现场", "门口", "路口")),
        ("经过", ("经过", "怎么回事", "起因", "原因", "过程", "打架", "冲突")),
        ("责任", ("责任", "诬赖", "栽赃", "背锅", "谁先", "动手", "认定")),
        ("赔偿", ("赔偿", "赔钱", "补偿", "损失", "医药费", "钱怎么算")),
        ("安全", ("安全", "120", "救护车", "报警", "保护", "别碰")),
        ("关系", ("关系", "谁和谁", "亲戚", "家属", "朋友", "同事")),
    ]
    for label, keywords in topic_map:
        if any(keyword in content for keyword in keywords):
            return label
    return ""


def _extract_recent_topics(
    history: list[Any],
    role: models.Role,
    limit: int = 6,
    role_brain: Optional[dict[str, Any]] = None,
) -> list[str]:
    brain_topics = (
        role_brain.get("last_topics")
        if isinstance(role_brain, dict) and isinstance(role_brain.get("last_topics"), list)
        else []
    )
    topics = [_text(item) for item in brain_topics if _text(item)]
    if len(topics) >= 2:
        return topics[-limit:]
    topics: list[str] = []
    role_name = _role_display_name(role)
    for message in history[-limit:]:
        if _text(getattr(message, "role", "")) not in {"assistant", "ai"}:
            continue
        speaker = _text(getattr(message, "speaker_name", ""))
        if speaker and speaker != role_name:
            continue
        topic = _topic_label(_text(getattr(message, "content", "")))
        if topic:
            topics.append(topic)
    return topics


def _last_user_topic(user_text: str) -> str:
    return _topic_label(user_text)


def _needs_topic_shift(
    history: list[Any],
    role: models.Role,
    user_text: str,
    role_brain: Optional[dict[str, Any]] = None,
) -> bool:
    recent_topics = _extract_recent_topics(history, role, role_brain=role_brain)
    if len(recent_topics) < 2:
        return False
    user_topic = _last_user_topic(user_text)
    if not user_topic:
        return True
    if recent_topics[-1] == user_topic:
        return False
    return recent_topics[-1] == recent_topics[-2]


def _topic_shift_reply(role: models.Role, user_text: str) -> str:
    role_type = _text(getattr(role, "role_type", ""))
    if any(token in _text(user_text) for token in ("诬赖", "冤枉", "栽赃", "背锅", "垫背", "拉我下水")):
        return "你问的是刚才那句话有没有依据，我先按实际听到的说，别再把没说过的话往谁身上套。"
    if any(token in _text(user_text) for token in ("身份", "你是谁", "叫什么", "关系", "哥哥", "弟弟", "你哥", "你弟", "你姐", "你妹")):
        return "身份我先按我自己的情况说明，别把别人的话套到我身上。"
    if any(token in _text(user_text) for token in ("时间", "几点", "什么时候")):
        return "时间我先说能确认的那部分，别让我一直卡在同一个点上。"
    if any(token in _text(user_text) for token in ("地点", "哪里", "哪儿", "位置")):
        return "地点我先补清楚，后面你再问下一项。"
    if any(token in _text(user_text) for token in ("赔偿", "赔钱", "补偿", "损失", "医药费")):
        return "赔偿这块可以后面说，先把眼前的事说清。"
    if "嫌疑" in role_type:
        return "你先问一个新点，我把刚才没说清的补上。"
    if "证" in role_type:
        return "我换个我亲眼看到的细节说，免得一直绕同一件事。"
    return "这件事我先换个角度说，别一直绕在同一个点上。"


def _sanitize_unsupported_accusations(
    utterances: list[dict[str, str]],
    *,
    role: models.Role,
    user_text: str,
    history: list[Any],
) -> list[dict[str, str]]:
    evidence_text = f"{user_text}\n{_recent_dialogue_text(history, limit=3)}"
    accusation_terms = ("诬赖", "冤枉", "栽赃", "背锅", "拉我下水", "他说我动手", "非说我动手", "他说的不算数")
    has_evidence = any(term in evidence_text for term in accusation_terms) or any(
        phrase in evidence_text for phrase in ("说你", "说我", "指认", "指责", "动手")
    )
    if has_evidence:
        return utterances

    cleaned: list[dict[str, str]] = []
    replaced = False
    for item in utterances:
        content = _text(item.get("content"))
        if any(term in content for term in accusation_terms):
            if not replaced:
                cleaned.append(
                    {
                        "content": _vague_reply(role),
                        "delivery": item.get("delivery") or "defensive",
                    }
                )
                replaced = True
            continue
        cleaned.append(item)
    return cleaned or utterances


def _sanitize_identity_confusion(
    utterances: list[dict[str, str]],
    *,
    role: models.Role,
    identity_anchor: str,
    role_brain: Optional[dict[str, Any]] = None,
) -> list[dict[str, str]]:
    role_name = _role_display_name(role)
    brain_allowed = (
        role_brain.get("allowed_identity_terms")
        if isinstance(role_brain, dict) and isinstance(role_brain.get("allowed_identity_terms"), list)
        else []
    )
    if isinstance(role_brain, dict):
        supported_terms = {_text(token) for token in brain_allowed if _text(token)}
    else:
        anchor_evidence = "\n".join(
            line
            for line in identity_anchor.splitlines()
            if not _text(line).startswith("- 身份规则") and not _text(line).startswith("- 禁止")
        )
        supported_terms = set(_identity_terms_from_text(anchor_evidence))
    rewrite_rules: list[tuple[str, str]] = [
        ("我哥哥", role_name),
        ("我弟弟", role_name),
        ("我姐姐", role_name),
        ("我妹妹", role_name),
        ("我是哥哥", role_name),
        ("我是弟弟", role_name),
        ("我是姐姐", role_name),
        ("我是妹妹", role_name),
        ("我是父亲", role_name),
        ("我是母亲", role_name),
        ("我是丈夫", role_name),
        ("我是妻子", role_name),
        ("我是老公", role_name),
        ("我是老婆", role_name),
        ("我是证人", role_name),
        ("我是目击者", role_name),
        ("我是旁观者", role_name),
        ("我是嫌疑人", role_name),
        ("我是违法嫌疑人", role_name),
        ("我是被害人", role_name),
        ("我是受害人", role_name),
        ("我是报警人", role_name),
        ("我是当事人", role_name),
        ("我是家属", role_name),
        ("我是亲戚", role_name),
        ("我是朋友", role_name),
        ("我是同事", role_name),
        ("我是邻居", role_name),
        ("我是民警", role_name),
        ("我是警察", role_name),
        ("我是辅警", role_name),
        ("我是保安", role_name),
        ("我是店员", role_name),
        ("我是老板", role_name),
        ("我是司机", role_name),
        ("我是乘客", role_name),
        ("我是医生", role_name),
        ("我是护士", role_name),
        ("我是老师", role_name),
        ("我是学生", role_name),
        ("我是房东", role_name),
        ("我是租客", role_name),
        ("我爸", role_name),
        ("我妈", role_name),
        ("我哥", role_name),
        ("我弟", role_name),
        ("我姐", role_name),
        ("我妹", role_name),
        ("他爸", "对方"),
        ("他妈", "对方"),
        ("他哥", "对方"),
        ("他弟", "对方"),
        ("她爸", "对方"),
        ("她妈", "对方"),
        ("她哥", "对方"),
        ("她弟", "对方"),
        ("哥哥", "对方"),
        ("弟弟", "对方"),
        ("姐姐", "对方"),
        ("妹妹", "对方"),
        ("兄弟", "对方"),
        ("姐妹", "对方"),
        ("父亲", "对方"),
        ("母亲", "对方"),
        ("爸爸", "对方"),
        ("妈妈", "对方"),
        ("儿子", "对方"),
        ("女儿", "对方"),
        ("丈夫", "对方"),
        ("妻子", "对方"),
        ("老公", "对方"),
        ("老婆", "对方"),
        ("叔叔", "对方"),
        ("阿姨", "对方"),
        ("舅舅", "对方"),
        ("姑姑", "对方"),
        ("伯父", "对方"),
        ("伯母", "对方"),
        ("侄子", "对方"),
        ("侄女", "对方"),
        ("外甥", "对方"),
        ("外甥女", "对方"),
        ("亲戚", "对方"),
        ("家属", "对方"),
        ("朋友", "对方"),
        ("同事", "对方"),
        ("邻居", "对方"),
        ("同学", "对方"),
        ("证人", "对方"),
        ("目击者", "对方"),
        ("旁观者", "对方"),
        ("嫌疑人", "对方"),
        ("违法嫌疑人", "对方"),
        ("被害人", "对方"),
        ("受害人", "对方"),
        ("报警人", "对方"),
        ("当事人", "对方"),
        ("民警", "对方"),
        ("警察", "对方"),
        ("辅警", "对方"),
        ("保安", "对方"),
        ("店员", "对方"),
        ("老板", "对方"),
        ("司机", "对方"),
        ("乘客", "对方"),
        ("医生", "对方"),
        ("护士", "对方"),
        ("老师", "对方"),
        ("学生", "对方"),
        ("房东", "对方"),
        ("租客", "对方"),
    ]
    cleaned: list[dict[str, str]] = []
    for item in utterances:
        content = _text(item.get("content"))
        if not content:
            continue
        if any(token in content for token in _IDENTITY_TERMS):
            for token, replacement in sorted(rewrite_rules, key=lambda pair: len(pair[0]), reverse=True):
                if token in content and token not in supported_terms:
                    content = content.replace(token, replacement)
        cleaned.append({**item, "content": content})
    return cleaned or utterances


def _sanitize_topic_fixation(
    utterances: list[dict[str, str]],
    *,
    role: models.Role,
    history: list[Any],
    user_text: str,
    role_brain: Optional[dict[str, Any]] = None,
) -> list[dict[str, str]]:
    if not utterances:
        return utterances
    user_topic = _last_user_topic(user_text)
    first_topic = _topic_label(_text(utterances[0].get("content")))
    if user_topic and first_topic and first_topic != user_topic:
        repaired = list(utterances)
        repaired[0] = {
            **repaired[0],
            "content": _topic_shift_reply(role, user_text),
            "delivery": repaired[0].get("delivery") or "normal",
        }
        return repaired
    if not _needs_topic_shift(history, role, user_text, role_brain=role_brain):
        return utterances

    recent_topics = _extract_recent_topics(history, role, role_brain=role_brain)
    target_topic = user_topic or (recent_topics[-1] if recent_topics else "")
    if not target_topic:
        return utterances

    first_topic = _topic_label(_text(utterances[0].get("content")))
    if first_topic and first_topic == target_topic:
        return utterances

    repaired = list(utterances)
    repaired[0] = {
        **repaired[0],
        "content": _topic_shift_reply(role, user_text),
        "delivery": repaired[0].get("delivery") or "normal",
    }
    return repaired


def _normalize_repeat_key(text: str) -> str:
    return re.sub(r"[\s，。！？,.!?、；;：“”\"'（）()…]+", "", _text(text))


def _repeat_similarity(left: str, right: str) -> float:
    """Cheap character n-gram similarity for paraphrased repeat detection."""
    a = _normalize_repeat_key(left)
    b = _normalize_repeat_key(right)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    grams_a = {a[index:index + 2] for index in range(max(0, len(a) - 1))}
    grams_b = {b[index:index + 2] for index in range(max(0, len(b) - 1))}
    if not grams_a or not grams_b:
        return 0.0
    return len(grams_a & grams_b) / max(1, len(grams_a | grams_b))


def _repetition_repair(user_text: str, delivery: str = "defensive") -> str:
    """Change the interaction move when a role keeps paraphrasing itself."""
    text = _text(user_text)
    if _contains_any(text, ("时间", "几点", "什么时候")):
        return "时间我先说我记得的：大概就在那会儿。具体分钟我不敢乱讲，你再问我地点。"
    if _contains_any(text, ("哪里", "地点")):
        return "地点我可以先说大概范围，细的位置我得再想一下，别一下把几个问题混在一起。"
    if _looks_like_question(text):
        return "这句我听明白了。具体事实我先回答一个，别让我重复刚才那段：你要先问时间、地点，还是谁先动手？"
    if _contains_any(text, ("安全", "救护", "120", "分开", "保护")):
        return "安全这件事我听到了。你先告诉我现在谁在旁边、距离多远，我再继续说。"
    return "我不是不回应。刚才那句我说过了，这次我补一个具体点：你先把问题拆开，我能答清楚。"


def _recent_role_contents(history: list[Any], role: models.Role) -> list[str]:
    role_name = _role_display_name(role)
    contents: list[str] = []
    for message in history[-10:]:
        if _text(getattr(message, "role", "")) not in {"assistant", "ai"}:
            continue
        speaker = _text(getattr(message, "speaker_name", ""))
        if speaker and speaker != role_name:
            continue
        content = _text(getattr(message, "content", ""))
        if content:
            contents.append(content)
    return contents[-4:]


def _is_loss_control_snapshot(snapshot: dict[str, int], contract: Optional[dict[str, Any]] = None) -> bool:
    scores = (contract or {}).get("scores") if isinstance(contract, dict) else {}
    emotion = int((scores or {}).get("emotion", snapshot.get("emotion", 50)) or 50)
    cooperation = int((scores or {}).get("cooperation", snapshot.get("cooperation", 30)) or 30)
    risk = int((scores or {}).get("risk", snapshot.get("risk", 50)) or 50)
    clarity = int((scores or {}).get("clarity", snapshot.get("clarity", 50)) or 50)
    return emotion >= 88 and risk >= 82 and cooperation <= 24 and clarity <= 28


def _loss_control_reply(role: models.Role, user_text: str, recent_contents: list[str]) -> str:
    """Contextual fallback for the high emotion/high risk/zeroed cooperation+clarity corner."""
    text = _text(user_text)
    name = _role_display_name(role)
    pools: list[str]
    if _contains_any(text, ("冷静", "别激动", "慢慢", "深呼吸", "先坐", "别急", "我在听")):
        pools = [
            "你先别靠太近……我听见了，你一句一句说，别一上来就围着我。",
            "我现在脑子乱，但你别吼我，我可以先站在这儿不动。",
            "行，你说慢点。我不是不听，我现在就是一下子缓不过来。",
        ]
    elif _contains_any(text, ("安全", "分开", "距离", "救护", "120", "保护", "派警", "控制现场")):
        pools = [
            "那你先让旁边的人别围着我，我看见人一多就更慌。",
            "你说已经处理安全，那你得让我看见他们离远点，我才说得下去。",
            "先别碰我。你把人分开，我就站这儿，别再刺激我。",
        ]
    elif _contains_any(text, ("时间", "几点", "地点", "哪里", "谁先", "经过", "证据", "监控", "伤", "动手")):
        pools = [
            "你别一下问这么多，我现在只能先说一个点。你问时间，还是问谁先动的手？",
            "我不确定顺序，脑子里乱成一团。你把问题拆开问，我能答一点是一点。",
            "我现在说不完整，你先问最要紧的那个，别让我从头到尾捋。",
        ]
    elif _contains_any(text, ("快说", "老实", "别废话", "必须", "是不是你", "违法", "故意")):
        pools = [
            "你别这么逼我，我越急越说不清，真要问就一个问题一个问题来。",
            "凭什么一上来就压我？我现在不是不说，是你这样问我脑子更乱。",
            "你别把话说死，我现在听不得这个。你要问事实就直接问事实。",
        ]
    elif _contains_any(text, ("身份", "你是谁", "叫什么")):
        pools = [
            f"我是{name}……你先别催，我现在有点乱，但人就在这儿。",
            f"我叫{name}。别一堆人围着问，我会更慌。",
        ]
    else:
        pools = [
            "你刚才那句我听见了，但我现在脑子乱，你换个更具体的问题问。",
            "我不是故意顶你，我现在真的说不顺。你先问一件事。",
            "等一下……你别连着问，我现在只能听明白一件事。",
        ]

    recent_keys = {_normalize_repeat_key(item) for item in recent_contents}
    for candidate in pools:
        if _normalize_repeat_key(candidate) not in recent_keys:
            return candidate
    return pools[0]


def _dedupe_and_repair_utterances(
    utterances: list[dict[str, str]],
    *,
    role: models.Role,
    history: list[Any],
    user_text: str,
    role_snapshot: dict[str, int],
    state_contract: Optional[dict[str, Any]] = None,
) -> list[dict[str, str]]:
    recent = _recent_role_contents(history, role)
    recent_keys = {_normalize_repeat_key(item) for item in recent}
    seen: set[str] = set()
    repaired: list[dict[str, str]] = []
    loss_control = _is_loss_control_snapshot(role_snapshot, state_contract)

    for item in utterances or []:
        content = _text(item.get("content"))
        if not content:
            continue
        key = _normalize_repeat_key(content)
        # Chinese paraphrases often share only a few bigrams; keep this below
        # exact-match territory while requiring a reasonably long utterance.
        semantically_repeated = len(key) >= 8 and any(_repeat_similarity(content, previous) >= 0.58 for previous in recent)
        if key and (key in seen or key in recent_keys or semantically_repeated):
            if not repaired:
                repaired.append(
                    {
                        "content": _loss_control_reply(role, user_text, recent) if loss_control else _repetition_repair(
                            user_text,
                            item.get("delivery") or (state_contract or {}).get("delivery") or "defensive",
                        ),
                        "delivery": item.get("delivery") or (state_contract or {}).get("delivery") or "anxious",
                    }
                )
            continue
        seen.add(key)
        repaired.append(item)

    if not repaired and loss_control:
        repaired.append(
            {
                "content": _loss_control_reply(role, user_text, recent),
                "delivery": (state_contract or {}).get("delivery") or "anxious",
            }
        )
    return repaired or utterances


def _json_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if not isinstance(value, str) or not value.strip():
        return {}
    try:
        parsed = json.loads(value)
    except Exception:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _string_items(value: Any) -> list[str]:
    if isinstance(value, str):
        return [_text(value)] if _text(value) else []
    if isinstance(value, dict):
        primitive_values = [
            _text(item)
            for item in value.values()
            if not isinstance(item, (dict, list)) and _text(item)
        ]
        if primitive_values:
            return [" ".join(primitive_values)]
        items = []
        for key, item in value.items():
            if isinstance(item, (dict, list)):
                items.extend(_string_items(item))
            else:
                text = _text(item)
                if text:
                    items.append(f"{key}：{text}")
        return items
    if isinstance(value, list):
        items = []
        for item in value:
            items.extend(_string_items(item))
        return items
    text = _text(value)
    return [text] if text else []


def _structured_items(case: Optional[models.Case], *keys: str) -> list[str]:
    data = _json_dict(getattr(case, "structured_data", None))
    for key in keys:
        value = data.get(key)
        if value is not None:
            items = _string_items(value)
            if items:
                return items
    return []


def _contains_any(text: str, words: tuple[str, ...]) -> bool:
    return any(word in text for word in words)


def _first_time_fact(case: Optional[models.Case]) -> str:
    timeline = _structured_items(case, "timeline", "时间线", "events", "事件")
    for item in timeline:
        match = re.search(r"\d{1,2}[:：]\d{2}", item)
        if match:
            return item
    return timeline[0] if timeline else ""


def _location_fact(scene: Optional[models.Scene], case: Optional[models.Case]) -> str:
    source = " ".join(
        _text(value)
        for value in (
            getattr(scene, "dispatch_brief", ""),
            getattr(scene, "first_impression", ""),
            getattr(scene, "description", ""),
            getattr(case, "background", ""),
        )
        if _text(value)
    )
    patterns = (
        r"[\u4e00-\u9fa5A-Za-z0-9]+(?:店|门口|路|街|巷|小区|市场|夜市|广场|现场|附近)",
        r"在([^，。；、\s]{2,20})",
    )
    for pattern in patterns:
        match = re.search(pattern, source)
        if match:
            return match.group(1) if match.lastindex else match.group(0)
    return ""


def _role_fact(role: models.Role, case: Optional[models.Case]) -> str:
    name = _role_display_name(role)
    role_type = _text(getattr(role, "role_type", ""))
    people = _structured_items(case, "persons", "people", "人物", "相关人员")
    for person in people:
        if name and name in person:
            tokens = [token for token in re.split(r"\s+", person.replace(name, " ").strip()) if token]
            if role_type:
                tokens.append(role_type)
            deduped = list(dict.fromkeys(tokens))
            return " ".join(deduped)
    return role_type


def _append_unique(lines: list[str], line: str) -> None:
    clean = _text(line)
    if clean and clean not in lines:
        lines.append(clean)


def _role_archetype(role: models.Role) -> str:
    role_type = _text(getattr(role, "role_type", ""))
    name = _role_display_name(role)
    if "被害" in role_type or "受害" in role_type or "赵阳" in name:
        return "victim"
    if "嫌疑" in role_type or "违法" in role_type or "刘军" in name:
        return "suspect"
    if "证" in role_type or "旁观" in role_type:
        return "witness"
    return "neutral"


def _time_reply(role: models.Role, time_fact: str) -> str:
    archetype = _role_archetype(role)
    if archetype == "victim":
        return f"我记得差不多是{time_fact}，那会儿我和他已经在收银台那边吵起来了。"
    if archetype == "suspect":
        return f"大概是{time_fact}吧。我当时喝了酒，时间可能没那么准。"
    if archetype == "witness":
        return f"我看到的时候大概是{time_fact}，他们两个已经吵起来了。"
    return f"我记得大概是{time_fact}。"


def _identity_reply(role: models.Role, role_fact: str) -> list[str]:
    name = _role_display_name(role)
    archetype = _role_archetype(role)
    if archetype == "victim":
        return [f"我是{name}，被打的是我，算是这事里的被害人。", "我现在就是想把当时怎么起冲突、谁先动手说清楚。"]
    if archetype == "suspect":
        return [f"我是{name}。", "我和赵阳是起了冲突，但你们也先别一上来就说全是我的问题。"]
    if archetype == "witness":
        return [f"我是{name}，我是在现场看到情况的人。"]
    if role_fact:
        return [f"我是{name}，{role_fact}。"]
    return [f"我是{name}，当时就在现场。"]


def _vague_reply(role: models.Role) -> str:
    archetype = _role_archetype(role)
    if archetype == "victim":
        return "你问哪一段？是问他怎么动手，还是问我伤在哪儿？"
    if archetype == "suspect":
        return "你问清楚点行不行？时间、地点、还是问谁先动的手？"
    if archetype == "witness":
        return "你问具体哪一段，我只说我亲眼看到的。"
    return "你把问题说具体一点，我好回答。"


def _rule_based_utterances(
    role: models.Role,
    cast_entry: dict[str, Any],
    user_text: str,
    utterance_count: int,
    scene: Optional[models.Scene] = None,
    case: Optional[models.Case] = None,
    reaction: Optional[dict[str, Any]] = None,
    peer_utterances: Optional[list[dict[str, Any]]] = None,
) -> dict[str, Any]:
    name = _role_display_name(role)
    role_type = _text(getattr(role, "role_type", ""))
    participation = _text(cast_entry.get("participation"))
    text = _text(user_text)
    background = _text(getattr(case, "background", ""))
    first_impression = _text(getattr(scene, "first_impression", ""))
    canonical = extract_canonical_facts(case, scene)
    time_fact = canonical.get("case_time") if canonical.get("case_time") != "未明确" else _first_time_fact(case)
    location = canonical.get("case_location") if canonical.get("case_location") != "未明确" else _location_fact(scene, case)
    evidence = _structured_items(case, "evidence_points", "evidence", "证据", "证据要点")
    people = _structured_items(case, "persons", "people", "人物", "相关人员")
    role_fact = _role_fact(role, case)
    archetype = _role_archetype(role)
    reaction = reaction or {}
    reaction_key = _text(reaction.get("key"))
    lines: list[str] = []
    if _is_loss_control_snapshot(dict(cast_entry.get("role_snapshot") or {})):
        lines.append(_loss_control_reply(role, text, []))
    preface = reaction_preface(role, reaction, peer_utterances)
    self_name = _role_display_name(role)
    if preface.startswith(f"{self_name}，") or preface.startswith(f"{self_name}锛"):
        peer_name = ""
        for item in reversed(peer_utterances or []):
            candidate = _text(item.get("speaker_name") if isinstance(item, dict) else "")
            if candidate and candidate != self_name:
                peer_name = candidate
                break
        if "别把话说成" in preface or "妸璇濊" in preface:
            preface = f"{peer_name}，你别把话说成那样。" if peer_name else "你别把话说成那样。"
        elif peer_name:
            preface = re.sub(rf"^{re.escape(self_name)}[，锛][^你]*", f"{peer_name}，", preface, count=1)
        else:
            preface = re.sub(rf"^{re.escape(self_name)}[，锛]\s*", "", preface, count=1)
    direct_fact_question = _contains_any(
        text,
        ("身份", "你是谁", "叫什么", "关系", "几点", "时间", "什么时候", "哪里", "地点", "位置", "在哪"),
    )
    should_preface = bool(peer_utterances) or participation == "interrupt" or not direct_fact_question
    if preface and reaction_key != "sudden_cooperation" and should_preface:
        _append_unique(lines, preface)
    if participation == "interrupt":
        _append_unique(lines, f"{name}，你等一下，事情不是那样！")
    if _contains_any(text, ("冷静", "别激动", "放松", "慢慢说")):
        if archetype == "suspect":
            _append_unique(lines, "行，我先不吵了。但你让我把话说完。")
        elif archetype == "victim":
            _append_unique(lines, "我可以慢慢说，但他刚才确实动手了。")
        else:
            _append_unique(lines, "我配合，你问哪一段我说哪一段。")
    if reaction_key == "sudden_cooperation" and preface:
        _append_unique(lines, preface)
    if reaction_key == "avoidant_silence" and len(lines) < utterance_count:
        _append_unique(lines, "有些细节我真不敢乱说，你们别把我也卷进去。")
    if reaction_key == "protective_fear" and len(lines) < utterance_count:
        _append_unique(lines, "你们先保证我说完以后不会再被人找麻烦，我再慢慢讲。")
    if reaction_key == "topic_shift_bargain" and len(lines) < utterance_count:
        _append_unique(lines, "赔不赔、怎么处理总得有个说法吧，别光问谁对谁错。")
    if _contains_any(text, ("身份", "你是谁", "叫什么", "关系")):
        for line in _identity_reply(role, role_fact):
            _append_unique(lines, line)
    if _contains_any(text, ("几点", "时间", "什么时候", "发生")) and time_fact:
        _append_unique(lines, _time_reply(role, time_fact))
    if _contains_any(text, ("哪里", "地点", "位置", "在哪", "现场")) and location:
        if archetype == "suspect":
            _append_unique(lines, f"就在{location}，旁边人不少，我也不想在那儿丢这个脸。")
        elif archetype == "victim":
            _append_unique(lines, f"就在{location}，当时旁边有人围着看。")
        else:
            _append_unique(lines, f"地点是在{location}，我是在旁边看到的。")
    if _contains_any(text, ("伤", "打", "疼", "伤情", "动手")):
        if archetype == "victim":
            _append_unique(lines, "我眉弓这边被他打到了，现在还疼。")
        elif archetype == "suspect":
            _append_unique(lines, "我承认有推搡，也碰到他了，但当时是吵急了。")
        elif archetype == "witness":
            _append_unique(lines, "我看到他们有推搡，后来赵阳脸这边像是被打到了。")
    if _contains_any(text, ("证据", "监控", "证人", "谁看见", "付款")):
        fact = "；".join(evidence[:2]) if evidence else ""
        witness = next((item for item in people if "证人" in item or "孙桂兰" in item), "")
        if fact:
            _append_unique(lines, f"你们可以去看{fact}，别光听我们在这儿吵。")
        if witness:
            _append_unique(lines, f"{witness}，她当时也在，可以问她。")
    if _contains_any(text, ("经过", "怎么回事", "原因", "起因")):
        if archetype == "suspect":
            _append_unique(lines, "一开始就是结账那点事吵起来的，我喝了酒，话赶话就急了。")
        elif archetype == "victim":
            _append_unique(lines, "就是结账插队那点事，他说话冲，后面就推我、打到我脸上。")
        elif archetype == "witness":
            _append_unique(lines, "我看到他们先因为结账的事吵，后来声音越来越大，就有人动手了。")
        elif background:
            _append_unique(lines, background)
        else:
            _append_unique(lines, "刚才确实先吵了几句，后来才动了手。")
    if first_impression and len(lines) < utterance_count and _contains_any(text, ("现场", "情况", "人多")):
        _append_unique(lines, first_impression)
    if not lines:
        _append_unique(lines, _vague_reply(role))
    lines = lines[:utterance_count]
    base_delta = {"emotion": -2, "cooperation": 3, "risk": -1, "clarity": 2}
    if reaction_key and reaction_key not in {"sudden_cooperation", "probing_observation"}:
        base_delta = {"emotion": 0, "cooperation": 0, "risk": 0, "clarity": 0}
    return {
        "utterances": [{"content": line, "delivery": reaction.get("delivery") or "normal"} for line in lines],
        "inner_thought": "先稳住，看看警察怎么问。",
        "state_delta": merge_reaction_delta(base_delta, reaction),
        "new_fact_revealed": None,
    }


def _build_perspective_hint(
    role: models.Role,
    user_text: str,
    cast_entry: dict[str, Any],
    addressed_targets: Optional[list[str]] = None,
) -> str:
    self_name = _role_display_name(role)
    intent = _text(cast_entry.get("intent"))
    others = []
    for name in addressed_targets or []:
        clean = _text(name)
        if clean and clean != self_name and clean not in others:
            others.append(clean)
    if not others:
        text = _text(user_text)
        for name in addressed_targets or []:
            if name and name != self_name and name in text:
                others.append(name)
    if intent == "witness_account" or others:
        joined = "、".join(others) if others else "对方"
        return (
            f"你是「{self_name}」（{_text(role.role_type) or '相关人员'}）。"
            f"学员主要在问「{joined}」，你必须以本人/旁观者身份回答，禁止用「我」冒充{joined}的第一人称经历。"
        )
    return f"你是「{self_name}」，必须以本人第一人称回答，不要替其他角色说话。"


def generate_role_dialogue(
    *,
    role: models.Role,
    cast_entry: dict[str, Any],
    director_plan: dict[str, Any],
    scene: Optional[models.Scene],
    case: Optional[models.Case],
    history: list[Any],
    user_text: str,
    current_stage: str,
    role_snapshot: dict[str, int],
    addressed_targets: Optional[list[str]] = None,
    peer_utterances: Optional[list[dict[str, Any]]] = None,
    role_brain: Optional[dict[str, Any]] = None,
    use_llm: bool = True,
) -> dict[str, Any]:
    utterance_count = max(1, min(8, int(cast_entry.get("utterance_count") or 1)))
    profile = build_persona_profile(role, case, scene)
    script = build_role_script(role, case, scene, profile)
    role_brain = _build_role_brain(
        role=role,
        case=case,
        scene=scene,
        profile=profile,
        script=script,
        history=history,
        previous_brain=role_brain,
    )
    knowledge_bundle = load_case_knowledge_bundle(case, role)
    retrieval_query = rag_service.build_retrieval_query(
        user_text,
        getattr(case, "case_type", "") if case else "",
        getattr(case, "title", "") if case else "",
        getattr(scene, "name", "") if scene else "",
        current_stage,
        history=[getattr(message, "content", "") for message in history[-4:]],
    )
    retrieval_bundle = rag_service.build_context_block(
        retrieval_query,
        limit=4,
        libraries=RUNTIME_RETRIEVAL_LIBRARIES,
        max_chars=2800,
    )
    momentum = analyze_dialogue_momentum(
        user_text,
        profile,
        "",
        role_snapshot.get("cooperation", 30),
        role_snapshot.get("emotion", 50),
    )
    momentum = enrich_momentum_with_axis_deltas(momentum, user_text, [], profile)
    state_contract = build_state_contract(role_snapshot, momentum, profile)
    persona_block = format_persona_block(profile, script, {}, momentum)
    role_brain_block = _format_role_brain_block(role_brain)
    identity_anchor_block = _text(role_brain.get("identity_anchor")) or _format_identity_anchor(role, case, profile)
    state_contract_block = format_state_contract_block(state_contract)
    reaction = choose_role_reaction(
        role=role,
        role_snapshot=role_snapshot,
        user_text=user_text,
        scene_mood=_text(director_plan.get("scene_mood")) or _text(director_plan.get("scene_mood_shift")) or "stable",
        persona_profile=profile,
        cast_entry=cast_entry,
        peer_utterances=peer_utterances or [],
    )
    if cast_entry.get("reaction_hint"):
        reaction["director_hint"] = _text(cast_entry.get("reaction_hint"))
    human_reaction_block = format_actor_reaction_block(reaction, peer_utterances or [])
    perspective_hint = _build_perspective_hint(
        role,
        user_text,
        cast_entry,
        addressed_targets or director_plan.get("addressed_targets"),
    )

    output: Optional[dict[str, Any]] = None
    if use_llm:
        prompt = ROLE_ACTOR_PROMPT.format(
            role_name=_role_display_name(role),
            interaction_mode=_text(director_plan.get("interaction_mode")) or "mixed",
            participation=_text(cast_entry.get("participation")) or "primary_respond",
            utterance_count=utterance_count,
            intent=_text(cast_entry.get("intent")) or "respond",
            trigger_reason=_text(cast_entry.get("trigger_reason")) or "现场对话",
            scene_name=_text(getattr(scene, "name", "")) or "现场",
            current_stage=current_stage or "训练中",
            user_text=user_text or "（学员沉默）",
            persona_block=persona_block,
            role_brain_block=role_brain_block,
            identity_anchor_block=identity_anchor_block,
            state_contract_block=state_contract_block,
            human_reaction_block=human_reaction_block,
            perspective_hint=perspective_hint,
            canonical_facts_block=format_canonical_facts_block(case, scene),
            case_knowledge_block=knowledge_bundle.get("knowledge_block") or "暂无案件知识库内容",
            retrieved_knowledge_block=retrieval_bundle.get("context_block") or "本轮未召回到可用法规、SOP或教学资料。",
            knows_facts=merge_role_knows_facts(role, case),
            hidden_truths=_format_facts(getattr(role, "hidden_truths", [])),
            does_not_know=_format_facts(getattr(role, "does_not_know", [])),
            peer_utterances_block=format_peer_utterances_block(peer_utterances or []),
            history_block=_build_history_block(history),
        )
        try:
            response = create_json_chat_completion(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.82,
                model=get_chat_model(),
                max_tokens=1800,
            )
            raw = extract_message_text(response) or ""
            match = re.search(r"\{[\s\S]*\}", raw)
            payload = json.loads(match.group(0) if match else raw)
            utterances = payload.get("utterances") if isinstance(payload.get("utterances"), list) else []
            cleaned = []
            for item in utterances[:utterance_count]:
                if isinstance(item, dict) and _text(item.get("content")):
                    cleaned.append({"content": _text(item.get("content")), "delivery": _text(item.get("delivery")) or "normal"})
                elif isinstance(item, str) and _text(item):
                    cleaned.append({"content": _text(item), "delivery": "normal"})
            if cleaned:
                cleaned = sanitize_utterances(cleaned)
                cleaned = _sanitize_utterances_for_last_user(cleaned, user_text)
                cleaned = _sanitize_unsupported_accusations(
                    cleaned,
                    role=role,
                    user_text=user_text,
                    history=history,
                )
                cleaned = _sanitize_identity_confusion(
                    cleaned,
                    role=role,
                    identity_anchor=identity_anchor_block,
                    role_brain=role_brain,
                )
                cleaned = _sanitize_topic_fixation(
                    cleaned,
                    role=role,
                    history=history,
                    user_text=user_text,
                    role_brain=role_brain,
                )
                delta = payload.get("state_delta") if isinstance(payload.get("state_delta"), dict) else {}
                output = {
                    "utterances": cleaned,
                    "inner_thought": _text(payload.get("inner_thought")) or "",
                    "state_delta": merge_reaction_delta(
                        {
                            "emotion": _clamp_delta(delta.get("emotion")),
                            "cooperation": _clamp_delta(delta.get("cooperation")),
                            "risk": _clamp_delta(delta.get("risk")),
                            "clarity": _clamp_delta(delta.get("clarity")),
                        },
                        reaction,
                    ),
                    "new_fact_revealed": payload.get("new_fact_revealed"),
                }
        except Exception:
            output = None

    if not output:
        output = _rule_based_utterances(
            role,
            {**cast_entry, "role_snapshot": role_snapshot},
            user_text,
            utterance_count,
            scene,
            case,
            reaction=reaction,
            peer_utterances=peer_utterances or [],
        )

    output["utterances"] = apply_delivery_from_contract(
        sanitize_utterances(_sanitize_utterances_for_last_user(output.get("utterances") or [], user_text)),
        state_contract,
    )
    output["utterances"] = _sanitize_unsupported_accusations(
        output["utterances"],
        role=role,
        user_text=user_text,
        history=history,
    )
    output["utterances"] = _sanitize_identity_confusion(
        output["utterances"],
        role=role,
        identity_anchor=identity_anchor_block,
        role_brain=role_brain,
    )
    output["utterances"] = _sanitize_topic_fixation(
        output["utterances"],
        role=role,
        history=history,
        user_text=user_text,
        role_brain=role_brain,
    )
    output["utterances"] = _dedupe_and_repair_utterances(
        output["utterances"],
        role=role,
        history=history,
        user_text=user_text,
        role_snapshot=role_snapshot,
        state_contract=state_contract,
    )

    role_brain = _update_role_brain_after_output(role_brain, output["utterances"], user_text)

    return {
        "speaker_name": _role_display_name(role),
        "speaker_role_id": role.id,
        "role": role,
        "participation": cast_entry.get("participation"),
        "utterances": output["utterances"][:utterance_count],
        "inner_thought": output.get("inner_thought") or "",
        "state_delta": output.get("state_delta") or {},
        "new_fact_revealed": output.get("new_fact_revealed"),
        "updated_snapshot": _apply_snapshot_delta(role_snapshot, output.get("state_delta") or {}),
        "state_contract": state_contract,
        "reaction_type": reaction.get("key"),
        "reaction_label": reaction.get("label"),
        "reaction_types": reaction.get("keys") or [reaction.get("key")],
        "reaction_labels": reaction.get("labels") or [reaction.get("label")],
        "role_brain": role_brain,
    }


def _apply_snapshot_delta(snapshot: dict[str, int], delta: dict[str, Any]) -> dict[str, int]:
    base = dict(snapshot or {})
    for key in ("emotion", "cooperation", "risk", "clarity"):
        base[key] = max(0, min(100, int(base.get(key, 50)) + _clamp_delta(delta.get(key))))
    return base
