<template>
  <div class="profile-page space-y-5 pb-20">
    <div class="admin-list-header">
      <div>
        <h1>学员个人画像</h1>
        <p>从训练记录中提炼整体水平、短板变化和下一步建议，方便管理端快速判断带训重点。</p>
      </div>
      <div class="header-actions">
        <div class="student-identity">
          <span class="student-identity__label">Student</span>
          <strong>{{ profile?.student?.username || '--' }}</strong>
          <span class="student-identity__level">{{ profile?.summary?.level || '待生成' }}</span>
        </div>
        <van-button plain class="!rounded-[6px] !border-slate-200 !text-slate-600" @click="router.push('/admin/students')">
          返回学员列表
        </van-button>
      </div>
    </div>

    <div v-if="loading" class="page-card page-card--loading">
      <van-loading color="#003087" vertical>正在生成画像...</van-loading>
    </div>

    <div v-else-if="pageError" class="page-error">
      <van-icon name="warning-o" size="30" class="text-amber-500" />
      <p class="page-error__text">{{ pageError }}</p>
      <van-button plain type="primary" class="mt-5" @click="fetchProfile">重新加载</van-button>
    </div>

    <template v-else-if="profile">
      <section class="page-card summary-panel">
        <div class="summary-hero">
          <div class="summary-hero__badge">{{ profile.summary.level }}</div>
          <p class="summary-hero__text">{{ profile.summary.summary_text || '暂无总结' }}</p>
        </div>

        <div class="summary-stats">
          <div class="summary-stat">
            <span>累计训练</span>
            <strong>{{ profile.summary.total_sessions }}</strong>
          </div>
          <div class="summary-stat">
            <span>完成训练</span>
            <strong>{{ profile.summary.finished_sessions }}</strong>
          </div>
          <div class="summary-stat">
            <span>平均分</span>
            <strong>{{ formatScore(profile.summary.average_score) }}</strong>
          </div>
          <div class="summary-stat">
            <span>稳定性</span>
            <strong>{{ profile.summary.stability_status || '--' }}</strong>
          </div>
          <div class="summary-stat">
            <span>阶段趋势</span>
            <strong>{{ profile.summary.progress_status || '--' }}</strong>
          </div>
          <div class="summary-stat">
            <span>最近训练</span>
            <strong>{{ formatDate(profile.summary.latest_training_at) }}</strong>
          </div>
        </div>
      </section>

      <section class="page-card">
        <div class="panel-title">能力概览</div>
        <div class="dimension-grid">
          <div v-for="item in profile.dimensions" :key="item.key" class="dimension-card">
            <div class="dimension-head">
              <span>{{ item.label }}</span>
              <span class="dimension-trend" :class="trendClass(item.trend)">{{ item.trend || '持平' }}</span>
            </div>
            <div class="dimension-score">{{ formatScore(item.score) }}</div>
            <van-progress :percentage="normalizeScore(item.score)" stroke-width="10" color="#003087" />
          </div>
        </div>
      </section>

      <section class="page-card">
        <div class="panel-title">场景表现</div>
        <div v-if="profile.scene_performance.length" class="scene-list">
          <div v-for="item in profile.scene_performance" :key="item.label" class="scene-item">
            <div>
              <div class="scene-name">{{ item.label }}</div>
              <div class="scene-meta">训练 {{ item.session_count }} 次</div>
            </div>
            <div class="text-right">
              <div class="scene-score">{{ formatScore(item.average_score) }}</div>
              <div class="scene-status">{{ item.status || '--' }}</div>
            </div>
          </div>
        </div>
        <div v-else class="empty-tip">暂无可展示的场景训练记录。</div>
      </section>

      <section class="diagnose-grid">
        <div class="page-card">
          <div class="panel-title">高频问题</div>
          <div v-if="profile.high_frequency_issues.length" class="issue-list">
            <div v-for="item in profile.high_frequency_issues" :key="`freq-${item.label}`" class="issue-item">
              <span>{{ item.label }}</span>
              <span class="issue-count">{{ item.count }} 次</span>
            </div>
          </div>
          <div v-else class="empty-tip">暂未发现稳定重复出现的问题。</div>
        </div>

        <div class="page-card">
          <div class="panel-title">高风险问题</div>
          <div v-if="profile.high_risk_issues.length" class="issue-list">
            <div v-for="item in profile.high_risk_issues" :key="`risk-${item.label}`" class="issue-item issue-item--risk">
              <span>{{ item.label }}</span>
              <span class="issue-count">{{ item.count }} 次</span>
            </div>
          </div>
          <div v-else class="empty-tip">当前没有明显高风险短板。</div>
        </div>

        <div class="page-card">
          <div class="panel-title">顽固问题</div>
          <div v-if="profile.stubborn_issues.length" class="issue-list">
            <div
              v-for="item in profile.stubborn_issues"
              :key="`stubborn-${item.label}`"
              class="issue-item issue-item--warn"
            >
              <span>{{ item.label }}</span>
              <span class="issue-count">{{ item.count }} 次</span>
            </div>
          </div>
          <div v-else class="empty-tip">最近训练中没有连续反复出现的问题。</div>
        </div>
      </section>

      <section class="page-card">
        <div class="panel-title">成长趋势</div>
        <div v-if="profile.trend_points.length" class="trend-row">
          <div v-for="item in profile.trend_points" :key="item.session_id" class="trend-card">
            <div class="trend-date">{{ formatShortDate(item.created_at) }}</div>
            <div class="trend-score">{{ formatScore(item.score) }}</div>
          </div>
        </div>
        <div v-else class="empty-tip">完成训练次数还不够，后续会自动生成趋势。</div>
      </section>

      <section class="page-card">
        <div class="panel-title">训练建议</div>
        <div v-if="profile.suggestions.length" class="suggestion-list">
          <div v-for="(item, index) in profile.suggestions" :key="`${index}-${item}`" class="suggestion-item">
            <div class="suggestion-index">{{ Number(index) + 1 }}</div>
            <div class="text-sm leading-7 text-slate-700">{{ item }}</div>
          </div>
        </div>
        <div v-else class="empty-tip">建议会在积累更多训练记录后自动补充。</div>
      </section>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import request from '../utils/request'

