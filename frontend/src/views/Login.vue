<template>
  <div class="min-h-screen login-shell">
    <div class="login-backdrop"></div>

    <div class="relative z-10 min-h-screen flex items-center justify-center px-5 py-10">
      <div class="w-full max-w-[1120px] grid grid-cols-1 lg:grid-cols-[1.08fr_0.92fr] gap-8 items-stretch">
        <section class="hero-panel">
          <div class="hero-badge">项目简介</div>
          <h1 class="hero-title">统一身份登录</h1>
          <p class="hero-desc">
            本平台面向警情处置模拟训练、教学组织与训练评估场景，支持案件剧本管理、角色配置、学员对话训练、过程记录与结果评估，帮助院校和单位搭建更完整的实战化训练闭环。
          </p>

          <div class="hero-feature-list">
            <div class="hero-feature">
              <div class="hero-feature__icon"><van-icon name="shield-o" size="20" /></div>
              <div>
                <div class="hero-feature__title">训练组织</div>
                <div class="hero-feature__desc">支持案件、场景、角色与知识内容的统一配置，便于课程建设与批量组织训练。</div>
              </div>
            </div>
            <div class="hero-feature">
              <div class="hero-feature__icon"><van-icon name="records-o" size="20" /></div>
              <div>
                <div class="hero-feature__title">模拟对话</div>
                <div class="hero-feature__desc">围绕真实警情处置流程开展多轮问询与应对训练，沉淀完整训练过程数据。</div>
              </div>
            </div>
            <div class="hero-feature">
              <div class="hero-feature__icon"><van-icon name="cluster-o" size="20" /></div>
              <div>
                <div class="hero-feature__title">评估反馈</div>
                <div class="hero-feature__desc">自动汇总训练记录、关键信息获取情况与评估结果，辅助复盘改进与教学分析。</div>
              </div>
            </div>
          </div>
        </section>

        <section class="login-card">
          <div class="login-card__top">
            <div>
              <div class="login-card__brand">警情处置模拟训练平台</div>
              <h2 class="login-card__title">密码登录</h2>
              <p class="login-card__subtitle">请输入学号或系统账号与登录密码</p>
            </div>
            <div class="login-card__mark">Secure</div>
          </div>

          <van-form @submit="onSubmit" class="space-y-5">
            <div class="field-block">
              <label class="field-label">学号 / 系统账号</label>
              <div class="field-shell">
                <van-icon name="contact" class="field-icon" />
                <van-field
                  v-model="account"
                  name="username"
                  placeholder="请输入学号或系统账号"
                  class="field-input"
                  autocomplete="username"
                />
              </div>
            </div>

            <div class="field-block">
              <label class="field-label">密码</label>
              <div class="field-shell">
                <van-icon name="lock" class="field-icon" />
                <van-field
                  v-model="password"
                  :type="showPassword ? 'text' : 'password'"
                  name="password"
                  placeholder="请输入密码"
                  class="field-input"
                  autocomplete="current-password"
                />
                <button type="button" class="field-action" @click="showPassword = !showPassword">
                  {{ showPassword ? '隐藏' : '显示' }}
                </button>
              </div>
            </div>

            <div class="login-tip">
              管理员与学员共用统一入口，登录后会根据账号角色自动进入对应工作区。
            </div>

            <van-button
              round
              block
              type="primary"
              native-type="submit"
              :loading="submitting"
              class="login-submit"
            >
              登录
            </van-button>
          </van-form>
        </section>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { showToast } from 'vant'
import { persistAuth } from '../utils/auth'
import request from '../utils/request'

const router = useRouter()
const account = ref('')
const password = ref('')
const showPassword = ref(false)
const submitting = ref(false)

