<template>
  <div class="video-library">
    <section class="library-panel">
      <div class="library-panel__tabs">
        <el-tabs v-model="activeTab" @tab-change="onFilterChange">
          <el-tab-pane label="全部素材" name="" />
          <el-tab-pane label="教学素材" name="teaching" />
          <el-tab-pane label="交互实训" name="interactive" />
          <el-tab-pane label="模拟警情" name="police" />
        </el-tabs>
      </div>

      <div class="library-toolbar">
        <div class="library-toolbar__filters">
          <el-select v-model="statusFilter" clearable placeholder="全部状态" class="toolbar-select" @change="onFilterChange">
            <el-option label="草稿" value="draft" />
            <el-option label="已发布" value="published" />
            <el-option label="已归档" value="archived" />
          </el-select>

          <el-select v-model="sortMode" class="toolbar-select">
            <el-option label="最新上传" value="latest" />
            <el-option label="节点最多" value="nodes" />
            <el-option label="按状态分组" value="status" />
          </el-select>

          <el-input
            v-model="keyword"
            clearable
            class="toolbar-search"
            placeholder="搜索视频名称、标签"
            :prefix-icon="Search"
            @input="onKeywordChange"
            @clear="onFilterChange"
          />

          <el-button plain class="toolbar-reset" @click="resetFilters">重置</el-button>
        </div>

        <div class="view-switch">
          <button type="button" class="view-switch__btn" :class="{ 'is-active': viewMode === 'grid' }" @click="viewMode = 'grid'">网格视图</button>
          <button type="button" class="view-switch__btn" :class="{ 'is-active': viewMode === 'list' }" @click="viewMode = 'list'">列表视图</button>
        </div>
      </div>

      <section class="auto-import-banner">
        <div class="auto-import-banner__badge">自动入库已开启</div>
        <div class="auto-import-banner__desc">
          新上传的视频将自动扫描、生成节点并配置 AI 分析。当前监控目录：
          <code>{{ autoImportInfo.watched_dir || '--' }}</code>
        </div>
        <div class="auto-import-banner__meta">
          <span>本轮检测 {{ autoImportInfo.detected_count || 0 }} 个文件</span>
          <span>成功入库 {{ autoImportInfo.imported_count || 0 }} 个</span>
          <span>已存在跳过 {{ autoImportInfo.skipped_count || 0 }} 个</span>
          <span class="auto-import-banner__status">运行中</span>
        </div>
      </section>

      <section class="summary-grid">
        <article v-for="card in summaryCards" :key="card.label" class="summary-card">
          <div class="summary-card__main">
            <span class="summary-card__label">{{ card.label }}</span>
            <strong class="summary-card__value">{{ card.value }}</strong>
            <span class="summary-card__desc">{{ card.desc }}</span>
          </div>
          <div class="summary-card__icon" :class="`is-${card.tone}`">
            <el-icon><component :is="card.icon" /></el-icon>
          </div>
        </article>
      </section>

      <section class="library-content">
        <div class="library-content__head">
          <div>
            <h3 class="library-content__title">视频素材列表</h3>
            <p class="library-content__subtitle">共 {{ total }} 个</p>
          </div>
          <el-button type="primary" :icon="Plus" @click="openUploadDialog">上传视频制作实训</el-button>
        </div>

        <section v-if="loading" class="state-panel">
          <el-skeleton :rows="6" animated />
        </section>

        <section v-else-if="!displayedVideos.length" class="state-panel">
          <el-empty description="暂无视频素材，先上传一个试试。" />
        </section>

        <section v-else :class="['video-grid', { 'video-grid--list': viewMode === 'list' }]">
          <article v-for="video in displayedVideos" :key="video.id" class="video-card">
            <div class="video-card__cover" @click="openDetail(video)">
              <img v-if="coverFor(video)" :src="coverFor(video)" :alt="video.title" class="cover-img" />
              <div v-else class="cover-placeholder">
                <el-icon :size="36"><VideoPlay /></el-icon>
              </div>
              <div class="cover-overlay">
                <el-icon :size="30"><VideoPlay /></el-icon>
              </div>
              <span class="type-chip" :class="video.video_type === 'interactive' ? 'type-chip--interactive' : 'type-chip--teaching'">
                {{ video.video_type === 'interactive' ? '交互实训' : '教学素材' }}
              </span>
              <span class="duration-chip">{{ formatDuration(video.duration) }}</span>
            </div>

            <div class="video-card__body">
              <div class="video-card__title" :title="video.title">{{ video.title }}</div>
              <div class="video-card__meta">
                <span class="meta-item">{{ video.node_count }} 个节点</span>
                <span class="meta-divider">|</span>
                <span class="meta-item">{{ formatDate(video.updated_at || video.created_at) }}</span>
              </div>

              <div class="video-card__badges">
                <el-tag :type="statusTagType(video.status)" size="small" round>{{ statusLabel(video.status) }}</el-tag>
                <span class="readiness-badge" :class="readinessFor(video).ready ? 'is-ready' : 'is-pending'">
                  {{ readinessFor(video).ready ? '已就绪' : '待配置' }}
                </span>
                <span v-if="analysisModeLabel(video.ai_analysis_mode)" class="analysis-badge">{{ analysisModeLabel(video.ai_analysis_mode) }}</span>
                <span v-if="video.material_metadata?.is_police_simulation" class="analysis-badge analysis-badge--police">{{ policeScenarioLabel(video.material_metadata.police_scenario) || '模拟警情' }}</span>
              </div>

              <p class="video-card__hint">{{ readinessFor(video).text }}</p>

              <div class="video-card__footer">
                <div class="card-actions">
                  <el-button size="small" text :icon="MagicStick" @click.stop="openAnalysisDialog(video)">AI 分析</el-button>
                  <el-button size="small" text :icon="SetUp" @click.stop="openNodeEditor(video)">节点配置</el-button>
                  <el-button size="small" text :icon="Edit" @click.stop="openEditMeta(video)">编辑</el-button>
                  <el-dropdown trigger="click" @command="handleCommand($event, video)">
                    <el-button size="small" text :icon="MoreFilled">更多</el-button>
                    <template #dropdown>
                      <el-dropdown-menu>
                        <el-dropdown-item command="analyze">重新 AI 分析</el-dropdown-item>
                        <el-dropdown-item v-if="video.status !== 'published'" command="publish">发布素材</el-dropdown-item>
                        <el-dropdown-item v-if="video.status === 'published'" command="draft">转为草稿</el-dropdown-item>
                        <el-dropdown-item command="archive">归档</el-dropdown-item>
                        <el-dropdown-item command="delete" divided style="color: #f56c6c">删除</el-dropdown-item>
                      </el-dropdown-menu>
                    </template>
                  </el-dropdown>
                </div>
              </div>
            </div>
          </article>
        </section>

        <section v-if="total > 0" class="pagination-bar">
          <span class="pagination-bar__count">共 {{ total }} 条</span>
          <el-pagination
            v-model:current-page="page"
            v-model:page-size="pageSize"
            :page-sizes="[12, 20, 24]"
            background
            layout="prev, pager, next, sizes"
            :total="total"
            @current-change="fetchVideos"
            @size-change="onPageSizeChange"
          />
        </section>
      </section>
    </section>

    <el-dialog v-model="showUpload" title="上传视频" width="640px" :close-on-click-modal="false">
      <el-form ref="uploadFormRef" :model="uploadForm" :rules="uploadRules" label-width="96px">
        <el-form-item label="视频标题" prop="title">
          <el-input v-model="uploadForm.title" placeholder="请输入视频标题" maxlength="120" show-word-limit />
        </el-form-item>
        <el-form-item label="视频类型" prop="video_type">
          <el-radio-group v-model="uploadForm.video_type">
            <el-radio value="auto">自动判断</el-radio>
            <el-radio value="interactive">交互实训</el-radio>
            <el-radio value="teaching">教学素材</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="警情模板">
          <div class="training-template-row">
            <el-select v-model="uploadForm.scenarioHint" clearable placeholder="可选：模拟警情类型">
              <el-option v-for="item in policeScenarioOptions" :key="item.value" :label="item.label" :value="item.value" />
            </el-select>
            <el-select v-model="uploadForm.trainingVariant" placeholder="训练版本">
              <el-option v-for="item in trainingVariantOptions" :key="item.value" :label="item.label" :value="item.value" />
            </el-select>
            <el-select v-model="uploadForm.difficultyLevel" placeholder="难度">
              <el-option v-for="item in difficultyOptions" :key="item.value" :label="item.label" :value="item.value" />
            </el-select>
          </div>
        </el-form-item>
        <el-form-item label="视频简介">
          <el-input v-model="uploadForm.description" type="textarea" :rows="3" placeholder="可选" />
        </el-form-item>
        <el-form-item label="标签">
          <el-input v-model="uploadForm.tagsInput" placeholder="多个标签用逗号分隔" />
        </el-form-item>
        <el-form-item label="自动配置">
          <el-switch v-model="uploadForm.autoConfigure" inline-prompt active-text="开" inactive-text="关" />
          <span class="form-tip">自动截取封面、尝试识别类型，并生成简报与节点。</span>
        </el-form-item>
        <el-form-item label="视频文件" prop="file">
          <div class="upload-area" @click="triggerFileInput" @dragover.prevent @drop.prevent="onDrop">
            <template v-if="!uploadForm.file">
              <el-icon :size="30" class="upload-icon"><UploadFilled /></el-icon>
              <p class="upload-hint">点击或拖拽上传视频<br /><small>支持 mp4 / webm / mov，最大 2GB</small></p>
            </template>
            <template v-else>
              <el-icon :size="24" color="#67c23a"><CircleCheck /></el-icon>
              <p class="upload-hint">
                {{ uploadForm.file.name }}<br />
                <small>{{ formatFileSize(uploadForm.file.size) }}</small>
                <small v-if="extractedDuration != null"> / {{ formatDuration(extractedDuration) }}</small>
                <small v-if="analyzing" class="warn-text"> / 正在提取封面</small>
              </p>
              <el-button size="small" text @click.stop="resetSelectedVideo">重新选择</el-button>
            </template>
          </div>
          <input ref="fileInputRef" type="file" accept="video/mp4,video/webm,video/ogg,video/quicktime" hidden @change="onFileChange" />
        </el-form-item>
        <el-form-item label="封面图">
          <div class="upload-area upload-area--small" @click="triggerThumbInput">
            <template v-if="!thumbPreview">
              <el-icon :size="20"><Picture /></el-icon>
              <span>可选。不上传时系统会自动截取视频封面。</span>
            </template>
            <template v-else>
              <img :src="thumbPreview" class="thumb-preview" />
              <div class="thumb-actions">
                <span class="thumb-auto-tag" v-if="!uploadForm.thumbnail">自动截图</span>
                <el-button size="small" text @click.stop="clearThumb">更换</el-button>
              </div>
            </template>
          </div>
          <input ref="thumbInputRef" type="file" accept="image/*" hidden @change="onThumbChange" />
        </el-form-item>
      </el-form>

      <div v-if="uploading" class="upload-progress">
        <el-progress :percentage="uploadProgress" :stroke-width="8" />
        <p class="progress-text">{{ uploadProgressText }}</p>
      </div>

      <template #footer>
        <el-button :disabled="uploading" @click="showUpload = false">取消</el-button>
        <el-button type="primary" :loading="uploading" @click="submitUpload">{{ uploading ? '上传中...' : '开始上传' }}</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showEditMeta" title="编辑视频信息" width="560px">
      <el-form v-if="editTarget" :model="editTarget" label-width="96px">
        <el-form-item label="视频标题">
          <el-input v-model="editTarget.title" maxlength="120" show-word-limit />
        </el-form-item>
        <el-form-item label="视频类型">
          <el-radio-group v-model="editTarget.video_type">
            <el-radio value="interactive">交互实训</el-radio>
            <el-radio value="teaching">教学素材</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="视频简介">
          <el-input v-model="editTarget.description" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item label="训练简报">
          <el-input v-model="editTarget.briefing" type="textarea" :rows="5" placeholder="学员进入训练前看到的任务背景、训练重点和评分说明" />
        </el-form-item>
        <el-form-item label="标签">
          <el-input v-model="editTagsInput" placeholder="多个标签用逗号分隔" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showEditMeta = false">取消</el-button>
        <el-button type="primary" :loading="savingMeta" @click="saveMeta">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showAnalysisDialog" :title="analysisVideo ? `AI 分析结果 - ${analysisVideo.title}` : 'AI 分析结果'" width="960px" :close-on-click-modal="false">
      <div v-if="analysisLoading" class="state-panel">
        <el-skeleton :rows="8" animated />
      </div>
      <template v-else-if="analysisVideo">
        <div class="analysis-toolbar">
          <div class="analysis-toolbar__left">
            <span class="analysis-pill">{{ analysisModeLabel(analysisVideo.ai_analysis_mode) || '未分析' }}</span>
            <span class="analysis-toolbar__meta">类型：{{ videoTypeLabel(analysisVideo.video_type) }}</span>
            <span class="analysis-toolbar__meta">节点：{{ analysisVideo.node_count }}</span>
            <span class="analysis-toolbar__meta">时长：{{ formatDuration(analysisVideo.duration) }}</span>
          </div>
          <div class="analysis-toolbar__actions">
            <el-select v-model="analysisScenario" clearable placeholder="警情类型" class="analysis-select">
              <el-option v-for="item in policeScenarioOptions" :key="item.value" :label="item.label" :value="item.value" />
            </el-select>
            <el-select v-model="analysisVariant" placeholder="训练版本" class="analysis-select">
              <el-option v-for="item in trainingVariantOptions" :key="item.value" :label="item.label" :value="item.value" />
            </el-select>
            <el-select v-model="analysisDifficulty" placeholder="难度" class="analysis-select analysis-select--small">
              <el-option v-for="item in difficultyOptions" :key="item.value" :label="item.label" :value="item.value" />
            </el-select>
            <el-button plain :icon="RefreshRight" :loading="analysisSubmitting" @click="rerunAnalysis('auto')">重新 AI 分析</el-button>
            <el-button v-if="showForceInteractiveButton" type="primary" :loading="analysisSubmitting" @click="rerunAnalysis('interactive')">按交互实训重建节点</el-button>
            <el-button type="success" :loading="analysisSubmitting" @click="rerunAnalysis('interactive', true)">生成模拟警情训练</el-button>
          </div>
        </div>

        <div class="analysis-hero">
          <div class="analysis-hero__main">
            <div class="analysis-hero__eyebrow">AI 判断说明</div>
            <div class="analysis-hero__title">{{ analysisSummary.reason || '暂无分析结论' }}</div>
            <div class="analysis-hero__desc">
              <span v-if="analysisSummary.missing_items?.length">当前仍缺少：{{ analysisSummary.missing_items.join('、') }}</span>
              <span v-else>基础配置已经完整，可以继续微调后发布。</span>
            </div>
          </div>
          <div class="analysis-hero__stats">
            <div class="hero-stat">
              <strong>{{ analysisVideo.node_count }}</strong>
              <span>训练节点</span>
            </div>
            <div class="hero-stat">
              <strong>{{ analysisSummary.is_interactive ? '交互' : '教学' }}</strong>
              <span>当前归类</span>
            </div>
            <div class="hero-stat">
              <strong>{{ statusLabel(analysisVideo.status) }}</strong>
              <span>发布状态</span>
            </div>
          </div>
        </div>

        <div class="analysis-grid">
          <section class="analysis-card">
            <div class="analysis-card__title">配置摘要</div>
            <div class="analysis-kv">
              <div><span>视频类型</span><strong>{{ videoTypeLabel(analysisVideo.video_type) }}</strong></div>
              <div><span>当前状态</span><strong>{{ statusLabel(analysisVideo.status) }}</strong></div>
              <div><span>分析模式</span><strong>{{ analysisModeLabel(analysisVideo.ai_analysis_mode) || '未分析' }}</strong></div>
              <div><span>节点数量</span><strong>{{ analysisVideo.node_count }}</strong></div>
            </div>
            <div class="analysis-block">
              <div class="analysis-block__label">训练简报</div>
              <div class="analysis-block__content">{{ analysisVideo.briefing || '暂无训练简报' }}</div>
            </div>
            <div class="analysis-block">
              <div class="analysis-block__label">标签</div>
              <div class="analysis-tags">
                <span v-for="tag in analysisVideo.tags" :key="tag" class="analysis-tag">{{ tag }}</span>
                <span v-if="!analysisVideo.tags.length" class="analysis-tag analysis-tag--muted">暂无标签</span>
              </div>
            </div>
          </section>

          <section class="analysis-card">
            <div class="analysis-card__title">分析元数据</div>
            <div class="analysis-kv">
              <div><span>抽帧数量</span><strong>{{ analysisMeta.frame_count ?? '--' }}</strong></div>
              <div><span>错误信息</span><strong>{{ analysisMeta.analysis_error || '无' }}</strong></div>
            </div>
            <div class="analysis-block">
              <div class="analysis-block__label">OCR 摘要</div>
              <div v-if="analysisMeta.ocr_hints?.length" class="ocr-list">
                <div v-for="item in analysisMeta.ocr_hints" :key="item" class="ocr-item">{{ item }}</div>
              </div>
              <div v-else class="analysis-block__content analysis-block__content--muted">当前没有 OCR 提示。</div>
            </div>
            <div class="analysis-block">
              <div class="analysis-block__label">建议切片点</div>
              <div v-if="analysisMeta.suggested_timestamps?.length" class="analysis-block__content">
                {{ analysisMeta.suggested_timestamps.map((item) => formatDuration(item)).join('、') }}
              </div>
              <div v-else class="analysis-block__content analysis-block__content--muted">暂无明确切片建议。</div>
            </div>
          </section>
        </div>

        <section class="analysis-card analysis-card--full">
          <div class="analysis-card__title">节点预览</div>
          <div v-if="analysisVideo.nodes?.length" class="analysis-nodes">
            <article v-for="node in analysisVideo.nodes" :key="node.id || `${node.node_index}-${node.title}`" class="analysis-node">
              <div class="analysis-node__head">
                <div>
                  <div class="analysis-node__title">{{ node.title || `节点 ${node.node_index + 1}` }}</div>
                  <div class="analysis-node__time">触发时间 {{ formatDuration(node.trigger_time) }}</div>
                </div>
                <div class="analysis-node__chips">
                  <span class="analysis-chip">{{ nodeTypeLabel(node.node_type) }}</span>
                  <span v-if="node.node_config?.police_node_type" class="analysis-chip analysis-chip--police">{{ policeNodeTypeLabel(node.node_config.police_node_type) }}</span>
                  <span v-if="node.required_gesture" class="analysis-chip analysis-chip--accent">{{ gestureLabel(node.required_gesture) }}</span>
                  <span class="analysis-chip analysis-chip--warn">超时 {{ node.timeout_seconds || 0 }} 秒</span>
                </div>
              </div>
              <div class="analysis-node__instruction">{{ node.prompt_content?.police_question || node.prompt_content?.instruction || node.prompt_content?.question || '暂无节点说明' }}</div>
              <div v-if="node.prompt_content?.scene_summary" class="analysis-node__summary">{{ node.prompt_content.scene_summary }}</div>
              <div v-if="node.node_config?.standard_points?.length" class="analysis-node__points">
                <span v-for="point in node.node_config.standard_points" :key="point">{{ point }}</span>
              </div>
              <div class="analysis-node__meta">
                <span v-if="node.required_keywords?.length">关键词：{{ node.required_keywords.join('、') }}</span>
                <span>重试扣分 {{ node.retry_score_deduct || 0 }}</span>
                <span>跳过扣分 {{ node.skip_score_deduct || 0 }}</span>
              </div>
            </article>
          </div>
          <el-empty v-else description="当前还没有可预览的训练节点" />
        </section>
      </template>
    </el-dialog>

    <el-dialog v-model="showNodeEditor" :title="`节点配置 - ${nodeEditorVideo?.title || ''}`" width="900px" :close-on-click-modal="false">
      <VideoNodeEditor v-if="showNodeEditor && nodeEditorVideo" :video="nodeEditorVideo" @updated="onNodesUpdated" />
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  CircleCheck,
  Edit,
  MagicStick,
  MoreFilled,
  Picture,
  Plus,
  RefreshRight,
  Search,
  SetUp,
  UploadFilled,
  VideoPlay,
} from '@element-plus/icons-vue'
import request from '../utils/request'
import { captureBestVideoFrame } from '../utils/videoFrame'
import VideoNodeEditor from '../components/VideoNodeEditor.vue'
import { useVideoCover } from '../composables/useVideoCover'

