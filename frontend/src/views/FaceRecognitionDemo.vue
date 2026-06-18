<template>
  <div class="face-demo-page">
    <section class="face-demo-header">
      <div>
        <p class="eyebrow">训练身份强绑定</p>
        <h1>人脸核验训练看板</h1>
        <p class="intro">
          聚焦训练前身份核验、活体确认、训练中在岗监控和异常终止规则，保留可展示的流程与状态信息。
        </p>
      </div>
      <div class="header-status">
        <span class="status-dot"></span>
        运行中
      </div>
    </section>

    <section class="overview-grid">
      <article v-for="item in summaryCards" :key="item.label" class="metric-card">
        <div class="metric-card__icon">
          <component :is="item.icon" />
        </div>
        <div>
          <p>{{ item.label }}</p>
          <strong>{{ item.value }}</strong>
        </div>
      </article>
    </section>

    <section class="demo-layout">
      <aside class="flow-panel">
        <button
          v-for="step in steps"
          :key="step.key"
          type="button"
          class="flow-step"
          :class="{ 'flow-step--active': activeStep === step.key }"
          @click="activeStep = step.key"
        >
          <span>{{ step.no }}</span>
          <div>
            <strong>{{ step.title }}</strong>
            <small>{{ step.subtitle }}</small>
          </div>
        </button>
      </aside>

      <main class="stage-panel">
        <div class="camera-card">
          <div class="camera-frame">
            <div class="camera-grid"></div>
            <div class="face-silhouette">
              <span class="head"></span>
              <span class="shoulders"></span>
            </div>
            <div class="face-outline">
              <span class="scan-line"></span>
            </div>
            <div class="corner corner--tl"></div>
            <div class="corner corner--tr"></div>
            <div class="corner corner--bl"></div>
            <div class="corner corner--br"></div>
            <div class="camera-hud camera-hud--top">{{ activeConfig.cameraLabel }}</div>
            <div class="camera-hud camera-hud--bottom">{{ activeConfig.cameraStatus }}</div>
          </div>
          <div class="camera-status-row">
            <span v-for="tag in activeConfig.tags" :key="tag" class="status-chip">{{ tag }}</span>
          </div>
        </div>

        <div class="detail-panel">
          <div class="detail-head">
            <p class="eyebrow">{{ activeConfig.phase }}</p>
            <h2>{{ activeConfig.title }}</h2>
            <p>{{ activeConfig.description }}</p>
          </div>

          <div class="check-list">
            <div v-for="check in activeConfig.checks" :key="check.label" class="check-row">
              <span class="check-row__icon" :class="`check-row__icon--${check.status}`">
                <component :is="check.status === 'pass' ? CircleCheck : check.status === 'warn' ? Warning : Clock" />
              </span>
              <div>
                <strong>{{ check.label }}</strong>
                <small>{{ check.desc }}</small>
              </div>
            </div>
          </div>

          <div class="rule-box">
            <div class="rule-box__title">训练控制规则</div>
            <p>{{ activeConfig.rule }}</p>
          </div>
        </div>
      </main>
    </section>

    <section class="monitor-panel">
      <div class="monitor-head">
        <div>
          <p class="eyebrow">训练中实时监控</p>
          <h2>异常离线计数展示</h2>
        </div>
        <button type="button" class="reset-btn" @click="resetIncidents">重置计数</button>
      </div>

      <div class="incident-board">
        <div class="incident-counter">
          <span>{{ incidentCount }}</span>
          <small>/ 3 次异常</small>
        </div>
        <div class="incident-actions">
          <button type="button" @click="addIncident('人脸离开画面')">离开画面</button>
          <button type="button" @click="addIncident('多人进入画面')">多人出现</button>
          <button type="button" @click="addIncident('活体检测失败')">活体失败</button>
        </div>
        <div class="incident-result" :class="{ 'incident-result--danger': incidentCount >= 3 }">
          {{ incidentCount >= 3 ? '已达到 3 次异常：自动结束训练并进入评估流程' : '未达到终止阈值：继续监控并记录事件' }}
        </div>
      </div>

      <div class="timeline">
        <div v-for="event in incidentEvents" :key="event.id" class="timeline-item">
          <span></span>
          <div>
            <strong>{{ event.reason }}</strong>
            <small>{{ event.time }} 记录为一次失效事件</small>
          </div>
        </div>
        <div v-if="!incidentEvents.length" class="timeline-empty">暂无异常事件</div>
      </div>
    </section>

    <section class="detail-strip">
      <article class="strip-card">
        <p class="strip-label">采集结果</p>
        <strong>正脸照、账号、核验状态统一归档</strong>
        <span>可直接展示给管理端查看。</span>
      </article>
      <article class="strip-card">
        <p class="strip-label">核验条件</p>
        <strong>单人正脸通过后进入训练</strong>
        <span>多人、离开、翻拍都会触发异常。</span>
      </article>
      <article class="strip-card">
        <p class="strip-label">终止规则</p>
        <strong>累计 3 次异常自动评估</strong>
        <span>会话留痕并生成结束报告。</span>
      </article>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, inject, onMounted, onUnmounted, ref } from 'vue'
