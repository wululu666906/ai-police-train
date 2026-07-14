<template>
  <div class="student-settings">
    <section class="settings-header">
      <div>
        <p class="settings-eyebrow">个人设置</p>
        <h1>{{ headerName }}</h1>
        <p class="settings-subtitle">维护训练身份、人脸识别档案和账号安全信息。个人照片上传后会同步进入管理端学员档案，用于训练前核验和训练过程识别。</p>
      </div>
      <div class="header-badges">
        <van-tag :type="faceProfile?.registered ? 'success' : 'warning'" plain>
          {{ faceProfile?.registered ? '人脸档案已建立' : '待上传人脸照片' }}
        </van-tag>
        <van-tag plain>学员端</van-tag>
      </div>
    </section>

    <section class="settings-grid settings-grid--top">
      <div class="settings-card account-card">
        <div class="avatar-block">
          <div class="avatar-preview">
            <img
              v-if="facePhotoReady"
              :src="faceProfile?.face_image_url"
              alt="学员照片"
              @error="markFacePhotoFailed"
            />
            <span v-else>{{ initials }}</span>
          </div>
          <div>
            <h2>账号摘要</h2>
            <p>{{ settings?.user.username || displayName }} · {{ studentCode }}</p>
          </div>
        </div>
        <div class="summary-grid">
          <div>
            <span>账号角色</span>
            <strong>{{ roleLabel }}</strong>
          </div>
          <div>
            <span>所属班级</span>
            <strong>{{ classLabel }}</strong>
          </div>
          <div>
            <span>创建时间</span>
            <strong>{{ fmtDateTime(settings?.user.created_at) }}</strong>
          </div>
          <div>
            <span>最近登录</span>
            <strong>{{ fmtDateTime(settings?.user.last_login_at) }}</strong>
          </div>
        </div>
      </div>

      <div class="settings-card safety-card">
        <div class="card-title-row">
          <div>
            <h2>账号安全</h2>
            <p>定期更新密码，保护训练记录和个人档案。</p>
          </div>
        </div>
        <div class="security-actions">
          <van-button plain type="primary" icon="lock" @click="showPasswordPopup = true">修改密码</van-button>
          <van-button plain icon="revoke" class="logout-btn" @click="handleLogout">安全退出</van-button>
        </div>
      </div>
    </section>

    <section class="settings-grid">
      <div class="settings-card profile-card">
        <div class="card-title-row">
          <div>
            <h2>个人资料</h2>
            <p>这些信息用于学员端展示和管理端识别，不影响登录账号。</p>
          </div>
          <van-button type="primary" size="small" :loading="savingProfile" @click="saveProfile">保存资料</van-button>
        </div>

        <div class="profile-form">
          <label>
            <span>显示名称</span>
            <input v-model.trim="profileForm.display_name" type="text" maxlength="80" placeholder="例如：张三" />
          </label>
          <label>
            <span>真实姓名</span>
            <input v-model.trim="profileForm.real_name" type="text" maxlength="80" placeholder="用于档案核对" />
          </label>
          <label>
            <span>单位</span>
            <input v-model.trim="profileForm.unit" type="text" maxlength="120" placeholder="例如：某某分局" />
          </label>
          <label>
            <span>部门</span>
            <input v-model.trim="profileForm.department" type="text" maxlength="120" placeholder="例如：巡逻防控大队" />
          </label>
          <label>
            <span>手机号</span>
            <input v-model.trim="profileForm.phone" type="tel" maxlength="30" placeholder="用于通知联系" />
          </label>
          <label>
            <span>邮箱</span>
            <input v-model.trim="profileForm.email" type="email" maxlength="120" placeholder="name@example.com" />
          </label>
          <label class="profile-form__wide">
            <span>个人简介</span>
            <textarea v-model.trim="profileForm.bio" maxlength="300" rows="4" placeholder="可填写岗位、训练目标或备注信息"></textarea>
          </label>
        </div>
      </div>

      <div class="settings-card face-card">
        <div class="card-title-row">
          <div>
            <h2>人脸识别档案</h2>
            <p>建议上传本人清晰正脸照片，画面中只保留一张人脸。</p>
          </div>
          <van-button size="small" plain :loading="faceLoading" @click="fetchFaceProfile">刷新</van-button>
        </div>

        <div class="face-upload-panel">
          <div class="face-preview">
            <img
              v-if="facePhotoReady"
              :src="faceProfile?.face_image_url"
              alt="学员人脸照片"
              @error="markFacePhotoFailed"
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
                <dt>识别模型</dt>
                <dd>{{ faceProfile?.embedding_model || faceEngineLabel }}</dd>
              </div>
              <div>
                <dt>更新时间</dt>
                <dd>{{ fmtDateTime(faceProfile?.updated_at) }}</dd>
              </div>
              <div>
                <dt>照片要求</dt>
                <dd>正脸、单人、无遮挡、光线清晰</dd>
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

        <div class="guide-list">
          <div class="guide-item">
            <van-icon name="user-circle-o" />
            <p>训练前比对当前摄像头画面与个人照片特征。</p>
          </div>
          <div class="guide-item">
            <van-icon name="video-o" />
            <p>训练中离开画面、多人入镜或非本人参与会记录为异常。</p>
          </div>
          <div class="guide-item">
            <van-icon name="records-o" />
            <p>管理员可在学员档案查看同一份照片和识别数据。</p>
          </div>
        </div>
      </div>
    </section>

    <van-popup v-model:show="showPasswordPopup" teleport="body" :style="{ width: 'min(460px, 94vw)', borderRadius: '8px', overflow: 'hidden' }">
      <div class="password-popup">
        <div class="popup-header">
          <h2>修改密码</h2>
          <van-icon name="cross" @click="showPasswordPopup = false" />
        </div>
        <div class="password-form">
          <label>
            <span>当前密码</span>
            <input v-model="passwordForm.current_password" type="password" autocomplete="current-password" />
          </label>
          <label>
            <span>新密码</span>
            <input v-model="passwordForm.new_password" type="password" autocomplete="new-password" />
          </label>
          <label>
            <span>确认新密码</span>
            <input v-model="passwordForm.confirm_password" type="password" autocomplete="new-password" />
          </label>
        </div>
        <div class="popup-actions">
          <van-button plain @click="showPasswordPopup = false">取消</van-button>
          <van-button type="primary" :loading="changingPassword" @click="changePassword">确认修改</van-button>
        </div>
      </div>
    </van-popup>
  </div>
