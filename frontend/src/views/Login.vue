<template>
  <div class="h-screen bg-slate-900 flex flex-col justify-center px-6">
    <div class="text-center mb-10">
      <h1 class="text-3xl font-bold text-white tracking-widest bg-clip-text text-transparent bg-gradient-to-r from-blue-400 to-indigo-500">AI POLICE</h1>
      <p class="text-slate-400 text-sm mt-2">虚拟警情模拟训练平台统一登录入口</p>
    </div>
    
    <van-form @submit="onSubmit" class="space-y-4">
      <van-cell-group inset class="!bg-slate-800 !border-none custom-group">
        <van-field
          v-model="username"
          name="username"
          placeholder="用户名"
          class="!bg-transparent !text-white"
          left-icon="contact"
        />
        <van-field
          v-model="password"
          type="password"
          name="password"
          placeholder="密码"
          class="!bg-transparent !text-white"
          left-icon="lock"
        />
      </van-cell-group>
      
      <div style="margin: 32px 16px;">
        <van-button round block type="primary" native-type="submit" class="!bg-indigo-600 !border-none !h-12 !shadow-lg">
          进入平台
        </van-button>
      </div>
    </van-form>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { showToast } from 'vant'
import request from '../utils/request'

const router = useRouter()
const username = ref('admin')
const password = ref('123456')

const onSubmit = async () => {
  try {
    const formData = new FormData()
    formData.append('username', username.value)
    formData.append('password', password.value)

    const res: any = await request.post('/auth/token', formData)
    localStorage.setItem('token', res.access_token)
    localStorage.setItem('username', res.username)
    localStorage.setItem('role', res.role)
    localStorage.setItem('user_id', String(res.user_id))
    
    showToast({ type: 'success', message: '登录成功' })
    router.push(res.role === 'student' ? '/student/hall' : '/admin/dashboard')
  } catch (e) {
    console.error('Login error:', e)
  }
}
</script>

<style scoped>
:deep(.van-field__control) {
  color: #fff !important;
}
:deep(.van-icon) {
  color: #94a3b8 !important;
}
</style>
