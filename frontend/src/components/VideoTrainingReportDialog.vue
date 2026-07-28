<template>
  <van-popup
    v-model:show="popupVisible"
    round
    :teleport="page ? undefined : 'body'"
    :overlay="!page"
    :lock-scroll="!page"
    class="video-report-popup"
    :class="{ 'video-report-popup--page': page }"
    :overlay-style="page ? undefined : { backgroundColor: 'rgba(15, 23, 42, 0.72)', backdropFilter: 'blur(4px)' }"
  >
    <div v-if="hasReport" class="video-report-card">
      <div class="video-report-head">
        <div>
          <div class="video-report-head__eyebrow">{{ title }}</div>
          <div class="video-report-head__title">{{ reportTitle }}</div>
          <div class="video-report-head__meta">
            <span>{{ reportModeLabel }}</span>
            <span>得分率 {{ reportPercentage }}%</span>
            <span v-if="reportFinishedAt">完成于 {{ reportFinishedAt }}</span>
            <span>报告编号 VR-{{ props.report?.session_id || '0000' }}</span>
          </div>
        </div>
        <button v-if="showClose" type="button" class="video-report-close" @click="popupVisible = false">
          <van-icon name="cross" size="18" />
        </button>
      </div>

      <div class="video-report-layout">
        <aside class="video-report-summary-panel">
          <section class="video-report-side-card video-report-side-card--score">
            <h3>综合评分</h3>
            <div class="video-report-score-line">
              <strong>{{ reportScore }}</strong>
              <span>/{{ reportFullScore }}</span>
            </div>
            <div class="video-report-score-grade" :class="`video-report-score-grade--${gradeKey}`">{{ reportGrade }}</div>
            <p>{{ scoreHint }}</p>
          </section>

          <section class="video-report-side-card">
            <h3>训练概况</h3>
            <div class="video-report-side-row"><span>通过节点</span><strong>{{ reportPassCount }}</strong></div>
            <div class="video-report-side-row"><span>跳过节点</span><strong>{{ reportSkipCount }}</strong></div>
            <div class="video-report-side-row"><span>未通过节点</span><strong>{{ reportFailCount }}</strong></div>
            <div class="video-report-side-row"><span>违规次数</span><strong>{{ reportViolationCount }}</strong></div>
            <div class="video-report-side-row"><span>总扣分</span><strong>{{ reportTotalDeducted }}</strong></div>
            <div class="video-report-side-row"><span>节点总数</span><strong>{{ reportTotalNodes }}</strong></div>
          </section>
        </aside>

        <main class="video-report-document">
          <section class="video-report-section">
            <h3>一、综合评定</h3>
            <p class="video-report-text">
              本次视频实训共完成 {{ reportTotalNodes }} 个节点，其中通过 {{ reportPassCount }} 个，未通过 {{ reportFailCount }} 个，
              跳过 {{ reportSkipCount }} 个，累计违规 {{ reportViolationCount }} 次，最终得分 {{ reportScore }}/{{ reportFullScore }}，
              等级评定为“{{ reportGrade }}”。
            </p>
            <div class="video-report-notice-list">
              <p>训练模式：{{ reportModeLabel }}</p>
              <p>得分率：{{ reportPercentage }}%</p>
              <p v-if="reportFinishedAt">报告生成时间：{{ reportFinishedAt }}</p>
            </div>
          </section>

          <section v-if="dimensionScores.length" class="video-report-section">
            <h3>二、能力指标结果</h3>
            <div class="video-report-dimensions">
              <article v-for="item in dimensionScores" :key="item.key" class="video-report-dimension">
                <div class="video-report-dimension__head">
                  <strong>{{ item.label }}</strong>
                  <span>{{ item.score }}/{{ item.full_score }} 分</span>
                </div>
                <div class="video-report-bar"><i :style="{ width: `${item.percentage}%` }"></i></div>
                <p>完成度 {{ item.percentage }}%，系统已纳入该维度的动作、话术与流程表现综合判定。</p>
              </article>
            </div>
          </section>

          <section v-if="abilityProfile?.enabled" class="video-report-section">
            <h3>三、警情处置画像</h3>
            <div class="ability-profile">
              <div class="ability-profile__score">
                <strong>{{ abilityProfile.standard_point_coverage || 0 }}%</strong>
                <span>标准处置点覆盖率</span>
                <em>语义平均分 {{ abilityProfile.semantic_average || 0 }}</em>
              </div>
              <div class="ability-profile__body">
                <div v-if="abilityProfile.strengths?.length">
                  <h4>已形成能力</h4>
                  <p>{{ abilityProfile.strengths.join('、') }}</p>
                </div>
                <div v-if="abilityProfile.risks?.length">
                  <h4>待补强短板</h4>
                  <p>{{ abilityProfile.risks.join('、') }}</p>
                </div>
                <div v-if="abilityProfile.next_training?.length">
                  <h4>建议复训</h4>
                  <p>{{ abilityProfile.next_training.join('；') }}</p>
                </div>
              </div>
            </div>
          </section>

          <section v-if="failureReasonList.length || violationList.length" class="video-report-section">
            <h3>四、训练审计</h3>
            <div class="video-report-audit-grid">
              <div v-if="failureReasonList.length" class="video-report-audit-block">
                <h4>高频失分原因</h4>
                <div class="video-report-chip-list">
                  <span v-for="item in failureReasonList" :key="item.key" class="video-report-chip video-report-chip--danger">
                    {{ item.label }} x{{ item.count }}
                  </span>
                </div>
              </div>
              <div v-if="violationList.length" class="video-report-audit-block">
                <h4>违规记录</h4>
                <div class="video-report-chip-list">
                  <span v-for="item in violationList" :key="item.key" class="video-report-chip video-report-chip--warn">
                    {{ item.label }} x{{ item.count }}
                  </span>
                </div>
              </div>
            </div>
          </section>

          <section v-if="weaknessSummary.length" class="video-report-section">
            <h3>五、复盘建议</h3>
            <ul class="video-report-list">
              <li v-for="item in weaknessSummary" :key="item">{{ item }}</li>
            </ul>
          </section>

          <section class="video-report-section">
            <h3>六、节点明细</h3>
            <div class="video-report-node-list">
              <article v-for="item in reportNodes" :key="item.node_index" class="video-report-node">
                <div class="video-report-node__head">
                  <strong>{{ item.node_title || `节点 ${item.node_index + 1}` }}</strong>
                  <span class="video-report-node__result" :class="`video-report-node__result--${item.result}`">
                    {{ resultLabel(item.result) }}
                  </span>
                </div>
                <div class="video-report-node__meta">
                  <span>序号 {{ item.node_index + 1 }}</span>
                  <span>得分 {{ item.score_earned }}</span>
                  <span v-if="item.score_deducted">扣分 {{ item.score_deducted }}</span>
                  <span v-if="item.retry_count">重试 x{{ item.retry_count }}</span>
                </div>
                <div v-if="item.manual_review" class="video-report-node__review">
                  <span class="video-report-node__review-tag">已人工复核</span>
                  <span>复核人 {{ item.manual_review.reviewer_username || '管理员' }}</span>
                  <span v-if="item.manual_review.reviewed_at">{{ formatDateTime(item.manual_review.reviewed_at) }}</span>
                </div>
                <div v-if="item.speech_transcript" class="video-report-node__speech">
                  语音识别：{{ item.speech_transcript }}
                </div>
                <div v-if="item.failure_reasons?.length" class="video-report-node__issues">
                  失分原因：{{ item.failure_reasons.map(formatFailureReason).join('、') }}
                </div>
                <div v-if="item.manual_review?.review_note" class="video-report-node__speech">
                  复核说明：{{ item.manual_review.review_note }}
                </div>
                <div v-if="reviewable" class="video-report-node__actions">
                  <el-button size="small" type="primary" plain @click="emit('review-node', item)">
                    人工复核 / 改判
                  </el-button>
                </div>
              </article>
            </div>
          </section>
        </main>
      </div>

      <div class="video-report-actions">
        <slot name="actions">
          <el-button v-if="showClose" @click="popupVisible = false">关闭</el-button>
        </slot>
      </div>
    </div>
  </van-popup>
