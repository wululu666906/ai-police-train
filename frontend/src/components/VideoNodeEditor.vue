<template>
  <div class="node-editor">
    <div class="node-editor__sidebar">
      <div class="sidebar-header">
        <span class="sidebar-title">训练节点（{{ nodes.length }}）</span>
        <el-button type="primary" size="small" :icon="Plus" @click="addNode">新增</el-button>
      </div>

      <div v-if="!nodes.length" class="sidebar-empty">
        <el-icon :size="28" color="#d1d5db"><SetUp /></el-icon>
        <p>暂无节点，点击“新增”添加第一个训练节点。</p>
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
            <el-tag :type="nodeTypeTag(element.node_type)" size="small" effect="plain" style="flex-shrink: 0">
              {{ nodeTypeLabel(element.node_type) }}
            </el-tag>
            <el-button
              size="small"
              text
              type="danger"
              :icon="Delete"
              style="flex-shrink: 0; padding: 0 2px"
              @click.stop="deleteNode(index)"
            />
          </div>
        </template>
      </draggable>
    </div>

    <div class="node-editor__main">
      <div v-if="selectedIndex === -1 || !nodes.length" class="main-empty">
        <el-icon :size="40" color="#d1d5db"><Setting /></el-icon>
        <p>选中左侧节点后即可配置训练内容。</p>
      </div>

      <template v-else-if="currentNode">
        <div class="main-scroll">
          <div class="preview-panel">
            <div class="preview-panel__head">
              <div>
                <div class="preview-panel__eyebrow">学员端预览</div>
                <div class="preview-panel__title">{{ currentNode.title || `节点 ${selectedIndex + 1}` }}</div>
              </div>
              <div class="preview-panel__actions">
                <el-button size="small" @click="applyPracticePreset">练习预设</el-button>
                <el-button size="small" type="warning" @click="applyExamPreset">考核预设</el-button>
              </div>
            </div>

            <div class="preview-card">
              <div class="preview-card__instruction">{{ previewInstruction }}</div>
              <div class="preview-card__chips">
                <span v-for="item in previewMetaList" :key="item" class="preview-chip">{{ item }}</span>
              </div>
            </div>

            <div v-if="nodeWarnings.length" class="preview-warnings">
              <div v-for="item in nodeWarnings" :key="item" class="preview-warning">{{ item }}</div>
            </div>
          </div>

          <el-form :model="currentNode" label-width="96px" label-position="left">
            <div class="form-section-title">基础信息</div>
            <el-form-item label="节点名称">
              <el-input v-model="currentNode.title" placeholder="如：出示证件" maxlength="50" show-word-limit />
            </el-form-item>
            <el-form-item label="触发时间">
              <el-input-number
                v-model="currentNode.trigger_time"
                :min="0"
                :step="1"
                controls-position="right"
                style="width: 140px"
              />
              <span class="form-unit">秒（{{ formatTime(currentNode.trigger_time) }}）</span>
            </el-form-item>
            <el-form-item label="暂停方式">
              <el-radio-group v-model="currentNode.pause_mode">
                <el-radio value="auto_pause">完全暂停</el-radio>
                <el-radio value="light_motion">保留轻微动态</el-radio>
              </el-radio-group>
            </el-form-item>

            <div class="form-section-title">节点类型</div>
            <el-form-item label="训练形式">
              <el-select v-model="currentNode.node_type" style="width: 240px" @change="onNodeTypeChange">
                <el-option label="动作实操" value="action" />
                <el-option label="判断题" value="judge" />
                <el-option label="单选题" value="choice" />
                <el-option label="语音问答" value="voice_qa" />
              </el-select>
            </el-form-item>
            <el-form-item label="交互方式">
              <el-select v-model="currentNode.node_interaction_type" style="width: 240px">
                <el-option label="语音问答" value="voice_qa" />
                <el-option label="选择题" value="choice" />
                <el-option label="判断题" value="judgment" />
                <el-option label="虚拟道具选择" value="prop_select" />
                <el-option label="动作指令" value="action" />
              </el-select>
            </el-form-item>

            <div class="form-section-title">AI教官提示</div>
            <el-form-item label="教官引导语">
              <el-input
                v-model="currentNode.ai_instructor_hint"
                type="textarea"
                :rows="4"
                placeholder="练习模式下显示给学员的AI教官引导提示，格式建议：&#10;第1行：现在的情况是：...&#10;第2行：你需要：...&#10;第3行：注意要点：..."
              />
              <div class="form-help-text">练习模式下显示，考核模式下隐藏。建议包含场景描述、任务引导和关键提示三部分。</div>
            </el-form-item>
            <el-form-item label="正确答案">
              <el-input
                v-model="currentNode.correct_answer"
                placeholder="如：A 或 true/false 或关键词"
              />
            </el-form-item>
            <el-form-item label="训练目标">
              <el-input
                v-model="currentNode.node_config.training_goal"
                type="textarea"
                :rows="2"
                placeholder="说明本节点希望学员达成的训练目标"
              />
            </el-form-item>
            <el-form-item label="标准要点">
              <el-input
                v-model="standardPointsInput"
                type="textarea"
                :rows="4"
                placeholder="每行一个标准要点，如：表明身份、告知原因、规范检查证件"
                @blur="syncStandardPoints"
              />
              <div class="form-help-text">用于学员端标准提示和评估报告考察点展示。</div>
            </el-form-item>

            <template v-if="currentNode.node_type === 'action'">
              <el-form-item label="节点说明">
                <el-input
                  v-model="currentNode.prompt_content.instruction"
                  type="textarea"
                  :rows="2"
                  placeholder="告诉学员此节点要完成什么动作或执法步骤"
                />
              </el-form-item>
              <el-form-item label="标准动作">
                <el-input
                  v-model="currentNode.prompt_content.gesture_hint"
                  placeholder="如：右手五指并拢，指尖抬至眉心上方"
                />
              </el-form-item>
              <el-form-item label="标准话术">
                <el-input
                  v-model="currentNode.prompt_content.speech_hint"
                  type="textarea"
                  :rows="2"
                  placeholder="如：您好，我是 XX 分局民警，请配合检查。"
                />
              </el-form-item>
            </template>

            <template v-if="currentNode.node_type === 'judge'">
              <el-form-item label="题目内容">
                <el-input
                  v-model="currentNode.node_config.question"
                  type="textarea"
                  :rows="2"
                  placeholder="请输入判断题题干"
                />
              </el-form-item>
              <el-form-item label="正确答案">
                <el-radio-group v-model="currentNode.node_config.correct_answer">
                  <el-radio :value="true">正确</el-radio>
                  <el-radio :value="false">错误</el-radio>
                </el-radio-group>
              </el-form-item>
              <el-form-item label="答案解析">
                <el-input
                  v-model="currentNode.node_config.explanation"
                  type="textarea"
                  :rows="2"
                  placeholder="用于答题后展示解析"
                />
              </el-form-item>
            </template>

            <template v-if="currentNode.node_type === 'choice'">
              <el-form-item label="题目内容">
                <el-input
                  v-model="currentNode.node_config.question"
                  type="textarea"
                  :rows="2"
                  placeholder="请输入单选题题干"
                />
              </el-form-item>
              <el-form-item label="选项设置">
                <div class="choice-options">
                  <div
                    v-for="(option, optionIndex) in (currentNode.node_config.options || [])"
                    :key="optionIndex"
                    class="choice-option"
                  >
                    <el-radio
                      :model-value="currentNode.node_config.correct_index"
                      :value="Number(optionIndex)"
                      @change="currentNode.node_config.correct_index = Number(optionIndex)"
                    >
                      <span class="choice-alpha">{{ String.fromCharCode(65 + Number(optionIndex)) }}</span>
                    </el-radio>
                    <el-input
                      v-model="currentNode.node_config.options[optionIndex]"
                      placeholder="选项内容"
                      style="flex: 1"
                    />
                    <el-button size="small" text type="danger" :icon="Close" @click="removeOption(Number(optionIndex))" />
                  </div>
                  <el-button size="small" :icon="Plus" @click="addOption">添加选项</el-button>
                </div>
              </el-form-item>
              <el-form-item label="答题限时">
                <el-input-number
                  v-model="currentNode.node_config.time_limit"
                  :min="0"
                  :max="300"
                  :step="5"
                  style="width: 140px"
                />
                <span class="form-unit">秒（0 表示不限时）</span>
              </el-form-item>
              <el-form-item label="答案解析">
                <el-input
                  v-model="currentNode.node_config.explanation"
                  type="textarea"
                  :rows="2"
                  placeholder="用于答题后展示解析"
                />
              </el-form-item>
            </template>

            <template v-if="currentNode.node_type === 'voice_qa'">
              <el-form-item label="提问内容">
                <el-input
                  v-model="currentNode.prompt_content.instruction"
                  type="textarea"
                  :rows="2"
                  placeholder="如：请描述本次执法的法律依据"
                />
              </el-form-item>
              <el-form-item label="关键词">
                <el-input
                  v-model="keywordsInput"
                  placeholder="多个关键词用英文逗号分隔"
                  @blur="syncKeywords"
                />
              </el-form-item>
            </template>

            <div class="form-section-title">AI 识别</div>
            <el-form-item label="要求手势">
              <el-select
                v-model="currentNode.required_gesture"
                clearable
                placeholder="当前节点不要求手势识别"
                style="width: 220px"
              >
                <el-option label="标准敬礼" value="salute" />
                <el-option label="出示证件" value="show_id" />
                <el-option label="举手示意" value="raise_hand" />
                <el-option label="标准站姿" value="standard_stance" />
                <el-option label="双手前伸" value="hands_forward" />
                <el-option label="扶胸示意" value="hand_on_chest" />
                <el-option label="停止手势" value="stop_signal" />
                <el-option label="前方指引" value="point_front" />
              </el-select>
            </el-form-item>
            <el-form-item label="识别容差">
              <el-select v-model="currentNode.prompt_content.gesture_config.tolerance" style="width: 160px">
                <el-option label="严格" value="strict" />
                <el-option label="标准" value="standard" />
                <el-option label="宽松" value="relaxed" />
              </el-select>
            </el-form-item>
            <el-form-item label="最低置信度">
              <el-slider
                v-model="currentNode.prompt_content.gesture_config.min_confidence"
                :min="0.3"
                :max="0.95"
                :step="0.05"
                style="width: 240px"
              />
              <span class="form-unit">{{ Number(currentNode.prompt_content.gesture_config.min_confidence || 0).toFixed(2) }}</span>
            </el-form-item>
            <el-form-item label="持稳帧数">
              <el-input-number
                v-model="currentNode.prompt_content.gesture_config.hold_frames"
                :min="1"
                :max="12"
                style="width: 140px"
              />
              <span class="form-unit">连续识别帧</span>
            </el-form-item>
            <el-form-item label="联合判定">
              <el-select v-model="currentNode.node_config.pass_rule.mode" style="width: 220px">
                <el-option label="动作与语音都通过" value="all" />
                <el-option label="动作或语音任一通过" value="either" />
                <el-option label="仅动作达标" value="gesture_only" />
                <el-option label="仅语音达标" value="speech_only" />
              </el-select>
            </el-form-item>
            <el-form-item label="语音匹配">
              <el-select v-model="currentNode.node_config.speech_rule.match_mode" style="width: 180px">
                <el-option label="命中任一关键词" value="any" />
                <el-option label="命中全部关键词" value="all" />
                <el-option label="至少命中 N 个" value="min_count" />
              </el-select>
            </el-form-item>
            <el-form-item label="最少命中数">
              <el-input-number
                v-model="currentNode.node_config.speech_rule.min_count"
                :min="1"
                :max="10"
                style="width: 140px"
              />
            </el-form-item>
            <el-form-item label="最短话术">
              <el-input-number
                v-model="currentNode.node_config.speech_rule.min_length"
                :min="0"
                :max="120"
                style="width: 140px"
              />
              <span class="form-unit">字数</span>
            </el-form-item>
            <el-form-item label="身份校验">
              <el-select v-model="currentNode.prompt_content.identity_config.mode" style="width: 200px">
                <el-option label="本地在场 / 活体校验" value="presence" />
                <el-option label="参考人脸比对（后端CV）" value="reference_face" />
              </el-select>
            </el-form-item>
            <el-form-item label="校验要求">
              <el-checkbox v-model="currentNode.prompt_content.identity_config.require_single_face">要求单人入镜</el-checkbox>
              <el-checkbox v-model="currentNode.prompt_content.identity_config.require_live_motion">要求活体动作</el-checkbox>
              <el-checkbox v-model="currentNode.prompt_content.identity_config.backend_cv">启用后端CV接口</el-checkbox>
            </el-form-item>

            <div class="form-section-title">道具交互</div>
            <el-form-item label="道具模式">
              <el-radio-group v-model="currentNode.prop_mode">
                <el-radio value="auto">练习模式，系统自动提供</el-radio>
                <el-radio value="manual">手动模式，学员自行取用</el-radio>
              </el-radio-group>
            </el-form-item>
            <el-form-item label="道具名称">
              <el-input
                v-model="currentNode.prompt_content.prop_label"
                placeholder="如：执法记录仪、检查证件、警戒装备"
                maxlength="20"
                show-word-limit
              />
            </el-form-item>
            <el-form-item label="提示词">
              <el-input
                v-model="currentNode.prompt_content.prop_hint"
                type="textarea"
                :rows="2"
                placeholder="如：请先手动取出检查证件，再进行身份核验动作。"
              />
            </el-form-item>

            <div class="form-section-title">超时与评分</div>
            <el-form-item label="超时阈值">
              <el-input-number
                v-model="currentNode.timeout_seconds"
                :min="10"
                :max="600"
                :step="5"
                style="width: 140px"
              />
              <span class="form-unit">秒</span>
            </el-form-item>
            <el-form-item label="重试扣分">
              <el-input-number
                v-model="currentNode.retry_score_deduct"
                :min="0"
                :max="50"
                style="width: 140px"
              />
              <span class="form-unit">每次</span>
            </el-form-item>
            <el-form-item label="跳过扣分">
              <el-input-number
                v-model="currentNode.skip_score_deduct"
                :min="0"
                :max="100"
                style="width: 140px"
              />
              <span class="form-unit">分</span>
            </el-form-item>
            <el-form-item label="节点权重">
              <el-input-number
                v-model="currentNode.score_weight"
                :min="1"
                :max="100"
                style="width: 140px"
              />
              <span class="form-unit">分（满分）</span>
            </el-form-item>
          </el-form>
        </div>

        <div class="main-footer">
          <el-button type="primary" :loading="saving" @click="saveCurrentNode">保存节点</el-button>
          <transition name="fade">
            <span v-if="saveSuccess" class="save-tip">已保存</span>
          </transition>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { ElMessage, ElMessageBox, ElSlider } from 'element-plus'
