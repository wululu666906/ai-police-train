<template>
  <div class="node-editor">

    <!-- 左栏：节点列表 -->
    <div class="node-editor__sidebar">
      <div class="sidebar-header">
        <span class="sidebar-title">训练节点（{{ nodes.length }}）</span>
        <el-button type="primary" size="small" :icon="Plus" @click="addNode">新增</el-button>
      </div>

      <div v-if="!nodes.length" class="sidebar-empty">
        <el-icon :size="28" color="#d1d5db"><SetUp /></el-icon>
        <p>暂无节点，点击「新增」添加第一个训练节点</p>
      </div>

      <draggable
        v-else
        v-model="nodes"
        item-key="id"
        handle=".drag-handle"
        animation="180"
        @end="onReorder"
      >
        <template #item="{ element, index }">
          <div
            class="node-item"
            :class="{ 'node-item--active': selectedIndex === index }"
            @click="selectedIndex = index"
          >
            <el-icon class="drag-handle"><Rank /></el-icon>
            <div class="node-item__info">
              <span class="node-item__label">{{ element.title || `节点 ${index + 1}` }}</span>
              <span class="node-item__time">
                <el-icon :size="10"><Timer /></el-icon>
                {{ formatTime(element.trigger_time) }}
              </span>
            </div>
            <el-tag :type="nodeTypeTag(element.node_type)" size="small" effect="plain" style="flex-shrink:0">
              {{ nodeTypeLabel(element.node_type) }}
            </el-tag>
            <el-button
              size="small" text type="danger" :icon="Delete"
              style="flex-shrink:0;padding:0 2px"
              @click.stop="deleteNode(index)"
            />
          </div>
        </template>
      </draggable>
    </div>

    <!-- 右栏：编辑区 -->
    <div class="node-editor__main">
      <div v-if="selectedIndex === -1 || !nodes.length" class="main-empty">
        <el-icon :size="40" color="#d1d5db"><Setting /></el-icon>
        <p>选中左侧节点进行配置</p>
      </div>

      <template v-else-if="currentNode">
        <div class="main-scroll">
          <el-form :model="currentNode" label-width="90px" size="default" label-position="left">

            <!-- 基础信息 -->
            <div class="form-section-title">基础信息</div>
            <el-form-item label="节点名称">
              <el-input v-model="currentNode.title" placeholder="如：出示证件" maxlength="50" show-word-limit />
            </el-form-item>
            <el-form-item label="触发时间">
              <el-input-number
                v-model="currentNode.trigger_time"
                :min="0" :step="1" controls-position="right"
                style="width:120px"
              />
              <span class="form-unit">秒（{{ formatTime(currentNode.trigger_time) }}）</span>
            </el-form-item>
            <el-form-item label="暂停方式">
              <el-radio-group v-model="currentNode.pause_mode">
                <el-radio value="auto_pause">完全暂停</el-radio>
                <el-radio value="light_motion">保留轻微动态</el-radio>
              </el-radio-group>
            </el-form-item>

            <!-- 节点类型 -->
            <div class="form-section-title">节点类型</div>
            <el-form-item label="节点类型">
              <el-select v-model="currentNode.node_type" style="width:220px">
                <el-option label="指令引导（实操动作）" value="action" />
                <el-option label="判断题" value="judge" />
                <el-option label="单项选择题" value="choice" />
                <el-option label="语音问答（高阶）" value="voice_qa" />
              </el-select>
            </el-form-item>

            <!-- 指令引导 -->
            <template v-if="currentNode.node_type === 'action'">
              <el-form-item label="节点说明">
                <el-input
                  v-model="currentNode.prompt_content.instruction"
                  type="textarea" :rows="2"
                  placeholder="告知学员本节点需要执行的操作"
                />
              </el-form-item>
              <el-form-item label="标准手势">
                <el-input v-model="currentNode.prompt_content.gesture_hint" placeholder="如：右手五指并拢，指尖抬至眉心正上方" />
              </el-form-item>
              <el-form-item label="标准话术">
                <el-input
                  v-model="currentNode.prompt_content.speech_hint"
                  type="textarea" :rows="2"
                  placeholder="如：您好，我是XX分局民警，请配合检查"
                />
              </el-form-item>
            </template>

            <!-- 判断题 -->
            <template v-if="currentNode.node_type === 'judge'">
              <el-form-item label="题目内容">
                <el-input v-model="currentNode.node_config.question" type="textarea" :rows="2" placeholder="请输入判断题题干" />
              </el-form-item>
              <el-form-item label="正确答案">
                <el-radio-group v-model="currentNode.node_config.correct_answer">
                  <el-radio :value="true">正确</el-radio>
                  <el-radio :value="false">错误</el-radio>
                </el-radio-group>
              </el-form-item>
              <el-form-item label="答题解析">
                <el-input v-model="currentNode.node_config.explanation" type="textarea" :rows="2" placeholder="答错后展示的解析" />
              </el-form-item>
            </template>

            <!-- 单选题 -->
            <template v-if="currentNode.node_type === 'choice'">
              <el-form-item label="题目内容">
                <el-input v-model="currentNode.node_config.question" type="textarea" :rows="2" placeholder="请输入单选题题干" />
              </el-form-item>
              <el-form-item label="选项设置">
                <div class="choice-options">
                  <div
                    v-for="(opt, oi) in (currentNode.node_config.options || [])"
                    :key="oi"
                    class="choice-option"
                  >
                    <el-radio
                      :model-value="currentNode.node_config.correct_index"
                      :value="Number(oi)"
                      @change="currentNode.node_config.correct_index = Number(oi)"
                    >
                      <span class="choice-alpha">{{ String.fromCharCode(65 + Number(oi)) }}</span>
                    </el-radio>
                    <el-input v-model="currentNode.node_config.options[oi]" placeholder="选项内容" style="flex:1" />
                    <el-button size="small" text type="danger" :icon="Close" @click="removeOption(Number(oi))" />
                  </div>
                  <el-button size="small" :icon="Plus" @click="addOption">添加选项</el-button>
                </div>
              </el-form-item>
              <el-form-item label="答题限时">
                <el-input-number v-model="currentNode.node_config.time_limit" :min="0" :max="300" :step="5" style="width:120px" />
                <span class="form-unit">秒（0 = 不限时）</span>
              </el-form-item>
              <el-form-item label="答题解析">
                <el-input v-model="currentNode.node_config.explanation" type="textarea" :rows="2" placeholder="答错后展示的解析" />
              </el-form-item>
            </template>

            <!-- 语音问答 -->
            <template v-if="currentNode.node_type === 'voice_qa'">
              <el-form-item label="提问内容">
                <el-input v-model="currentNode.prompt_content.instruction" type="textarea" :rows="2" placeholder="如：请描述本次执法的法律依据" />
              </el-form-item>
              <el-form-item label="关键词">
                <el-input
                  v-model="keywordsInput"
                  placeholder="多个关键词用逗号分隔"
                  @blur="syncKeywords"
                />
              </el-form-item>
            </template>

            <!-- AI 识别 -->
            <div class="form-section-title">AI 识别</div>
            <el-form-item label="要求手势">
              <el-select v-model="currentNode.required_gesture" clearable placeholder="无手势要求" style="width:200px">
                <el-option label="标准敬礼" value="salute" />
                <el-option label="出示证件" value="show_id" />
                <el-option label="举手示意" value="raise_hand" />
                <el-option label="站姿标准" value="standard_stance" />
                <el-option label="双手前伸" value="hands_forward" />
              </el-select>
            </el-form-item>

            <!-- 道具 -->
            <div class="form-section-title">道具交互</div>
            <el-form-item label="道具模式">
              <el-radio-group v-model="currentNode.prop_mode">
                <el-radio value="auto">练习模式（自动弹出）</el-radio>
                <el-radio value="manual">考核模式（手动取出）</el-radio>
              </el-radio-group>
            </el-form-item>

            <!-- 评分 -->
            <div class="form-section-title">超时与评分</div>
            <el-form-item label="超时阈值">
              <el-input-number v-model="currentNode.timeout_seconds" :min="10" :max="600" :step="5" style="width:120px" />
              <span class="form-unit">秒</span>
            </el-form-item>
            <el-form-item label="重试扣分">
              <el-input-number v-model="currentNode.retry_score_deduct" :min="0" :max="50" style="width:120px" />
              <span class="form-unit">分/次</span>
            </el-form-item>
            <el-form-item label="跳过扣分">
              <el-input-number v-model="currentNode.skip_score_deduct" :min="0" :max="100" style="width:120px" />
              <span class="form-unit">分</span>
            </el-form-item>
            <el-form-item label="节点权重">
              <el-input-number v-model="currentNode.score_weight" :min="1" :max="100" style="width:120px" />
              <span class="form-unit">分（满分）</span>
            </el-form-item>

          </el-form>
        </div>

        <!-- 保存按钮 -->
        <div class="main-footer">
          <el-button type="primary" :loading="saving" @click="saveCurrentNode">保存节点</el-button>
          <transition name="fade">
            <span v-if="saveSuccess" class="save-tip">✓ 已保存</span>
          </transition>
        </div>
      </template>
    </div>

  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Delete, Setting, Rank, Close, Timer, SetUp } from '@element-plus/icons-vue'
