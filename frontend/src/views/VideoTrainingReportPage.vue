<template>
  <div class="video-report-page">
    <div class="video-report-page__toolbar">
      <div>
        <h1>{{ pageTitle }}</h1>
        <p>{{ pageSubtitle }}</p>
      </div>
      <div class="video-report-page__toolbar-actions">
        <el-button @click="goBack">返回</el-button>
        <el-button v-if="!isAdminReport && report?.video_id" type="primary" plain @click="restartTraining">
          重新训练
        </el-button>
      </div>
    </div>

    <section v-if="loading" class="video-report-page__state">
      <el-skeleton :rows="10" animated />
    </section>

    <section v-else-if="!report" class="video-report-page__state">
      <el-empty description="暂未找到训练评估报告">
        <el-button type="primary" @click="goBack">返回</el-button>
      </el-empty>
    </section>

    <VideoTrainingReportDialog
      v-else
      :show="true"
      :page="true"
      :show-close="false"
      :report="report"
      :reviewable="isAdminReport"
      :title="pageTitle"
      @review-node="openReviewDialog"
    >
      <template #actions>
        <el-button @click="goBack">返回</el-button>
        <el-button v-if="!isAdminReport && report.video_id" type="primary" @click="restartTraining">重新训练</el-button>
      </template>
    </VideoTrainingReportDialog>

    <el-dialog v-model="showReviewDialog" title="人工复核 / 改判" width="520px">
      <el-form :model="reviewForm" label-width="96px">
        <el-form-item label="节点">
          <div class="text-slate-700">{{ reviewTargetLabel }}</div>
        </el-form-item>
        <el-form-item label="复核结果">
          <el-select v-model="reviewForm.result" style="width: 180px">
            <el-option label="通过" value="pass" />
            <el-option label="未通过" value="fail" />
            <el-option label="跳过" value="skip" />
            <el-option label="超时" value="timeout" />
          </el-select>
        </el-form-item>
        <el-form-item label="得分">
          <el-input-number v-model="reviewForm.score_earned" :min="0" :max="reviewScoreMax" />
        </el-form-item>
        <el-form-item label="失分原因">
          <el-input
            v-model="reviewForm.failureReasonText"
            type="textarea"
            :rows="2"
            placeholder="多个原因用逗号分隔；复核通过时可留空"
          />
        </el-form-item>
        <el-form-item label="复核说明">
          <el-input
            v-model="reviewForm.review_note"
            type="textarea"
            :rows="3"
            placeholder="记录人工复核依据，便于后续追溯"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showReviewDialog = false">取消</el-button>
        <el-button type="primary" :loading="reviewSaving" @click="submitReview">提交复核</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, inject, onMounted, onUnmounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import request from '../utils/request'
import VideoTrainingReportDialog from '../components/VideoTrainingReportDialog.vue'

interface ArtifactItem {
  id: number
  artifact_type: string
  file_url?: string
  mime_type?: string
  duration_seconds?: number | null
  created_at?: string
}

interface ReportNode {
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
    reviewer_username?: string
    reviewed_at?: string
    review_note?: string
  } | null
}

interface ReportData {
  session_id?: number
  video_id?: number
  video_title?: string
  mode?: string
  grade?: string
  total_score?: number
  full_score?: number
  percentage?: number
  pass_count?: number
  skip_count?: number
  fail_count?: number
  total_nodes?: number
  total_deducted?: number
  violation_count?: number
  violation_summary?: Record<string, number>
  failure_reason_summary?: Record<string, number>
  artifacts?: ArtifactItem[]
  dimension_scores?: {
    key: string
    label: string
    score: number
    full_score: number
    percentage: number
  }[]
  weakness_summary?: string[]
  node_summaries?: ReportNode[]
  finished_at?: string
}

const route = useRoute()
const router = useRouter()
const setMainScrollable = inject<(value: boolean) => void>('setMainScrollable')

const report = ref<ReportData | null>(null)
const loading = ref(false)
const showReviewDialog = ref(false)
const reviewSaving = ref(false)
const reviewTarget = ref<ReportNode | null>(null)
const reviewForm = reactive({
  result: 'pass',
  score_earned: 0,
  review_note: '',
  failureReasonText: '',
})

