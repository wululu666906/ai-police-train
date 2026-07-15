<template>
  <div class="student-page student-page--video-hall">
    <section class="video-center-hero">
      <div class="video-center-hero__actions">
        <el-input
          v-model="keyword"
          class="search-input"
          placeholder="搜索视频名称、场景、关键词"
          clearable
          :prefix-icon="Search"
          @input="onFilterChanged"
          @clear="onFilterChanged"
        />
        <el-button plain class="history-btn" @click="router.push('/student/video-history')">实训历史</el-button>
      </div>
    </section>

    <section class="content-card">
      <div class="content-card__toolbar">
        <el-tabs v-model="activeTab" class="video-tabs" @tab-change="onFilterChanged">
          <el-tab-pane
            v-for="tab in tabs"
            :key="tab.value"
            :name="tab.value"
          >
            <template #label>{{ tab.label }}</template>
          </el-tab-pane>
        </el-tabs>

        <div class="filter-row">
          <el-select v-model="sortBy" class="filter-select filter-select--sort" placeholder="排序方式" @change="onFilterChanged">
            <el-option label="默认排序" value="default" />
            <el-option label="最新上传" value="latest" />
            <el-option label="时长优先" value="duration" />
            <el-option label="节点最多" value="nodes" />
          </el-select>
        </div>
      </div>

      <div v-if="loading" class="state-panel">
        <el-skeleton :rows="6" animated />
      </div>

      <div v-else-if="!pagedVideos.length" class="state-panel">
        <el-empty :description="keyword ? '未找到匹配的视频内容' : '当前暂无可展示的视频内容'" />
      </div>

      <div v-else class="video-grid">
        <article
          v-for="video in pagedVideos"
          :key="video.id"
          class="video-card"
        >
          <div class="video-card__cover" @click="openVideo(video)">
            <img v-if="coverFor(video)" :src="coverFor(video)" :alt="video.title" class="video-card__image" />
            <div v-else class="video-card__placeholder">
              <el-icon :size="36"><VideoPlay /></el-icon>
            </div>

            <span class="video-card__type" :class="`video-card__type--${video.video_type}`">
              {{ video.video_type === 'interactive' ? '交互实训' : '教学素材' }}
            </span>
            <span v-if="video.video_type === 'teaching' && video.teaching_unlocked === false" class="video-card__lock">
              训练后解锁
            </span>
            <span v-if="video.duration" class="video-card__duration">{{ formatDuration(video.duration) }}</span>
          </div>

          <div class="video-card__body">
            <div class="video-card__title">{{ video.title }}</div>
            <div class="video-card__meta">
              <span>{{ nodeText(video) }}</span>
              <span>{{ difficultyLabel(difficultyFor(video)) }}</span>
            </div>

            <div class="video-card__progress">
              <template v-if="sessionForVideo(video)?.status === 'active'">
                <div class="video-card__progress-text video-card__progress-text--active">
                  已进行到 {{ progressFraction(video) }} 节点
                </div>
                <div class="video-card__progress-bar">
                  <span :style="{ width: `${progressPercent(video)}%` }" />
                </div>
              </template>
              <template v-else-if="sessionForVideo(video)">
                <div class="video-card__progress-text video-card__progress-text--done">已完成</div>
                <div class="video-card__progress-bar">
                  <span style="width: 100%" />
                </div>
              </template>
              <template v-else>
                <div class="video-card__progress-text">
                  {{ video.video_type === 'interactive' ? '未开始实训' : (video.teaching_unlocked === false ? '需先完成关联实训' : '未开始学习') }}
                </div>
                <div class="video-card__progress-bar">
                  <span style="width: 0%" />
                </div>
              </template>
            </div>

            <div class="video-card__actions">
              <template v-if="video.video_type === 'interactive'">
                <el-button type="primary" class="video-card__btn video-card__btn--primary" @click="openVideo(video)">
                  {{ sessionForVideo(video)?.status === 'active' ? '继续训练' : '进入训练' }}
                </el-button>
              </template>
              <template v-else>
                <el-button
                  :type="video.teaching_unlocked === false ? undefined : 'primary'"
                  class="video-card__btn"
                  :disabled="video.teaching_unlocked === false"
                  @click="openVideo(video)"
                >
                  {{ sessionForVideo(video) ? '查看回放' : '开始学习' }}
                </el-button>
                <el-button class="video-card__btn" @click="openVideo(video)">
                  {{ sessionForVideo(video) ? '查看报告' : '查看详情' }}
                </el-button>
              </template>
            </div>
          </div>
        </article>
      </div>

      <div v-if="filteredVideos.length" class="pagination-row">
        <span class="pagination-row__total">共 {{ filteredVideos.length }} 条</span>
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          background
          layout="prev, pager, next, sizes"
          :page-sizes="[8, 12, 16]"
          :total="filteredVideos.length"
        />
      </div>
    </section>

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
            :src="playerVideoUrl"
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

    <van-popup
      v-model:show="showTrainingEntry"
      round
      class="training-entry-popup"
      :close-on-click-overlay="false"
      :overlay-style="{ backgroundColor: 'rgba(5,10,20,0.75)', backdropFilter: 'blur(6px)' }"
      teleport="body"
    >
      <div v-if="playerVideo" class="entry-dialog entry-dialog--dark">
        <div class="entry-dialog__header">
          <div class="entry-dialog__steps">
            <span class="entry-step" :class="{ 'entry-step--active': entryStep === 1, 'entry-step--done': entryStep > 1 }">1</span>
            <span class="entry-step-line" :class="{ 'entry-step-line--done': entryStep > 1 }"></span>
            <span class="entry-step" :class="{ 'entry-step--active': entryStep === 2 }">2</span>
          </div>
          <van-icon name="cross" class="entry-dialog__close" @click="showTrainingEntry = false; entryStep = 1" />
        </div>

        <!-- Step 1: Training Details -->
        <div v-if="entryStep === 1" class="entry-dialog__body entry-dialog__body--split">
          <div class="entry-left">
            <div class="entry-cover entry-cover--compact">
              <img v-if="coverFor(playerVideo)" :src="coverFor(playerVideo)" class="entry-cover__img" />
              <div v-else class="entry-cover__placeholder">
                <el-icon :size="40" color="rgba(255,255,255,0.2)"><VideoPlay /></el-icon>
              </div>
              <span class="entry-cover__badge">交互实训</span>
            </div>
            <div class="entry-stats entry-stats--vertical">
              <div class="entry-stat-card">
                <span class="entry-stat-card__num">{{ playerVideo.node_count || 0 }}</span>
                <span class="entry-stat-card__label">训练节点</span>
              </div>
              <div class="entry-stat-card">
                <span class="entry-stat-card__num">{{ playerVideo.duration ? formatDuration(playerVideo.duration) : '--' }}</span>
                <span class="entry-stat-card__label">视频时长</span>
              </div>
              <div class="entry-stat-card">
                <span class="entry-stat-card__num">{{ playerVideo.node_count ? playerVideo.node_count * 10 : 100 }}</span>
                <span class="entry-stat-card__label">满分</span>
              </div>
            </div>
          </div>

          <div class="entry-right">
            <h3 class="entry-info__title">{{ playerVideo.title }}</h3>
            <p class="entry-info__desc">{{ playerVideo.description || '本视频为第一视角交互式训练，系统将在关键节点自动暂停并检测你的动作与话术。' }}</p>

            <div v-if="playerVideo.briefing_objectives?.length || playerVideo.description" class="entry-section entry-section--compact">
              <div class="entry-section__title">📌 训练目标</div>
              <ul class="entry-objectives">
                <li v-for="(obj, i) in (playerVideo.briefing_objectives || ['掌握本场景规范执法流程', '练习标准话术和规范动作', '培养现场处置综合能力'])" :key="i">{{ obj }}</li>
              </ul>
            </div>

            <div v-if="(playerVideo.tags || []).length" class="entry-section entry-section--compact">
              <div class="entry-section__title">🏷 考察要点</div>
              <div class="entry-tags">
                <el-tag v-for="tag in playerVideo.tags" :key="tag" size="small" effect="dark" type="info">{{ tag }}</el-tag>
              </div>
            </div>

            <div class="entry-section entry-section--compact">
              <div class="entry-section__title">📋 设备要求</div>
              <p class="entry-section__text">需要开启摄像头和麦克风，建议 Chrome 浏览器。</p>
            </div>

            <div v-if="sessionForVideo(playerVideo)" class="entry-section entry-section--compact">
              <div class="entry-section__title">📊 我的记录</div>
              <p class="entry-section__text">
                上次状态：{{ sessionForVideo(playerVideo)?.status === 'active' ? '训练中（未完成）' : '已完成' }}
              </p>
            </div>

            <div class="entry-actions">
              <el-button @click="showTrainingEntry = false; entryStep = 1">取消</el-button>
              <el-button type="primary" @click="entryStep = 2">下一步 — 准备开始</el-button>
            </div>
          </div>
        </div>

        <!-- Step 2: Confirm & Mode Selection -->
        <div v-if="entryStep === 2" class="entry-dialog__body">
          <div class="entry-info">
            <h3 class="entry-info__title">准备开始训练</h3>
            <p class="entry-info__desc">请确认设备状态，选择训练模式后开始。</p>

            <div class="entry-section">
              <div class="entry-section__title">📷 设备检测</div>
              <div class="entry-device-list">
                <div class="entry-device">
                  <span class="entry-device__label">摄像头</span>
                  <span class="entry-device__status entry-device__status--pending">进入后自动检测</span>
                </div>
                <div class="entry-device">
                  <span class="entry-device__label">麦克风</span>
                  <span class="entry-device__status entry-device__status--pending">进入后自动检测</span>
                </div>
                <div class="entry-device">
                  <span class="entry-device__label">人脸识别</span>
                  <span class="entry-device__status entry-device__status--pending">进入后自动校验</span>
                </div>
              </div>
              <p class="entry-device-hint">设备权限将在进入训练页面后由系统自动请求并检测。</p>
            </div>

            <div class="entry-section">
              <div class="entry-section__title">🎯 训练模式</div>
              <div class="entry-mode-select">
                <button
                  class="entry-mode-btn"
                  :class="{ 'entry-mode-btn--active': entryMode === 'practice' }"
                  @click="entryMode = 'practice'"
                >
                  <span class="entry-mode-btn__title">练习模式</span>
                  <span class="entry-mode-btn__desc">提供标准话术参考和操作提示，适合熟悉流程</span>
                </button>
                <button
                  class="entry-mode-btn entry-mode-btn--exam"
                  :class="{ 'entry-mode-btn--active': entryMode === 'exam' }"
                  @click="entryMode = 'exam'"
                >
                  <span class="entry-mode-btn__title">考核模式</span>
                  <span class="entry-mode-btn__desc">不提供提示，严格评分，计入正式记录</span>
                </button>
              </div>
            </div>

            <div class="entry-notices entry-notices--compact">
              <div class="notice-row notice-row--warn">
                <span class="notice-icon">!</span>
                视频播放期间<strong>禁止拖动进度条</strong>，违规将被记录
              </div>
              <div class="notice-row notice-row--info">
                <span class="notice-icon">i</span>
                节点超时触发扣分，请保持专注
              </div>
              <div class="notice-row notice-row--info">
                <span class="notice-icon">i</span>
                切换标签页、离开页面等行为将被系统记录
              </div>
            </div>

            <div class="entry-actions">
              <el-button @click="entryStep = 1">上一步</el-button>
              <el-button type="primary" @click="enterTraining(playerVideo)">
                <el-icon style="margin-right: 4px"><VideoPlay /></el-icon>
                已了解，开始训练
              </el-button>
            </div>
          </div>
        </div>
      </div>
    </van-popup>
  </div>
