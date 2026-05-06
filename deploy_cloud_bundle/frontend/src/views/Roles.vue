<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import request from '../utils/request'


const roles = ref<any[]>([])
const loading = ref(false)
const showDetail = ref(false)
const selectedRole = ref<any>(null)

// 根据案件名称对角色进行分组
const groupedRoles = computed(() => {
  const groups: Record<string, any[]> = {}
  roles.value.forEach(role => {
    const title = role.case_title || '预设公共角色'
    if (!groups[title]) groups[title] = []
    groups[title].push(role)
  })
  return groups
})

const fetchRoles = async () => {
  loading.value = true
  try {
    const res: any = await request.get('/cases/all/roles')
    roles.value = res
  } catch (e) {
    console.error('Fetch roles error:', e)
  } finally {
    loading.value = false
  }
}

const getRoleTypeClass = (type: string) => {
    switch(type) {
        case '情绪型': return 'bg-orange-100 text-orange-700'
        case '对抗型': return 'bg-red-100 text-red-700'
        case '配合型': return 'bg-green-100 text-green-700'
        default: return 'bg-blue-100 text-blue-700'
    }
}

const openDetail = (role: any) => {
    selectedRole.value = { ...role }
    showDetail.value = true
}

onMounted(fetchRoles)
</script>

