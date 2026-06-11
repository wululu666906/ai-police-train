<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import request from '../utils/request'
import { showConfirmDialog, showFailToast, showSuccessToast } from 'vant'

const knowledgeList = ref<any[]>([])
const knowledgeSearchText = ref('')
const knowledgeCategoryFilter = ref('')
const knowledgeSourceFilter = ref('')
const loading = ref(false)
const showUpload = ref(false)
const form = ref({
  title: '',
  category: '',
  tags: '',
  source: 'manual',
  content: '',
})

const totalRefs = computed(() => knowledgeList.value.reduce((sum, item) => sum + Number(item.referenced_by_count || 0), 0))
const categoryFilterOptions = computed(() =>
  Array.from(new Set(knowledgeList.value.map((item) => String(item?.category || '').trim()).filter(Boolean))).sort()
)
const sourceFilterOptions = computed(() =>
  Array.from(new Set(knowledgeList.value.map((item) => String(item?.source || '').trim()).filter(Boolean))).sort()
)
const filteredKnowledgeList = computed(() => {
  const keyword = knowledgeSearchText.value.trim()
  return knowledgeList.value.filter((item) => {
    if (knowledgeCategoryFilter.value && item.category !== knowledgeCategoryFilter.value) return false
    if (knowledgeSourceFilter.value && item.source !== knowledgeSourceFilter.value) return false
    if (!keyword) return true
    const haystack = [
      item.title,
      item.content,
      item.category,
      item.source,
      ...(Array.isArray(item.tags) ? item.tags : []),
      ...(Array.isArray(item.referenced_by) ? item.referenced_by : []),
    ].join(' ')
    return haystack.includes(keyword)
  })
})

const fetchKnowledge = async () => {
  loading.value = true
  try {
    const res: any = await request.get('/knowledge/list')
    knowledgeList.value = Array.isArray(res) ? res : []
  } catch (error) {
    console.error('Fetch knowledge error:', error)
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
      message: '确定要从知识库中移除这条知识吗？删除后相关考察点将失去引用。',
    })
    await request.delete(`/knowledge/${id}`)
    showSuccessToast('已删除')
    fetchKnowledge()
  } catch (error) {
    // noop
  }
}

onMounted(fetchKnowledge)
</script>