interface VideoNodeItem {
  id?: number
  node_index: number
  title?: string
  trigger_time?: number
  timeout_seconds?: number
  retry_score_deduct?: number
  skip_score_deduct?: number
  node_type?: string
  required_gesture?: string
  required_keywords?: string[]
  prompt_content?: Record<string, any>
  node_config?: Record<string, any>
}

interface AutoAnalysisMeta {
  analysis_mode?: string
  frame_count?: number
  ocr_hints?: string[]
  analysis_error?: string
  suggested_timestamps?: number[]
}

interface AutoAnalysisSummary {
  analysis_mode?: string
  is_interactive?: boolean
  node_count?: number
  missing_items?: string[]
  reason?: string
}

interface MaterialMetadata {
  is_police_simulation?: boolean
  police_scenario?: string
  training_variant?: string
  difficulty_level?: string
  version_count?: number
}

interface VideoItem {
  id: number
  title: string
  description?: string
  briefing?: string
  video_type: 'teaching' | 'interactive'
  video_url?: string
  thumbnail_url?: string
  duration?: number
  file_size?: number
  tags: string[]
  status: 'draft' | 'published' | 'archived'
  sort_order: number
  node_count: number
  created_at?: string
  updated_at?: string
  nodes?: VideoNodeItem[]
  auto_analysis?: AutoAnalysisMeta
  auto_analysis_summary?: AutoAnalysisSummary
  ai_analysis_mode?: string
  material_metadata?: MaterialMetadata
}

