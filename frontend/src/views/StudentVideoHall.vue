<template>
  <div class="student-page student-page--video-hall">

    <!-- 顶部工具栏，与 StudentHall 保持同款风格 -->
    <section class="card card--compact filter-card">
      <div class="toolbar">
        <div class="toolbar__left">
          <span class="toolbar__title">视频实训中心</span>
          <span class="toolbar__sub">教学预习视频 · 第一视角交互式实训</span>
        </div>
        <el-input
          v-model="keyword"
          placeholder="搜索视频标题"
          clearable
          size="small"
          :prefix-icon="Search"
          style="width: 200px"
          @input="onKeywordChange"
          @clear="onKeywordChange"
        />
      </div>
    </section>

    <!-- 分类标签 + 内容区 -->
    <section class="card tasks-panel">
      <div class="tasks-toolbar">
        <el-tabs v-model="activeTab" class="task-tabs">
          <el-tab-pane
            v-for="tab in tabs"
            :key="tab.value"
            :name="tab.value"
          >
            <template #label>
              {{ tab.label }}
              <span class="tab-count">{{ tabCount(tab.value) }}</span>
            </template>
          </el-tab-pane>
        </el-tabs>
      </div>

      <!-- 加载中 -->
      <div v-if="loading" class="state-panel">
        <el-skeleton :rows="4" animated />
      </div>

      <!-- 空状态 -->
      <div v-else-if="!filteredVideos.length" class="state-panel">
        <el-empty :description="keyword ? '未找到匹配的视频' : '暂无已发布的视频，请等待教师上传'" />
      </div>

      <!-- 视频网格 -->
      <div v-else class="video-grid">
        <div
          v-for="video in filteredVideos"
          :key="video.id"
          class="vcard"
          @click="openVideo(video)"
        >
          <!-- 封面 -->
          <div class="vcard__cover">
            <img v-if="video.thumbnail_url" :src="video.thumbnail_url" :alt="video.title" class="cover-img" />
            <div v-else class="cover-placeholder">
              <el-icon :size="36" color="rgba(255,255,255,0.2)"><VideoPlay /></el-icon>
            </div>
            <!-- 类型角标 -->
            <span class="vcard__badge" :class="`vcard__badge--${video.video_type}`">
              {{ video.video_type === 'interactive' ? '交互实训' : '教学素材' }}
            </span>
            <!-- 时长 -->
            <span v-if="video.duration" class="vcard__duration">{{ formatDuration(video.duration) }}</span>
            <!-- 悬停遮罩 -->
            <div class="vcard__overlay">
              <el-icon :size="28"><VideoPlay /></el-icon>
              <span>{{ video.video_type === 'interactive' ? '进入实训' : '播放视频' }}</span>
            </div>
          </div>

          <!-- 信息区 -->
          <div class="vcard__body">
            <div class="vcard__title" :title="video.title">{{ video.title }}</div>
            <div v-if="video.description" class="vcard__desc">{{ video.description }}</div>
            <div class="vcard__meta">
              <span v-if="video.node_count" class="meta-badge meta-badge--node">
                <el-icon :size="10"><SetUp /></el-icon>
                {{ video.node_count }} 个节点
              </span>
              <span v-for="tag in (video.tags || []).slice(0, 2)" :key="tag" class="meta-badge">{{ tag }}</span>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- ── 教学视频播放弹窗 ── -->
    <van-popup
      v-model:show="showTeachingPlayer"
      round
      class="teaching-popup"
      :overlay-style="{ backgroundColor: 'rgba(15,23,42,0.5)', backdropFilter: 'blur(4px)' }"
      teleport="body"
    >
      <div v-if="playerVideo" class="teaching-dialog">
        <div class="teaching-dialog__header">
          <div class="teaching-dialog__title">{{ playerVideo.title }}</div>
          <van-icon name="cross" class="teaching-dialog__close" @click="showTeachingPlayer = false" />
        </div>
        <div class="teaching-dialog__player">
          <video
            controls
            class="video-player"
            :src="playerVideo.video_url"
            preload="metadata"
            controlslist="nodownload"
          >
            您的浏览器不支持视频播放
          </video>
        </div>
        <div v-if="playerVideo.description" class="teaching-dialog__desc">{{ playerVideo.description }}</div>
        <div v-if="(playerVideo.tags || []).length" class="teaching-dialog__tags">
          <el-tag v-for="tag in playerVideo.tags" :key="tag" size="small" effect="plain">{{ tag }}</el-tag>
        </div>
      </div>
    </van-popup>

    <!-- ── 交互式实训入口弹窗 ── -->
    <van-popup
      v-model:show="showTrainingEntry"
      round
      class="training-entry-popup"
      :overlay-style="{ backgroundColor: 'rgba(15,23,42,0.5)', backdropFilter: 'blur(4px)' }"
      teleport="body"
    >
      <div v-if="playerVideo" class="entry-dialog">
        <div class="entry-dialog__header">
          <van-icon name="cross" class="entry-dialog__close" @click="showTrainingEntry = false" />
        </div>
        <div class="entry-dialog__body">
          <!-- 左侧封面 -->
          <div class="entry-cover">
            <img v-if="playerVideo.thumbnail_url" :src="playerVideo.thumbnail_url" class="entry-cover__img" />
            <div v-else class="entry-cover__placeholder">
              <el-icon :size="56" color="rgba(255,255,255,0.2)"><VideoPlay /></el-icon>
            </div>
            <span class="entry-cover__badge">交互式实训</span>
          </div>

          <!-- 右侧信息 -->
          <div class="entry-info">
            <h3 class="entry-info__title">{{ playerVideo.title }}</h3>
            <p class="entry-info__desc">{{ playerVideo.description || '本视频为第一视角交互式训练，系统将在关键节点自动暂停并检测您的动作与话术。' }}</p>

            <!-- 统计 -->
            <div class="entry-stats">
              <div class="entry-stat">
                <el-icon color="#0066ff"><SetUp /></el-icon>
                <span>{{ playerVideo.node_count }} 个训练节点</span>
              </div>
              <div v-if="playerVideo.duration" class="entry-stat">
                <el-icon color="#0066ff"><Timer /></el-icon>
                <span>视频时长 {{ formatDuration(playerVideo.duration) }}</span>
              </div>
              <div class="entry-stat">
                <el-icon color="#0066ff"><VideoCamera /></el-icon>
                <span>需开启摄像头</span>
              </div>
            </div>

            <!-- 注意事项 -->
            <div class="entry-notices">
              <div class="notice-row notice-row--warn">
                <span class="notice-icon">!</span>
                视频播放期间<strong>禁止拖动进度条</strong>
              </div>
              <div class="notice-row notice-row--info">
                <span class="notice-icon">i</span>
                节点超时将触发扣分，请保持专注
              </div>
              <div class="notice-row notice-row--info">
                <span class="notice-icon">i</span>
                训练完成后解锁完整教学视频回放
              </div>
            </div>

            <!-- 标签 -->
            <div v-if="(playerVideo.tags || []).length" class="entry-tags">
              <el-tag v-for="tag in playerVideo.tags" :key="tag" size="small" effect="plain">{{ tag }}</el-tag>
            </div>

            <!-- 操作按钮 -->
            <div class="entry-actions">
              <el-button @click="showTrainingEntry = false">暂不进入</el-button>
              <el-button type="primary" @click="enterTraining(playerVideo)">
                <el-icon style="margin-right:4px"><VideoPlay /></el-icon>
                开始实训
              </el-button>
            </div>
          </div>
        </div>
      </div>
    </van-popup>

  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, inject } from 'vue'