</template>

<script setup lang="ts">
import { computed } from 'vue'

interface ReportItem {
  node_result_id?: number
  node_index: number
  node_title?: string
  result: string
  retry_count: number
  score_earned: number
  score_deducted: number
  speech_transcript?: string
  failure_reasons?: string[]
  manual_review?: {
    reviewer_id?: number
    reviewer_username?: string
    reviewed_at?: string
    review_note?: string
    original_result?: string
    original_score_earned?: number
    original_score_deducted?: number
    original_failure_reasons?: string[]
  } | null
}

interface ReportData {
  session_id?: number
  video_title?: string
  mode?: string
  total_score?: number
  full_score?: number
  percentage?: number
  grade?: string
  pass_count?: number
  skip_count?: number
  fail_count?: number
  total_nodes?: number
  total_deducted?: number
  violation_count?: number
  violation_summary?: Record<string, number>
  failure_reason_summary?: Record<string, number>
  dimension_scores?: {
    key: string
    label: string
    score: number
    full_score: number
    percentage: number
  }[]
  weakness_summary?: string[]
  ability_profile?: {
    enabled?: boolean
    semantic_average?: number
    standard_point_coverage?: number
    strengths?: string[]
    risks?: string[]
    next_training?: string[]
  }
  node_summaries?: ReportItem[]
  finished_at?: string
}

