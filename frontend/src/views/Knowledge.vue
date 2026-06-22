<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import request from '../utils/request'
import { showConfirmDialog, showFailToast, showSuccessToast } from 'vant'

type KnowledgeLibrary =
  | 'case_library'
  | 'role_library'
  | 'law_library'
  | 'sop_library'
  | 'training_library'
  | 'general'

type KnowledgeChunk = {
  id: string
  title?: string
  content?: string
  category?: string
  source?: string
  library?: KnowledgeLibrary | string
  tags?: string[]
  source_id?: string
  chunk_id?: string
  chunk_index?: number | string
  created_at?: string
  updated_at?: string
  referenced_by_count?: number
  referenced_by?: string[]
  metadata?: Record<string, any>
}

type CaseKnowledgeRow = KnowledgeChunk & {
  case_id?: string
  case_title?: string
  doc_type?: 'case_info' | 'role_script' | string
  role_id?: string
  role_name?: string
  in_knowledge?: boolean
}

type KnowledgeSource = {
  source_id: string
  title?: string
  source?: string
  category?: string
  library?: KnowledgeLibrary | string
  tags?: string[]
  chunk_count?: number
  created_at?: string
  updated_at?: string
  filename?: string
  file_type?: string
  extract_method?: string
  extract_engine?: string
  status?: string
  chunks?: KnowledgeChunk[]
}

type KnowledgeLibraryStats = {
  library: KnowledgeLibrary | string
  source_count?: number
  chunk_count?: number
  latest_updated_at?: string
  ingest_status?: string
  retrieval_status?: string
}

type KnowledgeStats = {
  total_chunks?: number
  total_sources?: number
  embedding_available?: boolean
  embedding_error?: string | null
  libraries?: Record<string, KnowledgeLibraryStats>
}

type WorkView = 'sources' | 'chunks' | 'caseSync' | 'search'

const libraryCatalog: Array<{
  label: string
  value: KnowledgeLibrary
  description: string
  examples: string
  category: string
  syncable?: boolean
}> = [
  {
    label: '案件知识',
    value: 'case_library',
    description: '案件背景、经过、线索、人物关系、风险点、隐藏信息',
    examples: '案件背景 / 线索 / 风险点',
    category: '案件信息',
    syncable: true,
  },
  {
    label: '角色剧本',
    value: 'role_library',
    description: '角色身份、性格、情绪、掌握信息、可透露信息、隐藏信息',
    examples: '身份设定 / 掌握信息 / 隐藏信息',
    category: '角色剧本',
    syncable: true,
  },
  {
    label: '法律法规',
    value: 'law_library',
    description: '法律条文、司法解释、行政法规、执法规范',
    examples: '法律条文 / 司法解释 / 执法规范',
    category: '法律法规',
    uploadable: true,
  },
  {
    label: '处置流程',
    value: 'sop_library',
    description: '接警、出警、询问、审讯、风险处置 SOP',
    examples: '接警流程 / 出警流程 / 询问流程',
    category: '处置流程',
    uploadable: true,
  },
  {
    label: '教学资料',
    value: 'training_library',
    description: '培训材料、案例分析、警务知识、学习建议',
    examples: '培训材料 / 案例分析 / 警务知识',
    category: '教学资料',
    uploadable: true,
  },
  {
    label: '其它/通用',
    value: 'general',
    description: '暂未归入固定分类的补充知识、话术模板和试点资料',
    examples: '通用话术 / 补充说明 / 临时资料',
    category: '通用',
    uploadable: true,
  },
]

const libraryOptions = libraryCatalog.map(({ label, value }) => ({ label, value }))
const activeLibrary = ref<KnowledgeLibrary>('case_library')
const activeView = ref<WorkView>('caseSync')
const knowledgeList = ref<KnowledgeChunk[]>([])
const caseKnowledgeList = ref<CaseKnowledgeRow[]>([])
const sourceList = ref<KnowledgeSource[]>([])
const stats = ref<KnowledgeStats | null>(null)
const keyword = ref('')
const categoryFilter = ref('')
const sourceFilter = ref('')
const caseFilter = ref('')
const docTypeFilter = ref('')
const loading = ref(false)
const syncing = ref(false)
const showUpload = ref(false)
const showFileUpload = ref(false)
const showDetail = ref(false)
const showSourceDetail = ref(false)
const selectedItem = ref<KnowledgeChunk | CaseKnowledgeRow | null>(null)
const selectedSource = ref<KnowledgeSource | null>(null)
const uploadFile = ref<File | null>(null)
const searchLoading = ref(false)
const sourceDetailLoading = ref(false)
const searchResult = ref<any>(null)
const lastUploadResult = ref<any>(null)

const form = ref({
  title: '',
  category: '',
  tags: '',
  source: 'manual',
  library: 'general' as KnowledgeLibrary,
  content: '',
})

const fileForm = ref({
  title: '',
  category: '通用',
  tags: '',
  source: 'file_upload',
  library: 'general' as KnowledgeLibrary,
  chunkSize: 800,
  overlap: 150,
})

const searchForm = ref({
  query: '',
  limit: 5,
  libraries: ['law_library', 'sop_library', 'training_library'] as KnowledgeLibrary[],
})