<template>
  <div class="knowledge-page">
    <section class="hero">
      <div>
        <h1>知识库管理</h1>
        <p>为考察点配置可引用的法规、流程与执法提示，让评估和训练都更有依据。</p>
      </div>
      <van-button type="primary" icon="plus" class="hero-btn" @click="showUpload = true">
        新增知识条目
      </van-button>
    </section>

    <section class="stats">
      <article class="stat-card">
        <span>知识条目</span>
        <strong>{{ knowledgeList.length }}</strong>
      </article>
      <article class="stat-card">
        <span>被引用次数</span>
        <strong>{{ totalRefs }}</strong>
      </article>
      <article class="stat-card">
        <span>知识状态</span>
        <strong>在线</strong>
      </article>
    </section>

    <section class="list-card">
      <div class="list-head">
        <div>
          <h3>知识清单</h3>
          <p>支持标题、分类、标签、来源和反向引用查看。</p>
        </div>
        <van-button icon="replay" size="small" plain round @click="fetchKnowledge" />
      </div>

      <div class="filter-panel">
        <div class="filter-bar">
          <label class="filter-item">
            <span>分类</span>
            <select v-model="knowledgeCategoryFilter">
              <option value="">全部</option>
              <option v-for="item in categoryFilterOptions" :key="item" :value="item">{{ item }}</option>
            </select>
          </label>
          <label class="filter-item">
            <span>来源</span>
            <select v-model="knowledgeSourceFilter">
              <option value="">全部</option>
              <option v-for="item in sourceFilterOptions" :key="item" :value="item">{{ item }}</option>
            </select>
          </label>
        </div>
        <label class="search-box">
          <van-icon name="search" />
          <input v-model.trim="knowledgeSearchText" type="text" placeholder="搜索标题、内容、标签或引用" />
        </label>
        <div class="filter-summary">当前筛选 {{ filteredKnowledgeList.length }} / {{ knowledgeList.length }} 条</div>
      </div>

      <div v-if="loading" class="loading-box">
        <van-loading type="spinner" color="#1D3557" />
      </div>

      <div v-else-if="filteredKnowledgeList.length" class="knowledge-table-wrap">
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
            <tr v-for="item in filteredKnowledgeList" :key="item.id">
              <td class="knowledge-title-cell">
                <div class="knowledge-row-title">{{ item.title || '未命名知识' }}</div>
                <div class="knowledge-row-content">{{ item.content }}</div>
                <div class="id-text">{{ item.id }}</div>
              </td>
              <td><span class="category-chip">{{ item.category || '通用' }}</span></td>
              <td><span class="source-chip">{{ item.source || 'manual' }}</span></td>
              <td>
                <div v-if="item.tags?.length" class="tag-list tag-list--compact">
                  <span v-for="tag in item.tags" :key="tag" class="tag-chip">{{ tag }}</span>
                </div>
                <span v-else class="reference-empty">-</span>
              </td>
              <td class="reference-cell">
                <strong>{{ item.referenced_by_count || 0 }} 次</strong>
                <div v-if="item.referenced_by?.length" class="reference-list reference-list--compact">
                  <span v-for="ref in item.referenced_by.slice(0, 3)" :key="ref" class="reference-chip">{{ ref }}</span>
                  <span v-if="item.referenced_by.length > 3" class="reference-empty">+{{ item.referenced_by.length - 3 }}</span>
                </div>
              </td>
              <td>
                <van-button icon="delete-o" size="small" danger plain class="delete-btn" @click="handleDelete(item.id)" />
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div v-else class="empty-box">
        <van-icon name="comment-o" size="56" />
        <p>暂无知识条目</p>
        <span>可以先录入法规、流程要点或处置模板。</span>
      </div>
    </section>

    <van-popup
      v-model:show="showUpload"
      teleport="body"
      :style="{ width: 'min(560px, 92vw)', maxHeight: '88vh', borderRadius: '18px', overflow: 'hidden' }"
      class="knowledge-upload-popup"
    >
      <div class="drawer">
        <div class="drawer-head">
          <div>
            <h3>新增知识条目</h3>
            <p>录入后可在考察点里直接关联引用。</p>
          </div>
          <van-icon name="cross" class="drawer-close" @click="showUpload = false" />
        </div>

        <div class="drawer-form">
          <label>标题</label>
          <input v-model="form.title" type="text" class="input" placeholder="例如：酒驾现场呼气检测告知要点" />

          <label>分类</label>
          <input v-model="form.category" type="text" class="input" placeholder="例如：道路交通 / 现场处置" />

          <label>标签</label>
          <input v-model="form.tags" type="text" class="input" placeholder="多个标签用逗号分隔" />

          <label>来源</label>
          <input v-model="form.source" type="text" class="input" placeholder="例如：manual / 法条 / 内部规范" />

          <label>知识内容</label>
          <textarea v-model="form.content" rows="12" class="textarea" placeholder="请输入法规条文、处置流程或教学提示..."></textarea>
        </div>

        <div class="drawer-actions">
          <van-button block round type="primary" class="submit-btn" @click="handleUpload">
            保存知识条目
          </van-button>
        </div>
      </div>
    </van-popup>
  </div>
</template>

