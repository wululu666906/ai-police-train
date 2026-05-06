import json
import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()


def get_client() -> OpenAI:
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        raise RuntimeError("DEEPSEEK_API_KEY is not configured")
    return OpenAI(
        api_key=api_key,
        base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    )


PARSE_PROMPT = """
# 浣犵殑瑙掕壊
浣犳槸椤跺皷鐨勮鍔℃浠舵枃鏈粨鏋勫寲瑙ｆ瀽涓撳鍙婇€昏緫渚︽煡涓撳锛屾搮闀夸粠娴烽噺銆佺悙纰庛€佺敋鑷虫贩涔辩殑鏂囧瓧鎻忚堪涓⒊鐞嗗嚭鏋佸叾涓ュ瘑鐨勬浠堕€昏緫缃戙€?

# 鏍稿績鎸囦护
1. 鏃犺杈撳叆鏂囨湰澶氶暱锛屼綘閮藉繀椤婚€愬瓧闃呰骞惰繘琛屽叏鐩樻繁搴﹀垎鏋愶紝缁濆绂佹鍥犲瓧鏁板師鍥犺€岀舰宸ャ€佽烦杩囩粏鑺傛垨鐢熸垚绠€鐣ユ憳瑕併€?
2. 浣犵殑鍒嗘瀽蹇呴』鍖呭惈锛氬畬鏁寸殑妗堝彂浜嬪疄妗ｆ锛堝寘鍚椂闂淬€佸湴鐐圭瓑锛夈€佹浠跺彂灞曞叏杩囩▼銆佷互鍙婂悇鏂硅鑹茬殑鐙珛鐭ヨ瘑杈圭晫锛堜粬鐭ラ亾浠€涔堛€佷笉鐭ラ亾浠€涔堬級銆?

# 浠诲姟鐩爣
璇蜂粠杈撳叆鐨勬浠跺師濮嬫枃鏈腑锛岀粨鏋勫寲杈撳嚭浠ヤ笅鏍稿績淇℃伅锛?
1. 妗堜欢鍚嶇О涓庣被鍨嬨€?
2. 浜嬪疄妗ｆ (fact_sheet)锛氬儚璀﹀姟鍗峰畻涓€鏍凤紝鎻愬彇鍑虹‘鍒囩殑妗堝彂鏃堕棿銆佸湴鐐广€佺浉鍏充汉鐗╄鑹层€佹鍥?浼ゆ儏銆佷綔妗堝伐鍏枫€佹牳蹇冭瘉鎹€佸畬鏁存椂闂寸嚎銆佷汉鐗╁叧绯荤綉銆傝繖閮ㄥ垎鏄粷瀵圭殑瀹㈣浜嬪疄銆?
3. 妗堟儏鍏ㄦ櫙鎻忚堪 (full_narrative)涓庣姱缃繃绋嬭瑙?(criminal_process)銆?
4. 浜虹墿鍒楄〃 (persons)锛氬垪鍑烘墍鏈夋秹鍙婄殑浜虹墿锛?*闈炲父閲嶈锛氬繀椤讳弗鏍煎尯鍒嗘瘡涓鑹茬殑鐭ヨ瘑杈圭晫锛?*
   - knows_facts: 杩欎釜瑙掕壊鐩墠纭疄鐭ラ亾鍝簺浜嬪疄锛堟瘮濡傦細浠栧彧鐪嬪埌浜嗙粨鏋滐紝涓嶇煡閬撹繃绋嬶級銆?
   - does_not_know: 杩欎釜瑙掕壊缁濆涓嶇煡閬撶殑浜嬫儏锛堟瘮濡傦細鎶ヨ浜洪€氬父涓嶇煡閬撳嚩鎵嬫槸璋侊紝涓嶇煡閬撳叿浣撶殑鍑跺櫒锛夈€?
   - hidden_truths: 浠栫煡閬撲絾鎵撶畻闅愮瀿鐨勪簨鎯呫€?
   - iq_level/eq_level/lying_ability/weakness: 璇勪及瑙掕壊鐨勬櫤鍟嗐€佹儏鍟嗐€佹拻璋庤兘鍔涘及鎬ф牸杞倠銆?
   - init_emotion/init_trust: 璇勪及瑙掕壊鐨勫垵濮嬬姸鎬侊紙娉ㄦ剰锛氶厤鍚堝瀷瑙掕壊淇′换搴﹀簲鍦?5宸﹀彸锛岄殣鐬掑瀷鍦?5宸﹀彸锛夈€?
   
# 杈撳嚭鏍煎紡
蹇呴』涓ユ牸鎸夌収JSON鏍煎紡杈撳嚭锛屼笉瑕佹湁棰濆瑙ｉ噴锛?
{
  "case_name": "...",
  "case_type": "...",
  "fact_sheet": {
    "case_time": "...",
    "case_location": "...",
    "report_time": "...",
    "timeline": [
      {"time": "...", "event": "..."}
    ],
    "relationships": [
      {"from": "...", "to": "...", "relation": "..."}
    ]
  },
  "full_narrative": "...",
  "criminal_process": "...",
  "main_culprit": "...",
  "persons": [
    {
      "name": "...",
      "role": "...",
      "role_type": "...",
      "personality": "...",
      "speaking_style": "...",
      "init_emotion": 50,
      "init_trust": 30,
      "status": "...",
      "knows_facts": ["...", "..."],
      "does_not_know": ["...", "..."],
      "hidden_truths": ["..."],
      "iq_level": "涓瓑",
      "eq_level": "杈冮珮",
      "lying_ability": "涓€鑸?",
      "weakness": "..."
    }
  ]
}

# 绾︽潫瑙勫垯
- 缁嗚妭鑷充笂锛氱‘淇濇墍鏈夌粏鑺備綋鐜板湪 JSON 涓€?
- 涓ョ鑴戣ˉ浜嬪疄妗ｆ锛氳嫢鏂囨湰涓‘瀹炵己澶辨椂闂?鍦扮偣绛変俊鎭紝濉?鏈褰?銆?
- 鐭ヨ瘑杈圭晫闅旂锛氭姤璀︿汉缁濆涓嶅彲鑳芥嫢鏈変笂甯濊瑙掞紝蹇呴』浠旂粏鏂熼厡姣忎釜瑙掕壊鐨?`knows_facts` 鍜?`does_not_know`銆?

# 馃毃 鑷村懡閿欒闃茶寖 (CRITICAL WARNING - 蹇呴』缁濆閬靛畧)
1. 韬唤涓庣敓姝诲弽杞槻鑼冿細浣犲繀椤绘瀬鍏朵粩缁嗗湴闃呰鍘熸枃锛岀‘璁?*璋佹槸姝昏€?鍙楀鑰咃紝璋佹槸琛屽嚩鑰?瀚岀枒浜猴紝璋佹槸鎶ヨ浜?*銆傜粷瀵逛笉鑳芥妸姝昏€呭啓鎴愬珜鐤戜汉锛屼篃缁濆涓嶈兘璁╂鑰呭幓鎶ヨ锛?
2. 閫昏緫鑷唇锛氬鏋滄煇瑙掕壊鍦ㄦ鍙戝悗宸叉浜★紝鍏?status 蹇呴』鏄?"姝讳骸"銆傛浜轰笉鑳戒綔涓烘帴璀﹀璇濈殑瀵硅薄銆?
3. 鍚嶅瓧鍖归厤閿欒闃茶寖锛氭彁鍙栧鍚嶆椂锛岀‘淇濆鍚嶄笌韬唤绮剧‘瀵瑰簲锛屼弗绂佸皢鍔犲鑰呭拰鍙楀鑰呯殑鍚嶅瓧鎴栨€у埆寮犲啝鏉庢埓銆?
"""