// @ts-ignore
import draggable from 'vuedraggable'
import request from '../utils/request'

interface NodeItem {
  id?: number
  video_id: number
  node_index: number
  title: string
  trigger_time: number
  pause_mode: string
  prompt_content: Record<string, any>
  timeout_seconds: number
  retry_score_deduct: number
  skip_score_deduct: number
  prop_mode: string
  node_type: string
  node_config: Record<string, any>
  required_gesture: string | null
  required_keywords: string[]
  score_weight: number
  _isNew?: boolean
}

const props = defineProps<{ video: { id: number; title: string; video_type: string } }>()
const emit = defineEmits<{ (e: 'updated'): void }>()

const nodes = ref<NodeItem[]>([])
const selectedIndex = ref(-1)
const saving = ref(false)
const saveSuccess = ref(false)
const keywordsInput = ref('')

const currentNode = computed<NodeItem | null>(() =>
  selectedIndex.value >= 0 && selectedIndex.value < nodes.value.length
    ? nodes.value[selectedIndex.value]
    : null
)

onMounted(fetchNodes)

async function fetchNodes() {
  try {
    const res: any = await request.get(`/videos/${props.video.id}/nodes`)
    nodes.value = (res || []).map((n: any) => ({
      ...n,
      prompt_content: n.prompt_content || {},
      node_config: ensureNodeConfig(n.node_type, n.node_config || {}),
    }))
    if (nodes.value.length) selectedIndex.value = 0
  } catch {
    ElMessage.error('加载节点失败')
  }
}

