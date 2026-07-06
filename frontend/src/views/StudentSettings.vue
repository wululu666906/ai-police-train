<template>
  <div class="student-settings">
    <section class="settings-header">
      <div>
        <p class="settings-eyebrow">个人设置</p>
        <h1>{{ displayName }}</h1>
        <p class="settings-subtitle">维护训练身份信息，上传的人脸照片会同步进入管理端学员档案，用于训练前身份核验和训练过程人脸识别。</p>
      </div>
      <van-tag :type="faceProfile?.registered ? 'success' : 'warning'" plain>
        {{ faceProfile?.registered ? '人脸档案已建立' : '待上传人脸照片' }}
      </van-tag>
    </section>

    <section class="settings-grid">
      <div class="settings-card face-card">
        <div class="card-title-row">
          <div>
            <h2>个人照片</h2>
            <p>建议上传本人清晰正脸照片，画面中只保留一张人脸。</p>
          </div>
          <van-button size="small" plain :loading="faceLoading" @click="fetchFaceProfile">刷新</van-button>
        </div>

        <div class="face-upload-panel">
          <div class="face-preview">
            <img
              v-if="faceProfile?.registered && faceProfile.face_image_url"
              :src="faceProfile.face_image_url"
              alt="学员人脸照片"
            />
            <div v-else class="face-preview-empty">
              <van-icon name="contact" size="42" />
              <span>{{ initials }}</span>
            </div>
          </div>

          <div class="face-meta">
            <div class="face-status" :class="{ 'face-status--ready': faceProfile?.registered }">
              <van-icon :name="faceProfile?.registered ? 'passed' : 'warning-o'" />
              <span>{{ faceProfile?.registered ? '已同步至管理端学员档案' : '尚未上传可识别照片' }}</span>
            </div>
            <dl>
              <div>
                <dt>账号</dt>
                <dd>{{ displayName }}</dd>
              </div>
              <div>
                <dt>学员ID</dt>
                <dd>{{ studentCode }}</dd>
              </div>
              <div>
                <dt>识别模型</dt>
                <dd>{{ faceProfile?.embedding_model || faceEngineLabel }}</dd>
              </div>
              <div>
                <dt>更新时间</dt>
                <dd>{{ fmtDateTime(faceProfile?.updated_at) }}</dd>
              </div>
            </dl>
          </div>
        </div>

        <div class="upload-actions">
          <input ref="fileInputRef" class="hidden" type="file" accept="image/*" @change="handleFaceFileChange" />
          <van-button type="primary" icon="photograph" :loading="faceUploading" @click="fileInputRef?.click()">
            {{ faceProfile?.registered ? '重新上传照片' : '上传个人照片' }}
          </van-button>
          <span>支持 JPG、PNG 等图片格式，单张不超过 8MB。</span>
        </div>
      </div>

      <div class="settings-card guide-card">
        <h2>人脸识别用途</h2>
        <div class="guide-list">
          <div class="guide-item">
            <van-icon name="user-circle-o" />
            <div>
              <strong>训练身份核验</strong>
              <p>进入训练前会比对当前摄像头画面与个人照片特征。</p>
            </div>
          </div>
          <div class="guide-item">
            <van-icon name="video-o" />
            <div>
              <strong>过程持续监测</strong>
              <p>训练中离开画面、多人入镜或非本人参与会记录为异常。</p>
            </div>
          </div>
          <div class="guide-item">
            <van-icon name="records-o" />
            <div>
              <strong>管理端档案同步</strong>
              <p>上传成功后，管理员在学员画像的人脸档案模块可查看同一份照片和识别数据。</p>
            </div>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, inject, onMounted, onUnmounted, ref } from 'vue'
import { showToast } from 'vant'
import request from '../utils/request'

type FaceProfile = {
  registered: boolean
  student_id?: number
  face_image_url?: string
  embedding_model?: string
  updated_at?: string
}

type FaceEngine = {
  model?: string
}

const setMainScrollable = inject<(value: boolean) => void>('setMainScrollable')
const faceProfile = ref<FaceProfile | null>(null)
const faceEngine = ref<FaceEngine | null>(null)
const faceLoading = ref(false)
const faceUploading = ref(false)
const fileInputRef = ref<HTMLInputElement | null>(null)

const displayName = computed(() => localStorage.getItem('username') || '学员')
const userId = computed(() => Number(localStorage.getItem('user_id') || 0))
const studentCode = computed(() => `STU${String(userId.value || 0).padStart(5, '0')}`)
const initials = computed(() => displayName.value.trim().slice(0, 2).toUpperCase() || 'ST')
const faceEngineLabel = computed(() => (faceEngine.value?.model ? `insightface:${faceEngine.value.model}` : 'insightface:buffalo_l'))

const normalizeFaceProfile = (payload: any): FaceProfile => {
  const imageUrl = String(payload?.face_image_url || '')
  const apiBase = String((request as any).defaults?.baseURL || '').replace(/\/$/, '')
  return {
    registered: Boolean(payload?.registered),
    student_id: payload?.student_id,
    face_image_url: imageUrl && imageUrl.startsWith('/') && apiBase ? `${apiBase}${imageUrl}` : imageUrl,
    embedding_model: payload?.embedding_model,
    updated_at: payload?.updated_at,
  }
}

