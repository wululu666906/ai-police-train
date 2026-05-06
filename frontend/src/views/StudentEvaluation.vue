<template>
  <div class="evaluation-page">
    <div v-if="loading" class="loading-state">
      <van-loading color="#165DFF" vertical>正在生成评估报告...</van-loading>
    </div>

    <div v-else-if="report" class="report-content">
      <div class="score-header">
        <div class="score-bg-icon">
          <van-icon name="medal-o" size="120" />
        </div>
        <p class="score-label">综合评分</p>
        <div class="score-number">{{ report.total_score }}</div>
        <div class="score-level">
          <van-tag :color="getLevelColor(report.total_score)" size="large" round>
            {{ getLevel(report.total_score) }}
          </van-tag>
        </div>
      </div>

      <section class="section">
        <h3 class="section-title">
          <span class="title-bar"></span>
          分项评分详情
        </h3>
        <div class="score-grid">
          <div v-for="s in report.scores" :key="s.dimension" class="score-card">
            <div class="score-card-header">
              <span class="dim-name">{{ s.dimension }}</span>
              <span class="dim-score" :class="getScoreClass(s.score, s.full_score)">
                {{ s.score }}<span class="dim-full">/{{ s.full_score }}</span>
              </span>
            </div>
            <div class="dim-bar-track">
              <div
                class="dim-bar-fill"
                :class="getBarClass(s.score, s.full_score)"
                :style="{ width: (s.score / s.full_score * 100) + '%' }"
              ></div>
            </div>
            <p class="dim-reason">{{ s.reason }}</p>
          </div>
        </div>
      </section>

      <div class="two-col">
        <section class="feedback-card strengths-card">
          <h3 class="feedback-title">
            <van-icon name="like-o" color="#00B42A" />
            表现亮点
          </h3>
          <ul class="feedback-list">
            <li v-for="item in report.strengths" :key="item">
              <span class="dot dot-green"></span>
              {{ item }}
            </li>
          </ul>
        </section>

        <section class="feedback-card improvements-card">
          <h3 class="feedback-title">
            <van-icon name="info-o" color="#FF7D00" />
            改进建议
          </h3>
          <ul class="feedback-list">
            <li v-for="item in report.improvements" :key="item">
              <span class="dot dot-orange"></span>
              {{ item }}
            </li>
          </ul>
        </section>
      </div>

      <section v-if="report.suggestions" class="section">
        <div class="expert-card">
          <van-icon name="comment-o" class="expert-icon" />
          <h3 class="expert-title">综合点评</h3>
          <p class="expert-text">{{ report.suggestions }}</p>
        </div>
      </section>

      <div class="action-bar">
        <van-button size="large" class="btn-secondary" @click="router.push('/student/hall')">
          返回训练大厅
        </van-button>
        <van-button type="primary" size="large" class="btn-primary" @click="router.push('/student/history')">
          查看训练历史
        </van-button>
      </div>
    </div>

    <div v-else class="empty-state">
      <van-icon name="info-o" size="48" color="#C9CDD4" />
      <p>暂无评估数据</p>
      <van-button type="primary" size="small" @click="router.push('/student/hall')">
        返回训练大厅
      </van-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { showToast } from 'vant'
import request from '../utils/request'

const router = useRouter()
const route = useRoute()
const report = ref<any>(null)
const loading = ref(true)

const safeParse = <T>(value: any, fallback: T): T => {
  if (value === null || value === undefined || value === '') return fallback
  if (typeof value !== 'string') return value as T
  try {
    return JSON.parse(value) as T
  } catch (error) {
    return fallback
  }
}

const fetchEvaluation = async () => {
  const rawSessionId = route.query.session_id
  const sessionId = Number(rawSessionId)

  if (!rawSessionId || Number.isNaN(sessionId) || sessionId <= 0) {
    showToast('缺少训练会话编号，无法加载评估报告')
    return
  }

  try {
    const res: any = await request.get(`/training/session/${sessionId}`)
    if (!res.evaluation_result) {
      showToast('当前训练尚未生成评估报告')
      return
    }
    report.value = safeParse(res.evaluation_result, null)
    if (!report.value) {
      showToast('评估报告解析失败')
    }
  } catch (error) {
    showToast('获取评估报告失败')
  }
}

onMounted(async () => {
  await fetchEvaluation()
  loading.value = false
})

const getLevel = (score: number) => {
  if (score >= 90) return '卓越'
  if (score >= 80) return '优秀'
  if (score >= 60) return '合格'
  return '需改进'
}

