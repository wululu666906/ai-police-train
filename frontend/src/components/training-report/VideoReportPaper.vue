<template>
  <main class="report-paper">
    <header class="paper-hero">
      <div>
        <h2>视频实训评估报告</h2>
        <p>
          报告编号：VR-{{ report?.session_id || '0000' }}
          <span>评估日期：{{ reportFinishedAt || '未记录' }}</span>
        </p>
      </div>
    </header>

    <section class="report-section report-section--summary">
      <div class="section-title"><i></i><span>本次结论</span></div>
      <div class="summary-layout">
        <div class="summary-copy">
          <h3>{{ reportGrade }}</h3>
          <p>{{ scoreHint }}</p>
        </div>
        <div class="summary-metrics">
          <article>
            <span>综合得分</span>
            <strong>{{ reportScore }}</strong>
            <p>/ {{ reportFullScore }} 分</p>
          </article>
          <article>
            <span>得分率</span>
            <strong>{{ reportPercentage }}%</strong>
            <p>{{ reportModeLabel }}</p>
          </article>
          <article>
            <span>通过节点</span>
            <strong>{{ reportPassCount }}</strong>
            <p>共 {{ reportTotalNodes }} 个节点</p>
          </article>
        </div>
      </div>
      <div class="insight-grid">
        <article>
          <span>优势亮点</span>
          <strong>{{ strengthTitle }}</strong>
          <p>{{ strengthNote }}</p>
        </article>
        <article>
          <span>提升建议</span>
          <strong>{{ weaknessTitle }}</strong>
          <p>{{ weaknessNote }}</p>
        </article>
      </div>
    </section>

    <section class="report-section">
      <div class="section-title"><i></i><span>训练概况</span></div>
      <div class="overview-table">
        <div><span>实训名称</span><strong>{{ reportTitle }}</strong></div>
        <div><span>训练模式</span><strong>{{ reportModeLabel }}</strong></div>
        <div><span>通过节点</span><strong>{{ reportPassCount }}</strong></div>
        <div><span>未通过节点</span><strong>{{ reportFailCount }}</strong></div>
        <div><span>跳过节点</span><strong>{{ reportSkipCount }}</strong></div>
        <div><span>违规次数</span><strong>{{ reportViolationCount }}</strong></div>
        <div><span>总扣分</span><strong>{{ reportTotalDeducted }}</strong></div>
        <div><span>完成时间</span><strong>{{ reportFinishedAt || '未记录' }}</strong></div>
      </div>
    </section>

    <section v-if="dimensionScores.length" class="report-section">
      <div class="section-title"><i></i><span>能力指标结果</span></div>
      <div class="score-grid">
        <article v-for="item in dimensionScores" :key="item.key" class="score-item">
          <div class="score-item__head">
            <strong>{{ item.label }}</strong>
            <span>{{ item.score }}/{{ item.full_score }} 分</span>
          </div>
          <div class="score-bar"><i :style="{ width: `${item.percentage}%` }"></i></div>
          <p>完成度 {{ item.percentage }}%，基于节点动作、话术与流程表现综合判定。</p>
        </article>
      </div>
    </section>

    <section v-if="abilityProfile?.enabled" class="report-section">
      <div class="section-title"><i></i><span>警情处置画像</span></div>
      <div class="overview-table">
        <div><span>标准点覆盖</span><strong>{{ abilityProfile.standard_point_coverage || 0 }}%</strong></div>
        <div><span>语义平均分</span><strong>{{ abilityProfile.semantic_average || 0 }}</strong></div>
        <div v-if="abilityProfile.strengths?.length"><span>已形成能力</span><strong>{{ abilityProfile.strengths.join('、') }}</strong></div>
        <div v-if="abilityProfile.risks?.length"><span>待补强短板</span><strong>{{ abilityProfile.risks.join('、') }}</strong></div>
      </div>
      <p v-if="abilityProfile.next_training?.length" class="report-text">{{ abilityProfile.next_training.join('；') }}</p>
    </section>

    <section v-if="failureReasonList.length || violationList.length" class="report-section">
      <div class="section-title"><i></i><span>训练审计</span></div>
      <div v-if="failureReasonList.length" class="chip-list" style="margin-bottom: 12px;">
        <span v-for="item in failureReasonList" :key="item.key" class="report-chip report-chip--danger">
          {{ item.label }} x{{ item.count }}
        </span>
      </div>
      <div v-if="violationList.length" class="chip-list">
        <span v-for="item in violationList" :key="item.key" class="report-chip report-chip--warn">
          {{ item.label }} x{{ item.count }}
        </span>
      </div>
    </section>

    <section v-if="weaknessSummary.length" class="report-section">
      <div class="section-title"><i></i><span>复盘建议</span></div>
      <ol class="report-list">
        <li v-for="item in weaknessSummary" :key="item">{{ item }}</li>
      </ol>
    </section>

    <section class="report-section">
      <div class="section-title"><i></i><span>节点明细</span></div>
      <div class="node-list">
        <article v-for="item in reportNodes" :key="item.node_index" class="node-item">
          <div class="node-item__head">
            <strong>{{ item.node_title || `节点 ${item.node_index + 1}` }}</strong>
            <span class="node-item__result" :class="`node-item__result--${item.result}`">{{ resultLabel(item.result) }}</span>
          </div>
          <div class="node-item__meta">
            <span>序号 {{ item.node_index + 1 }}</span>
            <span>得分 {{ item.score_earned }}</span>
            <span v-if="item.score_deducted">扣分 {{ item.score_deducted }}</span>
            <span v-if="item.retry_count">重试 x{{ item.retry_count }}</span>
          </div>
          <div v-if="item.speech_transcript" class="node-item__speech">语音识别：{{ item.speech_transcript }}</div>
          <div v-if="item.failure_reasons?.length" class="node-item__issues">
            失分原因：{{ item.failure_reasons.map(formatFailureReason).join('、') }}
          </div>
          <div v-if="item.manual_review?.review_note" class="node-item__speech">
            复核说明：{{ item.manual_review.review_note }}
          </div>
          <div v-if="reviewable" class="node-item__actions">
            <el-button size="small" type="primary" plain @click="emit('review-node', item)">人工复核 / 改判</el-button>
          </div>
        </article>
      </div>
    </section>
  </main>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import {
  formatDateTime,
  formatFailureReason,
  resultLabel,
  useVideoReportMetrics,
  type VideoReportData,
  type VideoReportNode,
} from '../../composables/useVideoReportMetrics'

