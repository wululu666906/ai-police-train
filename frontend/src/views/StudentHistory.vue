<template>
  <div class="history-page">
    <div class="page-header">
      <h1 class="page-title">训练历史</h1>
      <p class="page-desc">查看你的所有训练记录和成绩</p>
    </div>

    <div v-if="loading" class="loading-state">
      <van-loading color="#165DFF">加载中...</van-loading>
    </div>

    <div v-else-if="records.length === 0" class="empty-state">
      <van-icon name="records-o" size="48" color="#C9CDD4" />
      <p>暂无训练记录</p>
      <span>完成一次训练后，记录将显示在这里</span>
      <van-button type="primary" size="small" class="go-btn" @click="router.push('/student/hall')">
        前往训练大厅
      </van-button>
    </div>

    <div v-else class="history-table-wrapper">
      <table class="history-table">
        <thead>
          <tr>
            <th>训练编号</th>
            <th>案件名称</th>
            <th>案件类型</th>
            <th>场景</th>
            <th>难度</th>
            <th>对话轮数</th>
            <th>最终情绪</th>
            <th>最终信任</th>
            <th>状态</th>
            <th>训练时间</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="r in records" :key="r.id">
            <td class="id-cell">#{{ r.id }}</td>
            <td class="title-cell">{{ r.case_title }}</td>
            <td>
              <van-tag type="primary" plain size="small">{{ r.case_type }}</van-tag>
            </td>
            <td>{{ r.scene_name }}</td>
            <td>
              <van-tag :color="getDifficultyColor(r.difficulty)" plain size="small">
                {{ r.difficulty }}
              </van-tag>
            </td>
            <td>{{ Math.floor(r.message_count / 2) }} 轮</td>
            <td>
              <span :style="{ color: r.final_emotion > 70 ? '#F53F3F' : '#FF7D00' }">
                {{ r.final_emotion }}
              </span>
            </td>
            <td>
              <span style="color: #165DFF;">{{ r.final_trust }}</span>
            </td>
            <td>
              <van-tag :type="r.status === 'finished' ? 'success' : 'warning'" size="small">
                {{ r.status === 'finished' ? '已完成' : '进行中' }}
              </van-tag>
            </td>
            <td class="time-cell">{{ formatTime(r.created_at) }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import request from '../utils/request'
import { showToast } from 'vant'

const router = useRouter()
const records = ref<any[]>([])
const loading = ref(true)

const fetchHistory = async () => {
  try {
    const res: any = await request.get('/student/history')
    records.value = res
  } catch (e) {
    showToast('获取历史记录失败')
  } finally {
    loading.value = false
  }
}

const getDifficultyColor = (diff: string) => {
  if (diff === '简单') return '#00B42A'
  if (diff === '困难') return '#F53F3F'
  return '#FF7D00'
}

const formatTime = (iso: string) => {
  if (!iso) return '-'
  const d = new Date(iso)
  return `${d.getMonth() + 1}/${d.getDate()} ${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}`
}

onMounted(fetchHistory)
</script>

<style scoped>
.history-page {
  padding: 24px 32px;
  max-width: 1200px;
  margin: 0 auto;
  font-family: 'PingFang SC', 'Microsoft YaHei', 'Inter', sans-serif;
}

.page-header {
  margin-bottom: 24px;
}

.page-title {
  font-size: 24px;
  font-weight: 600;
  color: #1D2129;
  margin: 0;
}

.page-desc {
  font-size: 14px;
  color: #86909C;
  margin: 6px 0 0;
}

.loading-state,
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 80px 0;
  gap: 8px;
  color: #86909C;
}

.empty-state p {
  font-size: 15px;
  color: #4E5969;
  font-weight: 500;
  margin: 16px 0 4px;
}

.go-btn {
  margin-top: 16px;
  background: #165DFF !important;
  border: none !important;
  border-radius: 4px !important;
}

/* Table */
.history-table-wrapper {
  background: white;
  border-radius: 6px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
  overflow: hidden;
}

.history-table {
  width: 100%;
  border-collapse: collapse;
}

.history-table th {
  text-align: left;
  padding: 12px 16px;
  background: #F7F8FA;
  font-size: 13px;
  font-weight: 600;
  color: #86909C;
  border-bottom: 1px solid #E5E6EB;
  white-space: nowrap;
}

.history-table td {
  padding: 14px 16px;
  font-size: 14px;
  color: #4E5969;
  border-bottom: 1px solid #F2F3F5;
}

.history-table tr:hover td {
  background: #F7F8FA;
}

.id-cell {
  font-weight: 600;
  color: #1D2129 !important;
}

.title-cell {
  font-weight: 500;
  color: #1D2129 !important;
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.time-cell {
  font-size: 13px;
  color: #86909C !important;
}
</style>