const getLevelColor = (score: number) => {
  if (score >= 85) return '#00B42A'
  if (score >= 60) return '#FF7D00'
  return '#F53F3F'
}

const getScoreClass = (score: number, full: number) => {
  const ratio = score / full
  if (ratio >= 0.85) return 'score-green'
  if (ratio >= 0.6) return 'score-orange'
  return 'score-red'
}

const getBarClass = (score: number, full: number) => {
  const ratio = score / full
  if (ratio >= 0.85) return 'bar-green'
  if (ratio >= 0.6) return 'bar-orange'
  return 'bar-red'
}
</script>

<style scoped>
.evaluation-page {
  max-width: 860px;
  margin: 0 auto;
  padding: 32px;
  font-family: 'PingFang SC', 'Microsoft YaHei', 'Inter', sans-serif;
}

.loading-state,
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 100px 0;
  gap: 16px;
  color: #86909c;
}

.score-header {
  background: #0e2f56;
  border-radius: 18px;
  padding: 40px 0;
  text-align: center;
  position: relative;
  overflow: hidden;
  margin-bottom: 24px;
}

.score-bg-icon {
  position: absolute;
  right: -20px;
  top: -20px;
  color: rgba(255, 255, 255, 0.05);
}

.score-label {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.55);
  letter-spacing: 2px;
  margin: 0 0 8px;
}

.score-number {
  font-size: 64px;
  font-weight: 800;
  color: white;
  line-height: 1;
  margin-bottom: 12px;
}

.section {
  margin-bottom: 24px;
}

.section-title {
  font-size: 16px;
  font-weight: 600;
  color: #1d2129;
  margin: 0 0 16px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.title-bar {
  width: 3px;
  height: 16px;
  background: #165dff;
  border-radius: 2px;
}

.score-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
  gap: 12px;
}

.score-card,
.feedback-card,
.expert-card {
  background: white;
  border-radius: 16px;
  padding: 18px 20px;
  box-shadow: 0 4px 18px rgba(15, 23, 42, 0.06);
}

.score-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.dim-name {
  font-size: 14px;
  font-weight: 600;
  color: #1d2129;
}

.dim-score {
  font-size: 18px;
  font-weight: 700;
}

.dim-full {
  font-size: 12px;
  font-weight: 400;
  color: #86909c;
}

.dim-bar-track {
  height: 8px;
  border-radius: 999px;
  background: #f2f3f5;
  overflow: hidden;
}

.dim-bar-fill {
  height: 100%;
  border-radius: inherit;
}

.dim-reason {
  margin: 12px 0 0;
  font-size: 13px;
  line-height: 1.7;
  color: #4e5969;
}

.two-col {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
  margin-bottom: 24px;
}

.feedback-title {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0 0 14px;
  font-size: 16px;
  color: #1d2129;
}

.feedback-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.feedback-list li {
  display: flex;
  gap: 10px;
  align-items: flex-start;
  line-height: 1.7;
  color: #4e5969;
}

.dot {
  width: 8px;
  height: 8px;
  border-radius: 999px;
  margin-top: 8px;
  flex-shrink: 0;
}

.dot-green {
  background: #00b42a;
}

.dot-orange {
  background: #ff7d00;
}

.expert-card {
  text-align: center;
}

.expert-icon {
  font-size: 28px;
  color: #165dff;
}

.expert-title {
  margin: 10px 0 12px;
  font-size: 18px;
  color: #1d2129;
}

.expert-text {
  margin: 0;
  line-height: 1.85;
  color: #4e5969;
}

.action-bar {
  display: flex;
  justify-content: center;
  gap: 16px;
}

.btn-secondary,
.btn-primary {
  min-width: 180px;
  border-radius: 12px;
}

.score-green {
  color: #00b42a;
}

.score-orange {
  color: #ff7d00;
}

.score-red {
  color: #f53f3f;
}

.bar-green {
  background: linear-gradient(90deg, #22c55e 0%, #16a34a 100%);
}

.bar-orange {
  background: linear-gradient(90deg, #fb923c 0%, #f97316 100%);
}

.bar-red {
  background: linear-gradient(90deg, #fb7185 0%, #ef4444 100%);
}

@media (max-width: 768px) {
  .evaluation-page {
    padding: 16px;
  }

  .two-col {
    grid-template-columns: 1fr;
  }

  .action-bar {
    flex-direction: column;
  }
}
</style>