</template>

<script setup lang="ts">
import { computed, inject, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Document, MagicStick, Search, SetUp, Timer, VideoCamera, VideoPlay } from '@element-plus/icons-vue'
import request from '../utils/request'
import { useVideoCover } from '../composables/useVideoCover'

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
  teaching_unlocked?: boolean
  lock_reason?: string | null
  created_at?: string
}

interface SessionBrief {
  id: number
  video_id: number
  status: string
  current_node_index: number
  node_total: number
  total_score: number | null
  full_score: number | null
  grade?: string
}

type DifficultyValue = 'easy' | 'medium' | 'hard'

const router = useRouter()
const setMainScrollable = inject<(v: boolean) => void>('setMainScrollable')
const videoCacheBustToken = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`

const allVideos = ref<VideoItem[]>([])
const loading = ref(false)
const activeTab = ref('all')
const keyword = ref('')
const difficultyFilter = ref<'all' | DifficultyValue>('all')
const sceneFilter = ref('all')
const modeFilter = ref<'all' | 'interactive' | 'teaching' | 'resumable'>('all')
const sortBy = ref<'default' | 'latest' | 'duration' | 'nodes'>('default')
const currentPage = ref(1)
const pageSize = ref(8)

const showTeachingPlayer = ref(false)
const showTrainingEntry = ref(false)
const entryStep = ref(1)
const entryMode = ref<'practice' | 'exam'>('practice')
const playerVideo = ref<VideoItem | null>(null)
const recentSessionMap = ref<Record<number, SessionBrief>>({})
const { ensureVideoCover, ensureVideoCovers, getVideoCover } = useVideoCover()
const playerVideoUrl = computed(() => withCacheBust(playerVideo.value?.video_url, videoCacheBustToken))

const tabs = [
  { label: '全部视频', value: 'all' },
  { label: '教学素材', value: 'teaching' },
  { label: '交互实训', value: 'interactive' },
  { label: '可继续训练', value: 'resumable' },
]

onMounted(() => {
  setMainScrollable?.(true)
  fetchVideos()
  fetchHistorySummary()
})

onUnmounted(() => {
  setMainScrollable?.(false)
})

watch([activeTab, difficultyFilter, sceneFilter, modeFilter, sortBy, keyword], () => {
  currentPage.value = 1
})

const interactiveCount = computed(() => allVideos.value.filter(video => video.video_type === 'interactive').length)
const teachingCount = computed(() => allVideos.value.filter(video => video.video_type === 'teaching').length)
const resumableCount = computed(() =>
  Object.values(recentSessionMap.value).filter(item => item.status === 'active').length,
)

const availableScenes = computed(() => {
  const set = new Set<string>()
  allVideos.value.forEach(video => set.add(sceneFor(video)))
  return Array.from(set)
})

const filteredVideos = computed(() => {
  const kw = keyword.value.trim().toLowerCase()

  let list = allVideos.value.filter((video) => {
    if (activeTab.value === 'teaching' && video.video_type !== 'teaching') return false
    if (activeTab.value === 'interactive' && video.video_type !== 'interactive') return false
    if (activeTab.value === 'resumable' && sessionForVideo(video)?.status !== 'active') return false

    if (difficultyFilter.value !== 'all' && difficultyFor(video) !== difficultyFilter.value) return false
    if (sceneFilter.value !== 'all' && sceneFor(video) !== sceneFilter.value) return false
    if (modeFilter.value === 'interactive' && video.video_type !== 'interactive') return false
    if (modeFilter.value === 'teaching' && video.video_type !== 'teaching') return false
    if (modeFilter.value === 'resumable' && sessionForVideo(video)?.status !== 'active') return false

    if (!kw) return true

    return [
      video.title,
      video.description || '',
      ...(video.tags || []),
      sceneFor(video),
      difficultyLabel(difficultyFor(video)),
    ].join(' ').toLowerCase().includes(kw)
  })

  if (sortBy.value === 'latest') {
    list = [...list].sort((a, b) => String(b.created_at || '').localeCompare(String(a.created_at || '')))
  } else if (sortBy.value === 'duration') {
    list = [...list].sort((a, b) => Number(b.duration || 0) - Number(a.duration || 0))
  } else if (sortBy.value === 'nodes') {
    list = [...list].sort((a, b) => Number(b.node_count || 0) - Number(a.node_count || 0))
  }

  return list
})

const pagedVideos = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value
  return filteredVideos.value.slice(start, start + pageSize.value)
})

const statCards = computed(() => [
  {
    label: '全部视频',
    value: allVideos.value.length,
    desc: '全部可学视频',
    icon: VideoPlay,
    tone: 'blue',
  },
  {
    label: '教学素材',
    value: teachingCount.value,
    desc: '课前预习资源',
    icon: Document,
    tone: 'indigo',
  },
  {
    label: '交互实训',
    value: interactiveCount.value,
    desc: '实操训练考核',
    icon: MagicStick,
    tone: 'violet',
  },
  {
    label: '可继续训练',
    value: resumableCount.value,
    desc: '上次学习未完成',
    icon: SetUp,
    tone: 'orange',
  },
])

function onFilterChanged() {
  currentPage.value = 1
}

async function fetchVideos() {
  loading.value = true
  try {
    const res: any = await request.get('/videos/student/hall')
    allVideos.value = Array.isArray(res) ? res : []
    ensureVideoCovers(allVideos.value)
  } catch {
    allVideos.value = []
  } finally {
    loading.value = false
  }
}

async function fetchHistorySummary() {
  try {
    const res: any = await request.get('/video-training/history')
    const items = Array.isArray(res) ? res : []
    const map: Record<number, SessionBrief> = {}

    for (const item of items) {
      if (!item?.video_id || map[item.video_id]) continue
      map[item.video_id] = item
    }

    recentSessionMap.value = map
  } catch {
    recentSessionMap.value = {}
  }
}

function openVideo(video: VideoItem) {
  if (video.video_type === 'teaching' && video.teaching_unlocked === false) {
    ElMessage.info(video.lock_reason || '需先完成关联实训后解锁该教学素材')
    return
  }

  playerVideo.value = { ...video }
  void ensureVideoCover(playerVideo.value)

  if (video.video_type === 'teaching') {
    showTeachingPlayer.value = true
  } else {
    entryStep.value = 1
    entryMode.value = 'practice'
    showTrainingEntry.value = true
  }
}

function enterTraining(video: VideoItem) {
  showTrainingEntry.value = false
  entryStep.value = 1
  router.push(`/student/video-training/${video.id}?mode=${entryMode.value}`)
}

function sessionForVideo(video?: VideoItem | null) {
  if (!video) return null
  return recentSessionMap.value[video.id] || null
}

function coverFor(video?: VideoItem | null) {
  return getVideoCover(video)
}

function progressFraction(video: VideoItem) {
  const session = sessionForVideo(video)
  if (!session) return `0/${video.node_count || 0}`

  const current = Math.min(Number(session.current_node_index || 0), Number(session.node_total || video.node_count || 0))
  const total = Number(session.node_total || video.node_count || 0)
  return `${current}/${total}`
}

function progressPercent(video: VideoItem) {
  const session = sessionForVideo(video)
  const total = Number(session?.node_total || video.node_count || 0)
  if (!total) return 0
  return Math.min(100, Math.round((Number(session?.current_node_index || 0) / total) * 100))
}

function nodeText(video: VideoItem) {
  if (video.video_type === 'interactive') return `${video.node_count || 0} 个训练节点`
  return `${video.node_count || 0} 个片段`
}

function difficultyFor(video: VideoItem): DifficultyValue {
  const source = [video.title, video.description || '', ...(video.tags || [])].join(' ')
  if (/困难|高级|复杂/.test(source)) return 'hard'
  if (/中等|标准|进阶/.test(source)) return 'medium'
  return 'easy'
}

function difficultyLabel(value: DifficultyValue) {
  if (value === 'hard') return '困难难度'
  if (value === 'medium') return '中等难度'
  return '简单难度'
}

function sceneFor(video: VideoItem) {
  const source = [video.title, video.description || '', ...(video.tags || [])].join(' ')
  if (/盘查|询问/.test(source)) return '询问盘查'
  if (/法律|执法|法/.test(source)) return '法律知识'
  if (/队列|姿势|礼仪/.test(source)) return '队列礼仪'
  if (/现场|处置|环境/.test(source)) return '现场处置'
  return video.video_type === 'interactive' ? '交互实训' : '教学预习'
}

function formatDuration(seconds?: number) {
  if (!seconds) return ''
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`
}

