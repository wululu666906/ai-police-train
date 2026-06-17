<template>
  <div class="space-y-5">

    <!-- 页头 -->
    <section class="admin-list-header">
      <div>
        <h1>视频实训记录</h1>
        <p>查看所有学员的视频实训进度、得分与详细评估报告</p>
      </div>
    </section>

    <!-- 筛选栏 -->
    <section class="admin-filter-panel">
      <div class="admin-filter-bar">
        <label class="admin-filter-item">
          <span>实训视频</span>
          <el-select v-model="filterVideoId" clearable placeholder="全部视频" style="width:180px" @change="fetchSessions">
            <el-option v-for="v in videoOptions" :key="v.id" :label="v.title" :value="v.id" />
          </el-select>
        </label>
        <label class="admin-filter-item">
          <span>完成状态</span>
          <el-select v-model="filterStatus" clearable placeholder="全部状态" style="width:130px" @change="fetchSessions">
            <el-option label="进行中" value="active" />
            <el-option label="已完成" value="finished" />
            <el-option label="已放弃" value="abandoned" />
          </el-select>
        </label>
        <label class="admin-filter-item">
          <span>学员账号</span>
          <el-input v-model="filterUsername" placeholder="输入账号搜索" clearable style="width:160px" @change="onFilterChange" />
        </label>
      </div>
    </section>

    <!-- 数据表格 -->
    <section v-if="loading" class="rounded-[8px] bg-white border border-slate-100 py-16 text-center">
      <el-skeleton :rows="5" animated />
    </section>

    <section v-else-if="!sessions.length" class="rounded-[8px] border border-dashed border-slate-200 bg-white py-20 text-center">
      <van-icon name="orders-o" size="32" class="text-slate-300" />
      <h3 class="mt-4 text-lg font-bold text-slate-500">暂无实训记录</h3>
    </section>

    <section v-else class="case-table-wrap">
      <table class="case-table">
        <thead>
          <tr>
            <th>学员</th>
            <th>训练视频</th>
            <th>模式</th>
            <th>状态</th>
            <th>得分</th>
            <th>评级</th>
            <th>节点进度</th>
            <th>开始时间</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="s in sessions" :key="s.id">
            <td class="case-title-cell">
              <div class="case-row-title">{{ s.username }}</div>
              <div class="case-row-id">ID {{ s.user_id }}</div>
            </td>
            <td class="case-summary-cell">{{ s.video_title }}</td>
            <td>
              <van-tag :type="s.mode === 'exam' ? 'danger' : 'primary'" plain>
                {{ s.mode === 'exam' ? '考核' : '练习' }}
              </van-tag>
            </td>
            <td>
              <span :class="statusClass(s.status)">{{ statusLabel(s.status) }}</span>
            </td>
            <td class="case-metric-cell">
              <span v-if="s.total_score != null">
                {{ s.total_score }} / {{ s.full_score }}
              </span>
              <span v-else class="text-slate-400">—</span>
            </td>
            <td>
              <van-tag v-if="s.status === 'finished'" :type="gradeType(s.grade)" plain>
                {{ s.grade || '—' }}
              </van-tag>
              <span v-else class="text-slate-400">—</span>
            </td>
            <td class="case-metric-cell">
              <el-progress
                :percentage="nodeProgress(s)"
                :stroke-width="5"
                style="width:80px"
                :show-text="false"
                :color="s.status === 'finished' ? '#52c41a' : '#0066ff'"
              />
              <span style="font-size:11px;color:#6b7280;margin-left:4px">
                {{ s.current_node_index }}/{{ nodeTotal(s) }}
              </span>
            </td>
            <td style="font-size:12px;color:#6b7280">{{ formatDate(s.created_at) }}</td>
            <td class="case-action-cell">
              <van-button
                v-if="s.status === 'finished'"
                size="small"
                type="primary"
                class="!bg-[#1D3557] !border-none !rounded-[6px]"
                @click="viewReport(s)"
              >
                查看报告
              </van-button>
              <span v-else class="text-slate-400 text-xs">训练中</span>
            </td>
          </tr>
        </tbody>
      </table>
    </section>

    <!-- 分页 -->
    <div v-if="total > pageSize" class="flex justify-center py-2">
      <el-pagination
        v-model:current-page="page"
        :page-size="pageSize"
        :total="total"
        layout="prev, pager, next, total"
        @current-change="fetchSessions"
      />
    </div>

    <!-- 报告弹窗 -->
    <van-popup
      v-model:show="showReport"
      round
      :style="{ width: 'min(600px, 96vw)', maxHeight: '88vh', overflow: 'auto' }"
      teleport="body"
    >
      <div v-if="reportData" class="cpv-header">
        <div class="cpv-header__left">
          <div class="cpv-title">{{ reportData.video_title }} — 实训报告</div>
          <div class="cpv-meta">
            <van-tag :type="gradeType(reportData.grade)" plain>{{ reportData.grade }}</van-tag>
            <span class="cpv-meta-text">得分 {{ reportData.total_score }}/{{ reportData.full_score }}</span>
            <span class="cpv-meta-sep">·</span>
            <span class="cpv-meta-text">得分率 {{ reportData.percentage }}%</span>
          </div>
        </div>
        <van-icon name="cross" size="18" class="cpv-close" @click="showReport = false" />
      </div>

      <div v-if="reportData" class="cpv-body">
        <!-- 统计 -->
        <div class="cpv-stats">
          <div class="cpv-stat">
            <span class="cpv-stat__num text-emerald-600">{{ reportData.pass_count }}</span>
            <span class="cpv-stat__label">通过节点</span>
          </div>
          <div class="cpv-stat">
            <span class="cpv-stat__num text-amber-600">{{ reportData.skip_count }}</span>
            <span class="cpv-stat__label">跳过节点</span>
          </div>
          <div class="cpv-stat">
            <span class="cpv-stat__num text-red-600">{{ reportData.total_deducted }}</span>
            <span class="cpv-stat__label">总扣分</span>
          </div>
          <div class="cpv-stat">
            <span class="cpv-stat__num text-slate-700">{{ reportData.total_nodes }}</span>
            <span class="cpv-stat__label">节点总数</span>
          </div>
        </div>

        <!-- 节点明细 -->
        <div class="cpv-card">
          <div class="cpv-card__label">节点明细</div>
          <div class="cpv-scene-list">
            <div v-for="item in reportData.node_summaries" :key="item.node_index" class="cpv-scene">
              <span class="cpv-scene__idx">{{ item.node_index + 1 }}</span>
              <div class="cpv-scene__info">
                <div class="cpv-scene__name">
                  <span :class="resultColor(item.result)">{{ resultLabel(item.result) }}</span>
                  <span v-if="item.retry_count" class="ml-2 text-xs text-amber-600">重试×{{ item.retry_count }}</span>
                </div>
                <div v-if="item.speech_transcript" class="cpv-scene__desc">
                  语音：{{ item.speech_transcript }}
                </div>
              </div>
              <div class="text-right text-sm">
                <div class="font-bold text-slate-700">{{ item.score_earned }}分</div>
                <div v-if="item.score_deducted" class="text-red-500 text-xs">-{{ item.score_deducted }}</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </van-popup>

  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import request from '../utils/request'