const props = withDefaults(defineProps<{
  show: boolean
  report: ReportData | null
  title?: string
  reviewable?: boolean
  page?: boolean
  showClose?: boolean
}>(), {
  title: '训练评估报告',
  reviewable: false,
  page: false,
  showClose: true,
})

const emit = defineEmits<{
  'update:show': [value: boolean]
  'review-node': [item: ReportItem]
}>()

const popupVisible = computed({
  get: () => props.show,
  set: (value: boolean) => emit('update:show', value),
})

const hasReport = computed(() => Boolean(props.report))
const reportTitle = computed(() => props.report?.video_title || '视频实训报告')
const reportModeLabel = computed(() => (props.report?.mode === 'exam' ? '考核模式' : '练习模式'))
const reportPercentage = computed(() => Number(props.report?.percentage || 0))
const reportFinishedAt = computed(() => formatDateTime(props.report?.finished_at))
const reportScore = computed(() => Number(props.report?.total_score || 0))
const reportFullScore = computed(() => Number(props.report?.full_score || 0))
const reportGrade = computed(() => props.report?.grade || '待评定')
const reportPassCount = computed(() => Number(props.report?.pass_count || 0))
const reportSkipCount = computed(() => Number(props.report?.skip_count || 0))
const reportFailCount = computed(() => Number(props.report?.fail_count || 0))
const reportViolationCount = computed(() => Number(props.report?.violation_count || 0))
const reportTotalDeducted = computed(() => Number(props.report?.total_deducted || 0))
const reportTotalNodes = computed(() => Number(props.report?.total_nodes || props.report?.node_summaries?.length || 0))
const reportNodes = computed(() => props.report?.node_summaries || [])
const dimensionScores = computed(() => props.report?.dimension_scores || [])
const weaknessSummary = computed(() => props.report?.weakness_summary || [])
const abilityProfile = computed(() => props.report?.ability_profile)

const gradeKey = computed(() => {
  if (reportGrade.value === '优秀') return 'excellent'
  if (reportGrade.value === '合格') return 'pass'
  return 'fail'
})

const scoreHint = computed(() => {
  if (reportPercentage.value >= 90) return '训练表现稳定，动作、话术和流程控制较完整。'
  if (reportPercentage.value >= 70) return '整体完成度良好，建议重点复盘失分节点。'
  return '当前仍有明显薄弱项，建议按失分节点针对性重练。'
})

const failureReasonList = computed(() =>
  Object.entries(props.report?.failure_reason_summary || {}).map(([key, count]) => ({
    key,
    count,
    label: formatFailureReason(key),
  })),
)

const violationList = computed(() =>
  Object.entries(props.report?.violation_summary || {}).map(([key, count]) => ({
    key,
    count,
    label: formatViolationType(key),
  })),
)

function resultLabel(result: string) {
  return ({ pass: '通过', skip: '跳过', timeout: '超时', fail: '未通过' } as Record<string, string>)[result] || result
}

function formatFailureReason(reason: string) {
  return ({
    gesture_mismatch: '动作未达标',
    keyword_mismatch: '话术未匹配',
    judge_incorrect: '判断题错误',
    choice_incorrect: '选择题错误',
    prop_missed: '道具动作遗漏',
    manual_review_failed: '人工复核判定未通过',
  } as Record<string, string>)[reason] || reason
}

function formatViolationType(type: string) {
  return ({
    tab_switch: '切换标签页',
    page_leave: '关闭或刷新页面',
    page_hide: '页面切入后台',
    device_lost: '设备中断',
    identity_lost: '身份校验中断',
  } as Record<string, string>)[type] || type
}