interface AutoImportInfo {
  watched_dir: string
  imported_count: number
  skipped_count: number
  detected_count: number
}

const videoList = ref<VideoItem[]>([])
const loading = ref(false)
const total = ref(0)
const page = ref(1)
const pageSize = ref(12)
const activeTab = ref('')
const statusFilter = ref('')
const keyword = ref('')
const sortMode = ref<'latest' | 'nodes' | 'status'>('latest')
const viewMode = ref<'grid' | 'list'>('grid')
let keywordTimer: ReturnType<typeof setTimeout> | null = null

const showUpload = ref(false)
const uploading = ref(false)
const uploadProgress = ref(0)
const uploadProgressText = ref('')
const fileInputRef = ref<HTMLInputElement | null>(null)
const thumbInputRef = ref<HTMLInputElement | null>(null)
const uploadFormRef = ref<any>()
const thumbPreview = ref('')
const analyzing = ref(false)
const extractedDuration = ref<number | null>(null)
const autoThumbBlob = ref<Blob | null>(null)
let analyzeAbortFlag = 0
let thumbObjectUrls: string[] = []

const uploadForm = ref({
  title: '',
  video_type: 'auto',
  description: '',
  tagsInput: '',
  scenarioHint: '',
  trainingVariant: 'base',
  difficultyLevel: 'normal',
  file: null as File | null,
  thumbnail: null as File | null,
  autoConfigure: true,
})

