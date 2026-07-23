<template>
  <div class="mx-auto max-w-5xl space-y-5 pb-16">
    <div class="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
      <div>
        <h1 class="text-2xl font-bold text-gray-800">API Key</h1>
        <p class="mt-1 text-sm text-gray-500">千问负责语音识别与可选文字能力，DeepSeek 负责文字生成；配置会同时保留。</p>
      </div>
      <div class="flex flex-wrap gap-3">
        <van-button plain type="primary" icon="plus" @click="addProfile">新增 Key</van-button>
        <van-button plain type="primary" :loading="loading" @click="loadConfig">重新加载</van-button>
        <van-button type="primary" class="!bg-[#1D3557] !border-none" :loading="saving" @click="saveConfig">保存配置</van-button>
      </div>
    </div>

    <div v-if="restartRequired" class="rounded-[8px] border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
      配置已写入 env 文件。后端重启后，语音和文字生成会按平台分工同时使用对应模型接口。
    </div>

    <div class="rounded-[8px] border border-gray-100 bg-white p-4 shadow-sm">
      <div class="grid grid-cols-1 gap-5 md:grid-cols-[1fr_220px]">
        <el-form-item label="请求超时（秒）" class="!mb-0">
          <el-input-number v-model="timeoutSeconds" :min="5" :max="1800" :step="5" class="w-full" />
        </el-form-item>
        <div class="rounded-[8px] bg-slate-50 px-4 py-3 text-sm text-slate-600">
          <div class="font-semibold text-slate-700">env 文件位置</div>
          <div class="mt-1 break-all text-xs">{{ envPath || '加载后显示' }}</div>
        </div>
      </div>
    </div>

    <div class="space-y-4">
      <div
        v-for="(profile, index) in profiles"
        :key="profile.id"
        class="rounded-[8px] border border-gray-100 bg-white p-5 shadow-sm"
      >
        <div class="mb-4 flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
          <div class="min-w-0">
            <div class="flex flex-wrap items-center gap-2">
              <h2 class="truncate text-lg font-bold text-gray-800">{{ profile.name || defaultName(profile.provider, index) }}</h2>
              <van-tag v-if="profile.built_in" plain>内置</van-tag>
            </div>
            <p class="mt-1 text-xs text-gray-400">{{ usageText(profile.provider) }}</p>
          </div>
          <div class="flex shrink-0 items-center gap-3">
            <van-button v-if="!profile.built_in" size="small" plain type="danger" @click="removeProfile(profile.id)">删除</van-button>
          </div>
        </div>

        <el-form label-position="top" class="api-config-form">
          <div class="grid grid-cols-1 gap-5 md:grid-cols-2">
            <el-form-item label="卡片名称">
              <el-input v-model="profile.name" placeholder="例如 内网模型 A / DeepSeek 生产 Key" clearable />
            </el-form-item>

            <el-form-item label="模型提供方">
              <el-select v-model="profile.provider" class="w-full" :disabled="profile.built_in">
                <el-option label="内网本地模型（OpenAI 兼容）" value="custom" />
                <el-option label="通义千问 / 百炼" value="qwen" />
                <el-option label="DeepSeek" value="deepseek" />
              </el-select>
            </el-form-item>

            <el-form-item label="模型名称">
              <el-input v-model="profile.chat_model" placeholder="例如 qwen-plus / deepseek-v4-flash / local-model" clearable />
            </el-form-item>

            <el-form-item label="模型请求地址">
              <el-input v-model="profile.base_url" placeholder="例如 http://192.168.1.10:8000/v1" clearable />
            </el-form-item>

            <el-form-item label="API Key">
              <el-input v-model="profile.api_key" type="password" show-password placeholder="本地模型不需要时可填写 not-required 或留空" clearable />
            </el-form-item>

            <el-form-item label="最大输出 Token">
              <el-input-number v-model="profile.max_output_tokens" :min="1" :max="200000" :step="1024" class="w-full" />
            </el-form-item>

            <template v-if="profile.provider === 'qwen'">
              <el-form-item label="Workspace ID">
                <el-input v-model="profile.workspace_id" placeholder="百炼 Workspace ID，可留空" clearable />
              </el-form-item>

              <el-form-item label="区域">
                <el-input v-model="profile.region" placeholder="例如 cn-beijing" clearable />
              </el-form-item>

              <el-form-item label="语音请求地址">
                <el-input v-model="profile.asr_base_url" placeholder="例如 https://.../compatible-mode/v1" clearable />
              </el-form-item>

              <el-form-item label="语音模型名称">
                <el-input v-model="profile.asr_model" placeholder="例如 qwen3-asr-flash" clearable />
              </el-form-item>

              <el-form-item label="实时语音地址">
                <el-input v-model="profile.realtime_url" placeholder="例如 wss://.../api-ws/v1/realtime" clearable />
              </el-form-item>

              <el-form-item label="实时语音模型">
                <el-input v-model="profile.realtime_model" placeholder="例如 qwen3-asr-flash-realtime" clearable />
              </el-form-item>
            </template>
          </div>
        </el-form>
      </div>
    </div>

    <div class="rounded-[8px] border border-blue-100 bg-blue-50/60 p-4 text-sm leading-7 text-blue-800">
      千问、DeepSeek 与新增的内网模型卡片会同时保存在 env 中。平台会按功能分工使用：语音识别读取千问配置，文字生成优先读取 DeepSeek 配置；新增内网模型作为后续内网替换方案保留。
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { showConfirmDialog, showToast } from 'vant'
import request from '../utils/request'