function withCacheBust(url?: string, token = videoCacheBustToken) {
  if (!url) return ''
  const separator = url.includes('?') ? '&' : '?'
  return `${url}${separator}codex_no_cache=${encodeURIComponent(token)}`
}
</script>

<style scoped lang="scss">
.student-page--video-hall {
  display: flex;
  flex-direction: column;
  gap: 18px;
  padding: 18px 22px 22px;
  background: #f3f6fb;
  min-height: 100%;
}

.video-center-hero {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  padding: 6px 2px 0;
}

.video-center-hero__title h1 {
  margin: 0;
  font-size: 22px;
  font-weight: 800;
  color: #13213a;
}

.video-center-hero__title p {
  margin: 8px 0 0;
  font-size: 14px;
  color: #64748b;
}

.video-center-hero__actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.search-input {
  width: 360px;
}

.history-btn {
  height: 40px;
  border-radius: 10px;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
}

.stat-card {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 20px 22px;
  background: rgba(255, 255, 255, 0.86);
  border: 1px solid rgba(210, 222, 240, 0.9);
  border-radius: 8px;
  box-shadow: 0 12px 32px rgba(15, 23, 42, 0.06);
}

.stat-card__icon {
  width: 52px;
  height: 52px;
  border-radius: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 22px;
}