function ensureNodeConfig(nodeType: string, config: Record<string, any>): Record<string, any> {
  if (nodeType === 'choice') {
    return {
      question: config.question || '',
      options: config.options || ['', ''],
      correct_index: config.correct_index ?? 0,
      time_limit: config.time_limit ?? 30,
      explanation: config.explanation || '',
    }
  }
  if (nodeType === 'judge') {
    return {
      question: config.question || '',
      correct_answer: config.correct_answer ?? true,
      explanation: config.explanation || '',
    }
  }
  return config
}

watch(currentNode, (node) => {
  if (!node) return
  keywordsInput.value = Array.isArray(node.required_keywords)
    ? node.required_keywords.join(', ')
    : ''
})

watch(() => currentNode.value?.node_type, (newType) => {
  if (!currentNode.value || !newType) return
  currentNode.value.node_config = ensureNodeConfig(newType, currentNode.value.node_config)
})

function syncKeywords() {
  if (!currentNode.value) return
  currentNode.value.required_keywords = keywordsInput.value
    .split(',').map(s => s.trim()).filter(Boolean)
}

function addNode() {
  const newNode: NodeItem = {
    video_id: props.video.id,
    node_index: nodes.value.length,
    title: `节点 ${nodes.value.length + 1}`,
    trigger_time: 0,
    pause_mode: 'auto_pause',
    prompt_content: { instruction: '', gesture_hint: '', speech_hint: '' },
    timeout_seconds: 60,
    retry_score_deduct: 5,
    skip_score_deduct: 20,
    prop_mode: 'auto',
    node_type: 'action',
    node_config: {},
    required_gesture: null,
    required_keywords: [],
    score_weight: 10,
    _isNew: true,
  }
  nodes.value.push(newNode)
  selectedIndex.value = nodes.value.length - 1
}

async function deleteNode(index: number) {
  const node = nodes.value[index]
  await ElMessageBox.confirm(`确认删除节点「${node.title || '未命名节点'}」？`, '删除确认', {
    type: 'warning', confirmButtonText: '确认', cancelButtonText: '取消',
  })
  if (node.id) {
    try {
      await request.delete(`/videos/${props.video.id}/nodes/${node.id}`)
    } catch {
      ElMessage.error('删除失败')
      return
    }
  }
  nodes.value.splice(index, 1)
  if (selectedIndex.value >= nodes.value.length) selectedIndex.value = nodes.value.length - 1
  ElMessage.success('节点已删除')
  emit('updated')
}