<style scoped>
.knowledge-page {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.hero,
.list-card,
.stat-card {
  border-radius: var(--police-radius-lg);
  background: #fff;
  border: 1px solid var(--police-border);
}

.hero {
  display: flex;
  justify-content: space-between;
  gap: 18px;
  padding: 18px 20px;
}

.hero h1 {
  margin: 0;
  color: var(--police-text-primary);
  font-size: 22px;
  font-weight: 800;
}

.hero p {
  margin: 4px 0 0;
  color: var(--police-text-muted);
  font-size: 13px;
}

.hero-btn {
  align-self: center;
  border-radius: var(--police-radius) !important;
  border: none !important;
  background: var(--police-primary) !important;
}

.stats {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
}

.stat-card {
  padding: 16px 18px;
}

.stat-card span {
  display: block;
  color: #64748b;
  font-size: 13px;
}

.stat-card strong {
  display: block;
  margin-top: 8px;
  font-size: 28px;
  color: #0f172a;
}

.list-card {
  padding: 16px 20px;
}

.list-head {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: center;
  margin-bottom: 18px;
}

.filter-panel {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  margin-bottom: 16px;
  border: 1px solid var(--police-border);
  border-radius: var(--police-radius-lg);
  background: #fff;
  padding: 14px 16px;
}

.filter-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.filter-item {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: var(--police-text-secondary);
  font-size: 13px;
}

.filter-item select {
  min-width: 112px;
  height: 34px;
  border: 1px solid var(--police-border);
  border-radius: var(--police-radius);
  background: #fff;
  padding: 0 10px;
  color: var(--police-text-primary);
}

.search-box {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  width: min(360px, 100%);
  height: 34px;
  border: 1px solid var(--police-border);
  border-radius: var(--police-radius);
  background: #fff;
  padding: 0 12px;
  color: var(--police-text-muted);
}

.search-box input {
  min-width: 0;
  flex: 1;
  border: none;
  background: transparent;
  color: var(--police-text-primary);
  font-size: 13px;
  outline: none;
}

.filter-summary {
  color: var(--police-text-muted);
  font-size: 13px;
}

.list-head h3 {
  margin: 0;
  color: #0f172a;
}

.list-head p {
  margin: 6px 0 0;
  color: #64748b;
  font-size: 13px;
}

.loading-box,
.empty-box {
  min-height: 260px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #94a3b8;
  text-align: center;
}

.knowledge-list {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.knowledge-table-wrap {
  overflow-x: auto;
  border: 1px solid var(--police-border);
  border-radius: var(--police-radius-lg);
  background: #fff;
}

.knowledge-table {
  width: 100%;
  min-width: 960px;
  border-collapse: collapse;
}

.knowledge-table th {
  background: #f8fafc;
  border-bottom: 1px solid var(--police-border);
  padding: 12px 14px;
  text-align: left;
  font-size: 13px;
  font-weight: 700;
  color: var(--police-text-secondary);
  white-space: nowrap;
}

.knowledge-table td {
  border-bottom: 1px solid var(--police-border-light);
  padding: 13px 14px;
  vertical-align: top;
  font-size: 13px;
  color: var(--police-text-primary);
}

.knowledge-table tr:last-child td {
  border-bottom: none;
}

.knowledge-table tbody tr:hover td {
  background: #f8fafc;
}

.knowledge-title-cell {
  width: 42%;
}

.knowledge-row-title {
  font-weight: 700;
  color: #0f172a;
}

.knowledge-row-content {
  display: -webkit-box;
  margin-top: 6px;
  max-width: 560px;
  overflow: hidden;
  color: #475569;
  line-height: 1.65;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}

.reference-cell {
  min-width: 120px;
}

.knowledge-item {
  display: flex;
  gap: 16px;
  justify-content: space-between;
  align-items: flex-start;
  padding: 18px;
  border-radius: 22px;
  background: #f8fafc;
}

.knowledge-main {
  flex: 1;
  min-width: 0;
}

.knowledge-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 10px;
}

.source-chip,
.category-chip,
.tag-chip,
.reference-chip {
  padding: 5px 10px;
  border-radius: 999px;
  font-size: 12px;
}

.source-chip {
  background: rgba(22, 93, 255, 0.1);
  color: #165dff;
}

.category-chip {
  background: rgba(0, 180, 42, 0.1);
  color: #00b42a;
}

.id-text {
  align-self: center;
  color: #94a3b8;
  font-size: 11px;
}

.knowledge-item h4 {
  margin: 0;
  color: #0f172a;
}

.knowledge-item p {
  margin: 10px 0 0;
  line-height: 1.8;
  color: #334155;
  white-space: pre-wrap;
}

.tag-list,
.reference-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 12px;
}

.tag-list--compact,
.reference-list--compact {
  margin-top: 0;
  gap: 5px;
}

.tag-chip {
  background: #eef2ff;
  color: #334155;
}

.reference-box {
  margin-top: 14px;
  padding: 14px;
  border-radius: 16px;
  background: #fff;
}

.reference-box strong {
  color: #0f172a;
  font-size: 13px;
}

.reference-chip {
  background: #fef3c7;
  color: #92400e;
}

.reference-empty {
  margin-top: 10px;
  color: #94a3b8;
  font-size: 13px;
}

.delete-btn {
  flex-shrink: 0;
}

.drawer {
  height: 100%;
  display: flex;
  flex-direction: column;
  padding: 24px;
  background: #fff;
}

.drawer-head {
  display: flex;
  justify-content: space-between;
  gap: 14px;
  margin-bottom: 18px;
}

.drawer-head h3 {
  margin: 0;
  color: #0f172a;
}

.drawer-head p {
  margin: 6px 0 0;
  color: #64748b;
  font-size: 13px;
}

.drawer-close {
  cursor: pointer;
  color: #94a3b8;
}

.drawer-form {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.drawer-form label {
  font-size: 13px;
  font-weight: 700;
  color: #334155;
}

.input,
.textarea {
  border: 1px solid rgba(15, 23, 42, 0.08);
  border-radius: 16px;
  padding: 12px 14px;
  background: #f8fafc;
  color: #0f172a;
  outline: none;
}

.textarea {
  resize: vertical;
}

.input:focus,
.textarea:focus {
  border-color: rgba(22, 93, 255, 0.28);
  box-shadow: 0 0 0 4px rgba(22, 93, 255, 0.08);
}

.drawer-actions {
  padding-top: 16px;
}

.submit-btn {
  border: none !important;
  background: linear-gradient(135deg, #1d3557 0%, #3b5f93 100%) !important;
}

@media (max-width: 900px) {
  .stats {
    grid-template-columns: 1fr;
  }

  .hero {
    flex-direction: column;
  }
}
</style>