import { Camera, CircleCheck, Clock, Monitor, User, Warning } from '@element-plus/icons-vue'

type StepKey = 'register' | 'entry' | 'liveness' | 'monitor' | 'interrupt'

const activeStep = ref<StepKey>('register')
const incidentCount = ref(0)
const incidentEvents = ref<Array<{ id: number; reason: string; time: string }>>([])
const setMainScrollable = inject<((value: boolean) => void) | undefined>('setMainScrollable')

const summaryCards = [
  { label: '核验方式', value: '人脸 + 活体', icon: User },
  { label: '采集状态', value: '摄像头在线', icon: Camera },
  { label: '允许异常次数', value: '3 次', icon: Warning },
  { label: '处置结果', value: '自动评估', icon: Monitor },
]

const steps = [
  { key: 'register', no: '01', title: '管理端人脸注册', subtitle: '上传正脸照，建立特征库' },
  { key: 'entry', no: '02', title: '训练启动身份核验', subtitle: '摄像头启动、单人脸检测' },
  { key: 'liveness', no: '03', title: '活体检测', subtitle: '眨眼、转头、动态特征' },
  { key: 'monitor', no: '04', title: '训练中持续监控', subtitle: '实时比对与状态反馈' },
  { key: 'interrupt', no: '05', title: '异常自动中断', subtitle: '3 次异常后强制评估' },
] as const

const configs: Record<StepKey, any> = {
  register: {
    phase: '管理端',
    title: '采集学员本人正脸照',
    description: '管理员为学员建立唯一身份档案，训练入口只识别本人账号与人脸档案。',
    cameraLabel: '注册采集',
    cameraStatus: '档案已绑定',
    tags: ['正脸照', '账号绑定', '身份档案'],
    checks: [
      { label: '学员账号', desc: '账号与身份档案一一绑定', status: 'pass' },
      { label: '正脸照片', desc: '作为训练核验的基准照片', status: 'pass' },
      { label: '档案更新', desc: '重新采集后覆盖旧照片与旧状态', status: 'pass' },
    ],
    rule: '一个学员仅绑定一个有效人脸档案，更新照片时覆盖旧特征。',
  },
  entry: {
    phase: '学员端',
    title: '进入训练前先进行身份核验',
    description: '开始训练前确认画面中存在单人正脸，并与当前登录学员身份一致。',
    cameraLabel: '入场核验',
    cameraStatus: '等待通过',
    tags: ['摄像头启动', '单人脸', '正脸'],
    checks: [
      { label: '人脸存在', desc: '未识别到人脸时禁止进入训练', status: 'pass' },
      { label: '单人脸检测', desc: '多人出现时判定为异常', status: 'pass' },
      { label: '本人核验', desc: '身份一致后允许启动对话', status: 'pass' },
    ],
    rule: '身份验证失败时阻止训练会话和对话输入启动。',
  },
  liveness: {
    phase: '活体检测',
    title: '防止照片、视频播放与屏幕翻拍',
    description: '展示眨眼检测、头部轻微转动、光照响应和动态特征检测的状态。',
    cameraLabel: '活体检测',
    cameraStatus: '动态检测中',
    tags: ['眨眼', '转头', '动态响应'],
    checks: [
      { label: '眨眼检测', desc: '检测眼部关键点变化', status: 'pass' },
      { label: '头部转动', desc: '提示学员轻微左右转头', status: 'pass' },
      { label: '反翻拍', desc: '识别照片或屏幕播放风险', status: 'pass' },
    ],
    rule: '活体检测失败视为身份验证失败，训练入口保持锁定。',
  },
  monitor: {
    phase: '训练中',
    title: '持续身份确认与异常记录',
    description: '训练期间持续检测摄像头画面、人脸匹配和活体状态，形成可追溯监控记录。',
    cameraLabel: '训练监控',
    cameraStatus: '持续在岗',
    tags: ['持续比对', '离线记录', '状态反馈'],
    checks: [
      { label: '人脸持续在场', desc: '离开画面记录一次异常离线', status: 'pass' },
      { label: '本人持续匹配', desc: '非本人进入画面判定为异常', status: 'pass' },
      { label: '状态持续有效', desc: '异常行为进入预警并留痕', status: 'pass' },
    ],
    rule: '每次离开识别区域或多人出现，均记录为一次失效事件。',
  },
  interrupt: {
    phase: '自动终止',
    title: '达到 3 次异常后结束训练',
    description: '展示异常次数累计到上限后的训练终止、数据保存、评估流程与报告生成。',
    cameraLabel: '异常处置',
    cameraStatus: '进入评估',
    tags: ['3 次异常', '强制评估', '终止报告'],
    checks: [
      { label: '自动结束训练', desc: '当前训练会话进入评估状态', status: 'pass' },
      { label: '保存数据', desc: '保存对话记录、训练数据和异常日志', status: 'pass' },
      { label: '生成报告', desc: '生成训练终止报告供管理端查看', status: 'pass' },
    ],
    rule: '累计达到 3 次异常后，系统强制进入评估流程。',
  },
}