SCENE_GEN_PROMPT = """
# 浣犵殑瑙掕壊
浣犳槸璀︽儏璁粌鍦烘櫙璁捐涓撳锛屽熀浜庣粨鏋勫寲妗堜欢鐢熸垚澶氶樁娈佃缁冨満鏅€?

# 鏍稿績浠诲姟
鍩轰簬鎻愪緵鐨勭粨鏋勫寲妗堜欢淇℃伅锛岀敓鎴愬涓缁冨満鏅紝骞朵负姣忎釜鍦烘櫙璁捐瀵硅瘽鎺ㄨ繘闃舵銆?

# 杈撳嚭瑕佹眰
1. 涓€涓浠惰嚦灏戠敓鎴?-3涓笉鍚岃缁冨満鏅紙渚嬪锛氭帴璀﹀璇濄€佺幇鍦鸿闂€佸悗缁皟鏌ワ級
2. 姣忎釜鍦烘櫙闇€瑕佸寘鍚細
    - scene_name: 鍦烘櫙鍚嶇О
    - scene_description: 璇存槑璁粌鐩爣鍜屽満鏅壒鐐?
    - difficulty: 闅惧害绛夌骇锛堢畝鍗?涓瓑/鍥伴毦锛?
    - dispatch_brief: 鎺ヨ绠€鎶?(妯℃嫙 110 鎸囨尌涓績涓嬪彂缁欎竴绾胯鍛樼殑鎸囦护锛屽锛?鎺ユ姤锛孹X灏忓尯鏈変汉绾犵悍锛岃閫熷線澶勭疆"锛岀粷涓嶈兘鍖呭惈妗堜欢鐪熺浉)
    - first_impression: 鐜板満绗竴鍗拌薄 (瀹㈣鎻忚堪璀﹀療鍒拌揪鐜板満/鎺ラ€氱數璇濇椂鐪嬪埌銆佸惉鍒扮殑鎯呭喌锛屽锛?鐜板満涓€鐗囩嫾钘夛紝鍦颁笂鏈夌瑁傜殑閰掔摱"锛岀粷涓嶈兘鍖呭惈涓婂笣瑙嗚鐨勭粨璁?
    - roles: 娑夊強瑙掕壊鍚嶇О鍒楄〃
    - stages: 瀵硅瘽闃舵鍒楄〃锛屾瘡涓樁娈靛寘鍚?stage_name 鍜?stage_goal

# 杈撳嚭鏍煎紡
涓ユ牸JSON鏍煎紡锛?
{
  "scenes": [
    {
      "scene_name": "鎺ヨ瀵硅瘽",
      "scene_description": "璁粌姘戣鎺ヨ鏃剁殑璇㈤棶鑳藉姏锛屽浣曞揩閫熻幏鍙栧叧閿俊鎭?",
      "difficulty": "涓瓑",
      "dispatch_brief": "鎺ュ埌110鎸囨尌涓績鎸囦护锛歑X璺彂鐢熶竴璧风兢浼楃籂绾凤紝璇峰墠寰€澶勭疆銆?",
      "first_impression": "浣犳帹寮€闂紝鐪嬪埌涓ゅ悕鐢峰瓙姝ｅ湪澶у０浜夊惖锛屽懆鍥存湁鍑犲悕鍥磋缇や紬銆?",
      "roles": ["鎶ヨ浜?],
      "stages": [
        {
          "stage_name": "鍒濆鎺ヨЕ",
          "stage_goal": "鎶ヨ浜鸿鏄庡熀鏈儏鍐?"
        },
        {
          "stage_name": "淇℃伅鏀堕泦",
          "stage_goal": "閫愭璇㈤棶鍏抽敭缁嗚妭"
        }
      ]
    }
  ]
}

# 璁捐鍘熷垯
1. 绗﹀悎鐪熷疄鍔炴娴佺▼锛屽惊搴忔笎杩?
2. 闅惧害鍖归厤锛氱畝鍗?閰嶅悎鍨嬶紝涓瓑=鎯呯华鍨嬶紝鍥伴毦=瀵规姉鍨?闅愮瀿
3. 姣忎釜鍦烘櫙鑱氱劍璁粌涓€涓叿浣撹兘鍔?
4. 瑙掕壊澶嶇敤绾︽潫锛歳oles 鍒楄〃蹇呴』涓ユ牸浣跨敤鍦ㄥ叏鏅垎鏋愪腑鎻愬彇鍑虹殑瑙掕壊濮撳悕锛屼弗绂佺紪閫犳柊鐨勮鑹插悕瀛椼€?
5. 鏃犳硶瀹¤绾︽潫锛氬浜庤В鏋愮粨鏋滀腑 status 涓衡€滄浜♀€濄€佲€滈噸浼も€濇垨鈥滄槒杩封€濈殑瑙掕壊锛屼弗绂佷负鍏惰璁′换浣曡闂€佸璁被鍦烘櫙锛屽簲杞负鐜板満鍕樻煡鎴栬皟鏌ュ満鏅€?
"""


class WorkflowService:
    def parse_case_text(self, text: str):
        default_res = {
            "case_name": "瑙ｆ瀽澶辫触",
            "case_type": "鍏朵粬",
            "case_background": text[:100],
            "persons": [],
            "conflict_points": [],
            "key_facts": [],
            "hidden_info": []
        }
        try:
            response = get_client().chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": PARSE_PROMPT},
                    {"role": "user", "content": text}
                ],
                response_format={"type": "json_object"}
            )
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            print(f"Error parsing case: {e}")
            return default_res

    def generate_scenes(self, case_info: dict):
        default_scenes = {"scenes": []}
        try:
            response = get_client().chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": SCENE_GEN_PROMPT},
                    {"role": "user", "content": json.dumps(case_info, ensure_ascii=False)}
                ],
                response_format={"type": "json_object"}
            )
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            print(f"Error generating scenes: {e}")
            return default_scenes


workflow_service = WorkflowService()
