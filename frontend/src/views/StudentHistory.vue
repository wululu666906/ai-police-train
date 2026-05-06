<template>
  <div class="history-page">
    <div class="page-header">
      <div>
        <h1 class="page-title">训练历史</h1>
        <p class="page-desc">查看你的训练记录、会话完成情况和评估结果。</p>
      </div>
      <div class="history-tools">
        <span class="tool-label">显示空会话</span>
        <van-switch v-model="showEmptySessions" size="22px" @change="handleToggleEmpty" />
      </div>
    </div>

    <div v-if="!loading" class="summary-bar">
      <div class="summary-item">
        <span class="summary-num">{{ total }}</span>
        <span class="summary-label">{{ showEmptySessions ? '当前记录数' : '有效记录数' }}</span>
      </div>
      <div v-if="hiddenEmptyCount > 0 && !showEmptySessions" class="summary-item">
        <span class="summary-num summary-warn">{{ hiddenEmptyCount }}</span>
        <span class="summary-label">已隐藏空会话</span>
      </div>
      <div v-if="showEmptySessions" class="summary-tip">空会话指尚未产生有效对话内容的训练记录。</div>
    </div>

    <div v-if="loading" class="loading-state">
      <van-loading color="#165DFF">加载中...</van-loading>
    </div>

    <div v-else-if="records.length === 0" class="empty-state">
      <van-icon name="records-o" size="48" color="#C9CDD4" />
      <p>{{ showEmptySessions ? '暂无训练记录' : '暂无有效训练记录' }}</p>
      <span v-if="hiddenEmptyCount > 0">当前有 {{ hiddenEmptyCount }} 条空会话被自动隐藏。</span>
      <span v-else>完成一次训练后，记录会显示在这里。</span>
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
            <th>对话轮次</th>
            <th>最终情绪</th>
            <th>最终信任</th>
            <th>已获信息</th>
            <th>状态</th>
            <th>训练时间</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="r in records" :key="r.id">
            <td class="id-cell">#{{ r.id }}</td>
            <td class="title-cell">{{ r.case_title }}</td>
            <td><van-tag type="primary" plain size="medium">{{ r.case_type }}</van-tag></td>
            <td>{{ r.scene_name }}</td>
            <td>
              <van-tag :color="getDifficultyColor(r.difficulty)" plain size="medium">
                {{ r.difficulty }}
              </van-tag>
            </td>
            <td>
              {{ r.turn_count ?? 0 }} 轮
              <div v-if="r.is_empty_session" class="record-hint">尚未开始有效对话</div>
            </td>
            <td>
              <span :style="{ color: r.final_emotion > 70 ? '#F53F3F' : '#FF7D00' }">{{ r.final_emotion }}</span>
            </td>
            <td><span style="color: #165DFF;">{{ r.final_trust }}</span></td>
            <td>{{ r.revealed_info_count ?? 0 }}</td>
            <td>
              <van-tag :type="r.status === 'finished' ? 'success' : 'warning'" size="medium">
                {{ r.status === 'finished' ? '已完成' : '进行中' }}
              </van-tag>
            </td>
            <td class="time-cell">{{ formatTime(r.created_at) }}</td>
            <td>
              <van-button
                v-if="r.status === 'finished'"
                size="mini"
                type="primary"
                plain
                @click="router.push(`/student/evaluation?session_id=${r.id}`)"
              >
                查看报告
              </van-button>
              <van-button
                v-else
                size="mini"
                type="success"
                plain
                @click="router.push(`/student/training/${r.id}`)"
              >
                继续训练
              </van-button>
            </td>
          </tr>
        </tbody>
      </table>

      <div v-if="total > pageSize" class="pager">
        <van-button size="small" plain :disabled="page <= 1" @click="changePage(page - 1)">上一页</van-button>
        <span class="pager-text">第 {{ page }} / {{ totalPages }} 页，共 {{ total }} 条</span>
        <van-button size="small" plain :disabled="page >= totalPages" @click="changePage(page + 1)">下一页</van-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { showToast } from 'vant'
