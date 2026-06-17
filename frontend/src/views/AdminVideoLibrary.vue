<template>
  <div class="video-library">
    <!-- 顶部操作栏 -->
    <div class="page-header">
      <div class="page-header__left">
        <h2 class="page-title">视频素材库</h2>
        <p class="page-subtitle">管理教学素材视频与交互式实训视频</p>
      </div>
      <el-button type="primary" :icon="Plus" @click="openUploadDialog">上传视频</el-button>
    </div>

    <!-- 筛选栏 -->
    <div class="filter-bar">
      <el-tabs v-model="activeTab" @tab-change="fetchVideos">
        <el-tab-pane label="全部" name="" />
        <el-tab-pane label="教学素材" name="teaching" />
        <el-tab-pane label="交互式实训" name="interactive" />
      </el-tabs>
      <div class="filter-bar__right">
        <el-input
          v-model="keyword"
          placeholder="搜索视频标题"
          clearable
          :prefix-icon="Search"
          style="width: 220px"
          @input="onKeywordChange"
        />
        <el-select v-model="statusFilter" placeholder="状态筛选" clearable style="width: 120px" @change="fetchVideos">
          <el-option label="草稿" value="draft" />
          <el-option label="已发布" value="published" />
          <el-option label="已归档" value="archived" />
        </el-select>
      </div>
    </div>

    <!-- 视频列表 -->
    <div v-if="loading" class="state-panel">
      <el-skeleton :rows="4" animated />
    </div>
    <div v-else-if="!videoList.length" class="state-panel">
      <el-empty description="暂无视频，点击右上角上传第一个视频" />
    </div>
    <div v-else class="video-grid">
      <div v-for="video in videoList" :key="video.id" class="video-card">
        <!-- 封面 -->
        <div class="video-card__cover" @click="openDetail(video)">
          <img v-if="video.thumbnail_url" :src="video.thumbnail_url" :alt="video.title" class="cover-img" />
          <div v-else class="cover-placeholder">
            <el-icon :size="36"><VideoPlay /></el-icon>
          </div>
          <div class="cover-overlay">
            <el-icon :size="28" class="play-icon"><VideoPlay /></el-icon>
          </div>
          <el-tag class="type-tag" :type="video.video_type === 'interactive' ? 'danger' : 'primary'" size="small" effect="dark">
            {{ video.video_type === 'interactive' ? '实训' : '教学' }}
          </el-tag>
        </div>

        <!-- 信息 -->
        <div class="video-card__body">
          <div class="video-card__title" :title="video.title">{{ video.title }}</div>
          <div class="video-card__meta">
            <span class="meta-item">
              <el-icon><Timer /></el-icon>
              {{ formatDuration(video.duration) }}
            </span>
            <span class="meta-item">
              <el-icon><SetUp /></el-icon>
              {{ video.node_count }} 个节点
            </span>
          </div>
          <div class="video-card__footer">
            <el-tag :type="statusTagType(video.status)" size="small">{{ statusLabel(video.status) }}</el-tag>
            <div class="card-actions">
              <el-button size="small" text :icon="Edit" @click.stop="openNodeEditor(video)">节点</el-button>
              <el-button size="small" text :icon="Edit" @click.stop="openEditMeta(video)">编辑</el-button>
              <el-dropdown trigger="click" @command="(cmd: string) => handleCommand(cmd, video)">
                <el-button size="small" text :icon="MoreFilled" />
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item v-if="video.status !== 'published'" command="publish">发布</el-dropdown-item>
                    <el-dropdown-item v-if="video.status === 'published'" command="draft">设为草稿</el-dropdown-item>
                    <el-dropdown-item command="archive">归档</el-dropdown-item>
                    <el-dropdown-item command="delete" divided style="color: #f56c6c">删除</el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 分页 -->
    <div v-if="total > pageSize" class="pagination-bar">
      <el-pagination
        v-model:current-page="page"
        :page-size="pageSize"
        :total="total"
        layout="prev, pager, next, total"
        @current-change="fetchVideos"
      />
    </div>

    <!-- ── 上传对话框 ── -->
    <el-dialog v-model="showUpload" title="上传视频" width="560px" :close-on-click-modal="false">
      <el-form ref="uploadFormRef" :model="uploadForm" :rules="uploadRules" label-width="90px">
        <el-form-item label="视频标题" prop="title">
          <el-input v-model="uploadForm.title" placeholder="请输入视频标题" maxlength="120" show-word-limit />
        </el-form-item>
        <el-form-item label="视频类型" prop="video_type">
          <el-radio-group v-model="uploadForm.video_type">
            <el-radio value="teaching">教学素材（预习/复盘用）</el-radio>
            <el-radio value="interactive">交互式实训（含节点考核）</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="视频简介">
          <el-input v-model="uploadForm.description" type="textarea" :rows="3" placeholder="选填" />
        </el-form-item>
        <el-form-item label="标签">
          <el-input v-model="uploadForm.tagsInput" placeholder="多个标签用逗号分隔，如：交通执法,证件核查" />
        </el-form-item>
        <el-form-item label="视频文件" prop="file">
          <div class="upload-area" @click="triggerFileInput" @dragover.prevent @drop.prevent="onDrop">
            <template v-if="!uploadForm.file">
              <el-icon :size="32" class="upload-icon"><UploadFilled /></el-icon>
              <p class="upload-hint">点击或拖拽上传视频<br /><small>支持 mp4 / webm / mov，最大 2GB</small></p>
            </template>
            <template v-else>
              <el-icon :size="24" color="#67c23a"><CircleCheck /></el-icon>
              <p class="upload-hint">
                {{ uploadForm.file.name }}<br />
                <small>{{ formatFileSize(uploadForm.file.size) }}</small>
                <small v-if="extractedDuration != null"> · {{ formatDuration(extractedDuration) }}</small>
                <small v-if="analyzing" style="color:#e6a23c"> · 分析中...</small>
              </p>
              <el-button size="small" text @click.stop="uploadForm.file = null; extractedDuration = null; autoThumbBlob = null">重新选择</el-button>
            </template>
          </div>
          <input ref="fileInputRef" type="file" accept="video/mp4,video/webm,video/ogg,video/quicktime" hidden @change="onFileChange" />
        </el-form-item>
        <el-form-item label="封面图">
          <div class="upload-area upload-area--small" @click="triggerThumbInput">
            <template v-if="!thumbPreview">
              <el-icon :size="20"><Picture /></el-icon>
              <span>选择封面（可选，将自动截取第1帧）</span>
            </template>
            <template v-else>
              <img :src="thumbPreview" class="thumb-preview" />
              <div class="thumb-actions">
                <span class="thumb-auto-tag" v-if="!uploadForm.thumbnail">自动截帧</span>
                <el-button size="small" text @click.stop="clearThumb">更换</el-button>
              </div>
            </template>
          </div>
          <input ref="thumbInputRef" type="file" accept="image/*" hidden @change="onThumbChange" />
        </el-form-item>
      </el-form>

      <!-- 上传进度 -->
      <div v-if="uploading" class="upload-progress">
        <el-progress :percentage="uploadProgress" :stroke-width="8" />
        <p class="progress-text">{{ uploadProgressText }}</p>
      </div>

      <template #footer>
        <el-button @click="showUpload = false" :disabled="uploading">取消</el-button>
        <el-button type="primary" :loading="uploading" @click="submitUpload">
          {{ uploading ? '上传中...' : '开始上传' }}
        </el-button>
      </template>
    </el-dialog>

    <!-- ── 编辑元信息对话框 ── -->
    <el-dialog v-model="showEditMeta" title="编辑视频信息" width="480px">
      <el-form v-if="editTarget" :model="editTarget" label-width="90px">
        <el-form-item label="视频标题">
          <el-input v-model="editTarget.title" maxlength="120" show-word-limit />
        </el-form-item>
        <el-form-item label="视频类型">
          <el-radio-group v-model="editTarget.video_type">
            <el-radio value="teaching">教学素材</el-radio>
            <el-radio value="interactive">交互式实训</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="视频简介">
          <el-input v-model="editTarget.description" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item label="训练前简报">
          <el-input
            v-model="editTarget.briefing"
            type="textarea"
            :rows="5"
            placeholder="学员进入训练前展示的案情背景、训练要点、评分规则等（支持换行）"
          />
        </el-form-item>
        <el-form-item label="标签">
          <el-input v-model="editTagsInput" placeholder="多个标签用逗号分隔" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showEditMeta = false">取消</el-button>
        <el-button type="primary" :loading="savingMeta" @click="saveMeta">保存</el-button>
      </template>
    </el-dialog>

    <!-- ── 节点编辑器对话框 ── -->
    <el-dialog v-model="showNodeEditor" :title="`节点配置 — ${nodeEditorVideo?.title}`" width="820px" :close-on-click-modal="false">
      <VideoNodeEditor v-if="showNodeEditor && nodeEditorVideo" :video="nodeEditorVideo" @updated="onNodesUpdated" />
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Plus, Search, Edit, MoreFilled, VideoPlay,
  Timer, SetUp, UploadFilled, CircleCheck, Picture,
} from '@element-plus/icons-vue'
import request from '../utils/request'
import VideoNodeEditor from '../components/VideoNodeEditor.vue'