const fmtDateTime = (value: string | null | undefined) => {
  if (!value) return '--'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '--'
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')} ${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`
}

const fetchFaceEngine = async () => {
  try {
    faceEngine.value = await request.get('/face/engine', { _skipErrorToast: true } as any)
  } catch {
    faceEngine.value = null
  }
}

const fetchFaceProfile = async () => {
  faceLoading.value = true
  try {
    const result = await request.get('/face/me/profile', { _skipErrorToast: true } as any)
    faceProfile.value = normalizeFaceProfile(result)
  } catch (error: any) {
    faceProfile.value = { registered: false }
    showToast(error?.response?.data?.detail || '人脸档案加载失败')
  } finally {
    faceLoading.value = false
  }
}

const handleFaceFileChange = async (event: Event) => {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return

  faceUploading.value = true
  try {
    const form = new FormData()
    form.append('file', file)
    const result = await request.post('/face/me/register', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
      _skipErrorToast: true,
      timeout: 120000,
    } as any)
    faceProfile.value = normalizeFaceProfile(result)
    showToast({ type: 'success', message: '个人照片已上传，并同步至管理端学员档案' })
  } catch (error: any) {
    showToast(error?.response?.data?.detail || '照片上传失败，请使用清晰正脸照片重试')
  } finally {
    faceUploading.value = false
    input.value = ''
  }
}

onMounted(() => {
  setMainScrollable?.(true)
  fetchFaceEngine()
  fetchFaceProfile()
})

onUnmounted(() => {
  setMainScrollable?.(false)
})
</script>

<style scoped>
.student-settings {
  max-width: 1100px;
  margin: 0 auto;
  padding: 24px;
}

.settings-header,
.settings-card {
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #fff;
}

.settings-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 18px;
  padding: 22px 24px;
}

.settings-eyebrow {
  margin: 0 0 6px;
  color: #2563eb;
  font-size: 12px;
  font-weight: 800;
}

.settings-header h1,
.settings-card h2 {
  margin: 0;
  color: #111827;
  font-weight: 800;
}

.settings-header h1 {
  font-size: 24px;
}

.settings-subtitle {
  max-width: 680px;
  margin: 8px 0 0;
  color: #64748b;
  font-size: 13px;
  line-height: 1.8;
}

.settings-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.45fr) minmax(280px, 0.75fr);
  gap: 16px;
  margin-top: 16px;
}

.settings-card {
  padding: 20px;
}

.card-title-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.settings-card h2 {
  font-size: 16px;
}

.settings-card p {
  margin: 6px 0 0;
  color: #64748b;
  font-size: 13px;
  line-height: 1.7;
}

.face-upload-panel {
  display: grid;
  grid-template-columns: 180px minmax(0, 1fr);
  gap: 18px;
  margin-top: 20px;
}

.face-preview {
  width: 180px;
  aspect-ratio: 1;
  overflow: hidden;
  border: 1px solid #dbe3ee;
  border-radius: 8px;
  background: #f8fafc;
}

.face-preview img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.face-preview-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  width: 100%;
  height: 100%;
  color: #94a3b8;
}

.face-preview-empty span {
  color: #334155;
  font-size: 28px;
  font-weight: 900;
}

.face-status {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border: 1px solid #fed7aa;
  border-radius: 999px;
  background: #fff7ed;
  padding: 6px 10px;
  color: #c2410c;
  font-size: 12px;
  font-weight: 800;
}

.face-status--ready {
  border-color: #bbf7d0;
  background: #f0fdf4;
  color: #16a34a;
}

.face-meta dl {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  margin: 16px 0 0;
}

.face-meta dt {
  color: #94a3b8;
  font-size: 12px;
}

.face-meta dd {
  margin: 4px 0 0;
  color: #1e293b;
  font-size: 13px;
  font-weight: 700;
  word-break: break-all;
}

.upload-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 20px;
  padding-top: 18px;
  border-top: 1px solid #f1f5f9;
}

.upload-actions span {
  color: #94a3b8;
  font-size: 12px;
}

.guide-list {
  display: grid;
  gap: 12px;
  margin-top: 16px;
}

.guide-item {
  display: flex;
  gap: 12px;
  border: 1px solid #eef2f7;
  border-radius: 8px;
  background: #f8fafc;
  padding: 14px;
}

.guide-item > .van-icon {
  margin-top: 2px;
  color: #2563eb;
  font-size: 20px;
}

.guide-item strong {
  color: #1e293b;
  font-size: 13px;
}

.guide-item p {
  font-size: 12px;
}

@media (max-width: 900px) {
  .student-settings {
    padding: 16px;
  }

  .settings-grid,
  .face-upload-panel {
    grid-template-columns: 1fr;
  }

  .face-preview {
    width: min(220px, 100%);
  }

  .face-meta dl {
    grid-template-columns: 1fr;
  }

  .upload-actions,
  .settings-header {
    align-items: stretch;
    flex-direction: column;
  }
}
</style>
