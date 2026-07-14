<template>
  <main class="ops-login">
    <section class="ops-login__panel">
      <div class="ops-login__intro">
        <div class="ops-login__badge">
          <OpsIcon name="shield" :size="34" />
        </div>
        <div class="ops-login__eyebrow">维护控制台</div>
        <h1>账号维护端</h1>
        <p>用于开发者和维护人员开通、调整和回收管理端与学员端账号。</p>
      </div>

      <form class="ops-login__form" @submit.prevent="onSubmit">
        <div>
          <label>维护账号</label>
          <div class="ops-field">
            <OpsIcon name="user" />
            <input v-model.trim="account" autocomplete="username" placeholder="maintainer" />
          </div>
        </div>

        <div>
          <label>密码</label>
          <div class="ops-field">
            <OpsIcon name="lock" />
            <input
              v-model.trim="password"
              :type="showPassword ? 'text' : 'password'"
              autocomplete="current-password"
              placeholder="请输入维护端密码"
            />
            <button type="button" @click="showPassword = !showPassword">
              {{ showPassword ? '隐藏' : '显示' }}
            </button>
          </div>
        </div>

        <div class="ops-login__hint">默认维护账号为“maintainer”，初始密码为“123456”，生产环境首次登录后请立即改密。</div>

        <van-button block type="primary" native-type="submit" :loading="submitting" class="ops-login__submit">
          登录维护端
        </van-button>
      </form>
    </section>
  </main>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { showToast } from 'vant'
import request from '../utils/request'
import { persistAuth } from '../utils/auth'
import OpsIcon from '../components/OpsIcon.vue'

const router = useRouter()
const account = ref('maintainer')
const password = ref('123456')
const showPassword = ref(false)
const submitting = ref(false)

const onSubmit = async () => {
  if (!account.value || !password.value) {
    showToast({ type: 'fail', message: '请输入维护账号和密码' })
    return
  }
  submitting.value = true
  try {
    const formData = new FormData()
    formData.append('username', account.value)
    formData.append('password', password.value)
    const res: any = await request.post('/auth/token', formData, { _skipErrorToast: true } as any)
    persistAuth(res)
    if (res.role !== 'maintainer') {
      showToast({ type: 'fail', message: '当前账号没有维护端权限' })
      await router.push(res.role === 'student' ? '/student/hall' : '/admin/dashboard')
      return
    }
    showToast({ type: 'success', message: '登录成功' })
    await router.push('/ops/accounts')
  } catch (error: any) {
    const detail = String(error?.response?.data?.detail || '').trim()
    showToast({ type: 'fail', message: detail || '账号或密码错误' })
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
.ops-login {
  min-height: 100vh;
  display: grid;
  place-items: center;
  padding: 32px 20px;
  background:
    linear-gradient(90deg, rgba(15, 23, 42, 0.06) 1px, transparent 1px),
    linear-gradient(rgba(15, 23, 42, 0.06) 1px, transparent 1px),
    #eef2f7;
  background-size: 28px 28px;
}

.ops-login__panel {
  width: min(920px, 100%);
  display: grid;
  grid-template-columns: 1fr 390px;
  overflow: hidden;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  background: #fff;
  box-shadow: 0 24px 80px rgba(15, 23, 42, 0.16);
}

.ops-login__intro {
  padding: 56px;
  color: #fff;
  background: #172033;
}

.ops-login__eyebrow {
  font-size: 12px;
  font-weight: 800;
  color: #9cc4ff;
  letter-spacing: 0.18em;
}

.ops-login__badge {
  width: 56px;
  height: 56px;
  display: grid;
  place-items: center;
  border-radius: 8px;
  background: rgba(37, 99, 235, 0.18);
  color: #bfdbfe;
  box-shadow: inset 0 0 0 1px rgba(191, 219, 254, 0.18);
  margin-bottom: 24px;
}

.ops-login__intro h1 {
  margin: 24px 0 0;
  font-size: 38px;
  font-weight: 900;
}

.ops-login__intro p {
  max-width: 420px;
  margin: 18px 0 0;
  color: #cbd5e1;
  line-height: 1.9;
}

.ops-login__form {
  display: grid;
  gap: 18px;
  align-content: center;
  padding: 42px 36px;
}

.ops-login__form label {
  display: block;
  margin-bottom: 8px;
  color: #334155;
  font-size: 13px;
  font-weight: 800;
}

.ops-field {
  display: flex;
  align-items: center;
  gap: 10px;
  height: 44px;
  border: 1px solid #cbd5e1;
  border-radius: 6px;
  padding: 0 12px;
  background: #f8fafc;
}

.ops-field input {
  min-width: 0;
  flex: 1;
  border: 0;
  outline: none;
  background: transparent;
  color: #0f172a;
}

.ops-field button {
  border: 0;
  background: transparent;
  color: #1d4ed8;
  font-size: 13px;
  font-weight: 800;
}

.ops-login__hint {
  padding: 12px;
  border: 1px solid #fde68a;
  border-radius: 6px;
  background: #fffbeb;
  color: #92400e;
  font-size: 13px;
  line-height: 1.7;
}

.ops-login__submit {
  height: 44px !important;
  border-radius: 6px !important;
}

@media (max-width: 820px) {
  .ops-login__panel {
    grid-template-columns: 1fr;
  }

  .ops-login__intro {
    padding: 32px;
  }
}
</style>
