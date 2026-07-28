<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { showConfirmDialog, showSuccessToast, showToast } from 'vant'
import request from '../utils/request'
import { clearAuth } from '../utils/auth'

type ProfileUser = {
  id: number
  username: string
  role: string
  avatar_url?: string | null
  display_name?: string | null
  phone?: string | null
  email?: string | null
  department?: string | null
  bio?: string | null
  created_at?: string | null
  last_login_at?: string | null
}

type SettingsResponse = {
  user: ProfileUser
  classes: string[]
}

const router = useRouter()
const apiBase = String((request as any).defaults?.baseURL || '').replace(/\/$/, '')

const loading = ref(false)
const savingProfile = ref(false)
const uploadingAvatar = ref(false)
const changingPassword = ref(false)
const showPasswordPopup = ref(false)
const avatarInputRef = ref<HTMLInputElement | null>(null)
const settings = ref<SettingsResponse | null>(null)

const profileForm = reactive({
  display_name: '',
  phone: '',
  email: '',
  department: '',
  bio: '',
})

const passwordForm = reactive({
  current_password: '',
  new_password: '',
  confirm_password: '',
})

const user = computed(() => settings.value?.user)
const accountName = computed(() => user.value?.username || localStorage.getItem('username') || '管理员')
const displayName = computed(() => profileForm.display_name || accountName.value)
const roleLabel = computed(() => user.value?.role === 'admin' ? '系统管理员' : '账号用户')
const accountCode = computed(() => `ID ${String(user.value?.id || localStorage.getItem('user_id') || 0).padStart(4, '0')}`)
const avatarUrl = computed(() => {
  const raw = String(user.value?.avatar_url || '').trim()
  if (!raw) return 'https://fastly.jsdelivr.net/npm/@vant/assets/cat.jpeg'
  return raw.startsWith('/') && apiBase ? `${apiBase}${raw}` : raw
})

const fillProfileForm = (nextUser: ProfileUser) => {
  profileForm.display_name = nextUser.display_name || ''
  profileForm.phone = nextUser.phone || ''
  profileForm.email = nextUser.email || ''
  profileForm.department = nextUser.department || ''
  profileForm.bio = nextUser.bio || ''
}

const fetchSettings = async () => {
  loading.value = true
  try {
    const result = await request.get('/auth/me/settings', { _skipErrorToast: true } as any)
    settings.value = result as SettingsResponse
    fillProfileForm((result as SettingsResponse).user)
  } catch (error: any) {
    showToast(error?.response?.data?.detail || '个人资料加载失败')
  } finally {
    loading.value = false
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

const handleAvatarChange = async (event: Event) => {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  if (!file.type.startsWith('image/')) {
    showToast('请选择图片文件')
    input.value = ''
    return
  }

  uploadingAvatar.value = true
  try {
    const form = new FormData()
    form.append('file', file)
    const result = await request.post('/auth/me/avatar', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
      _skipErrorToast: true,
      timeout: 120000,
    } as any)
    if (settings.value) settings.value.user = result as ProfileUser
    showToast({ type: 'success', message: '头像已更新' })
  } catch (error: any) {
    showToast(error?.response?.data?.detail || '头像上传失败')
  } finally {
    uploadingAvatar.value = false
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
    clearAuth()
    router.push('/login')
    showSuccessToast('已成功退出')
  } catch (error) {
    if (error) console.error(error)
  }
}

onMounted(fetchSettings)
</script>

<template>
  <div class="profile-page">
    <section class="profile-hero">
      <div class="profile-hero__cover">
        <div class="profile-avatar">
          <img :src="avatarUrl" alt="管理员头像" />
          <button type="button" :disabled="uploadingAvatar" @click="avatarInputRef?.click()">
            <van-icon name="photograph" />
            <span>{{ uploadingAvatar ? '上传中' : '更换头像' }}</span>
          </button>
          <input ref="avatarInputRef" type="file" accept="image/*" @change="handleAvatarChange" />
        </div>
      </div>

      <div class="profile-hero__body">
        <div class="profile-identity">
          <h2>{{ displayName }}</h2>
          <div class="profile-meta">
            <span><van-icon name="manager-o" /> {{ accountName }}</span>
            <i />
            <span>{{ accountCode }}</span>
            <i />
            <strong>{{ roleLabel }}</strong>
          </div>
        </div>
        <div class="profile-actions">
          <van-button plain type="primary" icon="lock" @click="showPasswordPopup = true">修改密码</van-button>
          <van-button round plain class="profile-logout-btn" @click="handleLogout">安全退出系统</van-button>
        </div>
      </div>
    </section>

    <section class="profile-card">
      <div class="profile-card__header">
        <div>
          <h3>个人资料</h3>
          <p>资料会同步到当前管理员账号，用于后台显示和联系信息维护。</p>
        </div>
        <van-button type="primary" :loading="savingProfile || loading" @click="saveProfile">保存资料</van-button>
      </div>

      <div class="profile-form">
        <label>
          <span>显示名称</span>
          <input v-model.trim="profileForm.display_name" type="text" maxlength="80" placeholder="例如：教务管理员" />
        </label>
        <label>
          <span>显示账号</span>
          <input :value="accountName" type="text" disabled />
        </label>
        <label>
          <span>手机号</span>
          <input v-model.trim="profileForm.phone" type="tel" maxlength="30" placeholder="用于通知联系" />
        </label>
        <label>
          <span>邮箱</span>
          <input v-model.trim="profileForm.email" type="email" maxlength="120" placeholder="name@example.com" />
        </label>
        <label>
          <span>部门</span>
          <input v-model.trim="profileForm.department" type="text" maxlength="120" placeholder="例如：训练管理中心" />
        </label>
        <label class="profile-form__wide">
          <span>个人简介</span>
          <textarea v-model.trim="profileForm.bio" maxlength="300" rows="4" placeholder="可填写岗位职责或备注信息"></textarea>
        </label>
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

<style scoped>
.profile-page {
  width: min(100%, 1180px);
  margin: 0 auto;
  padding: 0 0 80px;
}

.profile-hero,
.profile-card {
  border: 1px solid #e5e7eb;
  border-radius: 24px;
  background: #fff;
  box-shadow: 0 16px 40px rgb(15 23 42 / 6%);
}

.profile-hero {
  overflow: hidden;
}

.profile-hero__cover {
  position: relative;
  height: 154px;
  background: #1d3557;
}

.profile-avatar {
  position: absolute;
  left: 36px;
  bottom: -52px;
  width: 112px;
  height: 112px;
  overflow: hidden;
  border: 5px solid #fff;
  border-radius: 24px;
  background: #fff;
  box-shadow: 0 16px 28px rgb(15 23 42 / 16%);
}

.profile-avatar img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.profile-avatar button {
  position: absolute;
  inset: auto 0 0;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  width: 100%;
  height: 34px;
  border: 0;
  background: rgb(15 23 42 / 72%);
  color: #fff;
  font-size: 12px;
  font-weight: 800;
  cursor: pointer;
}

.profile-avatar input {
  display: none;
}

.profile-hero__body {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 24px;
  min-width: 0;
  padding: 72px 36px 36px;
}

.profile-identity {
  min-width: 0;
}

.profile-identity h2 {
  margin: 0;
  color: #111827;
  font-size: 32px;
  font-weight: 900;
  line-height: 1.15;
  overflow-wrap: anywhere;
}

.profile-meta {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 10px;
  color: #9ca3af;
  font-size: 16px;
  font-weight: 700;
}

.profile-meta span {
  display: inline-flex;
  align-items: center;
  gap: 5px;
}

.profile-meta i {
  width: 1px;
  height: 18px;
  background: #cbd5e1;
}

.profile-meta strong {
  color: #457b9d;
}

.profile-actions {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 12px;
  flex: 0 0 auto;
}

.profile-logout-btn {
  border-color: #fecaca !important;
  color: #ef4444 !important;
  background: #fff !important;
}

.profile-logout-btn:hover {
  background: #fef2f2 !important;
}

.profile-card {
  margin-top: 24px;
  padding: 30px 36px 36px;
}

.profile-card__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  margin-bottom: 24px;
}