import { Close, Delete, Plus, Rank, SetUp, Setting, Timer } from '@element-plus/icons-vue'
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
  node_interaction_type: string
  ai_instructor_hint: string
  choice_options: Array<{ label: string; text: string }> | null
  correct_answer: string | null
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
const standardPointsInput = ref('')

const currentNode = computed<NodeItem | null>(() =>
  selectedIndex.value >= 0 && selectedIndex.value < nodes.value.length
    ? nodes.value[selectedIndex.value]
    : null,
)

const previewInstruction = computed(() => {
  const node = currentNode.value
  if (!node) return '请选择左侧节点进行配置'
  if (node.node_type === 'action' || node.node_type === 'voice_qa') {
    return node.prompt_content?.instruction || '这里会显示给学员的操作指令'
  }
  return node.node_config?.question || '这里会显示给学员的题目内容'
})

const previewMetaList = computed(() => {
  const node = currentNode.value
  if (!node) return []

  const list = [
    nodeTypeLabel(node.node_type),
    node.pause_mode === 'light_motion' ? '轻动态提示' : '自动暂停',
    node.prop_mode === 'manual' ? '手动道具' : '自动道具',
    `超时 ${node.timeout_seconds}s`,
    `权重 ${node.score_weight}分`,
  ]

  if (node.required_gesture) list.push(`动作：${gestureLabel(node.required_gesture)}`)
  if (node.required_keywords?.length) list.push(`关键词 ${node.required_keywords.length} 个`)
  if (node.node_config?.standard_points?.length) list.push(`标准要点 ${node.node_config.standard_points.length} 条`)
  if (node.prompt_content?.prop_label?.trim()) list.push(`道具：${node.prompt_content.prop_label.trim()}`)
  return list
})

