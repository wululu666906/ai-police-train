<template>
  <div class="video-library">
    <!-- 顶部：标题 + 搜索 -->
    <header class="library-header">
      <div class="library-header__left">
        <h2 class="library-header__title">视频实训管理</h2>
        <span class="library-header__count">共 {{ total }} 个</span>
      </div>
      <div class="library-header__right">
        <el-input
          v-model="keyword"
          clearable
          class="header-search"
          placeholder="搜索视频"
          :prefix-icon="Search"
          @input="onKeywordChange"
          @clear="onFilterChange"
        />
      </div>
    </header>

    <!-- 拖拽上传区域（支持批量） -->
    <div
      class="drop-zone"
      :class="{ 'drop-zone--active': isDragging }"
      @dragover.prevent="isDragging = true"
      @dragleave.prevent="isDragging = false"
      @drop.prevent="onBatchDrop"
      @click="triggerFileInput"
    >
      <el-icon :size="32" class="drop-zone__icon"><UploadFilled /></el-icon>
      <p class="drop-zone__text">拖入视频文件即可上传<br /><small>支持批量 · mp4 / webm / mov · 最大 2GB · AI 自动分析并发布</small></p>
      <input
        ref="fileInputRef"
        type="file"
        accept="video/mp4,video/webm,video/ogg,video/quicktime"
        multiple
        hidden
        @change="onFileInputChange"
      />
    </div>

    <!-- 上传/分析进度列表 -->
    <div v-if="uploadQueue.length" class="upload-queue">
      <div v-for="item in uploadQueue" :key="item.id" class="upload-queue__item">
        <div class="upload-queue__info">
          <span class="upload-queue__name">{{ item.filename }}</span>
          <span class="upload-queue__status" :class="`is-${item.status}`">
            {{ queueStatusLabel(item) }}
          </span>
        </div>
        <el-progress v-if="item.status === 'uploading'" :percentage="item.progress" :stroke-width="4" :show-text="false" />
        <div v-if="item.status === 'analyzing'" class="upload-queue__analyzing">
          <el-icon class="is-loading"><RefreshRight /></el-icon>
          <span>AI 分析中...</span>
        </div>
        <span v-if="item.status === 'failed'" class="upload-queue__error">{{ item.error }}</span>
      </div>
    </div>

    <!-- 视频列表 -->
    <section v-if="loading" class="state-panel">
      <el-skeleton :rows="4" animated />
    </section>

    <section v-else-if="!displayedVideos.length" class="state-panel">
      <el-empty description="暂无视频，拖入文件即可开始" />
    </section>

    <section v-else class="video-list">
      <article v-for="video in displayedVideos" :key="video.id" class="video-item">
        <div class="video-item__cover" @click="openDetail(video)">
          <img v-if="coverFor(video)" :src="coverFor(video)" :alt="video.title" />
          <div v-else class="cover-placeholder">
            <el-icon :size="28"><VideoPlay /></el-icon>
          </div>
          <span class="video-item__duration">{{ formatDuration(video.duration) }}</span>
        </div>

        <div class="video-item__body">
          <div class="video-item__title">{{ video.title }}</div>
          <div class="video-item__meta">
            <span v-if="video.scenario_type">{{ video.scenario_type }}</span>
            <span v-if="video.difficulty && video.difficulty !== 'normal'">{{ difficultyLabel(video.difficulty) }}</span>
            <span>{{ video.node_count || 0 }} 节点</span>
            <span>{{ formatDuration(video.duration) }}</span>
          </div>
          <div v-if="video.status === 'analyzing'" class="video-item__analyzing">
            <el-icon class="is-loading"><RefreshRight /></el-icon>
            <span>AI 分析中...</span>
          </div>
          <div v-else-if="video.status === 'draft' && video.description && video.description.startsWith('AI分析')" class="video-item__error">
            <span>{{ video.description }}</span>
            <el-button size="small" text type="primary" @click="retryAnalysis(video)">重新分析</el-button>
          </div>
        </div>

        <div class="video-item__actions">
          <el-switch
            :model-value="video.status === 'published'"
            :disabled="video.status === 'analyzing'"
            inline-prompt
            active-text="发布"
            inactive-text="下架"
            @change="togglePublish(video)"
          />
          <el-button size="small" text :icon="SetUp" :disabled="video.status === 'analyzing'" @click="openNodeEditor(video)">编辑节点</el-button>
          <el-button size="small" text type="danger" @click="deleteVideo(video)">删除</el-button>
        </div>
      </article>
    </section>

    <!-- 分页 -->
    <section v-if="total > pageSize" class="pagination-bar">
      <el-pagination
        v-model:current-page="page"
        v-model:page-size="pageSize"
        :page-sizes="[20, 40]"
        background
        layout="prev, pager, next"
        :total="total"
        @current-change="fetchVideos"
        @size-change="onPageSizeChange"
      />
    </section>

    <!-- 节点编辑器 -->
    <el-dialog v-model="showNodeEditor" :title="`编辑节点 - ${nodeEditorVideo?.title || ''}`" width="900px" :close-on-click-modal="false">
      <VideoNodeEditor v-if="showNodeEditor && nodeEditorVideo" :video="nodeEditorVideo" @updated="onNodesUpdated" />
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { RefreshRight, Search, SetUp, UploadFilled, VideoPlay } from '@element-plus/icons-vue'
import request from '../utils/request'
import VideoNodeEditor from '../components/VideoNodeEditor.vue'
import { useVideoCover } from '../composables/useVideoCover'