interface VideoItem {
  id: number
  title: string
  description?: string
  briefing?: string
  video_type: 'teaching' | 'interactive'
  video_url?: string
  thumbnail_url?: string
  duration?: number
  file_size?: number
  tags: string[]
  status: 'draft' | 'published' | 'archived'
  sort_order: number
  node_count: number
  created_at?: string
}

// ── 列表状态 ──
const videoList = ref<VideoItem[]>([])
const loading = ref(false)
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const activeTab = ref('')
const keyword = ref('')
const statusFilter = ref('')
let keywordTimer: ReturnType<typeof setTimeout> | null = null

// ── 上传对话框 ──
const showUpload = ref(false)
const uploading = ref(false)
const uploadProgress = ref(0)
const uploadProgressText = ref('')
const fileInputRef = ref<HTMLInputElement | null>(null)
const thumbInputRef = ref<HTMLInputElement | null>(null)
const thumbPreview = ref('')
const uploadFormRef = ref()
const analyzing = ref(false)          // 正在分析视频（提取时长+截帧）
const extractedDuration = ref<number | null>(null)   // 自动提取到的时长
const autoThumbBlob = ref<Blob | null>(null)         // 自动截取的封面
let analyzeAbortFlag = 0                             // 防止并发截帧竞争
let thumbObjectUrls: string[] = []                   // 追踪待释放的 Object URL
const uploadForm = ref({
  title: '',
  video_type: 'teaching',
  description: '',
  tagsInput: '',
  file: null as File | null,
  thumbnail: null as File | null,
})
const uploadRules = {
  title: [{ required: true, message: '请输入视频标题', trigger: 'blur' }],
  video_type: [{ required: true, message: '请选择视频类型', trigger: 'change' }],
  file: [{ required: true, validator: (_: any, __: any, cb: any) => uploadForm.value.file ? cb() : cb(new Error('请选择视频文件')), trigger: 'change' }],
}

