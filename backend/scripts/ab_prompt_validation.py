import argparse
import json
from statistics import mean

import database
import models
from services import ai_service
from services.ai_service import _get_case_type, _get_stage_config
from services.role_resolver import resolve_scene_role
from services.training_runtime_service import dump_runtime_state, load_runtime_state


THREE_LAYER_APPEND = """

【语音理解层规则】
你接收到的是实时语音转写文本，可能存在同音字错误、断句问题和口语停顿词。优先理解意图，不要求用户重写文本。
对关键事实（时间、地点、人物、风险）先做语义归一化；信息不确定时用一句话澄清，不输出长篇解释。

【执法训练主规则】
当前任务是训练学员的口头表达与随机应变能力。
每轮回复控制在 1-3 句，先结论，再追问下一步；优先围绕身份核实、时间线、现场风险、处置动作推进。
禁止引导用户编辑文本后再发，禁止书面化长段输出。

【安全与边界规则】
出现伤害风险、持械、失控、逃逸等信号时，先给立即动作建议，再给追问要点和安抚话术。
禁止输出会激化冲突、规避执法或违法建议。
"""


def orality_score(text: str) -> float:
    text = str(text or "").strip()
    if not text:
        return 0.0
    oral_tokens = ["吗", "呢", "先", "再", "你说", "有没有", "请问", "先说", "先确认", "具体"]
    formal_tokens = ["因此", "首先", "其次", "综上", "建议如下", "根据", "请补充"]
    oral_hits = sum(token in text for token in oral_tokens)
    formal_hits = sum(token in text for token in formal_tokens)
    length_penalty = 1 if len(text) > 36 else 0
    return max(0.0, oral_hits - formal_hits - length_penalty)


def create_session(db, scene_id: int, user_id: int) -> models.TrainingSession:
    scene = db.query(models.Scene).filter(models.Scene.id == scene_id).first()
    if not scene:
        raise ValueError(f"scene_id={scene_id} not found")
    case = db.query(models.Case).filter(models.Case.id == scene.case_id).first()
    role = resolve_scene_role(db, scene, case)
    stage_config = _get_stage_config(scene, "", case_type=_get_case_type(case))
    stage_name = str(stage_config.get("stage_name") or "初始接触")
    init_trust = int(getattr(role, "init_trust", 30) or 30) if role else 30
    init_emotion = int(getattr(role, "init_emotion", 50) or 50) if role else 50
    runtime_state = load_runtime_state([])
    runtime_state["state_snapshot"] = {"cooperation": init_trust, "risk": 50, "clarity": 50}
    ts = models.TrainingSession(
        user_id=user_id,
        scene_id=scene_id,
        current_stage=stage_name,
        current_emotion=init_emotion,
        current_trust=init_trust,
        revealed_info=dump_runtime_state(runtime_state),
        status="active",
    )
    db.add(ts)
    db.commit()
    db.refresh(ts)
    return ts


def run_group(db, scene_id: int, user_id: int, use_three_layer: bool, rounds: int = 8) -> dict:
    baseline_prompt = ai_service.SYSTEM_PROMPT_TEMPLATE
    if use_three_layer:
        ai_service.SYSTEM_PROMPT_TEMPLATE = baseline_prompt + "\n" + THREE_LAYER_APPEND

    try:
        session = create_session(db, scene_id, user_id)
        seed_questions = [
            "先说一下当时发生了什么？",
            "你和对方是什么关系？",
            "事情大概几点开始的？",
            "现场还有谁在？",
            "有没有人受伤或者还有风险？",
        ]
        next_question = seed_questions[0]
        question_lengths = []
        orality_scores = []
        hit_rates = []
        off_topic_count = 0
        records = []

        for idx in range(rounds):
            result = ai_service.generate_dialogue(db, session.id, next_question, user_id=user_id)
            if not result:
                break
            question_lengths.append(len(next_question))
            orality_scores.append(orality_score(next_question))

            req = result.get("stage_completion_requirements") or []
            sat = result.get("stage_completion_satisfied") or []
            hit_rate = (len(sat) / len(req)) if req else 0.0
            hit_rates.append(hit_rate)

            tags = (result.get("communication_feedback") or {}).get("tags") or []
            if ("stage_gap" in tags) or ("question_too_short" in tags):
                off_topic_count += 1

            records.append(
                {
                    "round": idx + 1,
                    "question": next_question,
                    "ai_response": str(result.get("response") or "")[:120],
                    "hit_rate": round(hit_rate, 3),
                    "feedback_tags": tags,
                }
            )

            recommended = result.get("recommended_questions") or []
            if recommended:
                next_question = str(recommended[0]).strip()
            else:
                next_question = seed_questions[(idx + 1) % len(seed_questions)]

        total_rounds = max(1, len(records))
        return {
            "rounds": len(records),
            "avg_student_utterance_length": round(mean(question_lengths), 2) if question_lengths else 0.0,
            "avg_orality_score": round(mean(orality_scores), 3) if orality_scores else 0.0,
            "avg_stage_hit_rate": round(mean(hit_rates), 3) if hit_rates else 0.0,
            "offtopic_ratio": round(off_topic_count / total_rounds, 3),
            "records": records,
        }
    finally:
        ai_service.SYSTEM_PROMPT_TEMPLATE = baseline_prompt


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scene-id", type=int, default=1)
    parser.add_argument("--user-id", type=int, default=2)
    parser.add_argument("--rounds", type=int, default=8)
    args = parser.parse_args()

    db = database.SessionLocal()
    try:
        a_group = run_group(db, args.scene_id, args.user_id, use_three_layer=False, rounds=args.rounds)
        b_group = run_group(db, args.scene_id, args.user_id, use_three_layer=True, rounds=args.rounds)
        diff = {
            "orality_delta": round(b_group["avg_orality_score"] - a_group["avg_orality_score"], 3),
            "hit_rate_delta": round(b_group["avg_stage_hit_rate"] - a_group["avg_stage_hit_rate"], 3),
            "offtopic_ratio_delta": round(b_group["offtopic_ratio"] - a_group["offtopic_ratio"], 3),
        }
        print(
            json.dumps(
                {
                    "scene_id": args.scene_id,
                    "rounds": args.rounds,
                    "A_old_prompt": a_group,
                    "B_three_layer_prompt": b_group,
                    "delta_B_minus_A": diff,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