import request from '../utils/request'

const router = useRouter()
const records = ref<any[]>([])
const loading = ref(true)
const page = ref(1)
const pageSize = 10
const total = ref(0)
const totalPages = ref(1)
const showEmptySessions = ref(false)
const hiddenEmptyCount = ref(0)

const fetchHistory = async () => {
  loading.value = true
  try {
    const res: any = await request.get('/student/history', {
      params: {
        page: page.value,
        page_size: pageSize,
        include_empty: showEmptySessions.value
      }
    })
    records.value = res.items || []
    total.value = res.total || 0
    hiddenEmptyCount.value = res.hidden_empty_count || 0
    totalPages.value = Math.max(1, Math.ceil(total.value / pageSize))
  } catch (error) {
    showToast('获取历史记录失败')
  } finally {
    loading.value = false
  }
}

const changePage = async (nextPage: number) => {
  if (nextPage === page.value || nextPage < 1 || nextPage > totalPages.value) return
  page.value = nextPage
  await fetchHistory()
}

const handleToggleEmpty = async () => {
  page.value = 1
  await fetchHistory()
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
  margin-bottom: 20px;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.page-title {
  font-size: 24px;
  font-weight: 600;
  color: #1d2129;
  margin: 0;
}

.page-desc {
  font-size: 14px;
  color: #86909c;
  margin: 6px 0 0;
}

.history-tools {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  background: #fff;
  border: 1px solid #e5e6eb;
  border-radius: 10px;
}

.tool-label {
  font-size: 13px;
  color: #4e5969;
}

.summary-bar {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 20px;
  padding: 14px 16px;
  background: #f7f8fa;
  border-radius: 10px;
  flex-wrap: wrap;
}

.summary-item {
  display: flex;
  align-items: baseline;
  gap: 8px;
}

.summary-num {
  font-size: 22px;
  font-weight: 700;
  color: #165dff;
}

.summary-warn {
  color: #ff7d00;
}

.summary-label,
.summary-tip {
  font-size: 13px;
  color: #4e5969;
}

.loading-state,
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 80px 0;
  gap: 8px;
  color: #86909c;
}

.empty-state p {
  font-size: 15px;
  color: #4e5969;
  font-weight: 500;
  margin: 16px 0 4px;
}

.go-btn {
  margin-top: 16px;
  background: #165dff !important;
  border: none !important;
  border-radius: 8px !important;
}

.history-table-wrapper {
  background: white;
  border-radius: 12px;
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
  background: #f7f8fa;
  font-size: 13px;
  font-weight: 600;
  color: #86909c;
  border-bottom: 1px solid #e5e6eb;
  white-space: nowrap;
}

.history-table td {
  padding: 14px 16px;
  font-size: 14px;
  color: #4e5969;
  border-bottom: 1px solid #f2f3f5;
  vertical-align: top;
}

.history-table tr:hover td {
  background: #f7f8fa;
}

.id-cell {
  font-weight: 600;
  color: #1d2129 !important;
}

.record-hint {
  margin-top: 4px;
  font-size: 12px;
  color: #86909c;
  line-height: 1.4;
}

.title-cell {
  font-weight: 500;
  color: #1d2129 !important;
  max-width: 220px;
}

.time-cell {
  font-size: 13px;
  color: #86909c !important;
  white-space: nowrap;
}

.pager {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 12px;
  padding: 16px;
  border-top: 1px solid #f2f3f5;
}

.pager-text {
  font-size: 13px;
  color: #86909c;
}

@media (max-width: 900px) {
  .history-page {
    padding: 16px;
  }

  .page-header {
    flex-direction: column;
  }

  .history-table-wrapper {
    overflow-x: auto;
  }

  .history-table {
    min-width: 1080px;
  }
}
</style>