const uploadRules = {
  title: [{ required: true, message: '请输入视频标题', trigger: 'blur' }],
  video_type: [{ required: true, message: '请选择视频类型', trigger: 'change' }],
  file: [{
    required: true,
    validator: (_: any, __: any, callback: any) => (uploadForm.value.file ? callback() : callback(new Error('请选择视频文件'))),
    trigger: 'change',
  }],
}

const showEditMeta = ref(false)
const savingMeta = ref(false)
const editTarget = ref<VideoItem | null>(null)
const editTagsInput = ref('')

const showNodeEditor = ref(false)
const nodeEditorVideo = ref<VideoItem | null>(null)

const showAnalysisDialog = ref(false)
const analysisLoading = ref(false)
const analysisSubmitting = ref(false)
const analysisVideo = ref<VideoItem | null>(null)
const analysisMeta = ref<AutoAnalysisMeta>({})
const analysisScenario = ref('')
const analysisVariant = ref('base')
const analysisDifficulty = ref('normal')

const policeScenarioOptions = [
  { label: '家庭/邻里纠纷', value: 'family_dispute' },
  { label: '酒后滋事', value: 'alcohol_trouble' },
  { label: '校园冲突', value: 'school_conflict' },
  { label: '群众求助', value: 'public_help' },
  { label: '交通现场处置', value: 'traffic_scene' },
  { label: '突发人员失控', value: 'unstable_person' },
]

const trainingVariantOptions = [
  { label: '新警基础版', value: 'base' },
  { label: '执法规范版', value: 'law_standard' },
  { label: '风险识别强化版', value: 'risk_focus' },
  { label: '考核版', value: 'exam' },
]

const difficultyOptions = [
  { label: '基础', value: 'basic' },
  { label: '标准', value: 'normal' },
  { label: '进阶', value: 'advanced' },
]

const autoImportInfo = ref<AutoImportInfo>({
  watched_dir: '',
  imported_count: 0,
  skipped_count: 0,
  detected_count: 0,
})

const { ensureVideoCovers, getVideoCover } = useVideoCover()

const interactiveCount = computed(() => videoList.value.filter((item) => item.video_type === 'interactive').length)
const teachingCount = computed(() => videoList.value.filter((item) => item.video_type === 'teaching').length)
const policeSimulationCount = computed(() => videoList.value.filter((item) => item.material_metadata?.is_police_simulation).length)
const aiReadyCount = computed(() => videoList.value.filter((item) => item.video_type === 'interactive' && item.node_count > 0).length)
const pendingConfigCount = computed(() => videoList.value.filter((item) => item.video_type === 'interactive' && !readinessFor(item).ready).length)
const generatedNodeTotal = computed(() => videoList.value.reduce((sum, item) => sum + (item.node_count || 0), 0))

const displayedVideos = computed(() => {
  const items = activeTab.value === 'police'
    ? videoList.value.filter((item) => item.material_metadata?.is_police_simulation)
    : [...videoList.value]
  if (sortMode.value === 'nodes') {
    return items.sort((a, b) => (b.node_count || 0) - (a.node_count || 0))
  }
  if (sortMode.value === 'status') {
    const weight: Record<string, number> = { published: 0, draft: 1, archived: 2 }
    return items.sort((a, b) => (weight[a.status] ?? 9) - (weight[b.status] ?? 9))
  }
  return items.sort((a, b) => new Date(b.updated_at || b.created_at || 0).getTime() - new Date(a.updated_at || a.created_at || 0).getTime())
})

const summaryCards = computed(() => [
  { label: '当前列表', value: total.value, desc: '当前筛选结果', icon: VideoPlay, tone: 'blue' },
  { label: '教学素材', value: teachingCount.value, desc: `占比 ${total.value ? Math.round((teachingCount.value / total.value) * 100) : 0}%`, icon: CircleCheck, tone: 'green' },
  { label: '交互实训', value: interactiveCount.value, desc: `占比 ${total.value ? Math.round((interactiveCount.value / total.value) * 100) : 0}%`, icon: MagicStick, tone: 'purple' },
  { label: '模拟警情', value: policeSimulationCount.value, desc: '已节点化警情素材', icon: MagicStick, tone: 'blue' },
  { label: '已生成节点', value: generatedNodeTotal.value, desc: `就绪素材 ${aiReadyCount.value} 个`, icon: SetUp, tone: 'orange' },
  { label: '待补配置', value: pendingConfigCount.value, desc: '建议优先处理', icon: Edit, tone: 'red' },
])

const analysisSummary = computed<AutoAnalysisSummary>(() => {
  if (!analysisVideo.value) return { missing_items: [], reason: '' }
  return buildAnalysisSummary(analysisVideo.value)
})

const showForceInteractiveButton = computed(() => {
  if (!analysisVideo.value) return false
  return analysisVideo.value.video_type === 'teaching' || analysisVideo.value.node_count === 0
})

onMounted(() => {
  void fetchVideos()
})

onUnmounted(() => {
  if (keywordTimer) clearTimeout(keywordTimer)
  revokeThumbUrls()
})

async function fetchVideos() {
  loading.value = true
  try {
    const params: Record<string, any> = { page: page.value, page_size: pageSize.value }
    if (activeTab.value && activeTab.value !== 'police') params.video_type = activeTab.value
    if (statusFilter.value) params.status = statusFilter.value
    if (keyword.value) params.keyword = keyword.value

    const response: any = await request.get('/videos/admin/list', { params })
    videoList.value = (response.items || []).map(normalizeVideo)
    total.value = response.total || 0
    autoImportInfo.value = response.auto_import || autoImportInfo.value
    ensureVideoCovers(videoList.value)
  } catch {
    ElMessage.error('加载视频列表失败')
  } finally {
    loading.value = false
  }
}

function normalizeVideo(item: VideoItem) {
  return {
    ...item,
    tags: Array.isArray(item.tags) ? item.tags : [],
    nodes: Array.isArray(item.nodes) ? item.nodes : [],
    material_metadata: item.material_metadata || {},
    ai_analysis_mode: item.ai_analysis_mode || inferAiAnalysisMode(item),
  }
}