const normalizeTags = (tags: unknown) => (Array.isArray(tags) ? tags.map(String).filter(Boolean) : [])
const normalizeLibrary = (value?: string): KnowledgeLibrary => {
  const clean = String(value || '').trim()
  return libraryCatalog.some((item) => item.value === clean) ? (clean as KnowledgeLibrary) : 'general'
}
const libraryLabel = (value?: string) => libraryCatalog.find((item) => item.value === value)?.label || value || '其它/通用'
const libraryMeta = (value?: string) => libraryCatalog.find((item) => item.value === value) || libraryCatalog[libraryCatalog.length - 1]
const activeLibraryMeta = computed(() => libraryCatalog.find((item) => item.value === activeLibrary.value) || libraryCatalog[0])
const selectedFormLibraryMeta = computed(() => libraryMeta(form.value.library))
const selectedFileLibraryMeta = computed(() => libraryMeta(fileForm.value.library))
const activeStats = computed(() => stats.value?.libraries?.[activeLibrary.value] || null)
const canSyncCases = computed(() => Boolean(activeLibraryMeta.value.syncable))
const totalRefs = computed(() => knowledgeList.value.reduce((sum, item) => sum + Number(item.referenced_by_count || 0), 0))

const caseKnowledgeChunks = computed<KnowledgeChunk[]>(() =>
  caseKnowledgeList.value
    .filter((item) => normalizeLibrary(item.library || (item.doc_type === 'role_script' ? 'role_library' : 'case_library')) === activeLibrary.value)
    .map((item) => ({ ...item, library: normalizeLibrary(item.library || (item.doc_type === 'role_script' ? 'role_library' : 'case_library')) }))
)

const allChunks = computed<KnowledgeChunk[]>(() => {
  const rows = new Map<string, KnowledgeChunk>()
  for (const item of [...knowledgeList.value, ...caseKnowledgeChunks.value]) {
    if (item.id) rows.set(item.id, item)
  }
  return Array.from(rows.values())
})
const activeSources = computed(() => sourceList.value.filter((item) => normalizeLibrary(item.library) === activeLibrary.value))
const activeChunks = computed(() => allChunks.value.filter((item) => normalizeLibrary(item.library) === activeLibrary.value))

const categoryOptions = computed(() =>
  Array.from(new Set(activeChunks.value.map((item) => String(item.category || '').trim()).filter(Boolean))).sort()
)