const onSubmit = async () => {
  if (submitting.value) return

  const safeAccount = account.value.trim()
  const safePassword = password.value.trim()
  if (!safeAccount || !safePassword) {
    showToast({ type: 'fail', message: '请输入学号或系统账号，以及登录密码' })
    return
  }

  submitting.value = true
  try {
    const formData = new FormData()
    formData.append('username', safeAccount)
    formData.append('password', safePassword)

    const res: any = await request.post('/auth/token', formData, { _skipErrorToast: true } as any)
    persistAuth(res)

    showToast({ type: 'success', message: '登录成功' })
    await router.push(res.role === 'student' ? '/student/hall' : '/admin/dashboard')
  } catch (error: any) {
    console.error('Login error:', error)
    const detail = String(error?.response?.data?.detail || '').trim()
    const message = detail === 'Incorrect account or password' ? '账号或密码错误，请重新输入' : detail || '登录失败，请稍后重试'
    showToast({ type: 'fail', message })
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
.login-shell {
  position: relative;
  overflow: hidden;
  background:
    radial-gradient(circle at top left, rgba(52, 116, 255, 0.2), transparent 34%),
    radial-gradient(circle at bottom right, rgba(16, 185, 129, 0.14), transparent 28%),
    linear-gradient(135deg, #f3f7fc 0%, #e8eef7 48%, #f8fbff 100%);
}

.login-backdrop {
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(rgba(22, 50, 79, 0.04) 1px, transparent 1px),
    linear-gradient(90deg, rgba(22, 50, 79, 0.04) 1px, transparent 1px);
  background-size: 22px 22px;
  mask-image: linear-gradient(180deg, rgba(0, 0, 0, 0.9), rgba(0, 0, 0, 0.35));
}

.hero-panel {
  position: relative;
  border-radius: 36px;
  padding: 48px 44px;
  overflow: hidden;
  color: white;
  background:
    linear-gradient(160deg, rgba(14, 36, 63, 0.98) 0%, rgba(22, 50, 79, 0.95) 48%, rgba(24, 95, 142, 0.92) 100%);
  box-shadow: 0 32px 80px rgba(22, 50, 79, 0.24);
}

.hero-panel::before {
  content: '';
  position: absolute;
  width: 240px;
  height: 240px;
  right: -70px;
  top: -80px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.08);
}

.hero-panel::after {
  content: '';
  position: absolute;
  width: 180px;
  height: 180px;
  left: -36px;
  bottom: -48px;
  border-radius: 999px;
  background: rgba(125, 211, 252, 0.12);
}

.hero-badge {
  display: inline-flex;
  align-items: center;
  height: 34px;
  padding: 0 16px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.08);
  border: 1px solid rgba(255, 255, 255, 0.12);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.2em;
  text-transform: uppercase;
}

.hero-title {
  margin: 26px 0 0;
  font-size: 44px;
  line-height: 1.08;
  font-weight: 800;
  letter-spacing: 0.04em;
}

.hero-desc {
  margin: 20px 0 0;
  max-width: 560px;
  color: rgba(235, 245, 255, 0.84);
  line-height: 1.9;
  font-size: 15px;
}

.hero-feature-list {
  position: relative;
  z-index: 1;
  margin-top: 34px;
  display: grid;
  gap: 16px;
}

.hero-feature {
  display: grid;
  grid-template-columns: 52px minmax(0, 1fr);
  gap: 14px;
  align-items: start;
  padding: 16px 18px;
  border-radius: 22px;
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.08);
  backdrop-filter: blur(10px);
}

.hero-feature__icon {
  width: 52px;
  height: 52px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.1);
}

.hero-feature__title {
  font-size: 16px;
  font-weight: 700;
}

.hero-feature__desc {
  margin-top: 6px;
  font-size: 13px;
  line-height: 1.8;
  color: rgba(230, 240, 252, 0.76);
}

.login-card {
  border-radius: 36px;
  background: rgba(255, 255, 255, 0.82);
  border: 1px solid rgba(255, 255, 255, 0.7);
  box-shadow: 0 28px 80px rgba(15, 23, 42, 0.12);
  padding: 40px 36px;
  backdrop-filter: blur(18px);
}

.login-card__top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 28px;
}

.login-card__brand {
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.28em;
  color: #5f6f86;
  text-transform: uppercase;
}

.login-card__title {
  margin: 12px 0 0;
  font-size: 32px;
  font-weight: 800;
  color: #11263d;
}

.login-card__subtitle {
  margin-top: 10px;
  font-size: 14px;
  color: #64748b;
}

.login-card__mark {
  min-width: 76px;
  height: 34px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0 14px;
  border-radius: 999px;
  background: #eff6ff;
  color: #1d4ed8;
  font-size: 12px;
  font-weight: 700;
}

.field-block {
  display: grid;
  gap: 10px;
}

.field-label {
  font-size: 13px;
  font-weight: 700;
  color: #334155;
}

.field-shell {
  display: flex;
  align-items: center;
  gap: 10px;
  min-height: 58px;
  padding: 0 16px;
  border-radius: 18px;
  border: 1px solid #d7e3f4;
  background: rgba(248, 251, 255, 0.95);
  transition: border-color 0.2s ease, box-shadow 0.2s ease, background 0.2s ease;
}

.field-shell:focus-within {
  border-color: #7aa2ff;
  background: #fff;
  box-shadow: 0 0 0 4px rgba(59, 130, 246, 0.12);
}

.field-icon {
  color: #6b7b91;
  flex-shrink: 0;
}

.field-input {
  flex: 1;
  padding: 0;
  background: transparent !important;
}

.field-action {
  border: none;
  background: transparent;
  color: #2563eb;
  font-size: 13px;
  font-weight: 700;
}

.login-tip {
  padding: 14px 16px;
  border-radius: 18px;
  background: #f8fafc;
  color: #64748b;
  font-size: 13px;
  line-height: 1.8;
}

.login-submit {
  height: 52px !important;
  border: none !important;
  background: linear-gradient(135deg, #16324f 0%, #1d4f7a 100%) !important;
  box-shadow: 0 18px 36px rgba(22, 50, 79, 0.22);
  font-weight: 700;
  letter-spacing: 0.06em;
}

:deep(.van-field__body),
:deep(.van-field__value),
:deep(.van-field__control) {
  background: transparent !important;
}

:deep(.van-field__control) {
  color: #0f172a !important;
  font-size: 15px;
}

:deep(.van-field__control::placeholder) {
  color: #94a3b8;
}

@media (max-width: 1023px) {
  .hero-panel {
    padding: 34px 28px;
  }

  .hero-title {
    font-size: 34px;
  }

  .login-card {
    padding: 30px 24px;
  }
}
</style>