function inferAiAnalysisMode(video: Partial<VideoItem>) {
  const tags = Array.isArray(video.tags) ? video.tags : []
  if (tags.includes('AI识别')) return 'llm_vision'
  if (tags.includes('自动建模') || tags.includes('自动导入')) return 'template_fallback'
  return ''
}

function buildAnalysisSummary(video: VideoItem): AutoAnalysisSummary {
  if (video.auto_analysis_summary) {
    return {
      analysis_mode: video.auto_analysis_summary.analysis_mode || video.ai_analysis_mode,
      is_interactive: video.auto_analysis_summary.is_interactive ?? (video.video_type === 'interactive'),
      node_count: video.auto_analysis_summary.node_count ?? video.node_count,
      missing_items: video.auto_analysis_summary.missing_items || [],
      reason: video.auto_analysis_summary.reason || defaultAnalysisReason(video),
    }
  }
  return {
    analysis_mode: video.ai_analysis_mode,
    is_interactive: video.video_type === 'interactive',
    node_count: video.node_count,
    missing_items: collectMissingItems(video),
    reason: defaultAnalysisReason(video),
  }
}

function defaultAnalysisReason(video: VideoItem) {
  if (video.video_type === 'teaching') return '当前视频被归类为教学素材，系统不会自动生成训练节点。'
  if (video.node_count > 0) return `当前视频已生成 ${video.node_count} 个训练节点，可直接继续微调和发布。`
  return '当前视频已归类为交互实训，但还没有生成可用节点。'
}

function collectMissingItems(video: VideoItem) {
  const missing: string[] = []
  if (video.video_type === 'interactive' && !video.node_count) missing.push('训练节点')
  if (video.video_type === 'interactive' && !video.briefing?.trim()) missing.push('训练简报')
  if (video.status !== 'published') missing.push('发布状态')
  return missing
}

function coverFor(video?: VideoItem | null) {
  return getVideoCover(video)
}

function readinessFor(video: VideoItem) {
  if (video.video_type !== 'interactive') return { ready: true, text: '教学素材可直接用于预习、讲解和复盘。' }
  const missing = collectMissingItems(video)
  if (!missing.length) return { ready: true, text: '节点、简报和发布状态已齐备，可以直接进入实训。' }
  return { ready: false, text: `待补充：${missing.join('、')}` }
}

function analysisModeLabel(mode?: string) {
  if (mode === 'llm_vision') return 'AI 视频识别'
  if (mode === 'template_fallback') return '模板兜底'
  return ''
}

function videoTypeLabel(type?: string) {
  return type === 'interactive' ? '交互实训' : '教学素材'
}

function nodeTypeLabel(type?: string) {
  return ({ action: '动作指令', judge: '判断题', choice: '选择题', voice_qa: '语音问答' } as Record<string, string>)[type || ''] || (type || '未设置')
}

function policeNodeTypeLabel(type?: string) {
  const labels: Record<string, string> = {
    risk_identification: '风险识别',
    procedure_decision: '程序决策',
    communication: '沟通稳控',
    law_application: '依法处置',
    safety_control: '现场安全',
  }
  return labels[type || ''] || '警情节点'
}

function policeScenarioLabel(type?: string) {
  return policeScenarioOptions.find((item) => item.value === type)?.label || ''
}

function trainingVariantLabel(type?: string) {
  return trainingVariantOptions.find((item) => item.value === type)?.label || ''
}

function onFilterChange() {
  page.value = 1
  void fetchVideos()
}

function onKeywordChange() {
  if (keywordTimer) clearTimeout(keywordTimer)
  keywordTimer = setTimeout(() => {
    page.value = 1
    void fetchVideos()
  }, 400)
}

function resetFilters() {
  activeTab.value = ''
  statusFilter.value = ''
  keyword.value = ''
  sortMode.value = 'latest'
  page.value = 1
  void fetchVideos()
}

function onPageSizeChange() {
  page.value = 1
  void fetchVideos()
}

function revokeThumbUrls() {
  thumbObjectUrls.forEach((url) => URL.revokeObjectURL(url))
  thumbObjectUrls = []
}

function openUploadDialog() {
  uploadForm.value = {
    title: '',
    video_type: 'auto',
    description: '',
    tagsInput: '',
    scenarioHint: '',
    trainingVariant: 'base',
    difficultyLevel: 'normal',
    file: null,
    thumbnail: null,
    autoConfigure: true,
  }
  revokeThumbUrls()
  thumbPreview.value = ''
  uploadProgress.value = 0
  uploadProgressText.value = ''
  extractedDuration.value = null
  autoThumbBlob.value = null
  analyzeAbortFlag += 1
  showUpload.value = true
}

function resetSelectedVideo() {
  uploadForm.value.file = null
  extractedDuration.value = null
  autoThumbBlob.value = null
  if (!uploadForm.value.thumbnail) thumbPreview.value = ''
}

function triggerFileInput() {
  fileInputRef.value?.click()
}

function triggerThumbInput() {
  thumbInputRef.value?.click()
}

function fillTitleFromFile(file: File) {
  if (uploadForm.value.title.trim()) return
  uploadForm.value.title = file.name.replace(/\\.[^.]+$/, '') || '未命名视频'
}

function onFileChange(event: Event) {
  const file = (event.target as HTMLInputElement).files?.[0]
  if (!file) return
  uploadForm.value.file = file
  fillTitleFromFile(file)
  if (!uploadForm.value.thumbnail) void analyzeVideo(file)
}

async function analyzeVideo(file: File) {
  const myFlag = ++analyzeAbortFlag
  analyzing.value = true
  extractedDuration.value = null
  autoThumbBlob.value = null
  if (!uploadForm.value.thumbnail) thumbPreview.value = ''

  try {
    const frame = await captureBestVideoFrame(file)
    if (myFlag !== analyzeAbortFlag) {
      if (frame) URL.revokeObjectURL(frame.objectUrl)
      return
    }

    const probeUrl = URL.createObjectURL(file)
    thumbObjectUrls.push(probeUrl)
    const videoEl = document.createElement('video')
    videoEl.preload = 'metadata'
    videoEl.muted = true
    videoEl.playsInline = true
    videoEl.src = probeUrl
    await new Promise<void>((resolve) => {
      const timer = setTimeout(resolve, 8000)
      videoEl.onloadedmetadata = () => {
        clearTimeout(timer)
        resolve()
      }
      videoEl.onerror = () => {
        clearTimeout(timer)
        resolve()
      }
    })

    if (videoEl.duration && Number.isFinite(videoEl.duration)) extractedDuration.value = Math.round(videoEl.duration)
    videoEl.remove()

    if (frame) {
      autoThumbBlob.value = frame.blob
      if (!uploadForm.value.thumbnail) {
        thumbObjectUrls.push(frame.objectUrl)
        thumbPreview.value = frame.objectUrl
      } else {
        URL.revokeObjectURL(frame.objectUrl)
      }
    }
  } finally {
    if (myFlag === analyzeAbortFlag) analyzing.value = false
  }
}

function onThumbChange(event: Event) {
  const file = (event.target as HTMLInputElement).files?.[0]
  if (!file) return
  uploadForm.value.thumbnail = file
  const previewUrl = URL.createObjectURL(file)
  thumbObjectUrls.push(previewUrl)
  thumbPreview.value = previewUrl
}

function clearThumb() {
  uploadForm.value.thumbnail = null
  if (autoThumbBlob.value) {
    const previewUrl = URL.createObjectURL(autoThumbBlob.value)
    thumbObjectUrls.push(previewUrl)
    thumbPreview.value = previewUrl
  } else {
    thumbPreview.value = ''
  }
}