interface VideoItem {
  id: number
  title: string
  description?: string
  video_type: string
  video_url?: string
  thumbnail_url?: string
  scenario_type?: string
  difficulty?: string
  duration?: number
  tags: string[]
  status: string
  node_count: number
  created_at?: string
  updated_at?: string
}

interface UploadQueueItem {
  id: string
  filename: string
  status: 'uploading' | 'analyzing' | 'done' | 'failed'
  progress: number
  error?: string
  videoId?: number
}

const videoList = ref<VideoItem[]>([])
const loading = ref(false)
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const keyword = ref('')
let keywordTimer: ReturnType<typeof setTimeout> | null = null

const isDragging = ref(false)
const fileInputRef = ref<HTMLInputElement | null>(null)
const uploadQueue = ref<UploadQueueItem[]>([])

const showNodeEditor = ref(false)
const nodeEditorVideo = ref<VideoItem | null>(null)

let pollTimer: ReturnType<typeof setInterval> | null = null

const { ensureVideoCovers, getVideoCover } = useVideoCover()

const displayedVideos = computed(() => {
  return [...videoList.value].sort((a, b) => {
    if (a.status === 'analyzing' && b.status !== 'analyzing') return -1
    if (b.status === 'analyzing' && a.status !== 'analyzing') return 1
    return new Date(b.updated_at || b.created_at || 0).getTime() - new Date(a.updated_at || a.created_at || 0).getTime()
  })
})

onMounted(() => {
  void fetchVideos()
  pollTimer = setInterval(pollAnalyzingVideos, 5000)
})

onUnmounted(() => {
  if (keywordTimer) clearTimeout(keywordTimer)
  if (pollTimer) clearInterval(pollTimer)
})

async function fetchVideos() {
  loading.value = true
  try {
    const params: Record<string, any> = { page: page.value, page_size: pageSize.value }
    if (keyword.value) params.keyword = keyword.value
    const response: any = await request.get('/videos/admin/list', { params })
    videoList.value = (response.items || []).map((item: any) => ({
      ...item,
      tags: Array.isArray(item.tags) ? item.tags : [],
    }))
    total.value = response.total || 0
    ensureVideoCovers(videoList.value)
  } catch {
    ElMessage.error('加载视频列表失败')
  } finally {
    loading.value = false
  }
}

async function pollAnalyzingVideos() {
  const analyzingItems = videoList.value.filter((v) => v.status === 'analyzing')
  if (!analyzingItems.length) return
  for (const item of analyzingItems) {
    try {
      const result: any = await request.get(`/videos/status/${item.id}`)
      if (result.status !== 'analyzing') {
        await fetchVideos()
        const queueItem = uploadQueue.value.find((q) => q.videoId === item.id)
        if (queueItem) {
          queueItem.status = result.status === 'published' ? 'done' : 'failed'
          if (result.status !== 'published') queueItem.error = 'AI 分析失败'
        }
        break
      }
    } catch { /* ignore */ }
  }
}