const activeConfig = computed(() => configs[activeStep.value])

const addIncident = (reason: string) => {
  if (incidentCount.value >= 3) return
  incidentCount.value += 1
  incidentEvents.value.unshift({
    id: Date.now(),
    reason,
    time: new Date().toLocaleTimeString('zh-CN', { hour12: false }),
  })
  if (incidentCount.value >= 3) activeStep.value = 'interrupt'
}

const resetIncidents = () => {
  incidentCount.value = 0
  incidentEvents.value = []
}

onMounted(() => {
  setMainScrollable?.(true)
})

onUnmounted(() => {
  setMainScrollable?.(false)
})
</script>

<style scoped>
.face-demo-page {
  min-height: 100%;
  padding: 24px;
  background: #eef3f8;
  color: #172033;
}

.face-demo-header,
.monitor-panel,
.stage-panel,
.flow-panel,
.metric-card {
  border: 1px solid #e3eaf4;
  border-radius: 8px;
  background: #fff;
}

.face-demo-header {
  display: flex;
  justify-content: space-between;
  gap: 20px;
  padding: 22px 24px;
  box-shadow: 0 8px 22px rgba(15, 23, 42, 0.04);
}

.eyebrow {
  margin: 0 0 6px;
  color: #2563eb;
  font-size: 12px;
  font-weight: 800;
}

h1,
h2,
p {
  margin-top: 0;
}

h1 {
  margin-bottom: 8px;
  font-size: 28px;
  letter-spacing: 0;
}

.intro {
  max-width: 760px;
  margin-bottom: 0;
  color: #64748b;
  line-height: 1.7;
}

.header-status {
  display: inline-flex;
  align-items: center;
  align-self: flex-start;
  gap: 8px;
  padding: 8px 12px;
  border-radius: 999px;
  background: #eff6ff;
  color: #1d4ed8;
  font-size: 13px;
  font-weight: 700;
  white-space: nowrap;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 999px;
  background: #22c55e;
}

.overview-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  margin-top: 12px;
}

.metric-card {
  display: flex;
  align-items: center;
  gap: 12px;
  min-height: 86px;
  padding: 16px 18px;
  box-shadow: 0 8px 20px rgba(15, 23, 42, 0.035);
}

.metric-card__icon {
  display: grid;
  place-items: center;
  width: 40px;
  height: 40px;
  border-radius: 8px;
  background: #eef6ff;
  color: #2563eb;
}

.metric-card p {
  margin-bottom: 4px;
  color: #64748b;
  font-size: 12px;
}

.metric-card strong {
  font-size: 19px;
  line-height: 1.25;
}

.demo-layout {
  display: grid;
  grid-template-columns: 248px minmax(0, 1fr);
  gap: 12px;
  margin-top: 12px;
}

.flow-panel {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 12px;
}