function onDrop(event: DragEvent) {
  const file = event.dataTransfer?.files?.[0]
  if (!file || !file.type.startsWith('video/')) return
  uploadForm.value.file = file
  fillTitleFromFile(file)
  if (!uploadForm.value.thumbnail) void analyzeVideo(file)
}

async function submitUpload() {
  await uploadFormRef.value?.validate()
  if (!uploadForm.value.file) {
    ElMessage.warning('请选择视频文件')
    return
  }
  if (analyzing.value) {
    ElMessage.warning('正在提取封面，请稍后再上传')
    return
  }

  uploading.value = true
  uploadProgress.value = 0
  uploadProgressText.value = '准备上传...'

  const formData = new FormData()
  formData.append('title', uploadForm.value.title)
  formData.append('video_type', uploadForm.value.video_type)
  formData.append('description', uploadForm.value.description || '')
  formData.append('tags', JSON.stringify(uploadForm.value.tagsInput.split(',').map((item) => item.trim()).filter(Boolean)))
  formData.append('auto_configure', String(uploadForm.value.autoConfigure))
  formData.append('scenario_hint', uploadForm.value.scenarioHint || '')
  formData.append('training_variant', uploadForm.value.trainingVariant || 'base')
  formData.append('difficulty_level', uploadForm.value.difficultyLevel || 'normal')
  if (extractedDuration.value != null) formData.append('duration', String(extractedDuration.value))
  formData.append('file', uploadForm.value.file)
  if (uploadForm.value.thumbnail) {
    formData.append('thumbnail', uploadForm.value.thumbnail)
  } else if (autoThumbBlob.value) {
    formData.append('thumbnail', new File([autoThumbBlob.value], 'auto_thumb.jpg', { type: 'image/jpeg' }))
  }

  try {
    await new Promise<void>((resolve, reject) => {
      const xhr = new XMLHttpRequest()
      const baseURL = String(request.defaults.baseURL || '').replace(/\/$/, '')
      xhr.open('POST', `${baseURL}/videos/upload`)
      const token = localStorage.getItem('token')
      if (token) xhr.setRequestHeader('Authorization', `Bearer ${token}`)
      xhr.upload.onprogress = (event) => {
        if (!event.lengthComputable) return
        uploadProgress.value = Math.round((event.loaded / event.total) * 100)
        uploadProgressText.value = `已上传 ${formatFileSize(event.loaded)} / ${formatFileSize(event.total)}`
      }
      xhr.onload = () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          resolve()
          return
        }
        try {
          const error = JSON.parse(xhr.responseText)
          reject(new Error(error.detail || '上传失败'))
        } catch {
          reject(new Error('上传失败'))
        }
      }
      xhr.onerror = () => reject(new Error('网络错误'))
      xhr.send(formData)
    })

    ElMessage.success(uploadForm.value.autoConfigure ? '视频已上传，并开始自动分析' : '视频上传成功')
    showUpload.value = false
    revokeThumbUrls()
    await fetchVideos()
  } catch (error: any) {
    ElMessage.error(error.message || '上传失败，请重试')
  } finally {
    uploading.value = false
  }
}

function openEditMeta(video: VideoItem) {
  editTarget.value = { ...video }
  editTagsInput.value = Array.isArray(video.tags) ? video.tags.join(', ') : ''
  showEditMeta.value = true
}

async function saveMeta() {
  if (!editTarget.value) return
  savingMeta.value = true
  try {
    const tags = editTagsInput.value.split(',').map((item) => item.trim()).filter(Boolean)
    await request.patch(`/videos/${editTarget.value.id}`, {
      title: editTarget.value.title,
      description: editTarget.value.description,
      briefing: editTarget.value.briefing,
      video_type: editTarget.value.video_type,
      tags,
    })
    ElMessage.success('保存成功')
    showEditMeta.value = false
    await fetchVideos()
  } catch {
    ElMessage.error('保存失败')
  } finally {
    savingMeta.value = false
  }
}

function openNodeEditor(video: VideoItem) {
  nodeEditorVideo.value = video
  showNodeEditor.value = true
}

async function onNodesUpdated() {
  await fetchVideos()
  if (analysisVideo.value) await loadAnalysisVideo(analysisVideo.value.id)
}

function openDetail(video: VideoItem) {
  if (video.video_url) window.open(video.video_url, '_blank')
}

async function openAnalysisDialog(video: VideoItem) {
  showAnalysisDialog.value = true
  await loadAnalysisVideo(video.id)
}

async function loadAnalysisVideo(videoId: number) {
  analysisLoading.value = true
  try {
    const detail: VideoItem = await request.get(`/videos/${videoId}`)
    analysisVideo.value = normalizeVideo(detail)
    analysisScenario.value = analysisVideo.value.material_metadata?.police_scenario || ''
    analysisVariant.value = analysisVideo.value.material_metadata?.training_variant || 'base'
    analysisDifficulty.value = analysisVideo.value.material_metadata?.difficulty_level || 'normal'
    analysisMeta.value = detail.auto_analysis || {
      analysis_mode: analysisVideo.value.ai_analysis_mode,
      frame_count: undefined,
      ocr_hints: [],
      analysis_error: '',
    }
  } catch {
    ElMessage.error('加载 AI 分析结果失败')
  } finally {
    analysisLoading.value = false
  }
}

async function rerunAnalysis(preferredType: 'auto' | 'interactive' | 'teaching' = 'auto', forcePolice = false) {
  const target = analysisVideo.value
  if (!target) return
  analysisSubmitting.value = true
  try {
    const response: VideoItem = await request.post(`/videos/${target.id}/auto-configure`, {
      overwrite_meta: true,
      overwrite_nodes: true,
      preferred_type: preferredType,
      scenario_hint: forcePolice ? (analysisScenario.value || 'family_dispute') : analysisScenario.value,
      training_variant: analysisVariant.value || 'base',
      difficulty_level: analysisDifficulty.value || 'normal',
    })
    analysisVideo.value = normalizeVideo(response)
    analysisMeta.value = response.auto_analysis || {}
    ElMessage.success(preferredType === 'interactive' ? '已按交互实训重建节点' : 'AI 分析已更新')
    await fetchVideos()
  } catch {
    ElMessage.error('重新 AI 分析失败')
  } finally {
    analysisSubmitting.value = false
  }
}

async function handleCommand(command: string | number | object, video: VideoItem) {
  const cmd = String(command)
  if (cmd === 'delete') {
    try {
      await ElMessageBox.confirm(`确认删除视频“${video.title}”吗？此操作不可恢复。`, '删除确认', {
        type: 'warning',
        confirmButtonText: '确认删除',
        cancelButtonText: '取消',
      })
    } catch {
      return
    }

    try {
      await request.delete(`/videos/${video.id}`)
      ElMessage.success('已删除')
      await fetchVideos()
    } catch {
      ElMessage.error('删除失败')
    }
    return
  }

  if (cmd === 'analyze') {
    await openAnalysisDialog(video)
    await rerunAnalysis('auto')
    return
  }

  const statusMap: Record<string, string> = {
    publish: 'published',
    draft: 'draft',
    archive: 'archived',
  }
  const newStatus = statusMap[cmd]
  if (!newStatus) return

  try {
    await request.patch(`/videos/${video.id}`, { status: newStatus })
    ElMessage.success('状态已更新')
    await fetchVideos()
  } catch {
    ElMessage.error('操作失败')
  }
}