function onFilterChange() {
  page.value = 1
  void fetchVideos()
}

function onKeywordChange() {
  if (keywordTimer) clearTimeout(keywordTimer)
  keywordTimer = setTimeout(() => { page.value = 1; void fetchVideos() }, 400)
}

function onPageSizeChange() {
  page.value = 1
  void fetchVideos()
}

function coverFor(video?: VideoItem | null) {
  return getVideoCover(video)
}

function triggerFileInput() {
  fileInputRef.value?.click()
}

function onFileInputChange(event: Event) {
  const files = (event.target as HTMLInputElement).files
  if (!files?.length) return
  uploadFiles(Array.from(files))
  if (fileInputRef.value) fileInputRef.value.value = ''
}

function onBatchDrop(event: DragEvent) {
  isDragging.value = false
  const files = event.dataTransfer?.files
  if (!files?.length) return
  const videoFiles = Array.from(files).filter((f) => f.type.startsWith('video/'))
  if (!videoFiles.length) {
    ElMessage.warning('请拖入视频文件（mp4 / webm / mov）')
    return
  }
  uploadFiles(videoFiles)
}

function uploadFiles(files: File[]) {
  for (const file of files) {
    const queueItem: UploadQueueItem = {
      id: `${Date.now()}-${Math.random().toString(36).slice(2)}`,
      filename: file.name,
      status: 'uploading',
      progress: 0,
    }
    uploadQueue.value.push(queueItem)
    uploadSingleFile(file, queueItem)
  }
}

async function uploadSingleFile(file: File, queueItem: UploadQueueItem) {
  const formData = new FormData()
  formData.append('file', file)

  try {
    await new Promise<void>((resolve, reject) => {
      const xhr = new XMLHttpRequest()
      const baseURL = String(request.defaults.baseURL || '').replace(/\/$/, '')
      xhr.open('POST', `${baseURL}/videos/upload`)
      const token = localStorage.getItem('token')
      if (token) xhr.setRequestHeader('Authorization', `Bearer ${token}`)
      xhr.upload.onprogress = (event) => {
        if (!event.lengthComputable) return
        queueItem.progress = Math.round((event.loaded / event.total) * 100)
      }
      xhr.onload = () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          try { queueItem.videoId = JSON.parse(xhr.responseText).id } catch { /* ok */ }
          resolve()
        } else {
          try { reject(new Error(JSON.parse(xhr.responseText).detail || '上传失败')) }
          catch { reject(new Error('上传失败')) }
        }
      }
      xhr.onerror = () => reject(new Error('网络错误'))
      xhr.send(formData)
    })
    queueItem.status = 'analyzing'
    await fetchVideos()
  } catch (error: any) {
    queueItem.status = 'failed'
    queueItem.error = error.message || '上传失败'
  }

  setTimeout(() => {
    const idx = uploadQueue.value.findIndex((q) => q.id === queueItem.id && (q.status === 'done' || q.status === 'failed'))
    if (idx >= 0) uploadQueue.value.splice(idx, 1)
  }, 8000)
}

function queueStatusLabel(item: UploadQueueItem) {
  if (item.status === 'uploading') return `上传中 ${item.progress}%`
  if (item.status === 'analyzing') return 'AI 分析中'
  if (item.status === 'done') return '完成'
  return '失败'
}

async function togglePublish(video: VideoItem) {
  try {
    const result: any = await request.patch(`/videos/${video.id}/toggle-publish`)
    video.status = result.status
    ElMessage.success(result.status === 'published' ? '已发布' : '已下架')
  } catch {
    ElMessage.error('操作失败')
  }
}

async function retryAnalysis(video: VideoItem) {
  try {
    await request.post(`/videos/retry-analysis/${video.id}`)
    video.status = 'analyzing'
    video.description = undefined
    ElMessage.success('已重新触发 AI 分析')
  } catch {
    ElMessage.error('重新分析失败')
  }
}

