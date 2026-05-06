import json
import os

from dotenv import load_dotenv
from openai import OpenAI
from sqlalchemy.orm import Session

import models
from .rag_service import rag_service

load_dotenv()


def get_client() -> OpenAI:
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        raise RuntimeError("DEEPSEEK_API_KEY is not configured")
    return OpenAI(
        api_key=api_key,
        base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
    )


SYSTEM_PROMPT_TEMPLATE = """
# 浣犵殑韬唤
浣犳槸銆恵role_name}銆戯紝姝ｅ湪鎺ュ彈璀﹀療鐩橀棶銆傝繖鏄竴鍦哄績鐞嗕笌浜嬪疄鐨勫崥寮堛€?

# 馃П 鏍稿績瑙勫垯 (蹇呴』閬靛畧)
1. **绂佹娌夐粯涓庣┖鍦?*锛氫綘蹇呴』瀵硅瀵熺殑姣忎竴鍙ヨ瘽鍋氬嚭瀹炶川鎬у洖搴旓紒灏辩畻瀹屽叏涓嶆兂閰嶅悎锛屼篃蹇呴』鐢ㄥ姩浣滅鎬佸姞鍐锋紶鐨勮瘽璇潵琛ㄨ揪銆?*缁濆绂佹杩斿洖绌哄瓧绗︿覆鎴栦笉绗﹀悎 JSON 鏍煎紡鐨勫唴瀹?*銆?
2. **鐭ヨ瘑杈圭晫**锛氫綘鍙煡閬撱€愪綘鐨勭煡璇嗚寖鍥淬€戦噷鐨勫唴瀹广€傚浜庛€愪綘涓嶇煡閬撶殑浜嬨€戯紝浣犲繀椤诲瀹炶〃绀轰笉鐭ラ亾锛堢敤绗﹀悎浜鸿鐨勬柟寮忚〃杈撅級銆?
3. **绉樺瘑淇濇姢**锛氬浜庛€愪綘鐨勭瀵嗐€戯紝浣犺鏍规嵁褰撳墠鐨勪俊浠诲害鍜屾儏缁喅瀹氭槸鍚﹂€忛湶銆?
4. **灏婇噸瀹㈣**锛氬浜庛€愭浠朵簨瀹炴。妗堛€戜腑鐨勫叕寮€瀹㈣淇℃伅锛堝浣犵殑鎶ヨ鏃堕棿銆佸叿浣撴鍙戝湴鐐癸級锛屼綘鍙互濡傚疄鍥炵瓟锛?*涓ョ鑷缂栭€犳椂闂?鍦扮偣绛夌‖浜嬪疄**銆?
5. **杈撳嚭鏍煎紡**锛氫綘蹇呴』杈撳嚭涓斾粎杈撳嚭涓€涓悎娉曠殑 JSON 瀵硅薄锛岀‘淇?`response` 瀛楁鐨勫唴瀹硅嚦灏戝寘鍚竴娈靛姩浣滄弿鍐欏拰涓€鍙ュ彴璇嶃€?

# 馃搵 妗堜欢浜嬪疄妗ｆ (瀹㈣淇℃伅鍙傝€?
妗堝彂鏃堕棿: {case_time}
妗堝彂鍦扮偣: {case_location}
鎶ヨ鏃堕棿: {report_time}
浜嬩欢鏃堕棿绾?
{timeline}

# 馃 浣犵殑鐭ヨ瘑鑼冨洿 (浣犵‘瀹炵煡閬撶殑)
{knows_facts}

# 馃毇 浣犱笉鐭ラ亾鐨?(琚棶鍒拌鍧氬喅琛ㄧず涓嶇煡鎯?)
{does_not_know}

# 馃敀 浣犵殑绉樺瘑 (淇′换搴﹁揪鏍囧悗鎵嶅彲鑳借鍑?)
{hidden_truths}

# 馃幁 浣犵殑浜鸿涓庣姸鎬?
- 鎬ф牸: {personality}
- 鏅哄晢: {iq_level} (浣?瀹规槗璇存紡鍢? 楂?閫昏緫涓ュ瘑)
- 鎯呭晢: {eq_level} (浣?鏄撹婵€鎬? 楂?鍠勪簬鎺у埗)
- 鎾掕皫鑳藉姏: {lying_ability} (宸?鐮寸唤鐧惧嚭, 寮?闈笉鏀硅壊)
- 杞倠: {weakness}
- 褰撳墠鎸囨爣锛氭儏缁?{emotion}/100锛屼俊浠?{trust}/100

# 馃幆 鍔ㄦ€佷俊鎭噴鏀捐鍒?
- 淇′换搴?< {release_threshold}: 涓ュ畧绉樺瘑锛岃杩介棶鍒欒浆绉昏瘽棰樸€佸洖閬挎垨琛ㄧ幇瀵规姉銆?
- 淇′换搴?>= {release_threshold}: 鍙互寮€濮?涓嶅皬蹇?閫忛湶涓€鏉￠殣钘忎俊鎭€?
- 淇′换搴?> 80 + 琚Е鍙婅蒋鑲? 蹇冪悊闃茬嚎宕╁锛屼富鍔ㄥ潶鐧芥墍鏈夌瀵嗐€?

# 馃幆 褰撳墠璁粌闃舵鐩爣
{current_stage}

# 杈撳嚭瑕佹眰 (JSON 鏍煎紡)
{{
  "response": "瑙掕壊鍥炲锛堝寘鍚姩浣滄弿鍐欏拰鐪熷疄鍙拌瘝锛岀粷涓嶅彲涓虹┖锛?,
  "inner_thought": "瑙掕壊褰撳墠鐨勭湡瀹炲績鐞嗘椿鍔?,
  "updated_emotion": 鏁存暟,
  "updated_trust": 鏁存暟,
  "new_fact_revealed": "鏂板悙闇茬殑绉樺瘑浜嬪疄鍏抽敭璇嶏紝鏃犲垯null",
  "is_stage_completed": true/false
}}
"""


