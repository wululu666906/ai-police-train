<template>
  <TrainingReportShell
    :breadcrumb="pageBreadcrumb"
    :loading="loading"
    :has-content="Boolean(report)"
    empty-title="暂未找到训练评估报告"
    empty-description="该实训记录可能尚未完成评估，或报告暂未生成。"
    @back="goBack"
    @print="printReport"
  >
    <template #actions>
      <el-button type="primary" size="small" @click="printReport">打印 / 保存 PDF</el-button>
      <el-button plain size="small" @click="goBack">返回</el-button>
      <el-button v-if="!isAdminReport && report?.video_id" type="primary" plain @click="restartTraining">重新训练</el-button>
    </template>

    <article v-if="report" class="evaluation-document">
      <VideoReportPaper :report="report" :reviewable="isAdminReport" @review-node="openReviewDialog" />
    </article>
  </TrainingReportShell>

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
        <el-input v-model="reviewForm.failureReasonText" type="textarea" :rows="2" placeholder="多个原因用逗号分隔；复核通过时可留空" />
      </el-form-item>
      <el-form-item label="复核说明">
        <el-input v-model="reviewForm.review_note" type="textarea" :rows="3" placeholder="记录人工复核依据，便于后续追溯" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="showReviewDialog = false">取消</el-button>
      <el-button type="primary" :loading="reviewSaving" @click="submitReview">提交复核</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, inject, onMounted, onUnmounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import request from '../utils/request'
import TrainingReportShell from '../components/training-report/TrainingReportShell.vue'
import VideoReportPaper from '../components/training-report/VideoReportPaper.vue'
import type { VideoReportData, VideoReportNode } from '../composables/useVideoReportMetrics'

const route = useRoute()
const router = useRouter()
const setMainScrollable = inject<(value: boolean) => void>('setMainScrollable')

const report = ref<VideoReportData | null>(null)
const loading = ref(false)
const showReviewDialog = ref(false)
const reviewSaving = ref(false)
const reviewTarget = ref<VideoReportNode | null>(null)
const reviewForm = reactive({
  result: 'pass',
  score_earned: 0,
  review_note: '',
  failureReasonText: '',
})

const sessionId = computed(() => Number(route.params.sessionId))
const isAdminReport = computed(() => route.meta.reportRole === 'admin')
const pageBreadcrumb = computed(() => (isAdminReport.value ? '实训管理 / 训练评估报告 / 详情' : '视频实训 / 训练评估报告 / 详情'))

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
    const res: VideoReportData = await request.get(url)
    report.value = {
      ...res,
      session_id: res.session_id || sessionId.value,
    }
  } catch {
    report.value = null
    ElMessage.error('加载报告失败')
  } finally {
    loading.value = false
  }
}

function printReport() {
  window.print()
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

function openReviewDialog(item: VideoReportNode) {
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
</script>
