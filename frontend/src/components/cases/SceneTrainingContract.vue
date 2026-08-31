<script setup lang="ts">
import { computed } from 'vue'
import { normalizeSceneScriptFields } from '../../utils/sceneRoleBinding'

const props = defineProps<{ scene: Record<string, any>; caseData?: Record<string, any> | null }>()

const factMap = computed(() => {
  const source = props.caseData || {}
  let structured: any = source
  if (typeof source.structured_data === 'string') {
    try { structured = { ...source, ...JSON.parse(source.structured_data) } } catch { structured = source }
  } else if (source.structured_data && typeof source.structured_data === 'object') {
    structured = { ...source, ...source.structured_data }
  }
  const world = structured.story_world || {}
  const facts = world.fact_cards || world.facts || structured.facts || structured.fact_cards || []
  return new Map((Array.isArray(facts) ? facts : []).map((fact: any) => [String(fact.id || fact.fact_id || fact.claim_id), fact]))
})

const normalized = computed(() => normalizeSceneScriptFields(props.scene || {}))
const outcomes = computed(() => normalized.value.expected_outcomes || [])
const factIds = computed(() => Array.isArray(props.scene?.fact_ids) ? props.scene.fact_ids.filter(Boolean) : [])
const stages = computed(() => normalized.value.stages || [])
const plotArc = computed(() => String(normalized.value.plot_arc || '').trim())
const roleTrainingFunctions = computed(() => normalized.value.role_training_functions || [])
const completionCriteria = computed(() => normalized.value.completion_criteria || [])
const failurePatterns = computed(() => normalized.value.failure_patterns || [])
const factLabel = (id: string) => String((factMap.value.get(String(id)) as any)?.content || id)
</script>

<template>
  <section class="training-contract">
    <article class="training-contract__card">
      <div class="training-contract__index">01</div>
      <div class="training-contract__label">案件训练定位</div>
      <div class="training-contract__body">
        <p><strong>训练目标：</strong>{{ normalized.training_goal || '待补充民警可执行的训练目标' }}</p>
        <p><strong>学员角色：</strong>{{ normalized.student_role || '民警' }}</p>
        <div class="training-contract__sub">
          <div class="training-contract__sub-label">考察点</div>
          <ol v-if="outcomes.length">
            <li v-for="item in outcomes" :key="item">{{ item }}</li>
          </ol>
          <p v-else class="training-contract__missing">待补充可观察、可判断的考察点</p>
        </div>
      </div>
    </article>

    <article class="training-contract__card">
      <div class="training-contract__index">02</div>
      <div class="training-contract__label">推荐场景包</div>
      <div class="training-contract__body">
        <div class="training-contract__kv">
          <span>接警简报</span>
          <p>{{ normalized.dispatch_brief || '待补充接警信息' }}</p>
        </div>
        <div class="training-contract__kv">
          <span>现场第一印象</span>
          <p>{{ normalized.first_impression || '待补充现场可观察描述' }}</p>
        </div>
        <div class="training-contract__kv">
          <span>进入阶段</span>
          <p>{{ normalized.training_entry_phase || 'post_incident_onsite' }}</p>
        </div>
      </div>
    </article>

    <article class="training-contract__card training-contract__card--wide">
      <div class="training-contract__index">03</div>
      <div class="training-contract__label">分阶段剧本</div>
      <div class="training-contract__body">
        <div v-if="stages.length" class="training-contract__stages">
          <div v-for="(stage, index) in stages" :key="`${stage.stage_name}-${index}`">
            <div class="training-contract__stage-head">
              <strong>{{ stage.stage_name || `阶段 ${index + 1}` }}</strong>
              <span>{{ stage.stage_goal || '待补充阶段目标' }}</span>
            </div>
            <p v-if="Array.isArray(stage.learner_actions) && stage.learner_actions.length">
              学员动作：{{ stage.learner_actions.join('；') }}
            </p>
            <p v-if="Array.isArray(stage.role_pressure_points) && stage.role_pressure_points.length">
              角色压力点：{{ stage.role_pressure_points.join('；') }}
            </p>
            <p v-if="Array.isArray(stage.expected_stage_effects) && stage.expected_stage_effects.length">
              阶段考察点：{{ stage.expected_stage_effects.join('；') }}
            </p>
          </div>
        </div>
        <p v-else class="training-contract__missing">待补充开端 / 发展 / 收尾阶段</p>
      </div>
    </article>

    <article class="training-contract__card">
      <div class="training-contract__index">04</div>
      <div class="training-contract__label">在场角色与训练功能</div>
      <div class="training-contract__body">
        <div v-if="roleTrainingFunctions.length" class="training-contract__role-functions">
          <div v-for="(item, index) in roleTrainingFunctions" :key="`${item.role_name}-${index}`">
            <strong>{{ item.role_name || '未命名角色' }}</strong>
            <span>{{ item.training_function || '待补充训练功能' }}</span>
            <p>{{ item.expected_interaction_effect || '待补充预期互动考察点' }}</p>
          </div>
        </div>
        <p v-else class="training-contract__missing">待补充角色训练功能</p>
      </div>
    </article>

    <article class="training-contract__card">
      <div class="training-contract__index">05</div>
      <div class="training-contract__label">完成标准</div>
      <div class="training-contract__body">
        <div class="training-contract__sub">
          <div class="training-contract__sub-label">达标条件</div>
          <ol v-if="completionCriteria.length">
            <li v-for="item in completionCriteria" :key="item">{{ item }}</li>
          </ol>
          <p v-else class="training-contract__missing">待补充完成标准</p>
        </div>
        <div class="training-contract__sub">
          <div class="training-contract__sub-label">常见失败表现</div>
          <ol v-if="failurePatterns.length">
            <li v-for="item in failurePatterns" :key="item">{{ item }}</li>
          </ol>
          <p v-else class="training-contract__missing">待补充失败表现</p>
        </div>
      </div>
    </article>

    <article class="training-contract__card">
      <div class="training-contract__index">06</div>
      <div class="training-contract__label">剧情走向</div>
      <div class="training-contract__body">
        <p>{{ plotArc || '待补充剧情走向' }}</p>
        <div class="training-contract__sub">
          <div class="training-contract__sub-label">绑定事实</div>
          <div v-if="factIds.length" class="training-contract__facts">
            <span v-for="id in factIds" :key="id" :title="factLabel(id)">{{ id }}</span>
          </div>
          <p v-else class="training-contract__missing">未绑定案件事实</p>
        </div>
      </div>
    </article>
  </section>