.profile-card__header h3 {
  margin: 0;
  color: #1f2937;
  font-size: 20px;
  font-weight: 900;
}

.profile-card__header p {
  margin: 6px 0 0;
  color: #94a3b8;
  font-size: 13px;
  line-height: 1.6;
}

.profile-form,
.password-form {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 18px;
}

.profile-form label,
.password-form label {
  display: grid;
  gap: 8px;
}

.profile-form span,
.password-form span {
  color: #64748b;
  font-size: 13px;
  font-weight: 800;
}

.profile-form input,
.profile-form textarea,
.password-form input {
  width: 100%;
  min-width: 0;
  border: 1px solid #dbe3ee;
  border-radius: 8px;
  background: #f8fafc;
  color: #1f2937;
  font-size: 14px;
  line-height: 1.4;
  outline: none;
  padding: 11px 12px;
  transition: border-color 0.16s ease, box-shadow 0.16s ease, background 0.16s ease;
}

.profile-form input:disabled {
  color: #64748b;
  cursor: not-allowed;
}

.profile-form textarea {
  resize: vertical;
}

.profile-form input:focus,
.profile-form textarea:focus,
.password-form input:focus {
  border-color: #1d4ed8;
  background: #fff;
  box-shadow: 0 0 0 3px rgb(37 99 235 / 10%);
}

.profile-form__wide {
  grid-column: 1 / -1;
}

.password-popup {
  padding: 24px;
  background: #fff;
}

.popup-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 18px;
}

.popup-header h2 {
  margin: 0;
  color: #111827;
  font-size: 20px;
  font-weight: 900;
}

.popup-header .van-icon {
  cursor: pointer;
}

.password-form {
  grid-template-columns: 1fr;
}

.popup-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 22px;
}

@media (max-width: 720px) {
  .profile-page {
    padding-bottom: 48px;
  }

  .profile-hero__cover {
    height: 128px;
  }

  .profile-avatar {
    left: 24px;
    width: 96px;
    height: 96px;
  }

  .profile-hero__body,
  .profile-card__header {
    align-items: flex-start;
    flex-direction: column;
  }

  .profile-hero__body {
    padding: 64px 24px 28px;
  }

  .profile-card {
    padding: 24px;
  }

  .profile-identity h2 {
    font-size: 26px;
  }

  .profile-actions,
  .profile-actions .van-button,
  .profile-card__header .van-button {
    width: 100%;
  }

  .profile-form {
    grid-template-columns: 1fr;
  }
}
</style>
