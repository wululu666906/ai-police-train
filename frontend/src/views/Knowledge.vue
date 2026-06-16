<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import request from '../utils/request'
import { showConfirmDialog, showFailToast, showSuccessToast } from 'vant'

type KnowledgeRow = {
  id: string
  title?: string
  content?: string
  category?: string
  source?: string
  tags?: string[]
  referenced_by_count?: number
  referenced_by?: string[]
}

type CaseKnowledgeRow = KnowledgeRow & {
  case_id?: string
  case_title?: string
  doc_type?: 'case_info' | 'role_script' | string
  role_id?: string
  role_name?: string
  in_knowledge?: boolean
  metadata?: Record<string, any>
}

const activeTab = ref<'general' | 'cases'>('cases')
const knowledgeList = ref<KnowledgeRow[]>([])
const caseKnowledgeList = ref<CaseKnowledgeRow[]>([])
const keyword = ref('')
const categoryFilter = ref('')
const sourceFilter = ref('')
const caseFilter = ref('')
const docTypeFilter = ref('')
const loading = ref(false)
const syncing = ref(false)
const showUpload = ref(false)
const showDetail = ref(false)
const selectedItem = ref<KnowledgeRow | CaseKnowledgeRow | null>(null)
const form = ref({
  title: '',
  category: '',
  tags: '',
  source: 'manual',
  content: '',
})

const normalizeTags = (tags: unknown) => (Array.isArray(tags) ? tags.map(String).filter(Boolean) : [])

const totalRefs = computed(() => knowledgeList.value.reduce((sum, item) => sum + Number(item.referenced_by_count || 0), 0))
const syncedCaseDocs = computed(() => caseKnowledgeList.value.filter((item) => item.in_knowledge).length)
const unsyncedCaseDocs = computed(() => caseKnowledgeList.value.filter((item) => !item.in_knowledge).length)

const categoryOptions = computed(() =>
  Array.from(new Set(knowledgeList.value.map((item) => String(item.category || '').trim()).filter(Boolean))).sort()
)
const sourceOptions = computed(() =>
  Array.from(new Set(knowledgeList.value.map((item) => String(item.source || '').trim()).filter(Boolean))).sort()
)
const caseOptions = computed(() =>
  Array.from(
    new Map(
      caseKnowledgeList.value
        .filter((item) => item.case_id)
        .map((item) => [String(item.case_id), item.case_title || `案件 ${item.case_id}`])
    ).entries()
  ).map(([id, title]) => ({ id, title }))
)

const currentGeneralList = computed(() => {
  const text = keyword.value.trim()
  return knowledgeList.value.filter((item) => {
    if (categoryFilter.value && item.category !== categoryFilter.value) return false
    if (sourceFilter.value && item.source !== sourceFilter.value) return false
    if (!text) return true
    const haystack = [item.title, item.content, item.category, item.source, ...(item.tags || []), ...(item.referenced_by || [])].join(' ')
    return haystack.includes(text)
  })
})

const currentCaseList = computed(() => {
  const text = keyword.value.trim()
  return caseKnowledgeList.value.filter((item) => {
    if (caseFilter.value && String(item.case_id || '') !== caseFilter.value) return false
    if (docTypeFilter.value && item.doc_type !== docTypeFilter.value) return false
    if (!text) return true
    const haystack = [
      item.id,
      item.title,
      item.content,
      item.case_title,
      item.role_name,
      item.category,
      item.source,
      ...(item.tags || []),
    ].join(' ')
    return haystack.includes(text)
  })
})

const fetchKnowledge = async () => {
  loading.value = true
  try {
    const [general, cases]: any[] = await Promise.all([request.get('/knowledge/list'), request.get('/knowledge/cases')])
    knowledgeList.value = Array.isArray(general) ? general.map((item) => ({ ...item, tags: normalizeTags(item.tags) })) : []
    caseKnowledgeList.value = Array.isArray(cases) ? cases.map((item) => ({ ...item, tags: normalizeTags(item.tags) })) : []
  } catch (error) {
    console.error('Fetch knowledge error:', error)
    showFailToast('知识库加载失败')
  } finally {
    loading.value = false
  }
}

