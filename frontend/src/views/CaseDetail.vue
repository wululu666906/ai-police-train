<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { showToast } from 'vant'
import request from '../utils/request'

const route = useRoute()
const router = useRouter()

const caseId = computed(() => route.params.id)
const loading = ref(false)
const caseData = ref<any>(null)
const error = ref('')

const fetchCase = async () => {
  loading.value = true
  error.value = ''
  try {
    const res: any = await request.get(`/cases/${caseId.value}`)
    caseData.value = res
  } catch {
    error.value = '案件加载失败，请稍后重试'
    showToast('案件加载失败')
  } finally {
    loading.value = false
  }
}

onMounted(fetchCase)

const goBack = () => router.push('/admin/cases')
const goEdit = () => router.push(`/admin/cases/${caseId.value}/edit`)

const structuredData = computed(() => {
  if (!caseData.value?.structured_data) return {}
  try {
    return typeof caseData.value.structured_data === 'string'
      ? JSON.parse(caseData.value.structured_data)
      : caseData.value.structured_data
  } catch {
    return {}
  }
})

const persons = computed(() => {
  const p = structuredData.value?.persons
  return Array.isArray(p) ? p : []
})

const formatDate = (dt: string | null | undefined) => {
  if (!dt) return '—'
  try { return new Date(dt).toLocaleDateString('zh-CN') } catch { return String(dt) }
}

const getTagType = (caseType: string) => {
  if (!caseType) return 'default'
  if (/纠纷|家庭|邻里|劳资|消费/.test(caseType)) return 'primary'
  if (/治安|打架|斗殴|醉酒/.test(caseType)) return 'warning'
  if (/刑事|盗窃|抢劫|诈骗/.test(caseType)) return 'danger'
  if (/交通/.test(caseType)) return 'success'
  return 'default'
}
</script>

