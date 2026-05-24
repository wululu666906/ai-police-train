# -*- coding: utf-8 -*-
from pathlib import Path

path = Path(__file__).resolve().parents[1] / "frontend" / "src" / "views" / "StudentTraining.vue"
text = path.read_text(encoding="utf-8")

old_block = """        <motion v-if="suggestedQuestions.length" class="suggested-questions">
          <motion class="suggested-questions__head">
            <span class="suggested-questions__title">建议追问</span>
            <span class="suggested-questions__hint">可直接点选话术，填入后按需修改再发送</span>
          </motion>
          <motion class="suggested-questions__list">
            <button
              v-for="(question, index) in suggestedQuestions"
              :key="`${index}-${question}`"
              type="button"
              class="suggested-question-chip"
              :disabled="isLoading"
              @click="applySuggestedQuestion(question)"
            >
              {{ question }}
            </button>
          </motion>
        </motion>"""

new_block = """        <div v-if="communicationFeedback.message" class="coach-feedback" :class="`coach-feedback--${communicationFeedback.level || 'info'}`">
          <span class="coach-feedback__label">问法提示</span>
          <span class="coach-feedback__text">{{ communicationFeedback.message }}</span>
        </div>
        <div v-if="stageMissing.length" class="stage-missing">
          <span class="stage-missing__label">本阶段待补齐</span>
          <span v-for="item in stageMissing" :key="item" class="stage-missing__tag">{{ item }}</span>
        </motion>
        <motion v-if="suggestedQuestionItems.length" class="suggested-questions">
          <motion class="suggested-questions__head">
            <span class="suggested-questions__title">建议追问</span>
            <span class="suggested-questions__hint">点选填入输入框，将自动对准询问对象</span>
          </motion>
          <motion class="suggested-questions__list">
            <button
              v-for="(item, index) in suggestedQuestionItems"
              :key="`${index}-${item.text}`"
              type="button"
              class="suggested-question-chip"
              :disabled="isLoading"
              @click="applySuggestedQuestion(item)"
            >
              <span class="suggested-question-chip__cat">{{ item.category || '追问' }}</span>
              <span class="suggested-question-chip__text">{{ item.text }}</span>
            </button>
          </motion>
        </motion>"""

for _ in range(3):
    old_block = old_block.replace("<motion ", "<" + "motion ")
    old_block = old_block.replace("</motion>", "</" + "motion>")
    new_block = new_block.replace("<motion ", "<" + "div ")
    new_block = new_block.replace("</motion>", "</" + "motion>")
old_block = old_block.replace("<" + "motion ", "<div ").replace("</" + "motion>", "</motion>")
new_block = new_block.replace("<" + "motion ", "<div ").replace("</" + "motion>", "</div>")

# fix botched
old_block = old_block.replace("</motion>", "</motion>")
# manual fix old
old_block = """        <motion v-if="suggestedQuestions.length" class="suggested-questions">"""
# Just read file and do simpler replace

text = path.read_text(encoding="utf-8")
old_simple = """        <div v-if="suggestedQuestions.length" class="suggested-questions">
          <motion class="suggested-questions__head">"""

if "suggestedQuestionItems" not in text:
    start = text.find('        <div v-if="suggestedQuestions.length"')
    end = text.find("        </div>\n        <TrainingInputBar")
    if start < 0 or end < 0:
        raise SystemExit("block not found")
    new_section = """        <div v-if="communicationFeedback.message" class="coach-feedback" :class="`coach-feedback--${communicationFeedback.level || 'info'}`">
          <span class="coach-feedback__label">问法提示</span>
          <span class="coach-feedback__text">{{ communicationFeedback.message }}</span>
        </div>
        <motion v-if="stageMissing.length" class="stage-missing">
          <span class="stage-missing__label">本阶段待补齐</span>
          <span v-for="item in stageMissing" :key="item" class="stage-missing__tag">{{ item }}</span>
        </motion>
        <motion v-if="suggestedQuestionItems.length" class="suggested-questions">
          <motion class="suggested-questions__head">
            <span class="suggested-questions__title">建议追问</span>
            <span class="suggested-questions__hint">点选填入输入框，将自动对准询问对象</span>
          </motion>
          <motion class="suggested-questions__list">
            <button
              v-for="(item, index) in suggestedQuestionItems"
              :key="`${index}-${item.text}`"
              type="button"
              class="suggested-question-chip"
              :disabled="isLoading"
              @click="applySuggestedQuestion(item)"
            >
              <span class="suggested-question-chip__cat">{{ item.category || '追问' }}</span>
              <span class="suggested-question-chip__text">{{ item.text }}</span>
            </button>
          </motion>
        </motion>"""
    new_section = new_section.replace("<motion ", "<div ").replace("</motion>", "</div>")
    text = text[:start] + new_section + text[end:]