const nodeWarnings = computed(() => {
  const node = currentNode.value
  if (!node) return []

  const warnings: string[] = []
  if (!node.title?.trim()) warnings.push('建议补充节点名称，方便教师和学员识别当前训练点。')
  if (!node.node_config?.training_goal?.trim()) warnings.push('建议补充训练目标，便于报告形成能力评价。')
  if (!node.node_config?.standard_points?.length) warnings.push('建议补充标准要点，便于学员复盘和报告展示。')
  if ((node.node_type === 'action' || node.node_type === 'voice_qa') && !node.prompt_content?.instruction?.trim()) {
    warnings.push('当前节点缺少给学员的操作说明，学员端会不知道先做什么。')
  }
  if ((node.node_type === 'judge' || node.node_type === 'choice') && !node.node_config?.question?.trim()) {
    warnings.push('当前题型缺少题干，建议补充明确的问题描述。')
  }
  if (
    node.node_type === 'choice' &&
    (!Array.isArray(node.node_config?.options) || node.node_config.options.filter((item: string) => item?.trim()).length < 2)
  ) {
    warnings.push('单选题至少需要 2 个有效选项。')
  }
  if (node.node_type === 'voice_qa' && !node.required_keywords?.length) {
    warnings.push('语音问答建议至少配置一组关键词，便于系统判定是否达标。')
  }
  if (node.prop_mode === 'manual' && !node.prompt_content?.prop_label?.trim()) {
    warnings.push('手动模式建议填写“道具名称”，避免学员端始终显示默认的虚拟证件或虚拟装备。')
  }
  if (node.timeout_seconds < 20) {
    warnings.push('超时阈值偏短，学员可能还没反应就被判超时。')
  }
  if (!node.required_gesture && !node.prompt_content?.speech_hint && node.node_type === 'action') {
    warnings.push('当前动作节点既没有手势要求，也没有标准话术提示，训练目标可能不够清晰。')
  }
  return warnings
})