import { useRouter } from 'vue-router'
import { Search, VideoPlay, SetUp, Timer, VideoCamera } from '@element-plus/icons-vue'
import request from '../utils/request'

interface VideoItem {
  id: number
  title: string
  description?: string
  video_type: 'teaching' | 'interactive'
  video_url?: string
  thumbnail_url?: string
  duration?: number
  tags: string[]
  status: string
  node_count: number
}

const router = useRouter()
const setMainScrollable = inject<(v: boolean) => void>('setMainScrollable')

const allVideos = ref<VideoItem[]>([])
const loading = ref(false)
const activeTab = ref('')
const keyword = ref('')
let kwTimer: ReturnType<typeof setTimeout> | null = null

const showTeachingPlayer = ref(false)
const showTrainingEntry = ref(false)
const playerVideo = ref<VideoItem | null>(null)

const tabs = [
  { label: '全部视频', value: '' },
  { label: '教学素材', value: 'teaching' },
  { label: '交互实训', value: 'interactive' },
]

onMounted(() => {
  setMainScrollable?.(true)
  fetchVideos()
})

onUnmounted(() => {
  setMainScrollable?.(false)
})

const filteredVideos = computed(() => {
  let list = allVideos.value
  if (activeTab.value) list = list.filter(v => v.video_type === activeTab.value)
  if (keyword.value.trim()) {
    const kw = keyword.value.trim().toLowerCase()
    list = list.filter(v =>
      v.title.toLowerCase().includes(kw) ||
      (v.description || '').toLowerCase().includes(kw)
    )
  }
  return list
})