interface SessionItem {
  id: number
  user_id: number
  username: string
  video_id: number
  video_title: string
  mode: string
  status: string
  current_node_index: number
  total_score: number | null
  full_score: number | null
  grade?: string
  created_at: string
  finished_at?: string
}

interface ReportData {
  session_id: number
  video_title: string
  grade: string
  total_score: number
  full_score: number
  percentage: number
  pass_count: number
  skip_count: number
  total_nodes: number
  total_deducted: number
  node_summaries: {
    node_index: number
    result: string
    retry_count: number
    score_earned: number
    score_deducted: number
    speech_transcript?: string
  }[]
}

const sessions = ref<SessionItem[]>([])
const videoOptions = ref<{ id: number; title: string }[]>([])
const loading = ref(false)
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)

const filterVideoId = ref<number | null>(null)
const filterStatus = ref('')
const filterUsername = ref('')

const showReport = ref(false)
const reportData = ref<ReportData | null>(null)

onMounted(() => {
  fetchVideoOptions()
  fetchSessions()
})

async function fetchVideoOptions() {
  try {
    const res: any = await request.get('/videos/admin/list', { params: { video_type: 'interactive', page_size: 200 } })
    videoOptions.value = (res.items || []).map((v: any) => ({ id: v.id, title: v.title }))
  } catch {}
}

async function fetchSessions() {
  loading.value = true
  try {
    const params: Record<string, any> = { page: page.value, page_size: pageSize.value }
    if (filterVideoId.value) params.video_id = filterVideoId.value
    if (filterStatus.value) params.status = filterStatus.value
    const res: any = await request.get('/video-training/admin/sessions', { params })
    let items = res.items || []
    if (filterUsername.value.trim()) {
      const kw = filterUsername.value.trim().toLowerCase()
      items = items.filter((s: SessionItem) => s.username.toLowerCase().includes(kw))
    }
    sessions.value = items
    total.value = res.total || 0
  } catch {
    ElMessage.error('加载实训记录失败')
  } finally {
    loading.value = false
  }
}

function onFilterChange() {
  page.value = 1
  fetchSessions()
}

async function viewReport(s: SessionItem) {
  try {
    const res: any = await request.get(`/video-training/admin/sessions/${s.id}/report`)
    reportData.value = { ...res, grade: gradeFromScore(res.percentage) }
    showReport.value = true
  } catch {
    ElMessage.error('加载报告失败')
  }
}

function gradeFromScore(pct: number): string {
  if (pct >= 90) return '优秀'
  if (pct >= 70) return '合格'
  return '待重修'
}

function nodeProgress(s: SessionItem): number {
  const total = nodeTotal(s)
  if (!total) return 0
  return Math.round((s.current_node_index / total) * 100)
}

function nodeTotal(_s: SessionItem): number {
  // 从报告里拿节点总数，这里简单用 current_node_index 估算
  return 0  // 会在报告弹窗里展示
}

function statusLabel(status: string): string {
  return { active: '进行中', finished: '已完成', abandoned: '已放弃' }[status] || status
}

function statusClass(status: string): string {
  if (status === 'finished') return 'case-ok'
  if (status === 'active') return 'text-blue-600 font-semibold'
  return 'text-slate-400'
}

function gradeType(grade?: string): 'success' | 'primary' | 'warning' | 'danger' {
  if (grade === '优秀') return 'success'
  if (grade === '合格') return 'primary'
  if (grade === '待重修') return 'danger'
  return 'warning'
}

function resultLabel(r: string): string {
  return { pass: '通过', skip: '跳过', timeout: '超时跳过', fail: '未完成' }[r] || r
}

function resultColor(r: string): string {
  if (r === 'pass') return 'text-emerald-600 font-semibold'
  if (r === 'skip' || r === 'timeout') return 'text-amber-600 font-semibold'
  return 'text-red-600 font-semibold'
}

function formatDate(iso?: string): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}
</script>