function formatDateTime(value?: string) {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  return date.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}
</script>

<style scoped lang="scss">
.video-report-popup {
  width: min(1180px, 96vw);
  max-height: 90vh;
  overflow: auto;
}

.video-report-popup--page {
  position: static;
  width: 100%;
  max-height: none;
  overflow: visible;
  transform: none;
  background: transparent;
  box-shadow: none;
}

.video-report-popup--page :deep(.van-popup__content) {
  width: 100%;
}

.video-report-popup--page .video-report-card {
  min-height: calc(100vh - 132px);
}

.video-report-card {
  padding: 24px;
  background: #f5f7fa;
  color: #1d2129;
}

.video-report-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  margin-bottom: 20px;
  padding: 0 0 18px;
  border-bottom: 1px solid #e5e6eb;
}

.video-report-head__eyebrow {
  font-size: 12px;
  color: #165dff;
  font-weight: 800;
  letter-spacing: 0.04em;
}

.video-report-head__title {
  font-size: 36px;
  font-weight: 800;
  margin-top: 10px;
  line-height: 1.05;
  color: #0f1419;
}

.video-report-head__meta {
  margin-top: 14px;
  font-size: 14px;
  color: #4e5969;
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
}

.video-report-close {
  border: 0;
  background: transparent;
  color: #86909c;
  cursor: pointer;
  padding: 4px;
  font-size: 24px;
}

.video-report-layout {
  display: grid;
  grid-template-columns: 300px minmax(0, 1fr);
  gap: 20px;
}

