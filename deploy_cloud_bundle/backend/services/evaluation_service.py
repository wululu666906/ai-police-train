import json
import os

from openai import OpenAI
from sqlalchemy.orm import Session

import models
from .rag_service import rag_service


def get_client() -> OpenAI:
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        raise RuntimeError("DEEPSEEK_API_KEY is not configured")
    return OpenAI(
        api_key=api_key,
        base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
    )


EVALUATION_PROMPT_TEMPLATE = """
# 浣犵殑瑙掕壊
浣犳槸璀﹀姟鎵ф硶璁粌涓撲笟璇勫垎瀹橈紝璐熻矗瀵规皯璀﹀湪妯℃嫙璀︽儏璁粌涓殑琛ㄧ幇杩涜涓撲笟璇勫垎銆?

# 璇勫垎缁村害锛堟弧鍒?00鍒嗭級
1. 鎵ф硶璇█瑙勮寖鎬э紙鏉冮噸25%锛夛細璇█鏄惁瑙勮寖銆佺鍚堟墽娉曡姹傦紝鏈夋病鏈変笉褰撹〃杩?
2. 鎵ф硶娴佺▼瀹屾暣鎬э紙鏉冮噸25%锛夛細鏄惁鎸夌収鍚堢悊娴佺▼璇㈤棶锛屾湁娌℃湁閬楁紡鍏抽敭淇℃伅
3. 娉曞緥渚濇嵁姝ｇ‘鎬э紙鏉冮噸20%锛夛細寮曠敤娉曞緥鏄惁姝ｇ‘锛屽鐞嗘柟寮忔槸鍚﹀悎娉?
4. 鎯呯华鎺у埗鑳藉姏锛堟潈閲?5%锛夛細闈㈠瀵规柟鎯呯华婵€鍔ㄦ椂锛岃兘鍚︿繚鎸佸喎闈欎笓涓?
5. 淇℃伅鑾峰彇鏁堢巼锛堟潈閲?5%锛夛細鑳藉惁蹇€熴€佸噯纭幏鍙栧叧閿俊鎭?

# 杈撳叆淇℃伅
- 妗堜欢淇℃伅锛歿case_info}
- 瀹屾暣瀵硅瘽鍘嗗彶锛歿dialogue_history}
- 鍙傝€冪煡璇嗗簱锛堣瘎鍒嗘爣鍑嗕緷鎹級锛歿knowledge_base}

# 璇勫垎瑕佹眰
1. 姣忎釜缁村害鍒嗗埆鎵撳垎锛屽苟缁欏嚭鎵ｅ垎鍘熷洜
2. 璁＄畻鎬诲垎
3. 缁欏嚭鍏蜂綋鏀硅繘寤鸿锛屾寚鍑哄摢閲屽仛寰楀ソ锛屽摢閲岄渶瑕佹敼杩?
4. 璇勪环瑕佸瑙傘€佸叿浣擄紝缁撳悎瀵硅瘽涓殑鍏蜂綋鍐呭

# 杈撳嚭鏍煎紡
涓ユ牸JSON锛?
{{
  "scores": [
    {{
      "dimension": "鎵ф硶璇█瑙勮寖鎬?",
      "score": 20,
      "full_score": 25,
      "reason": "鏁翠綋璇█瑙勮寖锛屼絾鍦╔X鍦版柟鏈変笉鎭板綋琛ㄨ堪"
    }}
  ],
  "total_score": 85,
  "strengths": ["鍋氬緱濂界殑鍦版柟1"],
  "improvements": ["闇€瑕佹敼杩涚殑鍦版柟1"],
  "suggestions": "鏁翠綋鏀硅繘寤鸿鎬荤粨"
}}

# 绾︽潫
1. 涓ユ牸鎵ｅ垎鍒讹細娌℃湁闂灏辩粰婊″垎锛屾湁闂鏍规嵁涓ラ噸绋嬪害鎵ｅ垎
2. 蹇呴』缁撳悎瀵硅瘽涓殑鍏蜂綋鍐呭璇存槑鍘熷洜锛屼笉瑕佺┖娉涜瘎浠?
3. 濡傛灉鍑虹幇鏄庢樉杩濇硶杩濊琛ㄨ堪锛岀洿鎺ュ搴旂淮搴︾粰0鍒?
"""


def evaluate_session(db: Session, session_id: int):
    session = db.query(models.TrainingSession).filter(models.TrainingSession.id == session_id).first()
    if not session:
        return None

    if session.status == "finished" and session.evaluation_result:
        return json.loads(session.evaluation_result)

    scene = db.query(models.Scene).filter(models.Scene.id == session.scene_id).first()
    case = db.query(models.Case).filter(models.Case.id == scene.case_id).first()
    msgs = db.query(models.Message).filter(models.Message.session_id == session_id).order_by(models.Message.created_at.asc()).all()

    dialogue_history = "\n".join([f"{'学员' if m.role == 'user' else 'AI角色'}: {m.content}" for m in msgs])

    knowledge = rag_service.search(case.case_type, limit=5)
    knowledge_base = "\n".join([f"- {k}" for k in knowledge]) if knowledge else "暂无相关法律标准参考。"

    full_prompt = EVALUATION_PROMPT_TEMPLATE.format(
        case_info=f"案件标题：{case.title}\n案件背景：{case.background}",
        dialogue_history=dialogue_history,
        knowledge_base=knowledge_base
    )

    try:
        response = get_client().chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "你是一名公正专业的警察学院教官。"},
                {"role": "user", "content": full_prompt}
            ],
            response_format={"type": "json_object"}
        )

        report_json = response.choices[0].message.content
        report = json.loads(report_json)

        session.status = "finished"
        session.evaluation_result = report_json
        db.commit()

        return report
    except Exception as e:
        print(f"Evaluation error: {e}")
        return {"error": str(e)}