onMounted(fetchNodes)

watch(currentNode, (node) => {
  if (!node) return
  keywordsInput.value = Array.isArray(node.required_keywords) ? node.required_keywords.join(', ') : ''
  standardPointsInput.value = Array.isArray(node.node_config?.standard_points) ? node.node_config.standard_points.join('\n') : ''
})

watch(
  () => currentNode.value?.node_type,
  (nextType) => {
    if (!currentNode.value || !nextType) return
    currentNode.value.node_config = ensureNodeConfig(nextType, currentNode.value.node_config)
  },
)

async function fetchNodes() {
  try {
    const response: any = await request.get(`/videos/${props.video.id}/nodes`)
    nodes.value = (response || []).map(normalizeFetchedNode)
    if (nodes.value.length) selectedIndex.value = 0
  } catch {
    ElMessage.error('加载节点失败')
  }
}

function normalizeFetchedNode(node: any): NodeItem {
  const nodeType = node.node_type || 'action'
  const nodeConfig = normalizeConfigFromLegacy(
    nodeType,
    ensureNodeConfig(nodeType, node.node_config || {}),
    node.choice_options,
    node.correct_answer,
  )
  return {
    ...node,
    node_interaction_type: node.node_interaction_type || defaultInteractionType(nodeType),
    ai_instructor_hint: node.ai_instructor_hint || '',
    choice_options: node.choice_options || null,
    correct_answer: node.correct_answer || null,
    prompt_content: normalizePromptContent(node.prompt_content),
    node_config: nodeConfig,
    required_keywords: Array.isArray(node.required_keywords) ? node.required_keywords : [],
  }
}

