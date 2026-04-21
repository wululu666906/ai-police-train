<script setup lang="ts">
import { ref, onMounted } from 'vue'
import request from '../utils/request'
import { showSuccessToast, showFailToast, showConfirmDialog } from 'vant'

const knowledgeList = ref<any[]>([])
const loading = ref(false)
const showUpload = ref(false)
const uploadText = ref('')

const fetchKnowledge = async () => {
    loading.value = true
    try {
        const res: any = await request.get('/knowledge/list')
        knowledgeList.value = res
    } catch (e) {
        console.error('Fetch knowledge error:', e)
    } finally {
        loading.value = false
    }
}

const handleUpload = async () => {
    if (!uploadText.value.trim()) return
    try {
        await request.post('/knowledge/upload', { text: uploadText.value })
        showSuccessToast('知识索引成功')
        uploadText.value = ''
        showUpload.value = false
        fetchKnowledge()
    } catch (e) {
        showFailToast('索引失败')
    }
}

const handleDelete = async (id: string) => {
    try {
        await showConfirmDialog({
            title: '确认删除',
            message: '确定要从向量库中移除该知识片段吗？',
        })
        await request.delete(`/knowledge/${id}`)
        showSuccessToast('已删除')
        fetchKnowledge()
    } catch (e) {
        // Cancelled or error
    }
}

onMounted(fetchKnowledge)
</script>

<template>
  <div class="space-y-6">
    <!-- Header Actions -->
    <div class="flex justify-between items-center">
        <div>
            <h2 class="text-xl font-bold text-gray-800">RAG 知识库管理</h2>
            <p class="text-sm text-gray-400 mt-1">管理 AI 演练引擎引用的法律条文与实操规程</p>
        </div>
        <van-button 
            type="primary" 
            round 
            icon="plus" 
            class="!bg-[#1D3557] !border-none px-6"
            @click="showUpload = true"
        >
            导入专业知识
        </van-button>
    </div>

    <!-- Stats Cards -->
    <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div class="bg-white p-6 rounded-2xl shadow-sm border border-gray-100 flex items-center space-x-4">
            <div class="w-12 h-12 bg-blue-50 flex items-center justify-center rounded-xl text-blue-600">
                <van-icon name="cluster" size="24" />
            </div>
            <div>
                <div class="text-gray-400 text-xs font-bold uppercase">入库片段数</div>
                <div class="text-2xl font-black text-gray-800">{{ knowledgeList.length }}</div>
            </div>
        </div>
        <div class="bg-white p-6 rounded-2xl shadow-sm border border-gray-100 flex items-center space-x-4">
            <div class="w-12 h-12 bg-green-50 flex items-center justify-center rounded-xl text-green-600">
                <van-icon name="shield-o" size="24" />
            </div>
            <div>
                <div class="text-gray-400 text-xs font-bold uppercase">数据库状态</div>
                <div class="text-2xl font-black text-gray-800">在线 (Healthy)</div>
            </div>
        </div>
    </div>

    <!-- Knowledge List -->
    <div class="bg-white rounded-3xl shadow-sm border border-gray-100 overflow-hidden">
        <div class="p-6 border-b border-gray-50 flex items-center justify-between">
            <h3 class="font-bold text-gray-700">当前知识检索序列</h3>
            <van-button icon="replay" size="small" plain round class="!border-gray-200 !text-gray-400" @click="fetchKnowledge" />
        </div>

        <div v-if="loading" class="p-12 flex justify-center">
            <van-loading type="spinner" color="#1D3557" />
        </div>

        <div v-else class="divide-y divide-gray-50">
            <div v-for="item in knowledgeList" :key="item.id" class="p-6 hover:bg-gray-50/50 transition-colors flex items-start justify-between group">
                <div class="flex-1 pr-8">
                    <div class="flex items-center space-x-2 mb-2">
                        <span class="px-2 py-0.5 bg-blue-100 text-blue-700 text-[10px] font-bold rounded uppercase">
                            {{ item.source }}
                        </span>
                        <span class="text-[10px] text-gray-300 font-mono tracking-tighter">{{ item.id }}</span>
                    </div>
                    <p class="text-gray-600 text-sm leading-relaxed">
                        {{ item.content }}
                    </p>
                </div>
                <div class="opacity-0 group-hover:opacity-100 transition-opacity">
                    <van-button 
                        icon="delete-o" 
                        size="small" 
                        danger 
                        round 
                        class="!text-red-500 !bg-red-50 !border-none" 
                        @click="handleDelete(item.id)"
                    />
                </div>
            </div>

            <div v-if="knowledgeList.length === 0" class="p-20 text-center flex flex-col items-center">
                <van-icon name="comment-o" size="60" class="text-gray-100 mb-4" />
                <p class="text-gray-400 text-sm italic">暂无知识库数据，请先进行导入</p>
            </div>
        </div>
    </div>

    <!-- Upload Modal -->
    <van-popup v-model:show="showUpload" position="right" :style="{ width: '450px', height: '100%' }" class="p-8">
        <div class="h-full flex flex-col">
            <div class="flex-shrink-0 mb-8">
                <div class="flex items-center justify-between mb-2">
                    <h3 class="text-xl font-black text-[#1D3557]">导入专业法律知识</h3>
                    <van-icon name="cross" class="text-gray-300 cursor-pointer" @click="showUpload = false" />
                </div>
                <p class="text-xs text-gray-400">我们将对上传的内容进行向量化处理，供演练引擎实时引用。</p>
            </div>

            <div class="flex-1 space-y-6">
                <div>
                    <label class="text-xs font-bold text-gray-700 mb-2 block uppercase tracking-widest">知识文本片段</label>
                    <textarea 
                        v-model="uploadText"
                        rows="12"
                        class="w-full bg-gray-50 border border-gray-100 rounded-2xl p-4 text-sm focus:outline-none focus:ring-2 focus:ring-[#1D3557]/20 transition-all font-sans"
                        placeholder="请输入法律条文、处警规范或专业指导建议..."
                    ></textarea>
                </div>
            </div>

            <div class="flex-shrink-0 pt-6 space-y-3">
                <van-button block round type="primary" class="!bg-[#1D3557] !border-none h-12" @click="handleUpload">
                    启动向量化索引
                </van-button>
                <p class="text-[10px] text-center text-gray-300 italic px-4">
                    提示：建议每次导入 500 字以内的单一知识点，以获得最佳检索精度。
                </p>
            </div>
        </div>
    </van-popup>
  </div>
</template>