.stat-card__icon--blue {
  background: rgba(37, 99, 235, 0.1);
  color: #2563eb;
}

.stat-card__icon--indigo {
  background: rgba(59, 130, 246, 0.1);
  color: #3b82f6;
}

.stat-card__icon--violet {
  background: rgba(124, 58, 237, 0.12);
  color: #7c3aed;
}

.stat-card__icon--orange {
  background: rgba(249, 115, 22, 0.12);
  color: #f97316;
}

.stat-card__content {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.stat-card__label {
  font-size: 13px;
  color: #64748b;
}

.stat-card__value {
  font-size: 32px;
  line-height: 1;
  font-weight: 800;
  color: #0f172a;
}

.stat-card__desc {
  font-size: 13px;
  color: #94a3b8;
}

.content-card {
  background: rgba(255, 255, 255, 0.9);
  border-radius: 8px;
  border: 1px solid rgba(214, 223, 237, 0.95);
  box-shadow: 0 20px 50px rgba(15, 23, 42, 0.06);
  overflow: hidden;
}

.content-card__toolbar {
  padding: 14px 18px 0;
}

.video-tabs {
  :deep(.el-tabs__header) {
    margin-bottom: 0;
  }

  :deep(.el-tabs__nav-wrap::after) {
    background-color: rgba(226, 232, 240, 0.9);
  }

  :deep(.el-tabs__item) {
    height: 44px;
    font-size: 16px;
    font-weight: 700;
    color: #475569;
  }

  :deep(.el-tabs__item.is-active) {
    color: #2563eb;
  }

  :deep(.el-tabs__active-bar) {
    height: 3px;
    border-radius: 999px;
    background: #2563eb;
  }
}

.filter-row {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  padding: 14px 0 18px;
  flex-wrap: wrap;
}

.filter-select {
  width: 140px;
}

.filter-select--sort {
  width: 136px;
}

.state-panel {
  padding: 54px 24px;
}

.video-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 18px;
  padding: 0 18px 18px;
}