const props = withDefaults(defineProps<{
  report: VideoReportData | null
  reviewable?: boolean
}>(), {
  reviewable: false,
})

const emit = defineEmits<{
  'review-node': [item: VideoReportNode]
}>()

const metrics = computed(() => useVideoReportMetrics(props.report))

const reportTitle = computed(() => metrics.value.reportTitle)
const reportModeLabel = computed(() => metrics.value.reportModeLabel)
const reportPercentage = computed(() => metrics.value.reportPercentage)
const reportFinishedAt = computed(() => metrics.value.reportFinishedAt)
const reportScore = computed(() => metrics.value.reportScore)
const reportFullScore = computed(() => metrics.value.reportFullScore)
const reportGrade = computed(() => metrics.value.reportGrade)
const reportPassCount = computed(() => metrics.value.reportPassCount)
const reportSkipCount = computed(() => metrics.value.reportSkipCount)
const reportFailCount = computed(() => metrics.value.reportFailCount)
const reportViolationCount = computed(() => metrics.value.reportViolationCount)
const reportTotalDeducted = computed(() => metrics.value.reportTotalDeducted)
const reportTotalNodes = computed(() => metrics.value.reportTotalNodes)
const reportNodes = computed(() => metrics.value.reportNodes)
const dimensionScores = computed(() => metrics.value.dimensionScores)
const weaknessSummary = computed(() => metrics.value.weaknessSummary)
const abilityProfile = computed(() => metrics.value.abilityProfile)
const scoreHint = computed(() => metrics.value.scoreHint)
const failureReasonList = computed(() => metrics.value.failureReasonList)
const violationList = computed(() => metrics.value.violationList)
const strengthTitle = computed(() => metrics.value.strengthTitle)
const strengthNote = computed(() => metrics.value.strengthNote)
const weaknessTitle = computed(() => metrics.value.weaknessTitle)
const weaknessNote = computed(() => metrics.value.weaknessNote)
</script>

<style scoped src="../../styles/training-report-shell.css"></style>