function tabCount(tabValue: string): number {
  if (!tabValue) return allVideos.value.length
  return allVideos.value.filter(v => v.video_type === tabValue).length
}

function onKeywordChange() {
  if (kwTimer) clearTimeout(kwTimer)
  kwTimer = setTimeout(() => {}, 300)
}

async function fetchVideos() {
  loading.value = true
  try {
    const res: any = await request.get('/videos/student/hall')
    allVideos.value = Array.isArray(res) ? res : []
  } catch {
    allVideos.value = []
  } finally {
    loading.value = false
  }
}

function openVideo(video: VideoItem) {
  playerVideo.value = { ...video }   // 浅拷贝，确保 title 等字符串字段正确传递
  if (video.video_type === 'teaching') {
    showTeachingPlayer.value = true
  } else {
    showTrainingEntry.value = true
  }
}

function enterTraining(video: VideoItem) {
  showTrainingEntry.value = false
  router.push(`/student/video-training/${video.id}`)
}

function formatDuration(seconds?: number): string {
  if (!seconds) return ''
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return `${m}:${String(s).padStart(2, '0')}`
}
</script>

<style scoped lang="scss">
.student-page--video-hall {
  display: flex;
  flex-direction: column;
  gap: 12px;
  /* background 和 min-height 由全局 .student-page 提供，不需要重复声明 */
}

/* 复用 StudentHall 的 card 结构 */
.card {
  background: #fff;
  border-radius: 10px;
  border: 1px solid #e5e7eb;
  overflow: hidden;

  &--compact { padding: 12px 16px; }
}

.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;

  &__left {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  &__title {
    font-size: 15px;
    font-weight: 700;
    color: #111827;
  }

  &__sub {
    font-size: 12px;
    color: #9ca3af;
  }
}

.tasks-panel { padding: 0; }

.tasks-toolbar {
  padding: 0 14px;
  border-bottom: 1px solid #f3f4f6;
}