script_replacements = [
    (
        "const suggestedQuestions = ref<string[]>([])",
        """interface SuggestedQuestionItem {
  text: string
  category?: string
  target_role_name?: string | null
}
const suggestedQuestionItems = ref<SuggestedQuestionItem[]>([])
const communicationFeedback = ref<{ level?: string; message?: string }>({ message: '' })
const stageMissing = ref<string[]>([])""",
    ),
    (
        """const META_QUESTION_PATTERN = /先围绕|把最关键|这一点|训练已恢复|补齐这些关键项/

const applySuggestedQuestions = (items: unknown) => {
  const list = Array.isArray(items) ? items : []
  suggestedQuestions.value = list
    .map((item) => String(item || '').trim())
    .filter((item) => item && !META_QUESTION_PATTERN.test(item) && item.length <= 48)
    .slice(0, 4)
}

const applySuggestedQuestion = (question: string) => {
  const text = String(question || '').trim()
  if (!text || isLoading.value) return
  inputMessage.value = text
}""",
        """const META_QUESTION_PATTERN = /先围绕|把最关键|这一点|训练已恢复|补齐这些关键项/

const normalizeSuggestedItems = (payload: unknown): SuggestedQuestionItem[] => {
  if (Array.isArray(payload) && payload.length && typeof payload[0] === 'object') {
    return payload
      .map((item: any) => ({
        text: String(item?.text || '').trim(),
        category: String(item?.category || '追问').trim() || '追问',
        target_role_name: item?.target_role_name || null,
      }))
      .filter((item) => item.text && !META_QUESTION_PATTERN.test(item.text) && item.text.length <= 48)
      .slice(0, 4)
  }
  const list = Array.isArray(payload) ? payload : []
  return list
    .map((item) => String(item || '').trim())
    .filter((item) => item && !META_QUESTION_PATTERN.test(item) && item.length <= 48)
    .slice(0, 4)
    .map((text) => ({ text, category: '追问', target_role_name: null }))
}

const applySuggestedQuestions = (items: unknown, fallbackTexts?: unknown) => {
  const normalized = normalizeSuggestedItems(items)
  if (normalized.length) {
    suggestedQuestionItems.value = normalized
    return
  }
  suggestedQuestionItems.value = normalizeSuggestedItems(fallbackTexts)
}

const applyGuidancePayload = (res: any) => {
  applySuggestedQuestions(res?.recommended_question_items, res?.recommended_questions)
  const feedback = res?.communication_feedback
  communicationFeedback.value = {
    level: feedback?.level || 'info',
    message: feedback?.message || '',
  }
  stageMissing.value = Array.isArray(res?.stage_completion_missing)
    ? res.stage_completion_missing.filter(Boolean)
    : []
}

const applySuggestedQuestion = (item: SuggestedQuestionItem | string) => {
  const payload = typeof item === 'string' ? { text: item } : item
  const text = String(payload?.text || '').trim()
  if (!text || isLoading.value) return
  inputMessage.value = text
  const roleName = String(payload?.target_role_name || '').trim()
  if (roleName) {
    targetRoleName.value = roleName
    return
  }
  const matched = sceneRoles.value.find((role) => text.startsWith(`${role.name}，`))
  if (matched) targetRoleName.value = matched.name
}""",
    ),
    (
        "applySuggestedQuestions(res.recommended_questions)",
        "applyGuidancePayload(res)",
    ),
]

for old, new in script_replacements:
    if old not in text:
        raise SystemExit(f"missing: {old[:40]}")
    text = text.replace(old, new, 1)

css_add = """
.coach-feedback {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  margin-bottom: 8px;
  padding: 8px 12px;
  border-radius: 10px;
  font-size: 12px;
  line-height: 1.5;
}
.coach-feedback--info { background: #e8f3ff; color: #1d2129; }
.coach-feedback--good { background: #e8ffea; color: #1d2129; }
.coach-feedback--warning { background: #fff7e8; color: #1d2129; }
.coach-feedback__label { font-weight: 700; flex-shrink: 0; }
.stage-missing {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  margin-bottom: 8px;
}
.stage-missing__label { font-size: 11px; color: #86909c; }
.stage-missing__tag {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 999px;
  background: #fff;
  border: 1px solid #e5e6eb;
  color: #4e5969;
}
.suggested-question-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border-radius: 12px;
  padding: 8px 10px;
}
.suggested-question-chip__cat {
  flex-shrink: 0;
  font-size: 10px;
  font-weight: 700;
  padding: 2px 6px;
  border-radius: 6px;
  background: #e8f3ff;
  color: #165dff;
}
.suggested-question-chip__text { flex: 1; min-width: 0; }
"""

if ".coach-feedback" not in text:
    text = text.replace(".suggested-questions {", css_add + "\n.suggested-questions {", 1)

path.write_text(text, encoding="utf-8")
print("patched ui")