def generate_dialogue(db: Session, session_id: int, user_message: str):
    try:
        ts = db.query(models.TrainingSession).filter(models.TrainingSession.id == session_id).first()
        if not ts:
            return None

        scene = db.query(models.Scene).filter(models.Scene.id == ts.scene_id).first()
        case = db.query(models.Case).filter(models.Case.id == scene.case_id).first() if scene else None

        primary_link = db.query(models.SceneRole).filter(
            models.SceneRole.scene_id == scene.id,
            models.SceneRole.is_primary == True
        ).first()

        if primary_link:
            role = db.query(models.Role).get(primary_link.role_id)
        else:
            fallback_link = db.query(models.SceneRole).filter(models.SceneRole.scene_id == scene.id).first()
            if fallback_link:
                role = db.query(models.Role).get(fallback_link.role_id)
            else:
                role = models.Role(
                    name="当事人",
                    role_type="配合型",
                    personality="普通人",
                    iq_level="中等",
                    eq_level="中等",
                    lying_ability="一般"
                )

        history = db.query(models.Message).filter(
            models.Message.session_id == session_id
        ).order_by(models.Message.created_at.desc()).limit(12).all()
        history.reverse()

        structured = json.loads(case.structured_data or "{}") if case and case.structured_data else {}
        fact_sheet = structured.get("fact_sheet", {})

        timeline_items = fact_sheet.get("timeline", [])
        if isinstance(timeline_items, list):
            timeline_text = "\n".join(
                [f"  {t.get('time', '')} - {t.get('event', '')}" for t in timeline_items if isinstance(t, dict)]
            )
        else:
            timeline_text = str(timeline_items)

        thresholds = {"配合型": 40, "情绪型": 50, "隐瞒型": 60, "对抗型": 70}
        release_threshold = thresholds.get(role.role_type, 50)

        system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
            role_name=role.name,
            case_time=fact_sheet.get("case_time", "未记录"),
            case_location=fact_sheet.get("case_location", "未记录"),
            report_time=fact_sheet.get("report_time", "未记录"),
            timeline=timeline_text or "未记录",
            knows_facts=role.knows_facts or "[]",
            does_not_know=role.does_not_know or "[]",
            hidden_truths=role.hidden_truths or "[]",
            personality=role.personality or "平民",
            iq_level=role.iq_level or "中等",
            eq_level=role.eq_level or "中等",
            lying_ability=role.lying_ability or "一般",
            weakness=role.weakness or "无明显弱点",
            current_stage=ts.current_stage or "初步接触",
            emotion=ts.current_emotion,
            trust=ts.current_trust,
            release_threshold=release_threshold
        )

        msgs = [{"role": "system", "content": system_prompt}]
        for m in history:
            msgs.append({"role": "assistant" if m.role in ["ai", "assistant"] else "user", "content": m.content})
        msgs.append({"role": "user", "content": user_message})

        max_retries = 2
        result = None

        for attempt in range(max_retries):
            response = get_client().chat.completions.create(
                model="deepseek-chat",
                messages=msgs,
                response_format={"type": "json_object"},
                temperature=0.7 + (attempt * 0.2)
            )

            raw_content = response.choices[0].message.content or ""
            print(f"--- AI RAW (Attempt {attempt + 1}) ---\n{raw_content}\n--------------")

            try:
                start_idx = raw_content.find("{")
                end_idx = raw_content.rfind("}")
                if start_idx != -1 and end_idx != -1:
                    clean_json = raw_content[start_idx:end_idx + 1]
                    result = json.loads(clean_json)
                else:
                    result = json.loads(raw_content)
                break
            except Exception as parse_e:
                print(f"!!! JSON Parsing Error on attempt {attempt + 1}: {parse_e}")
                if attempt == max_retries - 1:
                    return {
                        "response": "（系统提示：角色当前状态异常，可能由于问题触发了安全限制或解析失败，请尝试换种问法）",
                        "inner_thought": "ERROR: LLM JSON Parse Failed after retries.",
                        "updated_emotion": ts.current_emotion,
                        "updated_trust": ts.current_trust,
                        "is_stage_completed": False
                    }

        ts.current_emotion = result.get("updated_emotion", ts.current_emotion)
        ts.current_trust = result.get("updated_trust", ts.current_trust)

        ai_reply = result.get("response", "...")
        ai_thought = result.get("inner_thought", "...")

        db.add(models.Message(session_id=session_id, role="assistant", content=ai_reply, inner_thought=ai_thought))
        db.commit()

        return {
            "response": ai_reply,
            "inner_thought": ai_thought,
            "updated_emotion": ts.current_emotion,
            "updated_trust": ts.current_trust,
            "new_fact_revealed": result.get("new_fact_revealed"),
            "is_stage_completed": result.get("is_stage_completed", False)
        }

    except Exception as e:
        if db:
            db.rollback()
        print(f"!!! DIALOGUE ERROR: {e}")
        return {"response": f"(由于系统异常，对话暂时无法继续。错误详情: {str(e)})", "inner_thought": "ERROR"}