const sourceOptions = computed(() =>
  Array.from(new Set(activeChunks.value.map((item) => String(item.source || '').trim()).filter(Boolean))).sort()
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

const filteredChunks = computed(() => {
  const text = keyword.value.trim()
  return activeChunks.value.filter((item) => {
    if (categoryFilter.value && item.category !== categoryFilter.value) return false
    if (sourceFilter.value && item.source !== sourceFilter.value) return false
    if (!text) return true
    const haystack = [
      item.id,
      item.title,
      item.content,
      item.category,
      item.source,
      item.library,
      item.source_id,
      ...(item.tags || []),
      ...(item.referenced_by || []),
    ].join(' ')
    return haystack.includes(text)
  })
})

const filteredSources = computed(() => {
  const text = keyword.value.trim()
  return activeSources.value.filter((item) => {
    if (categoryFilter.value && item.category !== categoryFilter.value) return false
    if (sourceFilter.value && item.source !== sourceFilter.value) return false
    if (!text) return true
    const haystack = [
      item.source_id,
      item.title,
      item.category,
      item.source,
      item.filename,
      item.library,
      ...(item.tags || []),
      ...(item.chunks || []).map((chunk) => chunk.content || '').join(' '),
    ].join(' ')
    return haystack.includes(text)
  })
})

const currentCaseList = computed(() => {
  const text = keyword.value.trim()
  return caseKnowledgeList.value
    .filter((item) => normalizeLibrary(item.library || (item.doc_type === 'role_script' ? 'role_library' : 'case_library')) === activeLibrary.value)
    .filter((item) => {
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

const overviewCards = computed(() =>
  libraryCatalog.map((item) => {
    const libraryStats = stats.value?.libraries?.[item.value]
    const fallbackChunks =
      item.value === 'case_library' || item.value === 'role_library'
        ? caseKnowledgeList.value.filter((row) => normalizeLibrary(row.library || (row.doc_type === 'role_script' ? 'role_library' : 'case_library')) === item.value).length
        : knowledgeList.value.filter((row) => normalizeLibrary(row.library) === item.value).length
    return {
      ...item,
      chunkCount: Number(libraryStats?.chunk_count ?? fallbackChunks),
      sourceCount: Number(libraryStats?.source_count ?? sourceList.value.filter((source) => normalizeLibrary(source.library) === item.value).length),
      latest: libraryStats?.latest_updated_at || '',
      ingestStatus: libraryStats?.ingest_status || (fallbackChunks ? 'ready' : 'empty'),
      retrievalStatus: libraryStats?.retrieval_status || (stats.value?.embedding_available === false ? 'degraded' : 'available'),
    }
  })
)

const statusLabel = (value?: string) => {
  if (value === 'ready') return '已入库'
  if (value === 'available') return '可检索'
  if (value === 'degraded') return '降级检索'
  if (value === 'failed') return '异常'
  return '暂无数据'
}

const formatDate = (value?: string) => {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('zh-CN', { hour12: false })
}

const formatScore = (item: any) => {
  if (typeof item?.relevance === 'number') return `${Math.round(item.relevance * 100)}%`
  if (typeof item?.distance === 'number') return item.distance.toFixed(4)
  return '-'
}

const resetFilters = () => {
  keyword.value = ''
  categoryFilter.value = ''
  sourceFilter.value = ''
  caseFilter.value = ''
  docTypeFilter.value = ''
}

const setActiveLibrary = (library: KnowledgeLibrary) => {
  activeLibrary.value = library
  resetFilters()
  activeView.value = library === 'case_library' || library === 'role_library' ? 'caseSync' : 'sources'
}

const setFormDefaults = (library = activeLibrary.value) => {
  const meta = libraryCatalog.find((item) => item.value === library) || libraryCatalog[libraryCatalog.length - 1]
  form.value = {
    title: '',
    category: meta.category,
    tags: '',
    source: 'manual',
    library: meta.value,
    content: '',
  }
  fileForm.value = {
    title: '',
    category: meta.category,
    tags: '',
    source: 'file_upload',
    library: meta.value,
    chunkSize: 800,
    overlap: 150,
  }
}

const pickUploadLibrary = (target: KnowledgeLibrary, mode: 'manual' | 'file') => {
  const meta = libraryMeta(target)
  if (mode === 'manual') {
    form.value.library = meta.value
    form.value.category = meta.category
  } else {
    fileForm.value.library = meta.value
    fileForm.value.category = meta.category
  }
}

const openManualUpload = () => {
  setFormDefaults(activeLibrary.value)
  showUpload.value = true
}

const openFileUpload = () => {
  setFormDefaults(activeLibrary.value)
  uploadFile.value = null
  lastUploadResult.value = null
  showFileUpload.value = true
}

const normalizeChunk = (item: any): KnowledgeChunk => ({
  ...item,
  tags: normalizeTags(item?.tags),
  library: normalizeLibrary(item?.library),
  source_id: item?.source_id || item?.metadata?.source_id,
  chunk_index: item?.chunk_index ?? item?.metadata?.chunk_index,
  created_at: item?.created_at || item?.metadata?.created_at,
  updated_at: item?.updated_at || item?.metadata?.updated_at,
})

const normalizeSource = (item: any): KnowledgeSource => ({
  ...item,
  tags: normalizeTags(item?.tags),
  library: normalizeLibrary(item?.library),
  chunks: Array.isArray(item?.chunks) ? item.chunks.map(normalizeChunk) : [],
})

const fetchKnowledge = async () => {
  loading.value = true
  try {
    const [general, cases, statPayload, sources]: any[] = await Promise.all([
      request.get('/knowledge/list', { params: { limit: 500 } }),
      request.get('/knowledge/cases'),
      request.get('/knowledge/stats'),
      request.get('/knowledge/sources'),
    ])
    knowledgeList.value = Array.isArray(general) ? general.map(normalizeChunk) : []
    caseKnowledgeList.value = Array.isArray(cases)
      ? cases.map((item) => ({
          ...normalizeChunk(item),
          case_id: item.case_id,
          case_title: item.case_title,
          doc_type: item.doc_type,
          role_id: item.role_id,
          role_name: item.role_name,
          in_knowledge: item.in_knowledge,
          library: normalizeLibrary(item.library || (item.doc_type === 'role_script' ? 'role_library' : 'case_library')),
        }))
      : []
    stats.value = statPayload || null
    sourceList.value = Array.isArray(sources) ? sources.map(normalizeSource) : []
  } catch (error) {
    console.error('Fetch knowledge error:', error)
    showFailToast('知识库加载失败')
  } finally {
    loading.value = false
  }
}

const openDetail = (item: KnowledgeChunk | CaseKnowledgeRow) => {
  selectedItem.value = item
  showDetail.value = true
}

const openSourceDetail = async (item: KnowledgeSource) => {
  selectedSource.value = item
  showSourceDetail.value = true
  if (!item.source_id || item.chunks?.length) return
  sourceDetailLoading.value = true
  try {
    const detail: any = await request.get(`/knowledge/sources/${encodeURIComponent(item.source_id)}`)
    selectedSource.value = normalizeSource(detail)
  } catch (error) {
    showFailToast('文档源详情加载失败')
  } finally {
    sourceDetailLoading.value = false
  }
}

const handleDeleteSource = async (sourceId: string) => {
  try {
    await showConfirmDialog({
      title: '确认删除文档源',
      message: '将删除该文档源生成的全部知识片段，操作不可恢复。',
    })
    await request.delete(`/knowledge/sources/${encodeURIComponent(sourceId)}`)
    showSuccessToast('文档源已删除')
    showSourceDetail.value = false
    await fetchKnowledge()
  } catch (error) {
    // user cancelled
  }
}

const openSearchView = (libraries: KnowledgeLibrary[] = [activeLibrary.value]) => {
  activeView.value = 'search'
  searchForm.value.libraries = libraries
}

const handleFileChange = (event: Event) => {
  const input = event.target as HTMLInputElement
  uploadFile.value = input.files?.[0] || null
}

const handleUpload = async () => {
  if (!form.value.library) {
    showFailToast('请选择知识分类')
    return
  }
  if (!form.value.content.trim()) {
    showFailToast('知识内容不能为空')
    return
  }
  try {
    const result: any = await request.post('/knowledge/upload', {
      text: form.value.content,
      title: form.value.title || undefined,
      category: form.value.category || undefined,
      library: form.value.library,
      tags: form.value.tags
        .split(/[,，\n]/)
        .map((item) => item.trim())
        .filter(Boolean),
      source: form.value.source || 'manual',
    })
    showSuccessToast(`知识条目已录入，生成 ${result?.chunks ?? 0} 个片段`)
    showUpload.value = false
    setFormDefaults(activeLibrary.value)
    await fetchKnowledge()
  } catch (error) {
    showFailToast('知识录入失败')
  }
}

const handleFileUpload = async () => {
  if (!fileForm.value.library) {
    showFailToast('请选择知识分类')
    return
  }
  if (!uploadFile.value) {
    showFailToast('请选择文件')
    return
  }
  const payload = new FormData()
  payload.append('file', uploadFile.value)
  payload.append('title', fileForm.value.title)
  payload.append('category', fileForm.value.category)
  payload.append('tags', fileForm.value.tags)
  payload.append('source', fileForm.value.source)
  payload.append('library', fileForm.value.library)
  payload.append('chunk_size', String(fileForm.value.chunkSize))
  payload.append('overlap', String(fileForm.value.overlap))
  try {
    const result: any = await request.post('/knowledge/upload-file', payload, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    lastUploadResult.value = result
    showSuccessToast(`文件已入库，生成 ${result?.chunks ?? 0} 个片段`)
    uploadFile.value = null
    showFileUpload.value = false
    await fetchKnowledge()
  } catch (error) {
    showFailToast('文件入库失败')
  }
}

const handleSearch = async () => {
  if (!searchForm.value.query.trim()) {
    showFailToast('请输入检索内容')
    return
  }
  searchLoading.value = true
  try {
    const libraries = searchForm.value.libraries.length
      ? searchForm.value.libraries
      : libraryCatalog.map((item) => item.value)
    const res: any = await request.post('/knowledge/search', {
      query: searchForm.value.query,
      limit: searchForm.value.limit,
      libraries,
    })
    searchResult.value = res
    activeView.value = 'search'
  } catch (error) {
    showFailToast('检索失败')
  } finally {
    searchLoading.value = false
  }
}

const openHitSource = (hit: any) => {
  const sourceId = hit?.source_id || hit?.metadata?.source_id
  const matched = sourceList.value.find((item) => item.source_id === sourceId)
  if (matched) {
    openSourceDetail(matched)
  } else {
    openDetail(normalizeChunk(hit))
  }
}

const copyText = async (value: string) => {
  if (!value) return
  try {
    await navigator.clipboard.writeText(value)
    showSuccessToast('已复制')
  } catch (error) {
    showFailToast('复制失败')
  }
}

const handleDelete = async (id: string) => {
  try {
    await showConfirmDialog({
      title: '确认删除',
      message: '确定要从知识库中移除这条知识片段吗？',
    })
    await request.delete(`/knowledge/${encodeURIComponent(id)}`)
    showSuccessToast('已删除')
    await fetchKnowledge()
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

watch(activeLibrary, () => {
  categoryFilter.value = ''
  sourceFilter.value = ''
  caseFilter.value = ''
  docTypeFilter.value = ''
  setFormDefaults(activeLibrary.value)
})

onMounted(() => {
  setFormDefaults(activeLibrary.value)
  fetchKnowledge()
})
</script>

<template>
  <div class="knowledge-page">
    <section class="page-head">
      <div>
        <h1>???????</h1>
        <p>?????????????????????????????? RAG ???</p>
      </div>
      <div class="head-actions">
        <van-button plain icon="replay" :loading="loading" @click="fetchKnowledge">??</van-button>
        <van-button plain icon="search" :loading="searchLoading" @click="openSearchView()">????</van-button>
        <van-button plain icon="description" @click="openFileUpload">????</van-button>
        <van-button type="primary" icon="plus" @click="openManualUpload">????</van-button>
      </div>
    </section>

<section class="overview-grid">
      <button
        v-for="item in overviewCards"
        :key="item.value"
        type="button"
        :class="['library-card', { active: activeLibrary === item.value }]"
        @click="setActiveLibrary(item.value)"
      >
        <div class="library-card__head">
          <span>{{ item.label }}</span>
          <strong>{{ item.chunkCount }}</strong>
        </div>
        <p>{{ item.description }}</p>
        <div class="library-card__meta">
          <span>文档 {{ item.sourceCount }}</span>
          <span>{{ statusLabel(item.ingestStatus) }}</span>
          <span>{{ statusLabel(item.retrievalStatus) }}</span>
        </div>
      </button>
    </section>

    <section class="status-strip">
      <div>
        <span>总文档源</span>
        <strong>{{ stats?.total_sources ?? sourceList.length }}</strong>
      </div>
      <div>
        <span>总知识片段</span>
        <strong>{{ stats?.total_chunks ?? knowledgeList.length }}</strong>
      </div>
      <div>
        <span>当前分类</span>
        <strong>{{ activeStats?.chunk_count ?? activeChunks.length }}</strong>
      </div>
      <div>
        <span>检索状态</span>
        <strong :class="stats?.embedding_available === false ? 'text-warn' : 'text-ok'">
          {{ stats?.embedding_available === false ? '降级' : '正常' }}
        </strong>
      </div>
      <div>
        <span>考察点引用</span>
        <strong>{{ totalRefs }}</strong>
      </div>
    </section>

    <section class="active-library-panel">
      <div class="active-copy">
        <h2>{{ activeLibraryMeta.label }}</h2>
        <p>{{ activeLibraryMeta.description }}</p>
        <div class="hint-row">
          <span>{{ activeLibraryMeta.examples }}</span>
          <span>最近更新：{{ formatDate(activeStats?.latest_updated_at) }}</span>
        </div>
      </div>
      <div class="view-tabs">
        <button :class="{ active: activeView === 'sources' }" @click="activeView = 'sources'">文档源管理</button>
        <button :class="{ active: activeView === 'chunks' }" @click="activeView = 'chunks'">知识片段管理</button>
        <button v-if="canSyncCases" :class="{ active: activeView === 'caseSync' }" @click="activeView = 'caseSync'">案件库同步</button>
        <button :class="{ active: activeView === 'search' }" @click="openSearchView()">检索测试</button>
      </div>
    </section>

    <section class="toolbar">
      <label class="search-box">
        <van-icon name="search" />
        <input v-model.trim="keyword" type="text" placeholder="搜索标题、内容、来源、标签或 ID" />
      </label>
      <div class="filter-items" v-if="activeView !== 'search'">
        <label class="filter-item" v-if="activeView !== 'caseSync'">
          <span>分类</span>
          <select v-model="categoryFilter">
            <option value="">全部</option>
            <option v-for="item in categoryOptions" :key="item" :value="item">{{ item }}</option>
          </select>
        </label>
        <label class="filter-item" v-if="activeView !== 'caseSync'">
          <span>来源</span>
          <select v-model="sourceFilter">
            <option value="">全部</option>
            <option v-for="item in sourceOptions" :key="item" :value="item">{{ item }}</option>
          </select>
        </label>
        <template v-if="activeView === 'caseSync'">
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
        </template>
      </div>
    </section>

    <section v-if="stats?.embedding_available === false" class="degraded-banner">
      <van-icon name="warning-o" />
      <span>Embedding 服务当前不可用，检索与入库会使用降级能力。{{ stats?.embedding_error }}</span>
    </section>

    <section v-if="activeView === 'sources'" class="list-card">
      <div class="list-head">
        <div>
          <h3>文档源管理</h3>
          <p>按上传文件或手工录入来源聚合，查看每份资料生成了多少知识片段。</p>
        </div>
        <div class="list-actions">
          <van-button plain icon="search" @click="openSearchView([activeLibrary])">测试本分类</van-button>
          <van-button type="primary" icon="description" @click="openFileUpload">导入文件</van-button>
        </div>
      </div>

      <div v-if="loading" class="loading-box">
        <van-loading type="spinner" color="#1D3557" />
      </div>
      <div v-else-if="filteredSources.length" class="table-wrap">
        <table class="knowledge-table">
          <thead>
            <tr>
              <th>文档源</th>
              <th>分类</th>
              <th>来源</th>
              <th>片段数</th>
              <th>最近更新</th>
              <th>解析方式</th>
              <th>状态</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in filteredSources" :key="item.source_id">
              <td>
                <div class="row-title">{{ item.title || item.source_id }}</div>
                <div class="id-text">{{ item.source_id }}</div>
                <div v-if="item.filename" class="id-text">文件：{{ item.filename }}</div>
              </td>
              <td><span class="category-chip">{{ item.category || activeLibraryMeta.category }}</span></td>
              <td><span class="source-chip">{{ item.source || 'unknown' }}</span></td>
              <td>{{ item.chunk_count || item.chunks?.length || 0 }}</td>
              <td>{{ formatDate(item.updated_at || item.created_at) }}</td>
              <td>
                <div>{{ item.extract_method || '-' }}</div>
                <div class="id-text">{{ item.file_type || '-' }}</div>
              </td>
              <td><span class="status-chip ok">{{ statusLabel(item.status || 'ready') }}</span></td>
              <td class="actions-cell">
                <van-button size="small" plain @click="openSourceDetail(item)">查看</van-button>
                <van-button size="small" danger plain @click="handleDeleteSource(item.source_id)">删除</van-button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-else class="empty-box">
        <van-icon name="description-o" size="52" />
        <p>暂无文档源，可导入文件或新增知识；案件知识与角色剧本也可从案件库同步生成。</p>
      </div>
    </section>

    <section v-else-if="activeView === 'chunks'" class="list-card">
      <div class="list-head">
        <div>
          <h3>知识片段管理</h3>
          <p>展示切片后的 chunk 内容，训练时按这些片段进行向量检索召回。</p>
        </div>
        <div class="filter-summary">当前 {{ filteredChunks.length }} / {{ activeChunks.length }} 条</div>
      </div>

      <div v-if="loading" class="loading-box">
        <van-loading type="spinner" color="#1D3557" />
      </div>
      <div v-else-if="filteredChunks.length" class="table-wrap">
        <table class="knowledge-table">
          <thead>
            <tr>
              <th>标题 / 内容</th>
              <th>分类</th>
              <th>来源</th>
              <th>Chunk</th>
              <th>标签</th>
              <th>引用</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in filteredChunks" :key="item.id">
              <td>
                <div class="row-title">{{ item.title || '未命名知识' }}</div>
                <div class="preview-cell">{{ item.content }}</div>
                <div class="id-text">{{ item.id }}</div>
              </td>
              <td><span class="category-chip">{{ item.category || activeLibraryMeta.category }}</span></td>
              <td><span class="source-chip">{{ item.source || 'manual' }}</span></td>
              <td>
                <div>{{ item.chunk_index ?? item.metadata?.chunk_index ?? '-' }}</div>
                <div class="id-text">{{ item.source_id || item.metadata?.source_id || '-' }}</div>
              </td>
              <td>
                <div v-if="item.tags?.length" class="tag-list">
                  <span v-for="tag in item.tags" :key="tag" class="tag-chip">{{ tag }}</span>
                </div>
                <span v-else class="muted">-</span>
              </td>
              <td>{{ item.referenced_by_count || 0 }} 次</td>
              <td class="actions-cell">
                <van-button size="small" plain @click="openDetail(item)">查看</van-button>
                <van-button
                  icon="delete-o"
                  size="small"
                  danger
                  plain
                  @click="handleDelete(item.id)"
                />
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-else class="empty-box">
        <van-icon name="comment-o" size="52" />
        <p>暂无知识片段</p>
      </div>
    </section>

    <section v-else-if="activeView === 'caseSync'" class="list-card">
      <div class="list-head">
        <div>
          <h3>案件库同步</h3>
          <p>案件信息与角色剧本从案件库生成，避免在知识库中重复维护。</p>
        </div>
        <van-button type="primary" icon="exchange" :loading="syncing" @click="handleSyncAllCases">同步全部案件</van-button>
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
          <h3>检索测试</h3>
          <p>按单分类、多分类或全知识库测试召回效果，查看来源和相关度。</p>
        </div>
      </div>
      <div class="search-lab">
        <label>
          <span>检索内容</span>
          <input v-model="searchForm.query" type="text" class="input" placeholder="例如：受害人拒绝配合调查怎么办" />
        </label>
        <div class="inline-grid">
          <label>
            <span>Top K</span>
            <input v-model.number="searchForm.limit" type="number" class="input" min="1" max="10" />
          </label>
          <label>
            <span>知识分类</span>
            <select v-model="searchForm.libraries" class="input multi-select" multiple>
              <option v-for="item in libraryOptions" :key="item.value" :value="item.value">{{ item.label }}</option>
            </select>
          </label>
        </div>
        <div class="search-actions">
          <van-button plain @click="searchForm.libraries = [activeLibrary]">当前分类</van-button>
          <van-button plain @click="searchForm.libraries = libraryCatalog.map((item) => item.value)">全知识库</van-button>
          <van-button type="primary" icon="search" :loading="searchLoading" @click="handleSearch">开始检索</van-button>
        </div>
      </div>

      <div v-if="searchResult?.embedding_error" class="degraded-banner inline">
        <van-icon name="warning-o" />
        <span>当前为降级检索：{{ searchResult.embedding_error }}</span>
      </div>

      <div v-if="searchResult?.hits?.length" class="search-result-list">
        <article v-for="item in searchResult.hits" :key="item.id" class="search-result-item">
          <div class="search-result-head">
            <div>
              <strong>{{ item.title || item.id }}</strong>
              <p>{{ item.id }}</p>
            </div>
            <div class="result-badges">
              <span>{{ libraryLabel(item.library) }}</span>
              <span>相关度 {{ formatScore(item) }}</span>
              <span>{{ item.metadata?.source_id || item.source_id || 'source -' }}</span>
            </div>
          </div>
          <pre>{{ item.content }}</pre>
          <div class="result-actions">
            <van-button size="small" plain @click="openHitSource(item)">打开来源</van-button>
          </div>
        </article>
      </div>
      <div v-else class="empty-box compact">
        <p>暂无检索结果</p>
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
          <span>{{ libraryLabel(selectedItem?.library) }}</span>
          <span>{{ (selectedItem as CaseKnowledgeRow)?.doc_type === 'role_script' ? '角色剧本' : selectedItem?.category || '知识条目' }}</span>
          <span v-if="selectedItem?.source_id || selectedItem?.metadata?.source_id">来源：{{ selectedItem?.source_id || selectedItem?.metadata?.source_id }}</span>
          <span v-if="selectedItem?.chunk_index !== undefined || selectedItem?.metadata?.chunk_index !== undefined">
            Chunk：{{ selectedItem?.chunk_index ?? selectedItem?.metadata?.chunk_index }}
          </span>
          <span v-if="(selectedItem as CaseKnowledgeRow)?.role_name">角色：{{ (selectedItem as CaseKnowledgeRow).role_name }}</span>
          <span v-if="(selectedItem as CaseKnowledgeRow)?.in_knowledge !== undefined">
            {{ (selectedItem as CaseKnowledgeRow).in_knowledge ? '已同步到知识库' : '数据库快照，尚未同步' }}
          </span>
        </div>
        <pre class="detail-content">{{ selectedItem?.content || '暂无内容' }}</pre>
      </div>
    </van-popup>

    <van-popup v-model:show="showSourceDetail" teleport="body" class="detail-popup" :style="{ width: 'min(860px, 96vw)' }">
      <div class="drawer">
        <div class="drawer-head">
          <div>
            <h3>{{ selectedSource?.title || selectedSource?.source_id || '文档源详情' }}</h3>
            <p>{{ selectedSource?.source_id }}</p>
          </div>
          <van-icon name="cross" class="drawer-close" @click="showSourceDetail = false" />
        </div>
        <div class="detail-meta">
          <span>{{ libraryLabel(selectedSource?.library) }}</span>
          <span>{{ selectedSource?.category || '通用' }}</span>
          <span>{{ selectedSource?.source || 'unknown' }}</span>
          <span>片段 {{ selectedSource?.chunk_count || selectedSource?.chunks?.length || 0 }}</span>
          <span v-if="selectedSource?.filename">文件：{{ selectedSource.filename }}</span>
          <span v-if="selectedSource?.extract_method">解析：{{ selectedSource.extract_method }}</span>
          <span v-if="selectedSource?.updated_at">更新：{{ formatDate(selectedSource.updated_at) }}</span>
        </div>
        <div v-if="sourceDetailLoading" class="loading-box compact">
          <van-loading type="spinner" color="#1D3557" />
        </div>
        <div v-else class="source-chunks">
          <article v-for="chunk in selectedSource?.chunks || []" :key="chunk.id" class="source-chunk">
            <div class="source-chunk__head">
              <strong>{{ chunk.title || chunk.id }}</strong>
              <span class="source-chunk__actions">
                <button type="button" class="text-link" @click="copyText(chunk.id)">复制ID</button>
                <span>Chunk {{ chunk.metadata?.chunk_index ?? chunk.chunk_index ?? '-' }}</span>
              </span>
            </div>
            <pre>{{ chunk.content }}</pre>
          </article>
        </div>
        <div class="drawer-actions">
          <van-button
            v-if="selectedSource?.source_id"
            block
            danger
            plain
            @click="handleDeleteSource(selectedSource.source_id)"
          >
            删除文档源
          </van-button>
        </div>
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
            <p>请选择案件知识、角色剧本、法律法规、处置流程、教学资料等知识类型，保存后自动进入对应 RAG 分类。</p>
          </div>
          <van-icon name="cross" class="drawer-close" @click="showUpload = false" />
        </div>
        <div class="drawer-form">
          <div class="library-picker">
          <div class="field-title">
            <span>知识类型</span>
            <strong>当前选择：{{ selectedFormLibraryMeta.label }}</strong>
          </div>
            <div class="library-picker__grid">
              <button
                v-for="item in libraryCatalog"
                :key="item.value"
                type="button"
                :class="['library-picker__option', { active: form.library === item.value }]"
                @click="pickUploadLibrary(item.value, 'manual')"
              >
                <span>{{ item.label }}</span>
                <small>{{ item.examples }}</small>
              </button>
            </div>
            <p class="field-help">
              所有类型都可手工录入；案件知识、角色剧本也可通过案件库同步批量生成。
            </p>
            <p class="field-help">这里选择的类型会直接写入对应 RAG 分类，影响后续检索和召回范围。</p>
          </div>
          <label>标题</label>
          <input v-model="form.title" type="text" class="input" placeholder="例如：现场询问注意事项" />
          <label>知识类型</label>
          <select v-model="form.library" class="input">
            <option v-for="item in libraryOptions" :key="item.value" :value="item.value">{{ item.label }}</option>
          </select>
          <label>业务分类</label>
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

    <van-popup
      v-model:show="showFileUpload"
      teleport="body"
      :style="{ width: 'min(560px, 92vw)', maxHeight: '88vh', borderRadius: '12px', overflow: 'hidden' }"
    >
      <div class="drawer">
        <div class="drawer-head">
          <div>
            <h3>导入知识文件</h3>
            <p>请选择案件知识、角色剧本、法律法规、处置流程、教学资料等知识类型，文件会自动解析入库。</p>
          </div>
          <van-icon name="cross" class="drawer-close" @click="showFileUpload = false" />
        </div>
        <div class="drawer-form">
          <label>文件</label>
          <input type="file" class="input" accept=".pdf,.docx,.txt,.md,.markdown" @change="handleFileChange" />
          <label>标题</label>
          <input v-model="fileForm.title" type="text" class="input" placeholder="不填则使用文件名" />
          <div class="library-picker">
            <div class="field-title">
              <span>知识类型</span>
              <strong>当前选择：{{ selectedFileLibraryMeta.label }}</strong>
            </div>
            <div class="library-picker__grid">
              <button
                v-for="item in libraryCatalog"
                :key="item.value"
                type="button"
                :class="['library-picker__option', { active: fileForm.library === item.value }]"
                @click="pickUploadLibrary(item.value, 'file')"
              >
                <span>{{ item.label }}</span>
                <small>{{ item.examples }}</small>
              </button>
            </div>
            <p class="field-help">
              所有类型都可文件入库；案件知识、角色剧本也可通过案件库同步批量生成。
            </p>
            <p class="field-help">这里选择的类型会直接写入对应 RAG 分类，影响后续检索和召回范围。</p>
          </div>
          <label>知识类型</label>
          <select v-model="fileForm.library" class="input">
            <option v-for="item in libraryOptions" :key="item.value" :value="item.value">{{ item.label }}</option>
          </select>
          <label>业务分类</label>
          <input v-model="fileForm.category" type="text" class="input" placeholder="例如：法律法规 / SOP / 教学资料" />
          <label>标签</label>
          <input v-model="fileForm.tags" type="text" class="input" placeholder="多个标签用逗号分隔" />
          <div class="inline-grid">
            <label>
              <span>切片长度</span>
              <input v-model.number="fileForm.chunkSize" type="number" class="input" min="200" max="3000" />
            </label>
            <label>
              <span>重叠长度</span>
              <input v-model.number="fileForm.overlap" type="number" class="input" min="0" max="1000" />
            </label>
          </div>
        </div>
        <div class="drawer-actions">
          <van-button block type="primary" @click="handleFileUpload">解析并入库</van-button>
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

.page-head,
.active-library-panel,
.list-card,
.toolbar,
.status-strip,
.degraded-banner {
  border: 1px solid var(--police-border);
  border-radius: 8px;
  background: #fff;
}

.page-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 18px 20px;
}

.page-head h1,
.active-copy h2,
.list-head h3,
.drawer-head h3 {
  margin: 0;
  color: var(--police-text-primary);
}

.page-head p,
.active-copy p,
.list-head p,
.drawer-head p,
.search-result-head p {
  margin: 6px 0 0;
  color: var(--police-text-muted);
  font-size: 13px;
}

.head-actions,
.list-actions,
.actions-cell,
.search-actions,
.result-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  white-space: nowrap;
}



.overview-grid {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 10px;
}

.library-card {
  min-height: 132px;
  border: 1px solid var(--police-border);
  border-radius: 8px;
  background: #fff;
  padding: 14px;
  text-align: left;
  cursor: pointer;
  transition: border-color 0.2s ease, box-shadow 0.2s ease, transform 0.2s ease;
}

.library-card.active {
  border-color: var(--police-primary);
  box-shadow: 0 8px 22px rgba(29, 53, 87, 0.12);
  transform: translateY(-1px);
}

.library-card__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.library-card__head span {
  color: #0f172a;
  font-size: 14px;
  font-weight: 700;
}

.library-card__head strong {
  color: var(--police-primary);
  font-size: 24px;
}

.library-card p {
  min-height: 42px;
  margin: 8px 0 12px;
  color: var(--police-text-muted);
  font-size: 12px;
  line-height: 1.5;
}

.library-card__meta,
.hint-row,
.detail-meta,
.result-badges {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.library-card__meta span,
.hint-row span,
.detail-meta span,
.result-badges span {
  border-radius: 999px;
  background: #f1f5f9;
  padding: 4px 8px;
  color: #334155;
  font-size: 12px;
}

.status-strip {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 10px;
  padding: 12px 16px;
}

.status-strip span {
  display: block;
  color: var(--police-text-muted);
  font-size: 12px;
}

.status-strip strong {
  display: block;
  margin-top: 4px;
  color: #0f172a;
  font-size: 20px;
}

.text-ok {
  color: #166534 !important;
}

.text-warn {
  color: #92400e !important;
}

.active-library-panel {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  padding: 16px;
}

.active-copy {
  min-width: 0;
}

.view-tabs {
  display: inline-flex;
  flex-shrink: 0;
  gap: 4px;
  border: 1px solid var(--police-border);
  border-radius: 8px;
  padding: 4px;
}

.view-tabs button {
  height: 32px;
  border: none;
  border-radius: 6px;
  background: transparent;
  padding: 0 12px;
  color: var(--police-text-secondary);
  cursor: pointer;
}

.view-tabs button.active {
  background: var(--police-primary);
  color: #fff;
}

.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  padding: 12px;
}

.search-box {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  width: min(420px, 100%);
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

.filter-items {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
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

.degraded-banner {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  color: #92400e;
  background: #fffbeb;
  font-size: 13px;
}

.degraded-banner.inline {
  margin-top: 12px;
}

.list-card {
  padding: 16px;
}

.list-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
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
  min-width: 1040px;
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
  min-height: 220px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: var(--police-text-muted);
  text-align: center;
}

.compact {
  min-height: 120px;
}

.search-lab,
.drawer-form {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.library-picker {
  border: 1px solid var(--police-border);
  border-radius: 8px;
  background: #f8fafc;
  padding: 12px;
}

.field-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 10px;
  color: #334155;
  font-size: 13px;
  font-weight: 700;
}

.field-title strong {
  color: var(--police-primary);
  font-size: 12px;
}

.library-picker__grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}

.library-picker__option {
  min-height: 68px;
  border: 1px solid var(--police-border);
  border-radius: 8px;
  background: #fff;
  padding: 10px;
  text-align: left;
  cursor: pointer;
}

.library-picker__option span,
.library-picker__option small {
  display: block;
}

.library-picker__option span {
  color: #0f172a;
  font-size: 13px;
  font-weight: 700;
}

.library-picker__option small {
  margin-top: 4px;
  color: var(--police-text-muted);
  font-size: 12px;
  line-height: 1.4;
}

.library-picker__option.active {
  border-color: var(--police-primary);
  background: #eff6ff;
  box-shadow: 0 0 0 2px rgba(29, 53, 87, 0.08);
}

.library-picker__option.disabled {
  background: #f1f5f9;
}

.library-picker__option.disabled small {
  color: #92400e;
}

.field-help {
  margin: 10px 0 0;
  color: var(--police-text-muted);
  font-size: 12px;
  line-height: 1.5;
}

.search-lab label,
.drawer-form label,
.inline-grid label {
  display: flex;
  flex-direction: column;
  gap: 6px;
  color: #334155;
  font-size: 13px;
  font-weight: 700;
}

.inline-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
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

.multi-select {
  min-height: 120px;
  padding: 8px 10px;
}

.search-result-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-top: 14px;
}

.search-result-item {
  border: 1px solid var(--police-border);
  border-radius: 8px;
  background: #f8fafc;
  padding: 12px;
}

.search-result-head,
.source-chunk__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
}

.search-result-item pre,
.source-chunk pre,
.detail-content {
  margin: 0;
  white-space: pre-wrap;
  color: #0f172a;
  font-family: inherit;
  font-size: 13px;
  line-height: 1.7;
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

.detail-content {
  max-height: 62vh;
  overflow: auto;
  border: 1px solid var(--police-border);
  border-radius: 8px;
  background: #f8fafc;
  padding: 14px;
  font-size: 14px;
  line-height: 1.8;
}

.source-chunks {
  display: flex;
  flex-direction: column;
  gap: 10px;
  max-height: 62vh;
  overflow: auto;
}

.source-chunk {
  border: 1px solid var(--police-border);
  border-radius: 8px;
  background: #f8fafc;
  padding: 12px;
}

.source-chunk__head span {
  color: var(--police-text-muted);
  font-size: 12px;
}

.source-chunk__actions {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  white-space: nowrap;
}

.text-link {
  border: none;
  background: transparent;
  padding: 0;
  color: var(--police-primary);
  cursor: pointer;
  font-size: 12px;
}

.drawer-form {
  overflow-y: auto;
}

.drawer-actions {
  padding-top: 16px;
}

@media (max-width: 1280px) {
  .overview-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 900px) {
  .page-head,
  .toolbar,
  .list-head,
  .active-library-panel,
  .search-result-head {
    align-items: stretch;
    flex-direction: column;
  }

  .overview-grid,
  .status-strip {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .view-tabs,
  .head-actions,
  .list-actions,
  .search-actions {
    flex-wrap: wrap;
  }

  .inline-grid {
    grid-template-columns: 1fr;
  }

  .library-picker__grid {
    grid-template-columns: 1fr;
  }
}
</style>
