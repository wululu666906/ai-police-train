<template>
  <div class="p-4 text-white pb-20">
      <div class="flex justify-between items-center mb-4">
        <h2 class="text-white text-lg font-bold">AI角色预设库</h2>
        <van-button type="primary" size="small" icon="plus" class="!bg-purple-600 !border-none !rounded-full">新增角色</van-button>
      </div>
      
      <div class="space-y-3">
        <div v-for="r in roles" :key="r.id" class="bg-slate-800 p-4 rounded-xl border border-slate-700">
          <div class="flex justify-between items-start mb-3">
            <h3 class="text-white font-medium">{{r.name}}</h3>
          </div>
          
          <div class="grid grid-cols-2 gap-4">
            <div>
              <div class="text-xs text-slate-400 mb-1">初始情绪 ({{r.init_emotion}})</div>
              <div class="w-full bg-slate-700 rounded-full h-1.5">
                <div class="bg-red-500 h-1.5 rounded-full" :style="{ width: r.init_emotion + '%' }"></div>
              </div>
            </div>
            <div>
              <div class="text-xs text-slate-400 mb-1">初始信任 ({{r.init_trust}})</div>
              <div class="w-full bg-slate-700 rounded-full h-1.5">
                <div class="bg-blue-500 h-1.5 rounded-full" :style="{ width: r.init_trust + '%' }"></div>
              </div>
            </div>
          </div>
          
          <div class="mt-4 flex justify-end">
            <van-button size="mini" type="primary" plain class="!border-purple-500 !text-purple-400">调试Prompt</van-button>
          </div>
        </div>
      </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import request from '../utils/request'

const roles = ref<any[]>([])

const fetchRoles = async () => {
  try {
    const res: any = await request.get('/cases/all/roles')
    roles.value = res
  } catch (e) {
    console.error('Fetch roles error:', e)
  }
}

onMounted(fetchRoles)
</script>