const resetForm = () => {
  form.value = {
    title: '',
    category: '',
    tags: '',
    source: 'manual',
    content: '',
  }
}

const openDetail = (item: KnowledgeRow | CaseKnowledgeRow) => {
  selectedItem.value = item
  showDetail.value = true
}

const handleUpload = async () => {
  if (!form.value.content.trim()) {
    showFailToast('知识内容不能为空')
    return
  }
  try {
    await request.post('/knowledge/upload', {
      text: form.value.content,
      title: form.value.title || undefined,
      category: form.value.category || undefined,
      tags: form.value.tags
        .split(/[,，\n]/)
        .map((item) => item.trim())
        .filter(Boolean),
      source: form.value.source || 'manual',
    })
    showSuccessToast('知识条目已录入')
    resetForm()
    showUpload.value = false
    fetchKnowledge()
  } catch (error) {
    showFailToast('知识录入失败')
  }
}

const handleDelete = async (id: string) => {
  try {
    await showConfirmDialog({
      title: '确认删除',
      message: '确定要从知识库中移除这条知识吗？',
    })
    await request.delete(`/knowledge/${encodeURIComponent(id)}`)
    showSuccessToast('已删除')
    fetchKnowledge()
  } catch (error) {
    // user cancelled
  }
}

const handleSyncAllCases = async () => {
  syncing.value = true
  try {
    const res: any = await request.post('/knowledge/cases/sync-all')
    showSuccessToast(`同步完成：成功 ${res?.succeeded ?? 0}，失败 ${res?.failed ?? 0}`)
    await fetchKnowledge()
  } catch (error) {
    showFailToast('案件知识同步失败')
  } finally {
    syncing.value = false
  }
}

const handleSyncCase = async (caseId?: string) => {
  if (!caseId) return
  syncing.value = true
  try {
    await request.post(`/knowledge/cases/${caseId}/sync`)
    showSuccessToast('案件知识已同步')
    await fetchKnowledge()
  } catch (error) {
    showFailToast('案件知识同步失败')
  } finally {
    syncing.value = false
  }
}

onMounted(fetchKnowledge)
</script>