.video-card {
  overflow: hidden;
  border-radius: 8px;
  border: 1px solid #dce6f3;
  background: #fff;
  box-shadow: 0 12px 28px rgba(15, 23, 42, 0.05);
  transition: transform 0.18s ease, box-shadow 0.18s ease;
}

.video-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 18px 38px rgba(15, 23, 42, 0.1);
}

.video-card__cover {
  position: relative;
  aspect-ratio: 16 / 9;
  overflow: hidden;
  background: #0f172a;
  cursor: pointer;
}

.video-card__image {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.video-card__placeholder {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  color: rgba(255, 255, 255, 0.26);
  background: #0f172a;
}

.video-card__type,
.video-card__lock,
.video-card__duration {
  position: absolute;
  z-index: 1;
}

.video-card__type {
  top: 10px;
  left: 10px;
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 700;
  color: #fff;
}

.video-card__type--interactive {
  background: #2563eb;
}

.video-card__type--teaching {
  background: #16a34a;
}

.video-card__lock {
  top: 10px;
  right: 10px;
  padding: 4px 10px;
  border-radius: 999px;
  background: rgba(249, 115, 22, 0.92);
  color: #fff;
  font-size: 12px;
  font-weight: 700;
}

.video-card__duration {
  right: 10px;
  bottom: 10px;
  padding: 4px 8px;
  border-radius: 999px;
  background: rgba(2, 6, 23, 0.82);
  color: #fff;
  font-size: 12px;
  font-weight: 700;
}

.video-card__body {
  padding: 14px 14px 16px;
}

.video-card__title {
  font-size: 18px;
  line-height: 1.35;
  font-weight: 800;
  color: #0f172a;
  min-height: 48px;
}

.video-card__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 8px;
  font-size: 14px;
  color: #64748b;
}