.flow-step {
  display: grid;
  grid-template-columns: 34px 1fr;
  gap: 10px;
  align-items: center;
  width: 100%;
  min-height: 72px;
  padding: 11px;
  border: 1px solid transparent;
  border-radius: 8px;
  background: transparent;
  text-align: left;
  cursor: pointer;
}

.flow-step span {
  display: grid;
  place-items: center;
  width: 30px;
  height: 30px;
  border-radius: 999px;
  background: #e2e8f0;
  color: #475569;
  font-size: 12px;
  font-weight: 800;
}

.flow-step strong,
.flow-step small {
  display: block;
}

.flow-step strong {
  color: #172033;
  font-size: 14px;
}

.flow-step small {
  margin-top: 3px;
  color: #94a3b8;
  font-size: 12px;
}

.flow-step--active {
  border-color: #bfdbfe;
  background: #eff6ff;
}

.flow-step--active span {
  background: #2563eb;
  color: #fff;
}

.stage-panel {
  display: grid;
  grid-template-columns: minmax(420px, 0.95fr) minmax(0, 1fr);
  gap: 18px;
  padding: 18px;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.04);
}

.camera-frame {
  position: relative;
  aspect-ratio: 4 / 3;
  overflow: hidden;
  border-radius: 8px;
  background:
    radial-gradient(circle at 50% 42%, rgba(96, 165, 250, 0.22), transparent 34%),
    linear-gradient(135deg, #111d34 0%, #0a1325 64%, #0d1b34 100%);
  box-shadow: inset 0 0 0 1px rgba(148, 163, 184, 0.12);
}

.camera-grid {
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(rgba(148, 163, 184, 0.08) 1px, transparent 1px),
    linear-gradient(90deg, rgba(148, 163, 184, 0.08) 1px, transparent 1px);
  background-size: 48px 48px;
  mask-image: radial-gradient(circle at center, black, transparent 72%);
}

.face-silhouette {
  position: absolute;
  inset: 18% 28% 16%;
  display: grid;
  justify-items: center;
  align-content: center;
  opacity: 0.92;
}

.face-silhouette .head {
  width: 42%;
  aspect-ratio: 1;
  border-radius: 50%;
  background: linear-gradient(145deg, #dbeafe, #94a3b8);
  box-shadow: 0 0 30px rgba(96, 165, 250, 0.16);
}

.face-silhouette .shoulders {
  width: 78%;
  height: 25%;
  margin-top: 5%;
  border-radius: 999px 999px 18px 18px;
  background: linear-gradient(145deg, #bfdbfe, #64748b);
  opacity: 0.85;
}

.face-outline {
  position: absolute;
  inset: 16% 24%;
  border: 2px solid rgba(59, 130, 246, 0.95);
  border-radius: 42% 42% 48% 48%;
  box-shadow:
    0 0 0 999px rgba(15, 23, 42, 0.22),
    0 0 22px rgba(37, 99, 235, 0.35);
}

.scan-line {
  position: absolute;
  left: 8%;
  right: 8%;
  top: 18%;
  height: 2px;
  background: #60a5fa;
  animation: scan 2.4s linear infinite;
}

@keyframes scan {
  0% { transform: translateY(0); }
  50% { transform: translateY(150px); }
  100% { transform: translateY(0); }
}

.corner {
  position: absolute;
  width: 34px;
  height: 34px;
  border-color: rgba(96, 165, 250, 0.9);
}

.corner--tl {
  top: 18px;
  left: 18px;
  border-top: 2px solid;
  border-left: 2px solid;
}

.corner--tr {
  top: 18px;
  right: 18px;
  border-top: 2px solid;
  border-right: 2px solid;
}

.corner--bl {
  bottom: 18px;
  left: 18px;
  border-bottom: 2px solid;
  border-left: 2px solid;
}

.corner--br {
  right: 18px;
  bottom: 18px;
  border-right: 2px solid;
  border-bottom: 2px solid;
}

.camera-hud {
  position: absolute;
  left: 12px;
  padding: 5px 9px;
  border-radius: 4px;
  background: rgba(15, 23, 42, 0.72);
  color: #fff;
  font-size: 12px;
  font-weight: 700;
}

.camera-hud--top {
  top: 12px;
  left: auto;
  right: 12px;
}

.camera-hud--bottom {
  bottom: 12px;
}

.camera-status-row {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-top: 12px;
}

.status-chip {
  padding: 5px 9px;
  border-radius: 4px;
  background: #f1f5f9;
  color: #334155;
  font-size: 12px;
  font-weight: 700;
}

.detail-head h2 {
  margin-bottom: 8px;
  font-size: 22px;
  letter-spacing: 0;
}

.detail-head p {
  color: #64748b;
  line-height: 1.7;
}

.check-list {
  display: grid;
  gap: 10px;
  margin-top: 16px;
}

.check-row {
  display: grid;
  grid-template-columns: 34px 1fr;
  gap: 10px;
  align-items: center;
  padding: 11px;
  border: 1px solid #edf2f7;
  border-radius: 8px;
}

.check-row__icon {
  display: grid;
  place-items: center;
  width: 30px;
  height: 30px;
  border-radius: 999px;
}

.check-row__icon--pass {
  background: #dcfce7;
  color: #16a34a;
}

.check-row__icon--warn {
  background: #fff7ed;
  color: #f97316;
}

.check-row strong,
.check-row small {
  display: block;
}

.check-row small {
  margin-top: 3px;
  color: #64748b;
}

.rule-box {
  margin-top: 16px;
  padding: 14px;
  border-radius: 8px;
  background: #f8fafc;
}

.rule-box__title {
  margin-bottom: 6px;
  font-weight: 800;
}

.rule-box p {
  margin-bottom: 0;
  color: #475569;
}

.monitor-panel {
  margin-top: 12px;
  padding: 18px;
  box-shadow: 0 8px 22px rgba(15, 23, 42, 0.04);
}

.detail-strip {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  margin-top: 12px;
}

.strip-card {
  min-height: 126px;
  padding: 16px 18px;
  border: 1px solid #e3eaf4;
  border-radius: 8px;
  background: #fff;
  box-shadow: 0 8px 20px rgba(15, 23, 42, 0.03);
}

.strip-label {
  margin-bottom: 10px;
  color: #2563eb;
  font-size: 12px;
  font-weight: 800;
}

.strip-card strong {
  display: block;
  margin-bottom: 8px;
  font-size: 16px;
  line-height: 1.45;
}

.strip-card span {
  color: #64748b;
  line-height: 1.65;
}

.monitor-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
}

.monitor-head h2 {
  margin-bottom: 0;
}

.reset-btn,
.incident-actions button {
  border: 1px solid #bfdbfe;
  border-radius: 6px;
  background: #fff;
  color: #2563eb;
  font-weight: 700;
  cursor: pointer;
}

.reset-btn {
  padding: 8px 12px;
}

.incident-board {
  display: grid;
  grid-template-columns: 160px 1fr minmax(260px, 0.8fr);
  gap: 14px;
  align-items: center;
  margin-top: 14px;
}

.incident-counter {
  padding: 18px;
  border-radius: 8px;
  background: #eff6ff;
  color: #1d4ed8;
  text-align: center;
}

.incident-counter span {
  display: block;
  font-size: 42px;
  font-weight: 900;
}

.incident-counter small {
  font-weight: 700;
}

.incident-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.incident-actions button {
  padding: 9px 12px;
}

.reset-btn:hover,
.incident-actions button:hover {
  background: #eff6ff;
}

.incident-result {
  padding: 13px 14px;
  border-radius: 8px;
  background: #f8fafc;
  color: #475569;
  font-weight: 700;
}

.incident-result--danger {
  background: #fef2f2;
  color: #dc2626;
}

.timeline {
  display: grid;
  gap: 10px;
  margin-top: 16px;
}

.timeline-item {
  display: grid;
  grid-template-columns: 12px 1fr;
  gap: 10px;
  align-items: start;
}

.timeline-item > span {
  width: 10px;
  height: 10px;
  margin-top: 5px;
  border-radius: 999px;
  background: #ef4444;
}

.timeline-item strong,
.timeline-item small {
  display: block;
}

.timeline-item small,
.timeline-empty {
  color: #64748b;
}

@media (max-width: 1100px) {
  .overview-grid,
  .demo-layout,
  .stage-panel,
  .incident-board,
  .detail-strip {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 720px) {
  .face-demo-page {
    padding: 14px;
  }

  .face-demo-header,
  .monitor-head {
    flex-direction: column;
    align-items: flex-start;
  }

  h1 {
    font-size: 23px;
  }

  .stage-panel {
    padding: 12px;
  }
}
</style>