<template>
  <div class="knowledge-page">
    <section class="hero">
      <div>
        <h1>知识库管理</h1>
        <p>统一查看通用知识、案件信息和角色剧本，训练时 AI 角色会读取对应案件与剧本内容。</p>
      </div>
      <div class="hero-actions">
        <van-button plain icon="replay" :loading="loading" @click="fetchKnowledge">刷新</van-button>
        <van-button type="primary" icon="plus" @click="showUpload = true">新增知识</van-button>
      </div>
    </section>

    <section class="stats">
      <article class="stat-card">
        <span>通用知识</span>
        <strong>{{ knowledgeList.length }}</strong>
      </article>
      <article class="stat-card">
        <span>案件/剧本文档</span>
        <strong>{{ caseKnowledgeList.length }}</strong>
      </article>
      <article class="stat-card">
        <span>已同步 / 待同步</span>
        <strong>{{ syncedCaseDocs }} / {{ unsyncedCaseDocs }}</strong>
      </article>
      <article class="stat-card">
        <span>考察点引用</span>
        <strong>{{ totalRefs }}</strong>
      </article>
    </section>

    <section class="toolbar">
      <div class="tabs">
        <button :class="{ active: activeTab === 'cases' }" @click="activeTab = 'cases'">案件与角色剧本</button>
        <button :class="{ active: activeTab === 'general' }" @click="activeTab = 'general'">通用知识</button>
      </div>
      <label class="search-box">
        <van-icon name="search" />
        <input v-model.trim="keyword" type="text" placeholder="搜索标题、内容、角色或标签" />
      </label>
    </section>

    <section v-if="activeTab === 'cases'" class="list-card">
      <div class="list-head">
        <div>
          <h3>案件信息与角色剧本</h3>
          <p>案件信息和每个角色的剧本都会作为独立知识文档供 AI 角色读取。</p>
        </div>
        <van-button type="primary" icon="exchange" :loading="syncing" @click="handleSyncAllCases">同步全部案件</van-button>
      </div>

      <div class="filter-panel">
        <label class="filter-item">
          <span>案件</span>
          <select v-model="caseFilter">
            <option value="">全部案件</option>
            <option v-for="item in caseOptions" :key="item.id" :value="item.id">{{ item.title }}</option>
          </select>
        </label>
        <label class="filter-item">
          <span>类型</span>
          <select v-model="docTypeFilter">
            <option value="">全部类型</option>
            <option value="case_info">案件信息</option>
            <option value="role_script">角色剧本</option>
          </select>
        </label>
        <div class="filter-summary">当前 {{ currentCaseList.length }} / {{ caseKnowledgeList.length }} 条</div>
      </div>

      <div v-if="loading" class="loading-box">
        <van-loading type="spinner" color="#1D3557" />
      </div>
      <div v-else-if="currentCaseList.length" class="table-wrap">
        <table class="knowledge-table">
          <thead>
            <tr>
              <th>案件 / 文档</th>
              <th>类型</th>
              <th>角色</th>
              <th>同步状态</th>
              <th>内容预览</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in currentCaseList" :key="item.id">
              <td>
                <div class="row-title">{{ item.case_title || item.title || '未命名案件' }}</div>
                <div class="id-text">{{ item.id }}</div>
              </td>
              <td>
                <span class="category-chip">{{ item.doc_type === 'role_script' ? '角色剧本' : '案件信息' }}</span>
              </td>
              <td>{{ item.role_name || '-' }}</td>
              <td>
                <span :class="['status-chip', item.in_knowledge ? 'ok' : 'warn']">
                  {{ item.in_knowledge ? '已入库' : '未同步' }}
                </span>
              </td>
              <td class="preview-cell">{{ item.content }}</td>
              <td class="actions-cell">
                <van-button size="small" plain @click="openDetail(item)">查看</van-button>
                <van-button size="small" type="primary" plain :loading="syncing" @click="handleSyncCase(item.case_id)">同步</van-button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-else class="empty-box">
        <van-icon name="description-o" size="52" />
        <p>暂无案件知识文档</p>
      </div>
    </section>

    <section v-else class="list-card">
      <div class="list-head">
        <div>
          <h3>通用知识清单</h3>
          <p>法规、流程、处置模板等可被考察点引用的知识条目。</p>
        </div>
      </div>

      <div class="filter-panel">
        <label class="filter-item">
          <span>分类</span>
          <select v-model="categoryFilter">
            <option value="">全部</option>
            <option v-for="item in categoryOptions" :key="item" :value="item">{{ item }}</option>
          </select>
        </label>
        <label class="filter-item">
          <span>来源</span>
          <select v-model="sourceFilter">
            <option value="">全部</option>
            <option v-for="item in sourceOptions" :key="item" :value="item">{{ item }}</option>
          </select>
        </label>
        <div class="filter-summary">当前 {{ currentGeneralList.length }} / {{ knowledgeList.length }} 条</div>
      </div>

      <div v-if="loading" class="loading-box">
        <van-loading type="spinner" color="#1D3557" />
      </div>
      <div v-else-if="currentGeneralList.length" class="table-wrap">
        <table class="knowledge-table">
          <thead>
            <tr>
              <th>标题 / 内容</th>
              <th>分类</th>
              <th>来源</th>
              <th>标签</th>
              <th>引用</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in currentGeneralList" :key="item.id">
              <td>
                <div class="row-title">{{ item.title || '未命名知识' }}</div>
                <div class="preview-cell">{{ item.content }}</div>
                <div class="id-text">{{ item.id }}</div>
              </td>
              <td><span class="category-chip">{{ item.category || '通用' }}</span></td>
              <td><span class="source-chip">{{ item.source || 'manual' }}</span></td>
              <td>
                <div v-if="item.tags?.length" class="tag-list">
                  <span v-for="tag in item.tags" :key="tag" class="tag-chip">{{ tag }}</span>
                </div>
                <span v-else class="muted">-</span>
              </td>
              <td>{{ item.referenced_by_count || 0 }} 次</td>
              <td class="actions-cell">
                <van-button size="small" plain @click="openDetail(item)">查看</van-button>
                <van-button icon="delete-o" size="small" danger plain @click="handleDelete(item.id)" />
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-else class="empty-box">
        <van-icon name="comment-o" size="52" />
        <p>暂无知识条目</p>
      </div>
    </section>

    <van-popup v-model:show="showDetail" teleport="body" class="detail-popup" :style="{ width: 'min(760px, 94vw)' }">
      <div class="drawer">
        <div class="drawer-head">
          <div>
            <h3>{{ selectedItem?.title || selectedItem?.id || '知识详情' }}</h3>
            <p>{{ (selectedItem as CaseKnowledgeRow)?.case_title || selectedItem?.source || '知识库文档' }}</p>
          </div>
          <van-icon name="cross" class="drawer-close" @click="showDetail = false" />
        </div>
        <div class="detail-meta">
          <span>{{ (selectedItem as CaseKnowledgeRow)?.doc_type === 'role_script' ? '角色剧本' : selectedItem?.category || '知识条目' }}</span>
          <span v-if="(selectedItem as CaseKnowledgeRow)?.role_name">角色：{{ (selectedItem as CaseKnowledgeRow).role_name }}</span>
          <span v-if="(selectedItem as CaseKnowledgeRow)?.in_knowledge !== undefined">
            {{ (selectedItem as CaseKnowledgeRow).in_knowledge ? '已同步到知识库' : '数据库快照，尚未同步' }}
          </span>
        </div>
        <pre class="detail-content">{{ selectedItem?.content || '暂无内容' }}</pre>
      </div>
    </van-popup>

    <van-popup
      v-model:show="showUpload"
      teleport="body"
      :style="{ width: 'min(560px, 92vw)', maxHeight: '88vh', borderRadius: '12px', overflow: 'hidden' }"
    >
      <div class="drawer">
        <div class="drawer-head">
          <div>
            <h3>新增知识条目</h3>
            <p>案件信息和角色剧本请在案件管理中维护，这里用于录入通用知识。</p>
          </div>
          <van-icon name="cross" class="drawer-close" @click="showUpload = false" />
        </div>
        <div class="drawer-form">
          <label>标题</label>
          <input v-model="form.title" type="text" class="input" placeholder="例如：现场询问注意事项" />
          <label>分类</label>
          <input v-model="form.category" type="text" class="input" placeholder="例如：现场处置" />
          <label>标签</label>
          <input v-model="form.tags" type="text" class="input" placeholder="多个标签用逗号分隔" />
          <label>来源</label>
          <input v-model="form.source" type="text" class="input" placeholder="例如：manual / 内部规范" />
          <label>知识内容</label>
          <textarea v-model="form.content" rows="12" class="textarea" placeholder="请输入法规条文、处置流程或教学提示..."></textarea>
        </div>
        <div class="drawer-actions">
          <van-button block type="primary" @click="handleUpload">保存知识条目</van-button>
        </div>
      </div>
    </van-popup>
  </div>