async function deleteVideo(video: VideoItem) {
  try {
    await ElMessageBox.confirm(`确认删除"${video.title}"？`, '删除确认', { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' })
  } catch { return }
  try {
    await request.delete(`/videos/${video.id}`)
    ElMessage.success('已删除')
    await fetchVideos()
  } catch {
    ElMessage.error('删除失败')
  }
}

function openNodeEditor(video: VideoItem) {
  nodeEditorVideo.value = video
  showNodeEditor.value = true
}

async function onNodesUpdated() {
  await fetchVideos()
}

function openDetail(video: VideoItem) {
  if (video.video_url) window.open(video.video_url, '_blank')
}

function difficultyLabel(level?: string) {
  return ({ easy: '简单', normal: '标准', hard: '困难' } as Record<string, string>)[level || ''] || ''
}

function formatDuration(seconds?: number) {
  if (seconds == null) return '--'
  const s = Math.max(0, Math.round(seconds))
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`
}
</script>

<style scoped lang="scss">
.video-library {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 20px 24px;
  max-width: 1200px;
  margin: 0 auto;
}

.library-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.library-header__left {
  display: flex;
  align-items: baseline;
  gap: 12px;
}

.library-header__title {
  margin: 0;
  font-size: 22px;
  font-weight: 700;
  color: #1e293b;
}

.library-header__count {
  color: #64748b;
  font-size: 14px;
}

.header-search {
  width: 240px;
}

.drop-zone {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 28px 20px;
  border: 2px dashed #cbd5e1;
  border-radius: 12px;
  background: #f8fafc;
  cursor: pointer;
  transition: all 0.2s;
}

.drop-zone:hover,
.drop-zone--active {
  border-color: #3b82f6;
  background: #eff6ff;
}

.drop-zone__icon {
  color: #94a3b8;
}

.drop-zone--active .drop-zone__icon {
  color: #3b82f6;
}

.drop-zone__text {
  margin: 0;
  text-align: center;
  color: #64748b;
  font-size: 14px;
  line-height: 1.6;
}

.drop-zone__text small {
  color: #94a3b8;
}

.upload-queue {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.upload-queue__item {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 10px 14px;
  border-radius: 8px;
  background: #f1f5f9;
}

.upload-queue__info {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.upload-queue__name {
  font-size: 13px;
  color: #334155;
  font-weight: 500;
}

.upload-queue__status {
  font-size: 12px;
  font-weight: 600;
}

.upload-queue__status.is-uploading { color: #3b82f6; }
.upload-queue__status.is-analyzing { color: #f59e0b; }
.upload-queue__status.is-done { color: #10b981; }
.upload-queue__status.is-failed { color: #ef4444; }

.upload-queue__analyzing {
  display: flex;
  align-items: center;
  gap: 6px;
  color: #f59e0b;
  font-size: 12px;
}

.upload-queue__error {
  color: #ef4444;
  font-size: 12px;
}

.state-panel {
  padding: 48px 0;
  text-align: center;
}

.video-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.video-item {
  display: grid;
  grid-template-columns: 160px 1fr auto;
  gap: 16px;
  align-items: center;
  padding: 12px 16px;
  border-radius: 10px;
  background: #fff;
  border: 1px solid #e2e8f0;
  transition: box-shadow 0.2s;
}

.video-item:hover {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.06);
}

.video-item__cover {
  position: relative;
  width: 160px;
  height: 90px;
  border-radius: 8px;
  overflow: hidden;
  background: #0f172a;
  cursor: pointer;
}

.video-item__cover img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.cover-placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  height: 100%;
  color: #64748b;
}

.video-item__duration {
  position: absolute;
  bottom: 4px;
  right: 4px;
  padding: 2px 6px;
  border-radius: 4px;
  background: rgba(0, 0, 0, 0.7);
  color: #fff;
  font-size: 11px;
  font-weight: 600;
}

.video-item__body {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.video-item__title {
  font-size: 15px;
  font-weight: 600;
  color: #1e293b;
}

.video-item__meta {
  display: flex;
  gap: 8px;
  font-size: 12px;
  color: #64748b;
}

.video-item__meta span::after {
  content: '·';
  margin-left: 8px;
  color: #cbd5e1;
}

.video-item__meta span:last-child::after {
  content: '';
}

.video-item__analyzing {
  display: flex;
  align-items: center;
  gap: 6px;
  color: #f59e0b;
  font-size: 13px;
}

.video-item__error {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: #ef4444;
}

.video-item__actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.pagination-bar {
  display: flex;
  justify-content: center;
  padding: 12px 0;
}
</style>