.video-card__progress {
  margin-top: 14px;
}

.video-card__progress-text {
  font-size: 14px;
  color: #64748b;
  margin-bottom: 8px;
}

.video-card__progress-text--active,
.video-card__progress-text--done {
  color: #16a34a;
  font-weight: 700;
}

.video-card__progress-bar {
  height: 6px;
  border-radius: 999px;
  background: #e2e8f0;
  overflow: hidden;
}

.video-card__progress-bar span {
  display: block;
  height: 100%;
  border-radius: 999px;
  background: #2563eb;
}

.video-card__actions {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  margin-top: 16px;
}

.video-card__btn {
  width: 100%;
  height: 38px;
  border-radius: 10px;
}

.video-card__btn--primary {
  --el-button-bg-color: #2563eb;
  --el-button-border-color: #2563eb;
  --el-button-hover-bg-color: #1d4ed8;
  --el-button-hover-border-color: #1d4ed8;
}

.pagination-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 0 18px 18px;
}

.pagination-row__total {
  color: #64748b;
  font-size: 14px;
}

.teaching-popup {
  width: min(860px, calc(100vw - 24px));
  max-height: calc(100vh - 40px);
  overflow: auto;
  background: transparent;
}

.teaching-dialog {
  background: #fff;
  border-radius: 8px;
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

.training-entry-popup {
  width: min(780px, calc(100vw - 24px));
  max-height: calc(100vh - 40px);
  overflow: auto;
  background: transparent;
}

.entry-dialog {
  background: #ffffff;
  border-radius: 12px;
  border: 1px solid #e5e7eb;
  color: #1f2937;
  width: 100%;
  max-height: none;
  overflow-y: auto;

  &--dark {
    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.15);
  }

  &__header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 16px 20px 0;
  }

  &__steps {
    display: flex;
    align-items: center;
    gap: 0;
  }

  &__close {
    font-size: 20px;
    color: #9ca3af;
    cursor: pointer;
    &:hover { color: #374151; }
  }

  &__body {
    padding: 16px 24px 24px;

    &--split {
      display: flex;
      gap: 24px;
      align-items: flex-start;
    }
  }
}