type ProfileResponse = {
  student: { id: number; username: string }
  summary: {
    level: string
    summary_text: string
    total_sessions: number
    finished_sessions: number
    average_score: number | null
    stability_status: string
    progress_status: string
    latest_training_at: string | null
  }
  dimensions: Array<{ key: string; label: string; score: number; trend: string }>
  scene_performance: Array<{ label: string; session_count: number; average_score: number | null; status: string }>
  high_frequency_issues: Array<{ label: string; count: number }>
  high_risk_issues: Array<{ label: string; count: number }>
  stubborn_issues: Array<{ label: string; count: number }>
  trend_points: Array<{ session_id: number; score: number; created_at: string | null }>
  suggestions: string[]
}

const route = useRoute()
const router = useRouter()

const loading = ref(false)
const pageError = ref('')
const profile = ref<ProfileResponse | null>(null)

const studentId = computed(() => Number(route.params.id || 0))

const formatScore = (value: number | null | undefined) => {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '--'
  return Number(value).toFixed(1)
}

const normalizeScore = (value: number | null | undefined) => {
  const num = Number(value)
  if (!Number.isFinite(num)) return 0
  return Math.max(0, Math.min(100, num))
}

const formatDate = (value: string | null | undefined) => {
  if (!value) return '--'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '--'
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
}

const formatShortDate = (value: string | null | undefined) => {
  if (!value) return '--'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '--'
  return `${String(date.getMonth() + 1).padStart(2, '0')}/${String(date.getDate()).padStart(2, '0')}`
}

const trendClass = (trend: string) => {
  if (trend === '上升') return 'trend-up'
  if (trend === '下降') return 'trend-down'
  return 'trend-flat'
}

const isValidProfileResponse = (value: any): value is ProfileResponse => {
  return Boolean(
    value &&
      typeof value === 'object' &&
      value.student &&
      value.summary &&
      Array.isArray(value.dimensions) &&
      Array.isArray(value.scene_performance) &&
      Array.isArray(value.suggestions)
  )
}

const fetchProfile = async () => {
  if (!studentId.value) {
    profile.value = null
    pageError.value = '缺少学员编号，无法生成画像。'
    return
  }

  loading.value = true
  pageError.value = ''
  profile.value = null

  try {
    const result = await request.get(`/auth/students/${studentId.value}/profile`, {
      timeout: 15000,
      _skipErrorToast: true,
    } as any)

    if (!isValidProfileResponse(result)) {
      pageError.value = '画像数据暂未准备完成，请确认后端已更新后再试。'
      return
    }

    profile.value = result
  } catch {
    pageError.value = '画像加载失败，请确认后端服务已启动后再试。'
  } finally {
    loading.value = false
  }
}

onMounted(fetchProfile)
watch(() => route.params.id, fetchProfile)
</script>

<style scoped>
.profile-page {
  width: 100%;
}

.admin-list-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 18px 20px;
  border: 1px solid var(--police-border);
  border-radius: var(--police-radius-lg);
  background: #fff;
}

.admin-list-header h1 {
  margin: 0;
  color: var(--police-text-primary);
  font-size: 22px;
  font-weight: 800;
}