type LlmProvider = 'custom' | 'qwen' | 'deepseek'

type LlmProfile = {
  id: string
  provider: LlmProvider
  name: string
  base_url: string
  api_key: string
  chat_model: string
  long_output_model: string
  max_output_tokens: number
  workspace_id: string
  region: string
  asr_base_url: string
  asr_model: string
  realtime_url: string
  realtime_model: string
  built_in?: boolean
}

const loading = ref(false)
const saving = ref(false)
const restartRequired = ref(false)
const envPath = ref('')
const timeoutSeconds = ref(90)
const profiles = ref<LlmProfile[]>([])

const defaultName = (provider: LlmProvider, index: number) => {
  if (provider === 'qwen') return '通义千问 / 百炼'
  if (provider === 'deepseek') return 'DeepSeek'
  return `内网本地模型 ${index + 1}`
}

const defaultModel = (provider: LlmProvider) => {
  if (provider === 'qwen') return 'qwen-plus'
  if (provider === 'deepseek') return 'deepseek-v4-flash'
  return ''
}

const defaultMaxTokens = (provider: LlmProvider) => {
  if (provider === 'deepseek') return 128000
  return 32768
}

const usageText = (provider: LlmProvider) => {
  if (provider === 'qwen') return '用途：语音识别、实时语音和可选文字能力。'
  if (provider === 'deepseek') return '用途：文字生成、案件解析、评估报告和内容生成。'
  return '用途：内网 OpenAI 兼容模型，作为本地替换方案保留。'
}

const createProfile = (index: number): LlmProfile => ({
  id: `custom-${Date.now()}-${index}`,
  provider: 'custom',
  name: `内网本地模型 ${index + 1}`,
  base_url: '',
  api_key: '',
  chat_model: '',
  long_output_model: '',
  max_output_tokens: 32768,
  workspace_id: '',
  region: '',
  asr_base_url: '',
  asr_model: '',
  realtime_url: '',
  realtime_model: '',
  built_in: false,
})