// ── 编辑元信息 ──
const showEditMeta = ref(false)
const savingMeta = ref(false)
const editTarget = ref<VideoItem | null>(null)
const editTagsInput = ref('')

// ── 节点编辑器 ──
const showNodeEditor = ref(false)
const nodeEditorVideo = ref<VideoItem | null>(null)

onMounted(fetchVideos)

async function fetchVideos() {
  loading.value = true
  try {
    const params: Record<string, any> = { page: page.value, page_size: pageSize.value }
    if (activeTab.value) params.video_type = activeTab.value
    if (statusFilter.value) params.status = statusFilter.value
    if (keyword.value) params.keyword = keyword.value
    const res: any = await request.get('/videos/admin/list', { params })
    videoList.value = res.items || []
    total.value = res.total || 0
  } catch {
    ElMessage.error('加载视频列表失败')
  } finally {
    loading.value = false
  }
}

function onKeywordChange() {
  if (keywordTimer) clearTimeout(keywordTimer)
  keywordTimer = setTimeout(fetchVideos, 400)
}

// ── 上传 ──
function openUploadDialog() {
  uploadForm.value = { title: '', video_type: 'teaching', description: '', tagsInput: '', file: null, thumbnail: null }
  // 释放旧的 Object URL，避免内存泄漏
  thumbObjectUrls.forEach(u => URL.revokeObjectURL(u))
  thumbObjectUrls = []
  thumbPreview.value = ''
  uploadProgress.value = 0
  extractedDuration.value = null
  autoThumbBlob.value = null
  analyzeAbortFlag++   // 让任何正在进行的截帧任务自动作废
  showUpload.value = true
}