function normalizePromptContent(content?: Record<string, any>) {
  const rawGestureConfig = content?.gesture_config || {}
  const rawIdentityConfig = content?.identity_config || {}
  return {
    instruction: '',
    gesture_hint: '',
    speech_hint: '',
    prop_label: '',
    prop_hint: '',
    gesture_config: {
      min_confidence: rawGestureConfig.min_confidence ?? 0.55,
      hold_frames: rawGestureConfig.hold_frames ?? 5,
      tolerance: rawGestureConfig.tolerance || 'standard',
    },
    identity_config: {
      mode: rawIdentityConfig.mode || 'presence',
      require_single_face: rawIdentityConfig.require_single_face !== false,
      require_live_motion: rawIdentityConfig.require_live_motion !== false,
      backend_cv: Boolean(rawIdentityConfig.backend_cv),
    },
    ...(content || {}),
  }
}

function ensureNodeConfig(nodeType: string, config: Record<string, any>) {
  const baseConfig = {
    ...(config || {}),
    training_goal: config?.training_goal || '',
    standard_points: Array.isArray(config?.standard_points) ? config.standard_points : [],
  }
  if (nodeType === 'choice') {
    return {
      ...baseConfig,
      question: config?.question || '',
      options: Array.isArray(config?.options) && config.options.length ? config.options : ['', ''],
      correct_index: config?.correct_index ?? 0,
      time_limit: config?.time_limit ?? 30,
      explanation: config?.explanation || '',
      speech_rule: {
        match_mode: config?.speech_rule?.match_mode || 'any',
        min_count: config?.speech_rule?.min_count ?? 1,
        min_length: config?.speech_rule?.min_length ?? 0,
      },
      pass_rule: {
        mode: config?.pass_rule?.mode || 'all',
      },
    }
  }

  if (nodeType === 'judge') {
    return {
      ...baseConfig,
      question: config?.question || '',
      correct_answer: config?.correct_answer ?? true,
      explanation: config?.explanation || '',
      speech_rule: {
        match_mode: config?.speech_rule?.match_mode || 'any',
        min_count: config?.speech_rule?.min_count ?? 1,
        min_length: config?.speech_rule?.min_length ?? 0,
      },
      pass_rule: {
        mode: config?.pass_rule?.mode || 'all',
      },
    }
  }

  return {
    ...baseConfig,
    speech_rule: {
      match_mode: config?.speech_rule?.match_mode || 'any',
      min_count: config?.speech_rule?.min_count ?? 1,
      min_length: config?.speech_rule?.min_length ?? 0,
    },
    pass_rule: {
      mode: config?.pass_rule?.mode || 'all',
    },
  }
}