const sessionId = computed(() => Number(route.params.sessionId))
const isAdminReport = computed(() => route.meta.reportRole === 'admin')
const pageTitle = computed(() => (isAdminReport.value ? '实训评估报告' : '训练评估报告'))
const pageSubtitle = computed(() => {
  if (!report.value) return '查看训练评分、能力指标、审计记录和节点明细。'
  return `${report.value.video_title || '视频实训'} · 报告编号 VR-${report.value.session_id || sessionId.value}`
})
const reviewScoreMax = computed(() => {
  if (!reviewTarget.value) return 100
  return Math.max(reviewTarget.value.score_earned + reviewTarget.value.score_deducted, reviewTarget.value.score_earned, 0)
})
const reviewTargetLabel = computed(() => {
  if (!reviewTarget.value) return '--'
  return `第 ${reviewTarget.value.node_index + 1} 节点：${reviewTarget.value.node_title || '未命名节点'}`
})

onMounted(() => {
  setMainScrollable?.(true)
  void fetchReport()
})

onUnmounted(() => {
  setMainScrollable?.(false)
})

async function fetchReport() {
  if (!sessionId.value) {
    report.value = null
    return
  }

  loading.value = true
  try {
    const url = isAdminReport.value
      ? `/video-training/admin/sessions/${sessionId.value}/report`
      : `/video-training/session/${sessionId.value}/report`
    const res: ReportData = await request.get(url)
    report.value = {
      ...res,
      session_id: res.session_id || sessionId.value,
      grade: res.grade || gradeFromScore(Number(res.percentage || 0)),
    }
  } catch {
    report.value = null
    ElMessage.error('加载报告失败')
  } finally {
    loading.value = false
  }
}

function goBack() {
  if (window.history.length > 1) {
    router.back()
    return
  }
  router.push(isAdminReport.value ? '/admin/video-sessions' : '/student/video-history')
}

function restartTraining() {
  if (!report.value?.video_id) return
  router.replace(`/student/video-training/${report.value.video_id}`)
}

function openReviewDialog(item: ReportNode) {
  if (!isAdminReport.value) return
  reviewTarget.value = item
  reviewForm.result = item.result || 'pass'
  reviewForm.score_earned = item.score_earned || 0
  reviewForm.review_note = item.manual_review?.review_note || ''
  reviewForm.failureReasonText = (item.failure_reasons || []).join(', ')
  showReviewDialog.value = true
}

async function submitReview() {
  if (!reviewTarget.value?.node_result_id) {
    ElMessage.error('当前节点缺少复核目标')
    return
  }

  reviewSaving.value = true
  try {
    const failure_reasons = reviewForm.failureReasonText
      .split(/[，,]/)
      .map((item) => item.trim())
      .filter(Boolean)
    await request.post(`/video-training/admin/node-results/${reviewTarget.value.node_result_id}/review`, {
      result: reviewForm.result,
      score_earned: reviewForm.score_earned,
      failure_reasons,
      review_note: reviewForm.review_note.trim(),
    })
    showReviewDialog.value = false
    await fetchReport()
    ElMessage.success('复核结果已更新')
  } catch {
    ElMessage.error('提交复核失败')
  } finally {
    reviewSaving.value = false
  }
}

function gradeFromScore(pct: number): string {
  if (pct >= 90) return '优秀'
  if (pct >= 70) return '合格'
  return '待重修'
}
</script>

<style scoped lang="scss">
.video-report-page {
  min-height: 100%;
  padding: 18px 22px 28px;
  background: #f3f6fb;
}

.video-report-page__toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
  padding: 16px 18px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #fff;
}

.video-report-page__toolbar h1 {
  margin: 0;
  font-size: 22px;
  font-weight: 800;
  color: #13213a;
}

.video-report-page__toolbar p {
  margin: 6px 0 0;
  font-size: 14px;
  color: #64748b;
}

.video-report-page__toolbar-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 10px;
}

.video-report-page__state {
  padding: 56px 24px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #fff;
}

@media (max-width: 768px) {
  .video-report-page {
    padding: 14px;
  }

  .video-report-page__toolbar {
    align-items: flex-start;
    flex-direction: column;
  }

  .video-report-page__toolbar-actions {
    width: 100%;
    justify-content: flex-start;
  }
}
</style>
