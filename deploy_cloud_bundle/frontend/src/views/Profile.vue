<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { showConfirmDialog, showSuccessToast } from 'vant'

const router = useRouter()
const user = ref({
  name: localStorage.getItem('username') || '警员 8927',
  role: '系统管理员',
  id: 'POLICE_ID_001',
  email: 'admin@police.gov.cn',
  avatar: 'https://fastly.jsdelivr.net/npm/@vant/assets/cat.jpeg'
})

const handleLogout = async () => {
    try {
        await showConfirmDialog({
            title: '确认退出',
            message: '您确定要退出 AI 虚拟警情模拟训练平台吗？',
            confirmButtonColor: '#1D3557'
        })
        localStorage.removeItem('token')
        localStorage.removeItem('username')
        router.push('/login')
        showSuccessToast('已成功退出')
    } catch (e) {
        // Cancelled
    }
}
</script>

<template>
  <div class="space-y-6 pb-20 max-w-4xl mx-auto">
    <!-- Profile Header Card -->
    <div class="bg-white rounded-[2rem] shadow-sm border border-gray-100 overflow-hidden">
        <div class="h-32 bg-[#1D3557] relative">
            <div class="absolute -bottom-12 left-8">
                <div class="w-24 h-24 rounded-3xl border-4 border-white overflow-hidden shadow-lg bg-white">
                    <img :src="user.avatar" class="w-full h-full object-cover"/>
                </div>
            </div>
        </div>
        <div class="pt-16 pb-8 px-8 flex justify-between items-end">
            <div>
                <h2 class="text-2xl font-black text-gray-800">{{ user.name }}</h2>
                <div class="flex items-center space-x-3 mt-1 text-gray-400 text-sm">
                    <span class="flex items-center"><van-icon name="v-card" class="mr-1"/> {{ user.id }}</span>
                    <span>•</span>
                    <span class="text-[#457B9D] font-bold">{{ user.role }}</span>
                </div>
            </div>
            <van-button icon="edit" plain round size="small" class="!border-gray-200 !text-gray-400">编辑资料</van-button>
        </div>
    </div>

    <!-- Info Sections -->
    <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div class="bg-white rounded-3xl shadow-sm border border-gray-100 p-8">
            <h3 class="font-bold text-gray-700 mb-6 flex items-center">
                <van-icon name="setting-o" class="mr-2 text-[#1D3557]"/> 系统偏好设置
            </h3>
            <div class="space-y-4">
                <div class="flex items-center justify-between p-4 bg-gray-50 rounded-2xl">
                    <div class="text-sm font-medium text-gray-600">界面语言</div>
                    <div class="text-xs text-gray-400 font-bold">简体中文</div>
                </div>
                <div class="flex items-center justify-between p-4 bg-gray-50 rounded-2xl">
                    <div class="text-sm font-medium text-gray-600">自动保存</div>
                    <van-switch v-model="user.name" size="20px" active-color="#1D3557" />
                </div>
                <div class="flex items-center justify-between p-4 bg-gray-50 rounded-2xl">
                    <div class="text-sm font-medium text-gray-600">全局通知</div>
                    <van-switch :model-value="true" size="20px" active-color="#1D3557" />
                </div>
            </div>
        </div>

        <div class="bg-white rounded-3xl shadow-sm border border-gray-100 p-8">
            <h3 class="font-bold text-gray-700 mb-6 flex items-center">
                <van-icon name="description-o" class="mr-2 text-[#1D3557]"/> 模式切换
            </h3>
            <div class="space-y-4">
                <van-button block round class="!bg-blue-50 !border-none !text-blue-700 !font-bold h-12" icon="exchange" @click="router.push('/training/1')">
                    切换为学员训练模式
                </van-button>
                <div class="p-4 border border-orange-100 bg-orange-50/50 rounded-2xl">
                    <p class="text-[10px] text-orange-600 leading-relaxed font-medium">
                        提示：切换至学员模式后，您将以基层民警身份进入警情模拟，且无法实时修改剧本参数。
                    </p>
                </div>
            </div>

            <div class="mt-12 pt-6 border-t border-gray-50">
                <van-button block round plain class="!border-red-100 !text-red-500 hover:!bg-red-50 transition-colors" @click="handleLogout">
                    安全退出系统
                </van-button>
            </div>
        </div>
    </div>
  </div>
</template>