function syncKeywords() {
  if (!currentNode.value) return
  currentNode.value.required_keywords = keywordsInput.value
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean)
}

function defaultInteractionType(nodeType: string) {
  return ({
    action: 'action',
    judge: 'judgment',
    choice: 'choice',
    voice_qa: 'voice_qa',
  } as Record<string, string>)[nodeType] || 'voice_qa'
}

function normalizeChoiceOptions(options: unknown): Array<{ label: string; text: string }> {
  if (!Array.isArray(options)) return []
  return options
    .map((option, index) => {
      if (typeof option === 'string') {
        return { label: String.fromCharCode(65 + index), text: option.trim() }
      }
      if (option && typeof option === 'object') {
        const item = option as Record<string, unknown>
        return {
          label: String(item.label || String.fromCharCode(65 + index)).trim(),
          text: String(item.text ?? item.content ?? item.description ?? '').trim(),
        }
      }
      return { label: String.fromCharCode(65 + index), text: '' }
    })
    .filter((option) => option.text)
}

function normalizeConfigFromLegacy(
  nodeType: string,
  config: Record<string, any>,
  choiceOptions: unknown,
  correctAnswer: string | null,
) {
  if (nodeType !== 'choice') return config
  const configOptions = normalizeChoiceOptions(config.options)
  if (configOptions.length) return config

  const legacyOptions = normalizeChoiceOptions(choiceOptions)
  if (!legacyOptions.length) return config

  const correctIndex = legacyOptions.findIndex((option) => option.label === correctAnswer)
  return {
    ...config,
    options: legacyOptions.map((option) => option.text),
    correct_index: correctIndex >= 0 ? correctIndex : config.correct_index ?? 0,
  }
}