.admin-list-header p {
  margin: 4px 0 0;
  max-width: 760px;
  color: var(--police-text-muted);
  font-size: 13px;
  line-height: 1.8;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.student-identity {
  min-width: 220px;
  border: 1px solid #d9e3f0;
  border-radius: var(--police-radius-lg);
  background: linear-gradient(135deg, #eef4ff 0%, #f8fbff 100%);
  padding: 14px 16px;
  box-shadow: var(--police-shadow-sm);
}

.student-identity__label {
  display: block;
  color: var(--police-text-muted);
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.18em;
  text-transform: uppercase;
}

.student-identity strong {
  display: block;
  margin-top: 8px;
  color: var(--police-text-primary);
  font-size: 20px;
  font-weight: 800;
}

.student-identity__level {
  display: block;
  margin-top: 6px;
  color: var(--police-primary);
  font-size: 13px;
  font-weight: 700;
}

.page-card {
  border: 1px solid var(--police-border);
  border-radius: var(--police-radius-lg);
  background: #fff;
  box-shadow: var(--police-shadow-sm);
  padding: 20px;
}

.page-card--loading {
  padding: 80px 20px;
  text-align: center;
}

.page-error {
  border: 1px solid #fcd34d;
  border-radius: var(--police-radius-lg);
  background: #fffbeb;
  padding: 40px 24px;
  text-align: center;
}

.page-error__text {
  margin: 14px 0 0;
  color: #92400e;
  font-size: 14px;
  font-weight: 700;
}

.summary-panel {
  display: grid;
  grid-template-columns: 1.1fr 0.9fr;
  gap: 16px;
}

.summary-hero {
  border-radius: var(--police-radius-lg);
  background: linear-gradient(135deg, #003087 0%, #1a4fa0 100%);
  padding: 22px;
  color: #fff;
}

.summary-hero__badge {
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.14);
  padding: 6px 12px;
  color: #fff;
  font-size: 12px;
  font-weight: 700;
}

.summary-hero__text {
  margin: 16px 0 0;
  color: rgba(255, 255, 255, 0.92);
  font-size: 14px;
  line-height: 1.9;
}

.summary-stats {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.summary-stat {
  border: 1px solid var(--police-border-light);
  border-radius: var(--police-radius-lg);
  background: #f8fafc;
  padding: 14px;
}

.summary-stat span {
  display: block;
  color: var(--police-text-muted);
  font-size: 12px;
}

.summary-stat strong {
  display: block;
  margin-top: 6px;
  color: var(--police-text-primary);
  font-size: 18px;
}

.panel-title {
  margin-bottom: 16px;
  color: var(--police-text-primary);
  font-size: 18px;
  font-weight: 700;
}

.dimension-grid,
.diagnose-grid {
  display: grid;
  gap: 14px;
}

.dimension-grid {
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
}

.diagnose-grid {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.dimension-card,
.scene-item,
.issue-item,
.suggestion-item,
.trend-card {
  border: 1px solid var(--police-border-light);
  border-radius: var(--police-radius-lg);
  background: #f8fafc;
}

.dimension-card {
  padding: 16px;
}

.dimension-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  color: var(--police-text-secondary);
  font-size: 14px;
}

.dimension-score {
  margin: 12px 0;
  color: var(--police-text-primary);
  font-size: 28px;
  font-weight: 800;
}

.dimension-trend {
  border-radius: 999px;
  padding: 4px 10px;
  font-size: 12px;
  font-weight: 700;
}

.trend-up {
  background: #dcfce7;
  color: #15803d;
}

.trend-down {
  background: #fee2e2;
  color: #dc2626;
}

.trend-flat {
  background: #e2e8f0;
  color: #475569;
}

.scene-list,
.issue-list,
.suggestion-list,
.trend-row {
  display: grid;
  gap: 12px;
}

.scene-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  padding: 15px 16px;
}

.scene-name {
  color: var(--police-text-primary);
  font-size: 15px;
  font-weight: 700;
}

.scene-meta,
.scene-status,
.trend-date,
.empty-tip {
  color: var(--police-text-muted);
  font-size: 13px;
}

.scene-score,
.trend-score {
  color: var(--police-text-primary);
  font-size: 20px;
  font-weight: 800;
}

.issue-item,
.suggestion-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 14px 16px;
}

.issue-item--risk {
  border-color: #fed7aa;
  background: #fff7ed;
}

.issue-item--warn {
  border-color: #fde68a;
  background: #fefce8;
}

.issue-count {
  color: var(--police-primary);
  font-size: 13px;
  font-weight: 700;
}

.trend-row {
  grid-template-columns: repeat(auto-fit, minmax(110px, 1fr));
}

.trend-card {
  padding: 16px;
  text-align: center;
}

.suggestion-item {
  align-items: flex-start;
  justify-content: flex-start;
}

.suggestion-index {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  flex-shrink: 0;
  border-radius: 999px;
  background: var(--police-primary);
  color: #fff;
  font-size: 13px;
  font-weight: 800;
}

@media (max-width: 960px) {
  .admin-list-header,
  .header-actions {
    flex-direction: column;
    align-items: stretch;
  }

  .summary-panel,
  .diagnose-grid {
    grid-template-columns: 1fr;
  }

  .student-identity {
    min-width: 0;
  }
}
</style>
