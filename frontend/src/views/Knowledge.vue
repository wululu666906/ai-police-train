<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import request from '../utils/request'
import { showConfirmDialog, showFailToast, showSuccessToast } from 'vant'

const knowledgeList = ref<any[]>([])
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
      <van-button type="primary" round icon="plus" class="hero-btn" @click="showUpload = true">
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

      <div v-if="loading" class="loading-box">
        <van-loading type="spinner" color="#1D3557" />
      </div>

      <div v-else-if="knowledgeList.length" class="knowledge-list">
        <article v-for="item in knowledgeList" :key="item.id" class="knowledge-item">
          <div class="knowledge-main">
            <div class="knowledge-meta">
              <span class="source-chip">{{ item.source || 'manual' }}</span>
              <span class="category-chip">{{ item.category || '通用' }}</span>
              <span class="id-text">{{ item.id }}</span>
            </div>
            <h4>{{ item.title || '未命名知识' }}</h4>
            <p>{{ item.content }}</p>

            <div v-if="item.tags?.length" class="tag-list">
              <span v-for="tag in item.tags" :key="tag" class="tag-chip">{{ tag }}</span>
            </div>

            <div class="reference-box">
              <strong>被考察点引用 {{ item.referenced_by_count || 0 }} 次</strong>
              <div v-if="item.referenced_by?.length" class="reference-list">
                <span v-for="ref in item.referenced_by" :key="ref" class="reference-chip">{{ ref }}</span>
              </div>
              <div v-else class="reference-empty">当前还没有考察点引用这条知识。</div>
            </div>
          </div>

          <van-button icon="delete-o" size="small" danger round class="delete-btn" @click="handleDelete(item.id)" />
        </article>
      </div>

      <div v-else class="empty-box">
        <van-icon name="comment-o" size="56" />
        <p>暂无知识条目</p>
        <span>可以先录入法规、流程要点或处置模板。</span>
      </div>
    </section>

    <van-popup v-model:show="showUpload" position="right" :style="{ width: '460px', height: '100%' }">
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
  border-radius: 26px;
  background: rgba(255, 255, 255, 0.96);
  border: 1px solid rgba(15, 23, 42, 0.06);
  box-shadow: 0 18px 40px rgba(15, 23, 42, 0.05);
}

.hero {
  display: flex;
  justify-content: space-between;
  gap: 18px;
  padding: 24px;
}

.hero h1 {
  margin: 0;
  color: #0f172a;
}

.hero p {
  margin: 8px 0 0;
  color: #64748b;
}

.hero-btn {
  align-self: center;
  border: none !important;
  background: linear-gradient(135deg, #1d3557 0%, #3b5f93 100%) !important;
}

.stats {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
}

.stat-card {
  padding: 20px;
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
  padding: 22px;
}

.list-head {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: center;
  margin-bottom: 18px;
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