function normalizeNodeForSave(node: NodeItem): NodeItem {
  const nodeConfig = ensureNodeConfig(node.node_type, node.node_config || {})
  let choiceOptions = node.choice_options
  let correctAnswer = node.correct_answer
  let interactionType = node.node_interaction_type || defaultInteractionType(node.node_type)

  if (node.node_type === 'choice') {
    const options = normalizeChoiceOptions(nodeConfig.options)
    const maxIndex = Math.max(options.length - 1, 0)
    const correctIndex = Math.min(Math.max(Number(nodeConfig.correct_index ?? 0), 0), maxIndex)
    nodeConfig.options = options.map((option) => option.text)
    nodeConfig.correct_index = correctIndex
    choiceOptions = options
    correctAnswer = options[correctIndex]?.label || null
    if (!['choice', 'prop_select'].includes(interactionType)) interactionType = 'choice'
  } else if (node.node_type === 'judge') {
    choiceOptions = [
      { label: '对', text: '正确' },
      { label: '错', text: '错误' },
    ]
    correctAnswer = nodeConfig.correct_answer ? '对' : '错'
    interactionType = 'judgment'
  } else {
    choiceOptions = null
    if (interactionType === 'choice' || interactionType === 'judgment' || interactionType === 'prop_select') {
      interactionType = defaultInteractionType(node.node_type)
    }
  }

  return {
    ...node,
    node_interaction_type: interactionType,
    choice_options: choiceOptions,
    correct_answer: correctAnswer,
    node_config: nodeConfig,
  }
}

function syncStandardPoints() {
  if (!currentNode.value) return
  currentNode.value.node_config.standard_points = standardPointsInput.value
    .split('\n')
    .map((item) => item.trim())
    .filter(Boolean)
}

function onNodeTypeChange(nextType: string) {
  if (!currentNode.value) return
  currentNode.value.node_config = ensureNodeConfig(nextType, currentNode.value.node_config)
  currentNode.value.node_interaction_type = defaultInteractionType(nextType)
}

function addNode() {
  const newNode: NodeItem = {
    video_id: props.video.id,
    node_index: nodes.value.length,
    title: `节点 ${nodes.value.length + 1}`,
    trigger_time: 0,
    pause_mode: 'auto_pause',
    prompt_content: normalizePromptContent(),
    timeout_seconds: 60,
    retry_score_deduct: 5,
    skip_score_deduct: 20,
    prop_mode: 'auto',
    node_type: 'action',
    node_interaction_type: 'voice_qa',
    ai_instructor_hint: '',
    choice_options: null,
    correct_answer: null,
    node_config: ensureNodeConfig('action', {}),
    required_gesture: null,
    required_keywords: [],
    score_weight: 10,
    _isNew: true,
  }
  nodes.value.push(newNode)
  selectedIndex.value = nodes.value.length - 1
}

function applyPracticePreset() {
  if (!currentNode.value) return
  currentNode.value.pause_mode = 'auto_pause'
  currentNode.value.prop_mode = 'auto'
  currentNode.value.timeout_seconds = Math.max(currentNode.value.timeout_seconds || 0, 60)
  currentNode.value.retry_score_deduct = 5
  currentNode.value.skip_score_deduct = 15
  currentNode.value.score_weight = Math.max(currentNode.value.score_weight || 0, 10)
  ElMessage.success('已应用练习模式推荐配置')
}

function applyExamPreset() {
  if (!currentNode.value) return
  currentNode.value.pause_mode = 'auto_pause'
  currentNode.value.prop_mode = 'manual'
  currentNode.value.timeout_seconds = Math.max(30, Math.min(currentNode.value.timeout_seconds || 45, 60))
  currentNode.value.retry_score_deduct = 10
  currentNode.value.skip_score_deduct = 25
  currentNode.value.score_weight = Math.max(currentNode.value.score_weight || 0, 15)
  ElMessage.success('已应用考核模式推荐配置')
}

