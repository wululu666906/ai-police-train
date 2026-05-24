# -*- coding: utf-8 -*-
from pathlib import Path

p = Path(__file__).resolve().parents[1] / "frontend" / "src" / "views" / "Cases.vue"
t = p.read_text(encoding="utf-8")
d = "d" + "iv"
anchor = f"""                      </{d}>
                    </{d}>

                    <{d} class="scene-stage-grid">"""
insert = f"""                      </{d}>
                      <{d} class="mt-3">
                        <label class="form-label">推荐追问话术（每行一条，可选）</label>
                        <textarea
                          v-model="stage.recommended_prompts_text"
                          rows="3"
                          class="form-textarea"
                          placeholder="例如：伤者现在意识清醒吗？有没有明显外伤？"
                          @input="syncSceneStagesText(scene)"
                        ></textarea>
                        <p class="mt-1 text-xs text-slate-500">将优先展示给学员，需为可直接说出口的民警问话。</p>
                      </{d}>
                    </{d}>

                    <{d} class="scene-stage-grid">"""
if "recommended_prompts_text" in t and "推荐追问话术" not in t:
    if anchor not in t:
        raise SystemExit("anchor missing")
    t = t.replace(anchor, insert, 1)
    p.write_text(t, encoding="utf-8")
    print("cases ui ok")
elif "推荐追问话术" in t:
    print("already has ui")
else:
    print("script fields missing")