<template>
  <div class="space-y-10 pb-20">
    <div class="flex justify-between items-end">
        <div>
            <h2 class="text-xl font-bold text-gray-800">AI 演练角色库</h2>
            <p class="text-sm text-gray-400 mt-1">配置训练场景中各角色的初始状态、性格与语言风格</p>
        </div>
        <van-button 
            type="primary" 
            round 
            icon="plus" 
            class="!bg-[#1D3557] !border-none px-6"
        >
            预设新角色
        </van-button>
    </div>

    <!-- Role Cards Sections Grouped by Case -->
    <div v-if="loading" class="py-20 flex justify-center">
        <van-loading type="spinner" color="#1D3557" />
    </div>

    <div v-else class="space-y-12">
        <div v-for="(group, caseTitle) in groupedRoles" :key="caseTitle" class="space-y-6">
            <div class="flex items-center space-x-4">
                <div class="h-px flex-1 bg-gray-100"></div>
                <h3 class="text-xs font-black text-gray-400 uppercase tracking-[0.2em] bg-gray-50 px-4 py-1 rounded-full border border-gray-100">
                    所属案件：{{ caseTitle }}
                </h3>
                <div class="h-px flex-1 bg-gray-100"></div>
            </div>

            <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                <div 
                    v-for="r in group" 
                    :key="r.id" 
                    class="bg-white rounded-3xl shadow-sm border border-gray-100 p-6 hover:shadow-md transition-all cursor-pointer group"
                    @click="openDetail(r)"
                >
                    <div class="flex items-start justify-between mb-4">
                        <div class="flex items-center space-x-3">
                            <div class="w-12 h-12 bg-gray-50 rounded-2xl flex items-center justify-center border border-gray-100">
                                <van-icon name="user-o" size="24" class="text-gray-400" />
                            </div>
                            <div>
                                <h3 class="font-bold text-gray-800">{{ r.name }}</h3>
                                <span :class="['text-[10px] px-2 py-0.5 rounded-full font-bold', getRoleTypeClass(r.role_type)]">
                                    {{ r.role_type }}
                                </span>
                            </div>
                        </div>
                        <van-icon name="setting-o" class="text-gray-300 group-hover:text-[#1D3557] transition-colors" />
                    </div>

                    <div class="space-y-4">
                        <div class="grid grid-cols-2 gap-4">
                            <div class="space-y-1">
                                <div class="flex justify-between items-center text-[10px] uppercase font-bold text-gray-400 tracking-wider">
                                    <span>初始情绪</span>
                                    <span class="text-orange-500">{{ r.init_emotion }}%</span>
                                </div>
                                <div class="h-1 bg-gray-50 rounded-full overflow-hidden">
                                    <div class="h-full bg-orange-400" :style="{ width: r.init_emotion + '%' }"></div>
                                </div>
                            </div>
                            <div class="space-y-1">
                                <div class="flex justify-between items-center text-[10px] uppercase font-bold text-gray-400 tracking-wider">
                                    <span>初始信任</span>
                                    <span class="text-blue-500">{{ r.init_trust }}%</span>
                                </div>
                                <div class="h-1 bg-gray-50 rounded-full overflow-hidden">
                                    <div class="h-full bg-blue-500" :style="{ width: r.init_trust + '%' }"></div>
                                </div>
                            </div>
                        </div>

                        <div class="p-3 bg-gray-50 rounded-xl">
                            <div class="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-1">语言风格 (Speaking Style)</div>
                            <p class="text-xs text-gray-600 font-medium italic">"{{ r.speaking_style }}"</p>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <!-- Empty State -->
    <div v-if="!loading && roles.length === 0" class="py-20 text-center">
        <van-icon name="friends-o" size="60" class="text-gray-100 mb-4" />
        <p class="text-gray-400 text-sm italic">暂无角色数据，请在案件库生成后自动录入或手动创建</p>
    </div>

    <!-- Role Config Sidebar -->
    <van-popup v-model:show="showDetail" position="right" :style="{ width: '450px', height: '100%' }" class="p-8">
        <div v-if="selectedRole" class="h-full flex flex-col">
            <div class="flex-shrink-0 mb-8">
                <div class="flex items-center justify-between mb-2">
                    <h3 class="text-xl font-black text-[#1D3557]">角色精细化建模</h3>
                    <van-icon name="cross" class="text-gray-300 cursor-pointer" @click="showDetail = false" />
                </div>
                <p class="text-xs text-gray-400">调整角色在演练中的底层性格逻辑与对话反馈机制</p>
            </div>

            <div class="flex-1 space-y-8 overflow-y-auto pr-4">
                <section class="space-y-4">
                    <h4 class="text-xs font-black text-gray-800 uppercase tracking-widest border-l-4 border-[#1D3557] pl-3">基本特征</h4>
                    <van-field v-model="selectedRole.name" label="角色姓名" placeholder="输入姓名" border />
                    <van-field v-model="selectedRole.speaking_style" label="语言风格" placeholder="e.g. 粗鲁、胆怯、公事公办" border />
                </section>

                <section class="space-y-4">
                    <h4 class="text-xs font-black text-gray-800 uppercase tracking-widest border-l-4 border-orange-400 pl-3">性格详情 (Personality)</h4>
                    <textarea 
                        v-model="selectedRole.personality"
                        rows="4"
                        class="w-full bg-gray-50 border border-gray-100 rounded-2xl p-4 text-sm focus:outline-none focus:ring-2 focus:ring-[#1D3557]/20 transition-all font-sans"
                        placeholder="描述该角色的性格背景、心理弱点或行为动机..."
                    ></textarea>
                </section>

                <section class="space-y-4">
                    <h4 class="text-xs font-black text-gray-800 uppercase tracking-widest border-l-4 border-blue-400 pl-3">初始状态机</h4>
                    <div class="space-y-6 px-2">
                        <div>
                            <div class="flex justify-between mb-2">
                                <span class="text-xs text-gray-500">初始情绪值 (Emotion)</span>
                                <span class="text-xs font-bold">{{ selectedRole.init_emotion }}</span>
                            </div>
                            <van-slider v-model="selectedRole.init_emotion" active-color="#ee0a24" />
                        </div>
                        <div>
                            <div class="flex justify-between mb-2">
                                <span class="text-xs text-gray-500">初始信任感 (Trust)</span>
                                <span class="text-xs font-bold">{{ selectedRole.init_trust }}</span>
                            </div>
                            <van-slider v-model="selectedRole.init_trust" active-color="#1989fa" />
                        </div>
                    </div>
                </section>
            </div>

            <div class="flex-shrink-0 pt-8 border-t border-gray-50 flex space-x-4">
                <van-button block round class="!bg-gray-100 !border-none !text-gray-500 h-12" @click="showDetail = false">取消修改</van-button>
                <van-button block round type="primary" class="!bg-[#1D3557] !border-none h-12 shadow-lg shadow-blue-900/10">
                    保存建模参数
                </van-button>
            </div>
        </div>
    </van-popup>
  </div>
</template>