<template>
  <div class="cd-page">
    <!-- 顶部导航栏 -->
    <div class="cd-topbar">
      <button class="cd-back-btn" @click="goBack">
        <van-icon name="arrow-left" />
        <span>案件脚本库</span>
      </button>
      <div class="cd-topbar__center">
        <span class="cd-topbar__title">{{ caseData?.title || '案件详情' }}</span>
      </div>
      <div class="cd-topbar__actions">
        <van-button
          type="primary"
          size="small"
          class="!bg-[#1D3557] !border-none !rounded-[8px]"
          @click="goEdit"
        >
          编辑案件
        </van-button>
      </div>
    </div>

    <!-- 内容区 -->
    <div class="cd-content">

      <!-- 加载中 -->
      <div v-if="loading" class="cd-loading">
        <van-loading color="#1D3557" vertical>加载中...</van-loading>
      </div>

      <!-- 错误 -->
      <div v-else-if="error" class="cd-error">
        <van-icon name="warning-o" size="40" class="text-amber-400" />
        <p>{{ error }}</p>
        <van-button plain type="primary" @click="fetchCase">重新加载</van-button>
      </div>

      <!-- 详情内容 -->
      <template v-else-if="caseData">

        <!-- 案件头部 -->
        <div class="cd-hero">
          <div class="cd-hero__main">
            <div class="cd-hero__title">{{ caseData.title || '未命名案件' }}</div>
            <div class="cd-hero__meta">
              <van-tag :type="getTagType(caseData.case_type)" plain>{{ caseData.case_type || '未分类' }}</van-tag>
              <span class="cd-meta-item">ID {{ caseData.id }}</span>
              <span class="cd-meta-sep">·</span>
              <span class="cd-meta-item">创建于 {{ formatDate(caseData.created_at) }}</span>
              <span class="cd-meta-sep">·</span>
              <span class="cd-meta-item">{{ (caseData.scenes || []).length }} 个场景</span>
              <span class="cd-meta-sep">·</span>
              <span class="cd-meta-item">{{ persons.length }} 个角色</span>
            </div>
          </div>
        </div>

        <!-- 主体两栏布局 -->
        <div class="cd-body">

          <!-- 左主栏 -->
          <div class="cd-main">

            <!-- 案件背景 -->
            <div class="cd-card">
              <div class="cd-card__header">
                <span class="cd-card__icon">📋</span>
                <span class="cd-card__title">案件背景</span>
              </div>
              <div class="cd-card__body">
                <p class="cd-text">{{ caseData.background || '暂无背景描述' }}</p>
              </div>
            </div>

            <!-- 角色列表 -->
            <div class="cd-card">
              <div class="cd-card__header">
                <span class="cd-card__icon">👥</span>
                <span class="cd-card__title">角色模板</span>
                <span class="cd-card__count">{{ persons.length }} 人</span>
              </div>
              <div v-if="persons.length" class="cd-person-list">
                <div
                  v-for="(person, idx) in persons"
                  :key="idx"
                  class="cd-person-item"
                >
                  <div class="cd-person-avatar">{{ String(person.name || '?').charAt(0) }}</div>
                  <div class="cd-person-info">
                    <div class="cd-person-name">{{ person.name || '未命名' }}</div>
                    <div class="cd-person-meta">
                      <span>{{ person.role_type || person.role || '相关人员' }}</span>
                      <span v-if="person.behavior_archetype" class="cd-person-archetype">{{ person.behavior_archetype }}</span>
                    </div>
                    <p v-if="person.current_goal" class="cd-person-goal">{{ person.current_goal }}</p>
                  </div>
                  <div class="cd-person-status">
                    <span class="cd-status-tag">{{ person.status || '正常' }}</span>
                  </div>
                </div>
              </div>
              <div v-else class="cd-empty">暂无角色信息</div>
            </div>

            <!-- 场景列表 -->
            <div class="cd-card">
              <div class="cd-card__header">
                <span class="cd-card__icon">🎬</span>
                <span class="cd-card__title">训练场景</span>
                <span class="cd-card__count">{{ (caseData.scenes || []).length }} 个</span>
              </div>
              <div v-if="(caseData.scenes || []).length" class="cd-scene-list">
                <div
                  v-for="(scene, idx) in caseData.scenes"
                  :key="scene.id"
                  class="cd-scene-item"
                >
                  <div class="cd-scene-index">场景 {{ Number(idx) + 1 }}</div>
                  <div class="cd-scene-info">
                    <div class="cd-scene-name">{{ scene.name || '未命名场景' }}</div>
                    <p v-if="scene.description" class="cd-scene-desc">{{ scene.description }}</p>
                    <div class="cd-scene-meta">
                      <van-tag plain size="medium">{{ scene.difficulty || '中等' }}</van-tag>
                      <span v-if="scene.dispatch_brief" class="cd-scene-brief">{{ scene.dispatch_brief }}</span>
                    </div>
                  </div>
                </div>
              </div>
              <div v-else class="cd-empty">暂无场景</div>
            </div>

          </div>

          <!-- 右侧栏 -->
          <aside class="cd-aside">

            <!-- 案件统计 -->
            <div class="cd-card">
              <div class="cd-card__header">
                <span class="cd-card__icon">📊</span>
                <span class="cd-card__title">概览</span>
              </div>
              <div class="cd-card__body">
                <div class="cd-stat-list">
                  <div class="cd-stat-item">
                    <span class="cd-stat-label">案件类型</span>
                    <span class="cd-stat-value">{{ caseData.case_type || '—' }}</span>
                  </div>
                  <div class="cd-stat-item">
                    <span class="cd-stat-label">训练场景数</span>
                    <span class="cd-stat-value">{{ (caseData.scenes || []).length }}</span>
                  </div>
                  <div class="cd-stat-item">
                    <span class="cd-stat-label">角色模板数</span>
                    <span class="cd-stat-value">{{ persons.length }}</span>
                  </div>
                  <div class="cd-stat-item">
                    <span class="cd-stat-label">创建时间</span>
                    <span class="cd-stat-value">{{ formatDate(caseData.created_at) }}</span>
                  </div>
                </div>
              </div>
            </div>

            <!-- 角色快览 -->
            <div v-if="persons.length" class="cd-card">
              <div class="cd-card__header">
                <span class="cd-card__icon">🏷</span>
                <span class="cd-card__title">角色快览</span>
              </div>
              <div class="cd-card__body">
                <div class="cd-role-pills">
                  <span
                    v-for="(person, idx) in persons"
                    :key="idx"
                    class="cd-role-pill"
                  >{{ person.name }}</span>
                </div>
              </div>
            </div>

          </aside>
        </div>

      </template>
    </div>
  </div>
</template>

<style scoped>
.cd-page {
  min-height: 100vh;
  background: #f8fafc;
  display: flex;
  flex-direction: column;
}

/* ── 顶部导航栏 ─────────────────────────────────── */
.cd-topbar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 0 24px;
  height: 56px;
  background: #fff;
  border-bottom: 1px solid #f1f5f9;
  position: sticky;
  top: 0;
  z-index: 10;
}

.cd-back-btn {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 6px 10px;
  border-radius: 8px;
  border: none;
  background: transparent;
  color: #64748b;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.14s;
  white-space: nowrap;
}

.cd-back-btn:hover {
  background: #f1f5f9;
  color: #1e293b;
}

.cd-topbar__center {
  flex: 1;
  text-align: center;
}

.cd-topbar__title {
  font-size: 15px;
  font-weight: 700;
  color: #0f172a;
}

.cd-topbar__actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

/* ── 内容区 ─────────────────────────────────────── */
.cd-content {
  flex: 1;
  padding: 24px;
  max-width: 1200px;
  margin: 0 auto;
  width: 100%;
  box-sizing: border-box;
}