function triggerFileInput() { fileInputRef.value?.click() }
function triggerThumbInput() { thumbInputRef.value?.click() }

function onFileChange(e: Event) {
  const f = (e.target as HTMLInputElement).files?.[0]
  if (f) {
    uploadForm.value.file = f
    // 没有手动选封面时才自动截帧
    if (!uploadForm.value.thumbnail) analyzeVideo(f)
  }
}

/** 用浏览器原生能力提取视频时长和第1秒截帧封面 */
async function analyzeVideo(file: File) {
  const myFlag = ++analyzeAbortFlag  // 标记本次任务 ID，用于检测是否被取消
  analyzing.value = true
  extractedDuration.value = null
  autoThumbBlob.value = null
  if (!uploadForm.value.thumbnail) thumbPreview.value = ''

  try {
    const url = URL.createObjectURL(file)
    thumbObjectUrls.push(url)
    const videoEl = document.createElement('video')
    videoEl.preload = 'metadata'
    videoEl.muted = true
    videoEl.playsInline = true
    videoEl.src = url

    // 等待 metadata 加载（含超时保护）
    await new Promise<void>((resolve) => {
      const timer = setTimeout(resolve, 8000)
      videoEl.onloadedmetadata = () => { clearTimeout(timer); resolve() }
      videoEl.onerror = () => { clearTimeout(timer); resolve() }
    })

    // 被更新的任务取代，直接退出
    if (myFlag !== analyzeAbortFlag) return

    if (videoEl.duration && isFinite(videoEl.duration)) {
      extractedDuration.value = Math.round(videoEl.duration)
    }

    // seek 到第 1 秒（短视频取 10%）做截帧
    const seekTo = videoEl.duration > 0
      ? Math.min(1, videoEl.duration * 0.1)
      : 0
    videoEl.currentTime = seekTo

    await new Promise<void>((resolve) => {
      const timer = setTimeout(resolve, 3000)
      videoEl.onseeked = () => { clearTimeout(timer); resolve() }
      videoEl.onerror = () => { clearTimeout(timer); resolve() }
    })

    if (myFlag !== analyzeAbortFlag) return

    // 绘制 canvas 截帧
    const canvas = document.createElement('canvas')
    canvas.width = videoEl.videoWidth || 640
    canvas.height = videoEl.videoHeight || 360
    const ctx = canvas.getContext('2d')
    if (ctx && videoEl.videoWidth > 0) {
      ctx.drawImage(videoEl, 0, 0, canvas.width, canvas.height)
      await new Promise<void>((resolve) => {
        canvas.toBlob((blob) => {
          if (blob && myFlag === analyzeAbortFlag) {
            autoThumbBlob.value = blob
            if (!uploadForm.value.thumbnail) {
              const previewUrl = URL.createObjectURL(blob)
              thumbObjectUrls.push(previewUrl)
              thumbPreview.value = previewUrl
            }
          }
          resolve()
        }, 'image/jpeg', 0.85)
      })
    }

    videoEl.remove()
  } catch {
    // 截帧失败不阻断上传流程
  } finally {
    if (myFlag === analyzeAbortFlag) analyzing.value = false
  }
}

function onThumbChange(e: Event) {
  const f = (e.target as HTMLInputElement).files?.[0]
  if (f) {
    uploadForm.value.thumbnail = f
    thumbPreview.value = URL.createObjectURL(f)
  }
}

function clearThumb() {
  uploadForm.value.thumbnail = null
  // 退回到自动截帧预览（如果有）
  if (autoThumbBlob.value) {
    const url = URL.createObjectURL(autoThumbBlob.value)
    thumbObjectUrls.push(url)
    thumbPreview.value = url
  } else {
    thumbPreview.value = ''
  }
}

function onDrop(e: DragEvent) {
  const f = e.dataTransfer?.files?.[0]
  if (f && f.type.startsWith('video/')) {
    uploadForm.value.file = f
    if (!uploadForm.value.thumbnail) analyzeVideo(f)
  }
}