.entry-step {
  width: 26px;
  height: 26px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 700;
  background: #f3f4f6;
  color: #9ca3af;
  border: 2px solid #e5e7eb;
  transition: all 0.3s;

  &--active {
    background: #2563eb;
    color: #fff;
    border-color: #2563eb;
    box-shadow: 0 0 10px rgba(37, 99, 235, 0.3);
  }

  &--done {
    background: #22c55e;
    color: #fff;
    border-color: #22c55e;
  }
}

.entry-step-line {
  width: 40px;
  height: 2px;
  background: #e5e7eb;
  transition: background 0.3s;

  &--done {
    background: #22c55e;
  }
}

.entry-cover {
  border-radius: 10px;
  overflow: hidden;
  background: #1e293b;
  aspect-ratio: 16 / 9;
  position: relative;

  &--compact {
    width: 100%;
    margin-bottom: 0;
  }

  &--wide {
    width: 100%;
    margin-bottom: 18px;
  }

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
    background: #f3f4f6;
  }

  &__badge {
    position: absolute;
    bottom: 10px;
    left: 10px;
    background: rgba(37, 99, 235, 0.92);
    color: #fff;
    font-size: 11px;
    font-weight: 600;
    padding: 3px 10px;
    border-radius: 4px;
  }
}

.entry-info {
  &__title {
    margin: 0 0 8px;
    font-size: 18px;
    font-weight: 700;
    color: #111827;
    line-height: 1.4;
  }

  &__desc {
    margin: 0 0 16px;
    font-size: 13px;
    color: #6b7280;
    line-height: 1.7;
  }
}