</template>

<style scoped>
.knowledge-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.hero,
.list-card,
.stat-card,
.toolbar {
  border: 1px solid var(--police-border);
  border-radius: 8px;
  background: #fff;
}

.hero {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 18px 20px;
}

.hero h1,
.list-head h3,
.drawer-head h3 {
  margin: 0;
  color: var(--police-text-primary);
}

.hero p,
.list-head p,
.drawer-head p {
  margin: 6px 0 0;
  color: var(--police-text-muted);
  font-size: 13px;
}

.hero-actions,
.actions-cell {
  display: flex;
  align-items: center;
  gap: 8px;
  white-space: nowrap;
}

.stats {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.stat-card {
  padding: 14px 16px;
}

.stat-card span {
  color: var(--police-text-muted);
  font-size: 13px;
}

.stat-card strong {
  display: block;
  margin-top: 8px;
  color: #0f172a;
  font-size: 26px;
}

.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  padding: 12px;
}

.tabs {
  display: inline-flex;
  gap: 4px;
  border: 1px solid var(--police-border);
  border-radius: 8px;
  padding: 4px;
}

.tabs button {
  height: 32px;
  border: none;
  border-radius: 6px;
  background: transparent;
  padding: 0 14px;
  color: var(--police-text-secondary);
  cursor: pointer;
}