</template>

<script setup lang="ts">
import { computed, inject, onMounted, onUnmounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { showConfirmDialog, showToast } from 'vant'
import request from '../utils/request'
import { clearAuth } from '../utils/auth'
import { resolveMediaUrl } from '../utils/media'

type SettingsUser = {
  id: number
  username: string
  role: string
  display_name?: string | null
  real_name?: string | null
  phone?: string | null
  email?: string | null
  unit?: string | null
  department?: string | null
  bio?: string | null
  created_at?: string | null
  last_login_at?: string | null
}

type SettingsResponse = {
  user: SettingsUser
  classes: string[]
}

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

const router = useRouter()
const setMainScrollable = inject<(value: boolean) => void>('setMainScrollable')
const settings = ref<SettingsResponse | null>(null)
const faceProfile = ref<FaceProfile | null>(null)
const faceEngine = ref<FaceEngine | null>(null)
const faceLoading = ref(false)
const faceUploading = ref(false)
const failedFacePhotoUrl = ref('')
const savingProfile = ref(false)
const changingPassword = ref(false)
const showPasswordPopup = ref(false)
const fileInputRef = ref<HTMLInputElement | null>(null)

const profileForm = reactive({
  display_name: '',
  real_name: '',
  phone: '',
  email: '',
  unit: '',
  department: '',
  bio: '',
})

const passwordForm = reactive({
  current_password: '',
  new_password: '',
  confirm_password: '',
})

const displayName = computed(() => settings.value?.user.username || localStorage.getItem('username') || '学员')
const headerName = computed(() => profileForm.display_name || profileForm.real_name || displayName.value)
const userId = computed(() => Number(settings.value?.user.id || localStorage.getItem('user_id') || 0))
const studentCode = computed(() => `STU${String(userId.value || 0).padStart(5, '0')}`)
const initials = computed(() => headerName.value.trim().slice(0, 2).toUpperCase() || 'ST')
const classLabel = computed(() => settings.value?.classes?.length ? settings.value.classes.join('、') : '暂未加入班级')
const roleLabel = computed(() => settings.value?.user.role === 'admin' ? '管理员' : '学员')
const faceEngineLabel = computed(() => (faceEngine.value?.model ? `insightface:${faceEngine.value.model}` : 'insightface:buffalo_l'))
const facePhotoReady = computed(() => {
  const url = faceProfile.value?.face_image_url || ''
  return Boolean(faceProfile.value?.registered && url && url !== failedFacePhotoUrl.value)
})

const fillProfileForm = (user: SettingsUser) => {
  profileForm.display_name = user.display_name || ''
  profileForm.real_name = user.real_name || ''
  profileForm.phone = user.phone || ''
  profileForm.email = user.email || ''
  profileForm.unit = user.unit || ''
  profileForm.department = user.department || ''
  profileForm.bio = user.bio || ''
}

const normalizeFaceProfile = (payload: any): FaceProfile => {
  const imageUrl = resolveMediaUrl(payload?.face_image_url)
  failedFacePhotoUrl.value = ''
  return {
    registered: Boolean(payload?.registered),
    student_id: payload?.student_id,
    face_image_url: imageUrl,
    embedding_model: payload?.embedding_model,
    updated_at: payload?.updated_at,
  }
}

const markFacePhotoFailed = () => {
  failedFacePhotoUrl.value = faceProfile.value?.face_image_url || ''
}

const fmtDateTime = (value: string | null | undefined) => {
  if (!value) return '--'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '--'
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')} ${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`
}

const fetchSettings = async () => {
  try {
    const result = await request.get('/auth/me/settings', { _skipErrorToast: true } as any)
    settings.value = result as SettingsResponse
    fillProfileForm((result as SettingsResponse).user)
  } catch (error: any) {
    showToast(error?.response?.data?.detail || '个人资料加载失败')
  }
}

const saveProfile = async () => {
  savingProfile.value = true
  try {
    const result = await request.put('/auth/me/settings', { ...profileForm }, { _skipErrorToast: true } as any)
    settings.value = result as SettingsResponse
    fillProfileForm((result as SettingsResponse).user)
    showToast({ type: 'success', message: '个人资料已保存' })
  } catch (error: any) {
    showToast(error?.response?.data?.detail || '个人资料保存失败')
  } finally {
    savingProfile.value = false
  }
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

const changePassword = async () => {
  if (!passwordForm.current_password || !passwordForm.new_password) {
    showToast('请填写当前密码和新密码')
    return
  }
  if (passwordForm.new_password.length < 6) {
    showToast('新密码至少需要 6 位')
    return
  }
  if (passwordForm.new_password !== passwordForm.confirm_password) {
    showToast('两次输入的新密码不一致')
    return
  }

  changingPassword.value = true
  try {
    await request.post('/auth/me/password', {
      current_password: passwordForm.current_password,
      new_password: passwordForm.new_password,
    }, { _skipErrorToast: true } as any)
    passwordForm.current_password = ''
    passwordForm.new_password = ''
    passwordForm.confirm_password = ''
    showPasswordPopup.value = false
    showToast({ type: 'success', message: '密码已修改' })
  } catch (error: any) {
    showToast(error?.response?.data?.detail || '密码修改失败')
  } finally {
    changingPassword.value = false
  }
}

const handleLogout = async () => {
  try {
    await showConfirmDialog({
      title: '确认退出',
      message: '确定要退出当前账号吗？',
      confirmButtonColor: '#1D3557',
    })
  } catch {
    return
  }
  clearAuth()
  router.push('/login')
}

onMounted(() => {
  setMainScrollable?.(true)
  fetchSettings()
  fetchFaceEngine()
  fetchFaceProfile()
})

onUnmounted(() => {
  setMainScrollable?.(false)
})
</script>

<style scoped>
.student-settings {
  max-width: 1180px;
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
.settings-card h2,
.popup-header h2 {
  margin: 0;
  color: #111827;
  font-weight: 800;
}

.settings-header h1 {
  font-size: 24px;
}

.settings-subtitle {
  max-width: 760px;
  margin: 8px 0 0;
  color: #64748b;
  font-size: 13px;
  line-height: 1.8;
}

.header-badges {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.settings-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.1fr) minmax(380px, 0.9fr);
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

.avatar-block {
  display: flex;
  align-items: center;
  gap: 14px;
}

.avatar-preview {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 72px;
  aspect-ratio: 1;
  overflow: hidden;
  border-radius: 8px;
  background: #eff6ff;
  color: #1d4ed8;
  font-size: 22px;
  font-weight: 900;
}

.avatar-preview img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  margin-top: 18px;
}

.summary-grid div {
  border: 1px solid #eef2f7;
  border-radius: 8px;
  background: #f8fafc;
  padding: 12px;
}

.summary-grid span,
.profile-form span,
.password-form span {
  display: block;
  color: #64748b;
  font-size: 12px;
  font-weight: 700;
}

.summary-grid strong {
  display: block;
  margin-top: 6px;
  color: #1e293b;
  font-size: 13px;
  word-break: break-word;
}

.security-actions {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
  margin-top: 20px;
}

.logout-btn {
  color: #dc2626;
}

.profile-form {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
  margin-top: 18px;
}

.profile-form label,
.password-form label {
  display: grid;
  gap: 8px;
}

.profile-form input,
.profile-form textarea,
.password-form input {
  width: 100%;
  border: 1px solid #dbe3ee;
  border-radius: 6px;
  background: #fff;
  padding: 10px 12px;
  color: #0f172a;
  font-size: 13px;
  outline: none;
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
}

.profile-form input:focus,
.profile-form textarea:focus,
.password-form input:focus {
  border-color: #93b4d6;
  box-shadow: 0 0 0 3px rgba(69, 123, 157, 0.1);
}

.profile-form textarea {
  resize: vertical;
}

.profile-form__wide {
  grid-column: 1 / -1;
}

.face-upload-panel {
  display: grid;
  grid-template-columns: 148px minmax(0, 1fr);
  gap: 18px;
  margin-top: 20px;
}

.face-preview {
  width: 148px;
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
  font-size: 26px;
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
  gap: 10px;
  margin: 14px 0 0;
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
  gap: 10px;
  margin-top: 16px;
}

.guide-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  border: 1px solid #eef2f7;
  border-radius: 8px;
  background: #f8fafc;
  padding: 12px;
}

.guide-item > .van-icon {
  margin-top: 2px;
  color: #2563eb;
  font-size: 18px;
}

.guide-item p {
  margin: 0;
  font-size: 12px;
}

.password-popup {
  background: #fff;
}

.popup-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid #eef2f7;
  padding: 16px 18px;
}

.popup-header h2 {
  font-size: 16px;
}

.popup-header .van-icon {
  color: #64748b;
  cursor: pointer;
}

.password-form {
  display: grid;
  gap: 14px;
  padding: 18px;
}

.popup-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  border-top: 1px solid #eef2f7;
  padding: 14px 18px;
}

@media (max-width: 980px) {
  .student-settings {
    padding: 16px;
  }

  .settings-grid,
  .settings-grid--top,
  .face-upload-panel,
  .profile-form {
    grid-template-columns: 1fr;
  }

  .summary-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .face-preview {
    width: min(220px, 100%);
  }

  .upload-actions,
  .settings-header {
    align-items: stretch;
    flex-direction: column;
  }
}
</style>