.entry-left {
  width: 220px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.entry-right {
  flex: 1;
  min-width: 0;
}

.entry-stats {
  display: flex;
  gap: 12px;
  margin-bottom: 18px;

  &--vertical {
    flex-direction: column;
    gap: 8px;
    margin-bottom: 0;
  }
}

.entry-stat-card {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  padding: 12px 8px;
  background: #f9fafb;
  border: 1px solid #e5e7eb;
  border-radius: 8px;

  &__num {
    font-size: 18px;
    font-weight: 800;
    color: #2563eb;
  }

  &__label {
    font-size: 11px;
    color: #6b7280;
  }
}

.entry-section {
  margin-bottom: 14px;

  &--compact {
    margin-bottom: 10px;
  }

  &__title {
    font-size: 13px;
    font-weight: 600;
    color: #374151;
    margin-bottom: 6px;
  }

  &__text {
    font-size: 13px;
    color: #6b7280;
    line-height: 1.6;
    margin: 0;
  }
}

.entry-objectives {
  margin: 0;
  padding: 0 0 0 18px;
  font-size: 13px;
  color: #4b5563;
  line-height: 1.8;
}

.entry-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.entry-device-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.entry-device {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  background: #f9fafb;
  border-radius: 6px;
  border: 1px solid #e5e7eb;

  &__label {
    font-size: 13px;
    color: #374151;
  }

  &__status {
    font-size: 12px;

    &--pending { color: #9ca3af; }
    &--pass { color: #16a34a; }
    &--fail { color: #dc2626; }
  }
}

.entry-device-hint {
  margin: 8px 0 0;
  font-size: 12px;
  color: #9ca3af;
}

.entry-mode-select {
  display: flex;
  gap: 12px;
}

.entry-mode-btn {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 14px;
  border-radius: 8px;
  border: 2px solid #e5e7eb;
  background: #ffffff;
  cursor: pointer;
  text-align: left;
  transition: all 0.2s;

  &:hover {
    border-color: rgba(37, 99, 235, 0.4);
    background: rgba(37, 99, 235, 0.02);
  }

  &--active {
    border-color: #2563eb !important;
    background: rgba(37, 99, 235, 0.04) !important;
    box-shadow: 0 0 12px rgba(37, 99, 235, 0.1);
  }

  &__title {
    font-size: 14px;
    font-weight: 600;
    color: #111827;
  }

  &__desc {
    font-size: 12px;
    color: #6b7280;
    line-height: 1.4;
  }
}

.entry-notices {
  margin-bottom: 16px;
  display: flex;
  flex-direction: column;
  gap: 6px;

  &--compact {
    margin-top: 4px;
  }
}

.notice-row {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  font-size: 12px;
  color: #6b7280;
  line-height: 1.5;

  strong { color: #374151; }
}

.notice-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  font-size: 10px;
  font-weight: 700;
  flex-shrink: 0;
  margin-top: 1px;

  .notice-row--warn & { background: #fef3c7; color: #d97706; }
  .notice-row--info & { background: #dbeafe; color: #2563eb; }
}

.entry-actions {
  display: flex;
  gap: 12px;
  align-items: center;
  margin-top: 20px;
  justify-content: flex-end;
}

@media (max-width: 1440px) {
  .video-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 1180px) {
  .stats-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .video-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .video-center-hero {
    flex-direction: column;
    align-items: flex-start;
  }

  .video-center-hero__actions {
    width: 100%;
    flex-wrap: wrap;
  }

  .search-input {
    width: 100%;
  }
}

@media (max-width: 768px) {
  .student-page--video-hall {
    padding: 14px;
  }

  .stats-grid,
  .video-grid {
    grid-template-columns: 1fr;
  }

  .filter-row,
  .pagination-row {
    flex-direction: column;
    align-items: stretch;
  }

  .filter-select,
  .filter-select--sort {
    width: 100%;
  }

  .video-card__actions {
    grid-template-columns: 1fr;
  }

  .entry-dialog__body {
    flex-direction: column;
  }

  .entry-cover {
    width: 100%;
  }
}
</style>