.video-report-summary-panel {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.video-report-side-card {
  border-radius: 14px;
  background: #ffffff;
  border: 1px solid #e5e6eb;
  padding: 18px;
  box-shadow: 0 10px 24px rgba(15, 23, 42, 0.06);
}

.video-report-side-card h3 {
  margin: 0 0 14px;
  font-size: 16px;
  font-weight: 800;
  color: #0f1419;
}

.video-report-side-card--score {
  background: linear-gradient(180deg, #f8fbff 0%, #eef5ff 100%);
  border-color: rgba(22, 93, 255, 0.14);
}

.video-report-score-line {
  display: flex;
  align-items: baseline;
  gap: 6px;
  margin-bottom: 14px;
}

.video-report-score-line strong {
  font-size: 52px;
  line-height: 1;
  font-weight: 800;
  color: #0f1419;
}

.video-report-score-line span {
  font-size: 20px;
  color: #4e5969;
}

.video-report-score-grade {
  display: inline-flex;
  margin-bottom: 14px;
  padding: 6px 12px;
  border-radius: 999px;
  font-size: 13px;
  font-weight: 800;
}

.video-report-score-grade--excellent { background: rgba(34, 197, 94, 0.12); color: #15803d; }
.video-report-score-grade--pass { background: rgba(22, 93, 255, 0.12); color: #165dff; }
.video-report-score-grade--fail { background: rgba(239, 68, 68, 0.12); color: #b91c1c; }

.video-report-side-card p {
  margin: 0;
  font-size: 13px;
  line-height: 1.7;
  color: #4e5969;
}

.video-report-side-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 9px 0;
  border-bottom: 1px dashed #edf0f5;
}

.video-report-side-row:last-child {
  border-bottom: 0;
}

.video-report-side-row span {
  color: #4e5969;
  font-size: 14px;
}

.video-report-side-row strong {
  color: #0f1419;
  font-size: 15px;
  font-weight: 800;
}

.video-report-document {
  border-radius: 14px;
  background: #ffffff;
  border: 1px solid #e5e6eb;
  padding: 24px 26px;
  box-shadow: 0 10px 28px rgba(15, 23, 42, 0.06);
}

.video-report-section + .video-report-section {
  margin-top: 24px;
}

.video-report-section h3 {
  margin: 0 0 14px;
  font-size: 20px;
  font-weight: 800;
  color: #0f1419;
}

.video-report-text {
  margin: 0;
  font-size: 15px;
  line-height: 1.9;
  color: #1a1f26;
}

.video-report-notice-list {
  margin-top: 12px;
  padding: 14px 16px;
  border-radius: 12px;
  background: #f6f7f9;
  border-left: 4px solid #165dff;
}

.video-report-notice-list p {
  margin: 0;
  font-size: 14px;
  line-height: 1.8;
  color: #1d2129;
}

.video-report-notice-list p + p {
  margin-top: 6px;
}

.video-report-dimensions {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.video-report-dimension {
  border-radius: 12px;
  border: 1px solid #e5e6eb;
  background: #fff;
  padding: 16px;
}

.video-report-dimension__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 10px;
  font-size: 14px;
  color: #1d2129;
}

.video-report-bar {
  width: 100%;
  height: 8px;
  border-radius: 999px;
  background: #eef2f6;
  overflow: hidden;
}

.video-report-bar i {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, #165dff 0%, #5b8cff 100%);
}

.video-report-dimension p {
  margin: 10px 0 0;
  font-size: 13px;
  line-height: 1.7;
  color: #4e5969;
}

.ability-profile {
  display: grid;
  grid-template-columns: 180px minmax(0, 1fr);
  gap: 16px;
  padding: 16px;
  border: 1px solid #dbeafe;
  border-radius: 12px;
  background: #f8fbff;
}

.ability-profile__score {
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 6px;
  padding: 14px;
  border-radius: 10px;
  background: #eff6ff;
  color: #1d4ed8;
}

.ability-profile__score strong {
  font-size: 32px;
  line-height: 1;
}

.ability-profile__score span,
.ability-profile__score em {
  font-size: 12px;
  font-style: normal;
}

.ability-profile__body {
  display: grid;
  gap: 10px;
}

.ability-profile__body h4 {
  margin: 0 0 4px;
  color: #1d2129;
  font-size: 14px;
}

.ability-profile__body p {
  margin: 0;
  color: #4e5969;
  font-size: 13px;
  line-height: 1.7;
}

.video-report-audit-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.video-report-audit-block {
  border-radius: 12px;
  border: 1px solid #e5e6eb;
  background: #fff;
  padding: 16px;
}

.video-report-audit-block h4 {
  margin: 0 0 12px;
  font-size: 15px;
  font-weight: 800;
  color: #0f1419;
}

.video-report-chip-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.video-report-chip {
  padding: 7px 12px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 800;
}

.video-report-chip--danger { background: rgba(239, 68, 68, 0.1); color: #b91c1c; }
.video-report-chip--warn { background: rgba(245, 158, 11, 0.12); color: #b45309; }

.video-report-list {
  margin: 0;
  padding-left: 22px;
  color: #1a1f26;
}

.video-report-list li {
  font-size: 15px;
  line-height: 1.9;
}

.video-report-node-list {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.video-report-node {
  padding: 16px;
  border-radius: 12px;
  background: #fff;
  border: 1px solid #e5e6eb;
}

.video-report-node__head,
.video-report-node__meta,
.video-report-node__review,
.video-report-node__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 8px;
}

.video-report-node__head {
  margin-top: 0;
  align-items: center;
  justify-content: space-between;
}

.video-report-node__head strong {
  font-size: 17px;
  color: #0f1419;
}

.video-report-node__result {
  font-size: 14px;
  font-weight: 800;
}

.video-report-node__result--pass { color: #15803d; }
.video-report-node__result--skip,
.video-report-node__result--timeout { color: #b45309; }
.video-report-node__result--fail { color: #b91c1c; }

.video-report-node__meta,
.video-report-node__speech,
.video-report-node__issues {
  font-size: 13px;
  color: #4e5969;
  line-height: 1.7;
}

.video-report-node__issues {
  color: #b91c1c;
}

.video-report-node__review {
  font-size: 12px;
  color: #4e5969;
}

.video-report-node__review-tag {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  border-radius: 999px;
  background: rgba(250, 204, 21, 0.16);
  color: #92400e;
}

.video-report-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 20px;
}

@media (max-width: 768px) {
  .video-report-popup {
    width: min(96vw, 760px);
  }

  .video-report-popup--page {
    width: 100%;
  }

  .video-report-card {
    padding: 18px;
  }

  .video-report-head__title {
    font-size: 28px;
  }

  .video-report-layout {
    grid-template-columns: 1fr;
  }

  .video-report-document {
    padding: 18px;
  }

  .video-report-audit-grid,
  .video-report-dimensions,
  .ability-profile {
    grid-template-columns: 1fr;
  }

  .video-report-head__meta {
    gap: 8px 12px;
  }

  .video-report-node__head {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>