function formatDuration(seconds?: number) {
  if (seconds == null) return '--'
  const totalSeconds = Math.max(0, Math.round(seconds))
  const minutes = Math.floor(totalSeconds / 60)
  const remainSeconds = totalSeconds % 60
  return `${minutes}:${String(remainSeconds).padStart(2, '0')}`
}

function formatDate(value?: string) {
  if (!value) return '--'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '--'
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
}

function formatFileSize(bytes?: number) {
  if (!bytes) return '--'
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`
}

function statusLabel(status: string) {
  return ({ draft: '草稿', published: '已发布', archived: '已归档' } as Record<string, string>)[status] || status
}

function statusTagType(status: string): '' | 'success' | 'info' | 'warning' | 'danger' {
  return ({ draft: 'info', published: 'success', archived: 'warning' } as Record<string, '' | 'success' | 'info' | 'warning' | 'danger'>)[status] || 'info'
}

function gestureLabel(gesture?: string) {
  return ({
    salute: '敬礼',
    show_id: '出示证件',
    raise_hand: '举手',
    standard_stance: '标准站姿',
    hands_forward: '双手前伸',
    hand_on_chest: '手扶胸前',
    stop_signal: '拦停手势',
    point_front: '指向前方',
  } as Record<string, string>)[gesture || ''] || (gesture || '动作')
}
</script>

<style scoped lang="scss">
.video-library {
  display: flex;
  flex-direction: column;
  gap: 18px;
  padding: 4px 2px 8px;
}

.library-panel {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.library-panel__tabs,
.library-toolbar,
.auto-import-banner,
.summary-card,
.library-content,
.analysis-card,
.analysis-hero__main,
.analysis-hero__stats {
  border: 1px solid #dbe4f0;
  background: rgba(255, 255, 255, 0.96);
  box-shadow: 0 18px 40px rgba(15, 23, 42, 0.05);
}

.library-panel__tabs,
.library-toolbar,
.auto-import-banner,
.library-content,
.analysis-card,
.analysis-hero__main,
.analysis-hero__stats {
  border-radius: 8px;
}

.library-panel__tabs {
  padding: 0 18px;
}

.library-panel__tabs :deep(.el-tabs__header) {
  margin: 0;
}

.library-panel__tabs :deep(.el-tabs__nav-wrap::after) {
  display: none;
}

.library-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 16px 18px;
}

.library-toolbar__filters {
  display: flex;
  flex: 1;
  flex-wrap: wrap;
  gap: 12px;
}

.toolbar-select {
  width: 152px;
}

.training-template-row {
  display: grid;
  grid-template-columns: minmax(180px, 1.2fr) minmax(150px, 1fr) minmax(120px, 0.7fr);
  gap: 10px;
  width: 100%;
}

.toolbar-search {
  width: min(320px, 100%);
}

.toolbar-reset {
  border-radius: 10px;
}

.view-switch {
  display: flex;
  gap: 4px;
  padding: 4px;
  border-radius: 12px;
  background: #f3f7fd;
}

.view-switch__btn {
  border: none;
  background: transparent;
  color: #64748b;
  font-size: 13px;
  font-weight: 700;
  padding: 8px 14px;
  border-radius: 10px;
  cursor: pointer;
}

.view-switch__btn.is-active {
  background: #fff;
  color: #2563eb;
  box-shadow: 0 6px 16px rgba(37, 99, 235, 0.12);
}

.auto-import-banner {
  padding: 18px 20px;
  background: #f8fbff;
}

.auto-import-banner__badge {
  display: inline-flex;
  align-items: center;
  padding: 6px 12px;
  border-radius: 999px;
  background: #e0ecff;
  color: #1d4ed8;
  font-size: 13px;
  font-weight: 800;
}

.auto-import-banner__desc {
  margin-top: 10px;
  color: #334155;
  line-height: 1.75;
}

.auto-import-banner__desc code {
  padding: 2px 8px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.88);
}

.auto-import-banner__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 12px;
  color: #475569;
  font-size: 12px;
}

.auto-import-banner__status {
  color: #16a34a;
  font-weight: 800;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 16px;
}

.summary-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 18px;
  border-radius: 8px;
}

.summary-card__main {
  display: flex;
  flex-direction: column;
}

.summary-card__label {
  margin-bottom: 10px;
  color: #475569;
  font-size: 14px;
  font-weight: 700;
}

.summary-card__value {
  color: #13213a;
  font-size: 42px;
  line-height: 1;
  font-weight: 800;
}

.summary-card__desc {
  margin-top: 8px;
  color: #64748b;
  font-size: 13px;
}

.summary-card__icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 54px;
  height: 54px;
  border-radius: 16px;
  font-size: 24px;
  background: #eff6ff;
}

.summary-card__icon.is-blue { color: #2563eb; background: #eaf2ff; }
.summary-card__icon.is-green { color: #16a34a; background: #eafbf1; }
.summary-card__icon.is-purple { color: #7c3aed; background: #f3e8ff; }
.summary-card__icon.is-orange { color: #ea580c; background: #fff1e8; }
.summary-card__icon.is-red { color: #ef4444; background: #fff0f0; }

.library-content {
  padding: 18px;
}

.library-content__head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  margin-bottom: 16px;
}

.library-content__title {
  margin: 0;
  color: #13213a;
  font-size: 24px;
  font-weight: 800;
}

.library-content__subtitle {
  margin: 6px 0 0;
  color: #64748b;
  font-size: 14px;
}

.state-panel {
  padding: 48px 0;
}

.video-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 18px;
}

.video-grid--list {
  grid-template-columns: 1fr;
}

.video-grid--list .video-card {
  display: grid;
  grid-template-columns: 320px minmax(0, 1fr);
}

.video-card {
  overflow: hidden;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #fff;
  box-shadow: 0 14px 34px rgba(15, 23, 42, 0.06);
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.video-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 20px 44px rgba(15, 23, 42, 0.1);
}

.video-card__cover {
  position: relative;
  width: 100%;
  padding-top: 58%;
  overflow: hidden;
  background: #08111f;
  cursor: pointer;
}

.video-grid--list .video-card__cover {
  height: 100%;
  min-height: 220px;
  padding-top: 0;
}

.cover-img {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.cover-placeholder,
.cover-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}

.cover-placeholder {
  color: rgba(255, 255, 255, 0.3);
}

.cover-overlay {
  background: rgba(15, 23, 42, 0.52);
  color: #fff;
  opacity: 0;
  transition: opacity 0.2s ease;
}

.video-card:hover .cover-overlay {
  opacity: 1;
}

.type-chip,
.duration-chip,
.readiness-badge,
.analysis-badge,
.analysis-pill,
.analysis-tag,
.analysis-chip,
.thumb-auto-tag {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 800;
}

.type-chip {
  position: absolute;
  top: 12px;
  left: 12px;
  z-index: 2;
  padding: 6px 10px;
  color: #fff;
}

.type-chip--interactive { background: #2563eb; }
.type-chip--teaching { background: #16a34a; }

.duration-chip {
  position: absolute;
  right: 12px;
  bottom: 12px;
  z-index: 2;
  padding: 5px 10px;
  color: #fff;
  background: rgba(15, 23, 42, 0.78);
}

.video-card__body {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 16px;
}

.video-card__title {
  color: #0f172a;
  font-size: 18px;
  font-weight: 800;
}

.video-card__meta {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #64748b;
  font-size: 13px;
}

.meta-divider {
  color: #cbd5e1;
}

.video-card__badges {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.readiness-badge {
  padding: 4px 10px;
}

.readiness-badge.is-ready {
  background: rgba(34, 197, 94, 0.12);
  color: #15803d;
}

.readiness-badge.is-pending {
  background: rgba(249, 115, 22, 0.12);
  color: #c2410c;
}

.analysis-badge,
.analysis-pill,
.thumb-auto-tag {
  padding: 4px 10px;
  background: rgba(37, 99, 235, 0.12);
  color: #1d4ed8;
}

.analysis-badge--police {
  background: rgba(22, 163, 74, 0.12);
  color: #15803d;
}

.video-card__hint {
  min-height: 40px;
  margin: 0;
  color: #475569;
  font-size: 13px;
  line-height: 1.6;
}

.video-card__footer {
  margin-top: auto;
}

.card-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 2px 6px;
}

.pagination-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding-top: 20px;
}

.pagination-bar__count {
  color: #64748b;
  font-size: 14px;
}

.upload-area {
  width: 100%;
  padding: 18px;
  border: 1px dashed #cbd5e1;
  border-radius: 14px;
  background: #f8fafc;
  text-align: center;
  cursor: pointer;
}

.upload-area--small {
  padding: 12px;
}

.upload-icon {
  color: #3b82f6;
}

.upload-hint {
  margin: 8px 0 0;
  color: #475569;
  line-height: 1.7;
}

.upload-hint small,
.form-tip,
.warn-text,
.progress-text {
  color: #64748b;
}

.warn-text {
  color: #d97706 !important;
}

.form-tip {
  margin-left: 12px;
  font-size: 12px;
}

.thumb-preview {
  width: 96px;
  height: 58px;
  border-radius: 8px;
  object-fit: cover;
}

.thumb-actions {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 10px;
  margin-top: 8px;
}

.upload-progress {
  margin-top: 12px;
}

.progress-text {
  margin: 8px 0 0;
  text-align: center;
  font-size: 12px;
}

.analysis-toolbar,
.analysis-toolbar__left,
.analysis-toolbar__actions,
.analysis-kv,
.analysis-node__head,
.analysis-node__meta,
.analysis-node__chips,
.analysis-tags {
  display: flex;
}

.analysis-toolbar {
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}

.analysis-toolbar__left,
.analysis-toolbar__actions,
.analysis-kv,
.analysis-node__meta,
.analysis-node__chips,
.analysis-tags {
  flex-wrap: wrap;
  gap: 8px;
}

.analysis-select {
  width: 150px;
}

.analysis-select--small {
  width: 108px;
}

.analysis-toolbar__meta {
  color: #64748b;
  font-size: 13px;
}

.analysis-hero {
  display: grid;
  grid-template-columns: minmax(0, 1.7fr) minmax(280px, 1fr);
  gap: 14px;
  margin-bottom: 14px;
}

.analysis-hero__main,
.analysis-hero__stats {
  padding: 18px;
}

.analysis-hero__main {
  background: #f8fbff;
}

.analysis-hero__eyebrow {
  margin-bottom: 8px;
  color: #2563eb;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.04em;
}

.analysis-hero__title {
  color: #0f172a;
  font-size: 20px;
  font-weight: 800;
  line-height: 1.45;
}

.analysis-hero__desc {
  margin-top: 10px;
  color: #475569;
  line-height: 1.7;
}

.analysis-hero__stats {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.hero-stat {
  padding: 12px;
  border-radius: 14px;
  background: #f8fafc;
  text-align: center;
}

.hero-stat strong {
  display: block;
  color: #0f172a;
  font-size: 18px;
  font-weight: 800;
}

.hero-stat span {
  display: block;
  margin-top: 4px;
  color: #64748b;
  font-size: 12px;
}

.analysis-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
  margin-bottom: 14px;
}

.analysis-card {
  padding: 16px;
}

.analysis-card--full {
  margin-top: 4px;
}

.analysis-card__title {
  margin-bottom: 12px;
  color: #111827;
  font-size: 15px;
  font-weight: 700;
}

.analysis-kv {
  margin-bottom: 12px;
}

.analysis-kv > div {
  min-width: 180px;
  padding: 10px 12px;
  border-radius: 12px;
  background: #f8fafc;
}

.analysis-kv span {
  display: block;
  margin-bottom: 4px;
  color: #64748b;
  font-size: 12px;
}

.analysis-kv strong {
  color: #0f172a;
  font-size: 14px;
}

.analysis-block + .analysis-block {
  margin-top: 12px;
}

.analysis-block__label {
  margin-bottom: 6px;
  color: #475569;
  font-size: 12px;
  font-weight: 700;
}

.analysis-block__content {
  color: #0f172a;
  line-height: 1.75;
}

.analysis-block__content--muted,
.analysis-tag--muted {
  color: #94a3b8;
}

.analysis-tag {
  padding: 4px 10px;
  background: #eff6ff;
  color: #1d4ed8;
}

.ocr-list {
  display: grid;
  gap: 8px;
}

.ocr-item {
  padding: 8px 10px;
  border-radius: 10px;
  background: #f8fafc;
  color: #334155;
  line-height: 1.6;
}

.analysis-nodes {
  display: grid;
  gap: 12px;
}

.analysis-node {
  padding: 16px;
  border-radius: 16px;
  border: 1px solid #e2e8f0;
  background: #fff;
}

.analysis-node__head {
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 10px;
}

.analysis-node__title {
  color: #111827;
  font-size: 15px;
  font-weight: 700;
}

.analysis-node__time {
  margin-top: 4px;
  color: #64748b;
  font-size: 12px;
}

.analysis-node__instruction {
  margin-bottom: 8px;
  color: #0f172a;
  line-height: 1.7;
}

.analysis-node__summary {
  margin-bottom: 8px;
  padding: 8px 10px;
  border-radius: 8px;
  background: #f8fafc;
  color: #475569;
  font-size: 12px;
  line-height: 1.6;
}

.analysis-node__points {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 10px;
}

.analysis-node__points span {
  display: inline-flex;
  max-width: 100%;
  padding: 3px 8px;
  border-radius: 6px;
  background: #eff6ff;
  color: #1d4ed8;
  font-size: 12px;
  line-height: 1.5;
  word-break: break-word;
}

.analysis-node__meta {
  color: #475569;
  font-size: 12px;
}

.analysis-chip {
  padding: 4px 10px;
  background: #f1f5f9;
  color: #334155;
}

.analysis-chip--accent {
  background: #dcfce7;
  color: #15803d;
}

.analysis-chip--police {
  background: #dbeafe;
  color: #1d4ed8;
}

.analysis-chip--warn {
  background: #fff7ed;
  color: #c2410c;
}

@media (max-width: 1480px) {
  .summary-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .video-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 1180px) {
  .library-toolbar,
  .analysis-toolbar {
    flex-direction: column;
    align-items: stretch;
  }

  .summary-grid,
  .analysis-grid,
  .analysis-hero,
  .video-grid {
    grid-template-columns: 1fr 1fr;
  }

  .video-grid--list .video-card {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 780px) {
  .summary-grid,
  .analysis-grid,
  .analysis-hero,
  .video-grid,
  .analysis-hero__stats {
    grid-template-columns: 1fr;
  }

  .library-toolbar__filters,
  .pagination-bar {
    flex-direction: column;
    align-items: stretch;
  }

  .toolbar-select,
  .toolbar-search {
    width: 100%;
  }
}
</style>