async function deleteNode(index: number) {
  const node = nodes.value[index]
  try {
    await ElMessageBox.confirm(`确认删除节点“${node.title || '未命名节点'}”吗？`, '删除确认', {
      type: 'warning',
      confirmButtonText: '确认',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }

  if (node.id) {
    try {
      await request.delete(`/videos/${props.video.id}/nodes/${node.id}`)
    } catch {
      ElMessage.error('删除失败')
      return
    }
  }

  nodes.value.splice(index, 1)
  if (selectedIndex.value >= nodes.value.length) {
    selectedIndex.value = nodes.value.length - 1
  }
  ElMessage.success('节点已删除')
  emit('updated')
}

async function saveCurrentNode() {
  if (!currentNode.value) return

  syncKeywords()
  syncStandardPoints()
  saving.value = true
  saveSuccess.value = false

  try {
    const normalizedNode = normalizeNodeForSave(currentNode.value)
    const payload = {
      ...normalizedNode,
      prompt_content: normalizePromptContent(normalizedNode.prompt_content),
    }

    if (currentNode.value._isNew || !currentNode.value.id) {
      const response: any = await request.post(`/videos/${props.video.id}/nodes`, payload)
      Object.assign(currentNode.value, normalizeFetchedNode(response), { _isNew: false })
      ElMessage.success('节点已创建')
    } else {
      await request.patch(`/videos/${props.video.id}/nodes/${currentNode.value.id}`, payload)
      Object.assign(currentNode.value, normalizedNode)
      ElMessage.success('节点已保存')
    }

    saveSuccess.value = true
    setTimeout(() => {
      saveSuccess.value = false
    }, 2000)
    emit('updated')
  } catch {
    ElMessage.error('保存失败，请重试')
  } finally {
    saving.value = false
  }
}

async function onReorder() {
  const order = nodes.value.map((node) => node.id).filter(Boolean) as number[]
  try {
    await request.put(`/videos/${props.video.id}/nodes/reorder`, { order })
    nodes.value.forEach((node, index) => {
      node.node_index = index
    })
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

function formatTime(seconds: number) {
  if (!seconds && seconds !== 0) return '--'
  const minutes = Math.floor(seconds / 60)
  const remainSeconds = seconds % 60
  return `${String(minutes).padStart(2, '0')}:${String(remainSeconds).padStart(2, '0')}`
}

function nodeTypeLabel(type: string) {
  return ({
    action: '实操',
    judge: '判断',
    choice: '选择',
    voice_qa: '语音',
  } as Record<string, string>)[type] || type
}

function nodeTypeTag(type: string): '' | 'success' | 'info' | 'warning' | 'danger' {
  return ({
    action: '',
    judge: 'warning',
    choice: 'success',
    voice_qa: 'danger',
  } as Record<string, '' | 'success' | 'info' | 'warning' | 'danger'>)[type] || 'info'
}

function gestureLabel(value: string) {
  return ({
    salute: '标准敬礼',
    show_id: '出示证件',
    raise_hand: '举手示意',
    standard_stance: '标准站姿',
    hands_forward: '双手前伸',
    hand_on_chest: '扶胸示意',
    stop_signal: '停止手势',
    point_front: '前方指引',
  } as Record<string, string>)[value] || value
}
</script>

<style scoped lang="scss">
.node-editor {
  display: flex;
  height: 64vh;
  min-height: 480px;
  max-height: 680px;
}

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

  &:hover {
    background: #f0f6ff;
  }

  &--active {
    background: #e8f0fe;
    border-left: 3px solid #0066ff;
    padding-left: 5px;
  }

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

  &:active {
    cursor: grabbing;
  }
}

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

.preview-panel {
  margin-bottom: 16px;
  padding: 14px 16px;
  border-radius: 14px;
  background: linear-gradient(135deg, #eff6ff 0%, #f8fafc 100%);
  border: 1px solid #dbeafe;
}

.preview-panel__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.preview-panel__eyebrow {
  font-size: 11px;
  font-weight: 700;
  color: #64748b;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  margin-bottom: 4px;
}

.preview-panel__title {
  font-size: 16px;
  font-weight: 700;
  color: #0f172a;
}

.preview-panel__actions {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}

.preview-card {
  padding: 14px;
  border-radius: 12px;
  background: rgba(15, 23, 42, 0.95);
  color: #f8fafc;
}

.preview-card__instruction {
  font-size: 17px;
  font-weight: 700;
  line-height: 1.6;
}

.preview-card__chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 12px;
}

.preview-chip {
  display: inline-flex;
  align-items: center;
  padding: 5px 10px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.08);
  color: #cbd5e1;
  font-size: 11px;
  font-weight: 600;
}

.preview-warnings {
  display: grid;
  gap: 8px;
  margin-top: 12px;
}

.preview-warning {
  padding: 9px 12px;
  border-radius: 10px;
  background: #fff7ed;
  border: 1px solid #fdba74;
  color: #9a3412;
  font-size: 12px;
  line-height: 1.6;
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

  &:first-child {
    margin-top: 0;
  }
}

.form-help-text {
  margin-top: 4px;
  font-size: 12px;
  line-height: 1.5;
  color: #9ca3af;
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

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