.tabs button.active {
  background: var(--police-primary);
  color: #fff;
}

.search-box {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  width: min(360px, 100%);
  height: 36px;
  border: 1px solid var(--police-border);
  border-radius: 8px;
  padding: 0 12px;
  color: var(--police-text-muted);
}

.search-box input {
  min-width: 0;
  flex: 1;
  border: none;
  outline: none;
  color: var(--police-text-primary);
}

.list-card {
  padding: 16px;
}

.list-head,
.filter-panel {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
}

.filter-panel {
  justify-content: flex-start;
  flex-wrap: wrap;
  border: 1px solid var(--police-border);
  border-radius: 8px;
  padding: 12px;
}

.filter-item {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: var(--police-text-secondary);
  font-size: 13px;
}

.filter-item select {
  height: 34px;
  min-width: 140px;
  border: 1px solid var(--police-border);
  border-radius: 6px;
  background: #fff;
  padding: 0 10px;
}

.filter-summary,
.muted,
.id-text {
  color: var(--police-text-muted);
  font-size: 12px;
}

.table-wrap {
  overflow-x: auto;
  border: 1px solid var(--police-border);
  border-radius: 8px;
}

.knowledge-table {
  width: 100%;
  min-width: 1000px;
  border-collapse: collapse;
}

.knowledge-table th,
.knowledge-table td {
  border-bottom: 1px solid var(--police-border-light);
  padding: 12px;
  text-align: left;
  vertical-align: top;
  font-size: 13px;
}

.knowledge-table th {
  background: #f8fafc;
  color: var(--police-text-secondary);
  font-weight: 700;
}

.knowledge-table tr:last-child td {
  border-bottom: none;
}

.row-title {
  color: #0f172a;
  font-weight: 700;
}

.preview-cell {
  display: -webkit-box;
  max-width: 520px;
  overflow: hidden;
  color: #475569;
  line-height: 1.6;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  white-space: pre-wrap;
}

.category-chip,
.source-chip,
.tag-chip,
.status-chip {
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  padding: 4px 9px;
  font-size: 12px;
}

.category-chip {
  background: #e0f2fe;
  color: #0369a1;
}

.source-chip {
  background: #eef2ff;
  color: #4338ca;
}

.tag-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.tag-chip {
  background: #f1f5f9;
  color: #334155;
}

.status-chip.ok {
  background: #dcfce7;
  color: #166534;
}

.status-chip.warn {
  background: #fef3c7;
  color: #92400e;
}

.loading-box,
.empty-box {
  min-height: 240px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: var(--police-text-muted);
  text-align: center;
}

.drawer {
  display: flex;
  flex-direction: column;
  max-height: 88vh;
  padding: 22px;
  background: #fff;
}

.drawer-head {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
}

.drawer-close {
  cursor: pointer;
  color: var(--police-text-muted);
}

.detail-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 12px;
}

.detail-meta span {
  border-radius: 999px;
  background: #f1f5f9;
  padding: 5px 10px;
  color: #334155;
  font-size: 12px;
}

.detail-content {
  max-height: 62vh;
  overflow: auto;
  border: 1px solid var(--police-border);
  border-radius: 8px;
  background: #f8fafc;
  padding: 14px;
  color: #0f172a;
  font-family: inherit;
  font-size: 14px;
  line-height: 1.8;
  white-space: pre-wrap;
}

.drawer-form {
  display: flex;
  flex-direction: column;
  gap: 10px;
  overflow-y: auto;
}

.drawer-form label {
  color: #334155;
  font-size: 13px;
  font-weight: 700;
}

.input,
.textarea {
  border: 1px solid var(--police-border);
  border-radius: 8px;
  padding: 11px 12px;
  color: #0f172a;
  outline: none;
}

.textarea {
  resize: vertical;
}

.drawer-actions {
  padding-top: 16px;
}

@media (max-width: 900px) {
  .hero,
  .toolbar,
  .list-head {
    align-items: stretch;
    flex-direction: column;
  }

  .stats {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