</template>

<style scoped>
.training-contract {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid #e2e8f0;
  align-items: stretch;
}
.training-contract__card {
  min-width: 0;
  min-height: 220px;
  display: grid;
  grid-template-rows: auto auto minmax(0, 1fr);
  gap: 8px;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  background: #fff;
  padding: 14px;
}
.training-contract__card--wide {
  grid-column: 1 / -1;
  min-height: 240px;
}
.training-contract__index {
  width: fit-content;
  padding: 2px 8px;
  border-radius: 999px;
  background: #eff6ff;
  color: #1d4ed8;
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.04em;
}
.training-contract__label {
  color: #0f172a;
  font-size: 14px;
  font-weight: 800;
}
.training-contract__body {
  min-height: 0;
  overflow: auto;
  display: grid;
  gap: 8px;
  align-content: start;
}
.training-contract__body p,
.training-contract__body ol {
  margin: 0;
  color: #1e293b;
  font-size: 13px;
  line-height: 1.65;
}
.training-contract__body ol { padding-left: 18px; }
.training-contract__sub {
  display: grid;
  gap: 4px;
  padding-top: 4px;
}
.training-contract__sub-label {
  color: #64748b;
  font-size: 12px;
  font-weight: 700;
}
.training-contract__kv { display: grid; gap: 2px; }
.training-contract__kv span { font-size: 12px; color: #64748b; font-weight: 700; }
.training-contract__facts { display: flex; flex-wrap: wrap; gap: 6px; }
.training-contract__facts span {
  padding: 3px 7px;
  border: 1px solid #bfdbfe;
  color: #1d4ed8;
  background: #eff6ff;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 700;
}
.training-contract__missing { color: #b45309; }
.training-contract__stages { display: grid; gap: 8px; }
.training-contract__stages > div {
  display: grid;
  gap: 4px;
  font-size: 12px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 10px;
  background: #f8fafc;
}
.training-contract__stage-head {
  display: grid;
  grid-template-columns: minmax(72px, auto) minmax(0, 1fr);
  gap: 8px;
}
.training-contract__stages strong { color: #334155; }
.training-contract__stages span { color: #64748b; overflow-wrap: anywhere; }
.training-contract__stages p { margin: 0; color: #475569; font-size: 12px; }
.training-contract__role-functions { display: grid; gap: 8px; }
.training-contract__role-functions > div {
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 8px;
  background: #f8fafc;
  display: grid;
  gap: 3px;
}
.training-contract__role-functions strong { font-size: 12px; color: #0f172a; }
.training-contract__role-functions span { font-size: 12px; color: #1e40af; }
.training-contract__role-functions p { margin: 0; font-size: 12px; color: #475569; }
@media (max-width: 900px) {
  .training-contract { grid-template-columns: 1fr; }
  .training-contract__card,
  .training-contract__card--wide {
    grid-column: auto;
    min-height: 0;
  }
}
</style>