async function submitUpload() {
  await uploadFormRef.value?.validate()
  if (!uploadForm.value.file) { ElMessage.warning('请选择视频文件'); return }
  if (analyzing.value) { ElMessage.warning('视频分析中，请稍候再上传'); return }

  uploading.value = true
  uploadProgress.value = 0
  uploadProgressText.value = '准备上传...'

  const fd = new FormData()
  fd.append('title', uploadForm.value.title)
  fd.append('video_type', uploadForm.value.video_type)
  fd.append('description', uploadForm.value.description || '')
  fd.append('tags', JSON.stringify(
    uploadForm.value.tagsInput.split(',').map(s => s.trim()).filter(Boolean)
  ))
  // 时长：优先使用自动提取值
  if (extractedDuration.value != null) {
    fd.append('duration', String(extractedDuration.value))
  }
  fd.append('file', uploadForm.value.file)
  // 封面：优先用户手动选择，其次用自动截帧
  if (uploadForm.value.thumbnail) {
    fd.append('thumbnail', uploadForm.value.thumbnail)
  } else if (autoThumbBlob.value) {
    // 显式指定 type 为 image/jpeg，否则后端 content-type 校验会因 application/octet-stream 失败
    const thumbFile = new File([autoThumbBlob.value], 'auto_thumb.jpg', { type: 'image/jpeg' })
    fd.append('thumbnail', thumbFile)
  }

  try {
    // 使用 XMLHttpRequest 以支持上传进度
    await new Promise<void>((resolve, reject) => {
      const xhr = new XMLHttpRequest()
      const baseURL = (request.defaults.baseURL || '').replace(/\/$/, '')
      xhr.open('POST', `${baseURL}/videos/upload`)
      const token = localStorage.getItem('token')
      if (token) xhr.setRequestHeader('Authorization', `Bearer ${token}`)
      xhr.upload.onprogress = (e) => {
        if (e.lengthComputable) {
          uploadProgress.value = Math.round((e.loaded / e.total) * 100)
          uploadProgressText.value = `已上传 ${formatFileSize(e.loaded)} / ${formatFileSize(e.total)}`
        }
      }
      xhr.onload = () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          resolve()
        } else {
          try {
            const err = JSON.parse(xhr.responseText)
            reject(new Error(err.detail || '上传失败'))
          } catch {
            reject(new Error('上传失败'))
          }
        }
      }
      xhr.onerror = () => reject(new Error('网络错误'))
      xhr.send(fd)
    })
    ElMessage.success('视频上传成功')
    showUpload.value = false
    // 释放本次上传产生的所有 Object URL
    thumbObjectUrls.forEach(u => URL.revokeObjectURL(u))
    thumbObjectUrls = []
    fetchVideos()
  } catch (e: any) {
    ElMessage.error(e.message || '上传失败，请重试')
  } finally {
    uploading.value = false
  }
}

// ── 编辑元信息 ──
function openEditMeta(video: VideoItem) {
  editTarget.value = { ...video }
  editTagsInput.value = Array.isArray(video.tags) ? video.tags.join(', ') : ''
  showEditMeta.value = true
}

async function saveMeta() {
  if (!editTarget.value) return
  savingMeta.value = true
  try {
    const tags = editTagsInput.value.split(',').map(s => s.trim()).filter(Boolean)
    await request.patch(`/videos/${editTarget.value.id}`, {
      title: editTarget.value.title,
      description: editTarget.value.description,
      briefing: editTarget.value.briefing,
      video_type: editTarget.value.video_type,
      tags,
    })
    ElMessage.success('保存成功')
    showEditMeta.value = false
    fetchVideos()
  } catch {
    ElMessage.error('保存失败')
  } finally {
    savingMeta.value = false
  }
}

// ── 节点编辑器 ──
function openNodeEditor(video: VideoItem) {
  nodeEditorVideo.value = video
  showNodeEditor.value = true
}

function onNodesUpdated() {
  fetchVideos()
}

// ── 详情预览 ──
function openDetail(video: VideoItem) {
  if (video.video_url) window.open(video.video_url, '_blank')
}