.cd-loading,
.cd-error {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
  padding: 80px 20px;
  color: #94a3b8;
}

/* ── 案件头部 ───────────────────────────────────── */
.cd-hero {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 14px;
  padding: 20px 24px;
  margin-bottom: 20px;
}

.cd-hero__title {
  font-size: 22px;
  font-weight: 800;
  color: #0f172a;
  margin-bottom: 10px;
}

.cd-hero__meta {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.cd-meta-item {
  font-size: 13px;
  color: #64748b;
}

.cd-meta-sep {
  color: #d1d5db;
  font-size: 12px;
}

/* ── 主体两栏 ───────────────────────────────────── */
.cd-body {
  display: grid;
  grid-template-columns: 1fr 280px;
  gap: 20px;
  align-items: start;
}

@media (max-width: 900px) {
  .cd-body {
    grid-template-columns: 1fr;
  }
}

.cd-main {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.cd-aside {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* ── 卡片 ───────────────────────────────────────── */
.cd-card {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  overflow: hidden;
}

.cd-card__header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  border-bottom: 1px solid #f1f5f9;
  background: #f8fafc;
}

.cd-card__icon {
  font-size: 16px;
  line-height: 1;
}

.cd-card__title {
  font-size: 13px;
  font-weight: 700;
  color: #1e293b;
}

.cd-card__count {
  margin-left: auto;
  font-size: 11px;
  color: #94a3b8;
  background: #e2e8f0;
  border-radius: 999px;
  padding: 2px 8px;
  font-weight: 600;
}

.cd-card__body {
  padding: 16px;
}

.cd-text {
  font-size: 14px;
  line-height: 1.8;
  color: #334155;
}

.cd-empty {
  padding: 24px 16px;
  text-align: center;
  font-size: 13px;
  color: #94a3b8;
}

/* ── 角色列表 ───────────────────────────────────── */
.cd-person-list {
  display: flex;
  flex-direction: column;
  divide-y: 1px solid #f1f5f9;
}

.cd-person-item {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 14px 16px;
  border-bottom: 1px solid #f8fafc;
}

.cd-person-item:last-child {
  border-bottom: none;
}

.cd-person-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: linear-gradient(135deg, #1d3557, #3b82f6);
  color: #fff;
  font-size: 14px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.cd-person-info {
  flex: 1;
  min-width: 0;
}

.cd-person-name {
  font-size: 14px;
  font-weight: 700;
  color: #0f172a;
}

.cd-person-meta {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 2px;
  font-size: 12px;
  color: #64748b;
}

.cd-person-archetype {
  background: #f1f5f9;
  border-radius: 4px;
  padding: 1px 6px;
  font-size: 11px;
  color: #475569;
}

.cd-person-goal {
  margin-top: 4px;
  font-size: 12px;
  color: #94a3b8;
  line-height: 1.5;
}

.cd-person-status {
  flex-shrink: 0;
}

.cd-status-tag {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 600;
  background: #f0fdf4;
  color: #15803d;
  border: 1px solid #bbf7d0;
}

/* ── 场景列表 ───────────────────────────────────── */
.cd-scene-list {
  display: flex;
  flex-direction: column;
}

.cd-scene-item {
  display: flex;
  gap: 14px;
  padding: 14px 16px;
  border-bottom: 1px solid #f8fafc;
}

.cd-scene-item:last-child {
  border-bottom: none;
}

.cd-scene-index {
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 52px;
  height: 28px;
  border-radius: 8px;
  background: #f1f5f9;
  font-size: 11px;
  font-weight: 700;
  color: #475569;
  margin-top: 2px;
}

.cd-scene-info {
  flex: 1;
  min-width: 0;
}

.cd-scene-name {
  font-size: 14px;
  font-weight: 700;
  color: #0f172a;
}

.cd-scene-desc {
  margin-top: 4px;
  font-size: 12px;
  color: #64748b;
  line-height: 1.6;
}

.cd-scene-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 6px;
}

.cd-scene-brief {
  font-size: 12px;
  color: #94a3b8;
}

/* ── 右侧统计 ───────────────────────────────────── */
.cd-stat-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.cd-stat-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.cd-stat-label {
  font-size: 12px;
  color: #94a3b8;
  font-weight: 600;
}

.cd-stat-value {
  font-size: 13px;
  font-weight: 700;
  color: #1e293b;
  text-align: right;
}

/* ── 角色 pills ─────────────────────────────────── */
.cd-role-pills {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.cd-role-pill {
  display: inline-flex;
  align-items: center;
  padding: 4px 10px;
  border-radius: 999px;
  background: #eff6ff;
  border: 1px solid #bfdbfe;
  color: #1d4ed8;
  font-size: 12px;
  font-weight: 600;
}
</style>