async function saveCurrentNode() {
  if (!currentNode.value) return
  syncKeywords()
  saving.value = true
  saveSuccess.value = false
  try {
    const payload = { ...currentNode.value }
    if (currentNode.value._isNew || !currentNode.value.id) {
      const res: any = await request.post(`/videos/${props.video.id}/nodes`, payload)
      currentNode.value.id = res.id
      currentNode.value._isNew = false
      ElMessage.success('节点已创建')
    } else {
      await request.patch(`/videos/${props.video.id}/nodes/${currentNode.value.id}`, payload)
      ElMessage.success('节点已保存')
    }
    saveSuccess.value = true
    setTimeout(() => { saveSuccess.value = false }, 2000)
    emit('updated')
  } catch {
    ElMessage.error('保存失败，请重试')
  } finally {
    saving.value = false
  }
}

async function onReorder() {
  const order = nodes.value.map(n => n.id).filter(Boolean) as number[]
  try {
    await request.put(`/videos/${props.video.id}/nodes/reorder`, { order })
    nodes.value.forEach((n, i) => { n.node_index = i })
    emit('updated')
  } catch {
    ElMessage.error('重排失败')
  }
}

function addOption() {
  if (!currentNode.value) return
  currentNode.value.node_config.options = [...(currentNode.value.node_config.options || []), '']
}

function removeOption(index: number) {
  if (!currentNode.value) return
  currentNode.value.node_config.options.splice(index, 1)
  if (currentNode.value.node_config.correct_index >= currentNode.value.node_config.options.length) {
    currentNode.value.node_config.correct_index = 0
  }
}

function formatTime(seconds: number): string {
  if (!seconds && seconds !== 0) return '--'
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
}

function nodeTypeLabel(type: string): string {
  return { action: '实操', judge: '判断', choice: '选择', voice_qa: '语音' }[type] || type
}

function nodeTypeTag(type: string): '' | 'success' | 'info' | 'warning' | 'danger' {
  return ({ action: '', judge: 'warning', choice: 'success', voice_qa: 'danger' } as any)[type] || 'info'
}
</script>

<style scoped lang="scss">
.node-editor {
  display: flex;
  height: 64vh;
  min-height: 480px;
  max-height: 680px;
}

/* 左侧节点列表 */
.node-editor__sidebar {
  width: 220px;
  flex-shrink: 0;
  border-right: 1px solid #e5e7eb;
  display: flex;
  flex-direction: column;
  background: #f8fafc;
  overflow: hidden;
}

.sidebar-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  border-bottom: 1px solid #e5e7eb;
  flex-shrink: 0;
}

.sidebar-title {
  font-size: 12px;
  font-weight: 600;
  color: #374151;
}

.sidebar-empty {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 20px;
  text-align: center;
  color: #9ca3af;
  font-size: 12px;
  line-height: 1.6;
  gap: 8px;
}

.node-item {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 8px 10px 8px 8px;
  cursor: pointer;
  border-bottom: 1px solid #f0f0f0;
  transition: background 0.12s;
  user-select: none;

  &:hover { background: #f0f6ff; }
  &--active { background: #e8f0fe; border-left: 3px solid #0066ff; padding-left: 5px; }

  &__info {
    flex: 1;
    min-width: 0;
  }
  &__label {
    display: block;
    font-size: 12px;
    color: #1e293b;
    font-weight: 500;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  &__time {
    display: flex;
    align-items: center;
    gap: 2px;
    font-size: 11px;
    color: #9ca3af;
    margin-top: 1px;
  }
}

.drag-handle {
  cursor: grab;
  color: #d1d5db;
  flex-shrink: 0;
  font-size: 14px;

  &:active { cursor: grabbing; }
}

/* 右侧编辑区 */
.node-editor__main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.main-empty {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #9ca3af;
  gap: 10px;
  font-size: 13px;
}

.main-scroll {
  flex: 1;
  overflow-y: auto;
  padding: 14px 20px 0;
}

.main-footer {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 20px;
  border-top: 1px solid #e5e7eb;
  background: #f8fafc;
  flex-shrink: 0;
}

.save-tip {
  font-size: 12px;
  color: #22c55e;
}

.form-section-title {
  font-size: 11px;
  font-weight: 700;
  color: #6b7280;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  margin: 14px 0 8px;
  padding-bottom: 5px;
  border-bottom: 1px solid #f0f0f0;

  &:first-child { margin-top: 0; }
}

.form-unit {
  margin-left: 8px;
  font-size: 12px;
  color: #6b7280;
  white-space: nowrap;
}

.choice-options {
  display: flex;
  flex-direction: column;
  gap: 7px;
  width: 100%;
}

.choice-option {
  display: flex;
  align-items: center;
  gap: 6px;
}

.choice-alpha {
  font-weight: 600;
  color: #374151;
  width: 16px;
  display: inline-block;
}

.fade-enter-active, .fade-leave-active { transition: opacity 0.3s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>