const normalizeProfile = (payload: any, index: number): LlmProfile => ({
  id: payload?.id || `custom-${index + 1}`,
  provider: (payload?.provider || 'custom') as LlmProvider,
  name: payload?.name || defaultName(payload?.provider || 'custom', index),
  base_url: payload?.base_url || '',
  api_key: payload?.api_key || '',
  chat_model: payload?.chat_model || defaultModel(payload?.provider || 'custom'),
  long_output_model: payload?.chat_model || payload?.long_output_model || defaultModel(payload?.provider || 'custom'),
  max_output_tokens: Number(payload?.max_output_tokens || defaultMaxTokens(payload?.provider || 'custom')),
  workspace_id: payload?.workspace_id || '',
  region: payload?.region || '',
  asr_base_url: payload?.asr_base_url || '',
  asr_model: payload?.asr_model || '',
  realtime_url: payload?.realtime_url || '',
  realtime_model: payload?.realtime_model || '',
  built_in: Boolean(payload?.built_in),
})

const fillForm = (payload: any) => {
  profiles.value = Array.isArray(payload?.profiles) ? payload.profiles.map(normalizeProfile) : []
  if (!profiles.value.length) {
    profiles.value = [
      {
        ...createProfile(0),
        id: 'qwen',
        provider: 'qwen',
        name: '通义千问 / 百炼',
        chat_model: 'qwen-plus',
        long_output_model: 'qwen-plus',
        max_output_tokens: 32768,
        region: 'cn-beijing',
        asr_model: 'qwen3-asr-flash',
        realtime_model: 'qwen3-asr-flash-realtime',
        built_in: true,
      },
      {
        ...createProfile(1),
        id: 'deepseek',
        provider: 'deepseek',
        name: 'DeepSeek',
        chat_model: 'deepseek-v4-flash',
        long_output_model: 'deepseek-v4-flash',
        max_output_tokens: 128000,
        built_in: true,
      },
      createProfile(2),
    ]
  }
  timeoutSeconds.value = Number(payload?.timeout_seconds || 90)
  envPath.value = payload?.env_path || ''
  restartRequired.value = Boolean(payload?.restart_required)
}

const loadConfig = async () => {
  loading.value = true
  try {
    const result = await request.get('/llm-config', { _skipErrorToast: true } as any)
    fillForm(result)
  } catch (error: any) {
    showToast(error?.response?.data?.detail || '模型接口配置加载失败')
  } finally {
    loading.value = false
      }
  }

const addProfile = () => {
  profiles.value.push(createProfile(profiles.value.length))
}

const removeProfile = async (id: string) => {
  try {
    await showConfirmDialog({
      title: '删除配置',
      message: '确定删除这张 API Key 配置卡片吗？',
      confirmButtonColor: '#1D3557',
    })
    profiles.value = profiles.value.filter((profile) => profile.id !== id)
  } catch {
    // cancelled
  }
}

const validateProfiles = () => {
  for (const profile of profiles.value) {
    const hasCustomContent = Boolean(
      profile.base_url.trim() || profile.api_key.trim() || profile.chat_model.trim(),
    )
    if (profile.provider === 'custom' && hasCustomContent && (!profile.base_url.trim() || !profile.chat_model.trim())) {
      return `${profile.name || '内网本地模型'} 请填写模型请求地址和模型名称`
    }
  }
  return ''
}

const saveConfig = async () => {
  const message = validateProfiles()
  if (message) {
    showToast(message)
    return
  }

  saving.value = true
  try {
    const result: any = await request.put(
      '/llm-config',
      {
        timeout_seconds: timeoutSeconds.value,
        profiles: profiles.value.map((profile) => ({
          ...profile,
          long_output_model: profile.chat_model,
        })),
      },
      { _skipErrorToast: true } as any,
    )
    restartRequired.value = Boolean(result?.restart_required)
    envPath.value = result?.env_path || envPath.value
    showToast({ type: 'success', message: result?.message || '模型接口配置已保存' })
  } catch (error: any) {
    showToast(error?.response?.data?.detail || '模型接口配置保存失败')
  } finally {
    saving.value = false
  }
}

onMounted(loadConfig)
</script>

<style scoped>
.api-config-form :deep(.el-input-number) {
  width: 100%;
}

.api-config-form :deep(.el-input-number .el-input__wrapper) {
  width: 100%;
}
</style>