.task-tabs {
  :deep(.el-tabs__header) { margin-bottom: 0; }
  :deep(.el-tabs__nav-wrap::after) { display: none; }
  :deep(.el-tabs__item) {
    height: 40px;
    font-size: 13px;
    padding: 0 12px;
  }
  :deep(.el-tabs__item.is-active) {
    color: var(--student-accent, #0066ff);
    font-weight: 600;
  }
  :deep(.el-tabs__active-bar) {
    background: var(--student-accent, #0066ff);
  }
}

.tab-count {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 18px;
  height: 16px;
  padding: 0 4px;
  margin-left: 4px;
  border-radius: 8px;
  background: #f3f4f6;
  font-size: 11px;
  color: #6b7280;
  font-weight: 600;
  vertical-align: middle;

  .is-active & {
    background: rgba(0, 102, 255, 0.1);
    color: var(--student-accent, #0066ff);
  }
}

.state-panel {
  padding: 40px 16px;
  text-align: center;
}

/* 视频网格 */
.video-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  padding: 14px;
}

@media (max-width: 1200px) {
  .video-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}

@media (max-width: 720px) {
  .video-grid { grid-template-columns: 1fr; }
}

.vcard {
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #fff;
  overflow: hidden;
  cursor: pointer;
  transition: box-shadow 0.2s, transform 0.15s;

  &:hover {
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.1);
    transform: translateY(-2px);
    .vcard__overlay { opacity: 1; }
  }

  &__cover {
    position: relative;
    padding-top: 56.25%;
    background: #0f172a;
    overflow: hidden;
  }

  &__body {
    padding: 10px 12px;
  }

  &__title {
    font-size: 13px;
    font-weight: 600;
    color: #111827;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    margin-bottom: 4px;
  }

  &__desc {
    font-size: 12px;
    color: #9ca3af;
    display: -webkit-box;
    -webkit-box-orient: vertical;
    -webkit-line-clamp: 2;
    overflow: hidden;
    margin-bottom: 6px;
    line-height: 1.5;
  }

  &__meta {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
  }

  &__badge {
    position: absolute;
    top: 7px;
    left: 7px;
    padding: 2px 7px;
    border-radius: 4px;
    font-size: 11px;
    font-weight: 600;

    &--teaching { background: rgba(16,185,129,0.88); color: #fff; }
    &--interactive { background: rgba(239,68,68,0.9); color: #fff; }
  }

  &__duration {
    position: absolute;
    bottom: 5px;
    right: 7px;
    font-size: 11px;
    color: #fff;
    background: rgba(0,0,0,0.55);
    padding: 1px 5px;
    border-radius: 3px;
    font-weight: 600;
  }

  &__overlay {
    position: absolute;
    inset: 0;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 6px;
    background: rgba(0,0,0,0.42);
    opacity: 0;
    transition: opacity 0.2s;
    color: #fff;
    font-size: 12px;
    font-weight: 600;
  }
}

.cover-img {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.cover-placeholder {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #1e293b, #0f172a);
}

.meta-badge {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  padding: 2px 7px;
  border-radius: 8px;
  font-size: 11px;
  background: #f3f4f6;
  color: #6b7280;

  &--node {
    background: #eff6ff;
    color: #3b82f6;
  }
}

/* ── 教学视频播放弹窗 ── */
.teaching-popup {
  width: min(860px, calc(100vw - 24px));
  max-height: calc(100vh - 40px);
  overflow: auto;
  background: transparent;
}

.teaching-dialog {
  background: #fff;
  border-radius: 12px;
  border: 1px solid #e5e7eb;
  overflow: hidden;

  &__header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 14px 18px;
    border-bottom: 1px solid #f3f4f6;
  }

  &__title {
    font-size: 15px;
    font-weight: 700;
    color: #111827;
    flex: 1;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  &__close {
    font-size: 20px;
    color: #9ca3af;
    cursor: pointer;
    flex-shrink: 0;
    margin-left: 12px;
  }

  &__player {
    background: #000;
    line-height: 0;
  }

  &__desc {
    padding: 12px 18px;
    font-size: 13px;
    color: #6b7280;
    line-height: 1.7;
    border-top: 1px solid #f3f4f6;
  }

  &__tags {
    padding: 0 18px 14px;
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
  }
}

.video-player {
  width: 100%;
  max-height: 500px;
  display: block;
  background: #000;
}

/* ── 实训入口弹窗 ── */
.training-entry-popup {
  width: min(780px, calc(100vw - 24px));
  max-height: calc(100vh - 40px);
  overflow: auto;
  background: transparent;
}

.entry-dialog {
  background: #fff;
  border-radius: 12px;
  border: 1px solid #e5e7eb;

  &__header {
    display: flex;
    justify-content: flex-end;
    padding: 10px 14px 0;
  }

  &__close {
    font-size: 20px;
    color: #9ca3af;
    cursor: pointer;
  }

  &__body {
    display: flex;
    gap: 20px;
    padding: 4px 20px 24px;
    align-items: flex-start;

    @media (max-width: 560px) {
      flex-direction: column;
    }
  }
}

.entry-cover {
  width: 240px;
  flex-shrink: 0;
  border-radius: 8px;
  overflow: hidden;
  background: #0f172a;
  aspect-ratio: 16/9;
  position: relative;

  @media (max-width: 560px) { width: 100%; }

  &__img {
    width: 100%;
    height: 100%;
    object-fit: cover;
    display: block;
  }

  &__placeholder {
    width: 100%;
    height: 100%;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  &__badge {
    position: absolute;
    bottom: 7px;
    left: 7px;
    background: rgba(239,68,68,0.9);
    color: #fff;
    font-size: 11px;
    font-weight: 600;
    padding: 2px 8px;
    border-radius: 4px;
  }
}

.entry-info {
  flex: 1;
  min-width: 0;

  &__title {
    margin: 0 0 8px;
    font-size: 17px;
    font-weight: 700;
    color: #111827;
    line-height: 1.4;
  }

  &__desc {
    margin: 0 0 14px;
    font-size: 13px;
    color: #6b7280;
    line-height: 1.7;
  }
}

.entry-stats {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 14px;
}

.entry-stat {
  display: flex;
  align-items: center;
  gap: 7px;
  font-size: 13px;
  color: #374151;
}

.entry-notices {
  margin-bottom: 14px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.notice-row {
  display: flex;
  align-items: flex-start;
  gap: 7px;
  font-size: 12px;
  color: #4b5563;
  line-height: 1.5;
}

.notice-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 15px;
  height: 15px;
  border-radius: 50%;
  font-size: 10px;
  font-weight: 700;
  flex-shrink: 0;
  margin-top: 1px;

  .notice-row--warn & { background: #fef3c7; color: #d97706; }
  .notice-row--info & { background: #dbeafe; color: #2563eb; }
}

.entry-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
  margin-bottom: 18px;
}

.entry-actions {
  display: flex;
  gap: 10px;
  align-items: center;
}
</style>