// ── 状态操作 ──
async function handleCommand(command: string, video: VideoItem) {
  if (command === 'delete') {
    await ElMessageBox.confirm(`确认删除视频「${video.title}」？此操作不可恢复。`, '删除确认', {
      type: 'warning', confirmButtonText: '确认删除', cancelButtonText: '取消',
    })
    try {
      await request.delete(`/videos/${video.id}`)
      ElMessage.success('已删除')
      fetchVideos()
    } catch { ElMessage.error('删除失败') }
    return
  }
  const statusMap: Record<string, string> = { publish: 'published', draft: 'draft', archive: 'archived' }
  const newStatus = statusMap[command]
  if (!newStatus) return
  try {
    await request.patch(`/videos/${video.id}`, { status: newStatus })
    ElMessage.success('状态已更新')
    fetchVideos()
  } catch { ElMessage.error('操作失败') }
}

// ── 工具函数 ──
function formatDuration(seconds?: number): string {
  if (!seconds) return '--'
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return `${m}:${String(s).padStart(2, '0')}`
}

function formatFileSize(bytes?: number): string {
  if (!bytes) return '--'
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`
}

function statusLabel(status: string): string {
  return { draft: '草稿', published: '已发布', archived: '已归档' }[status] || status
}

function statusTagType(status: string): '' | 'success' | 'info' | 'warning' | 'danger' {
  return { draft: 'info', published: 'success', archived: 'warning' }[status] as any || 'info'
}
</script>

<style scoped lang="scss">
.video-library {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;

  &__left {}
}

.page-title {
  margin: 0 0 4px;
  font-size: 20px;
  font-weight: 700;
  color: #111827;
}

.page-subtitle {
  margin: 0;
  font-size: 13px;
  color: #6b7280;
}

.filter-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  border-bottom: 1px solid #e5e7eb;

  :deep(.el-tabs__header) { margin-bottom: 0; }
  :deep(.el-tabs__nav-wrap::after) { display: none; }

  &__right {
    display: flex;
    gap: 8px;
    padding-bottom: 8px;
  }
}

.state-panel {
  padding: 40px 0;
  text-align: center;
}

.video-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 16px;
}

.video-card {
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  background: #fff;
  overflow: hidden;
  transition: box-shadow 0.2s;
  cursor: pointer;

  &:hover {
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.1);

    .cover-overlay { opacity: 1; }
  }

  &__cover {
    position: relative;
    width: 100%;
    padding-top: 56.25%; /* 16:9 */
    background: #0f172a;
    overflow: hidden;
  }

  &__body {
    padding: 12px 14px;
  }

  &__title {
    font-size: 14px;
    font-weight: 600;
    color: #111827;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    margin-bottom: 6px;
  }

  &__meta {
    display: flex;
    gap: 12px;
    margin-bottom: 10px;
  }

  &__footer {
    display: flex;
    align-items: center;
    justify-content: space-between;
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
  color: rgba(255, 255, 255, 0.3);
}

.cover-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.4);
  opacity: 0;
  transition: opacity 0.2s;
  color: #fff;
}

.type-tag {
  position: absolute;
  top: 8px;
  left: 8px;
}

.play-icon { pointer-events: none; }

.meta-item {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: #9ca3af;
}

.card-actions {
  display: flex;
  align-items: center;
  gap: 0;
}

.pagination-bar {
  display: flex;
  justify-content: center;
  padding: 8px 0;
}

/* 上传区域 */
.upload-area {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  width: 100%;
  padding: 24px 16px;
  border: 2px dashed #d1d5db;
  border-radius: 8px;
  cursor: pointer;
  transition: border-color 0.2s, background 0.2s;
  text-align: center;
  color: #6b7280;

  &:hover {
    border-color: #0066ff;
    background: #f0f6ff;
  }

  &--small {
    padding: 12px;
    flex-direction: row;
  }
}

.upload-icon { color: #9ca3af; }
.upload-hint { margin: 0; font-size: 13px; line-height: 1.6; }

.thumb-preview {
  width: 80px;
  height: 50px;
  object-fit: cover;
  border-radius: 4px;
}

.thumb-actions {
  display: flex;
  align-items: center;
  gap: 6px;
}

.thumb-auto-tag {
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 3px;
  background: #e8f4ff;
  color: #0066ff;
  font-weight: 600;
}

.upload-progress {
  margin-top: 16px;
}

.progress-text {
  margin: 6px 0 0;
  font-size: 12px;
  color: #6b7280;
  text-align: center;
}
</style>
