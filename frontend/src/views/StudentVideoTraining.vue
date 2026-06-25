<template>
  <div class="video-training-page">

    <!-- 鍔犺浇涓?-->
    <div v-if="loading" class="state-center">
      <el-skeleton :rows="4" animated style="max-width:560px" />
    </div>

    <!-- 瑙嗛涓嶅瓨鍦?-->
    <div v-else-if="!video" class="state-center">
      <el-empty description="视频不存在或暂未开放">
        <el-button @click="router.back()">返回</el-button>
      </el-empty>
    </div>

    <!-- 涓讳綋 -->
    <template v-else>

      <!-- 鈹€鈹€ 鍓嶇疆绠€鎶ュ脊绐楋紙杩涘叆璁粌鍓嶅繀椤诲叧闂級 鈹€鈹€ -->
      <van-popup
        v-model:show="showBriefing"
        :close-on-click-overlay="false"
        round
        teleport="body"
        class="briefing-popup"
        :overlay-style="{ backgroundColor: 'rgba(0,0,0,0.82)' }"
      >
        <div class="briefing-card">
          <div class="briefing-card__head">
            <el-tag type="danger" effect="dark" size="small">实训简报</el-tag>
            <span class="briefing-card__title">{{ video.title }}</span>
          </div>

          <!-- 绠€鎶ュ唴瀹?-->
          <div class="briefing-card__body">
            <div v-if="video.briefing" class="briefing-content">{{ video.briefing }}</div>
            <div v-else class="briefing-default">
              <p>本次训练为第一视角交互式实训，系统会在关键节点自动暂停并检测你的动作与话术。</p>
              <p>完成全部节点后会生成评估报告，请认真对待每一个训练节点。</p>
            </div>

            <div class="precheck-panel">
              <div class="precheck-panel__head">
                <span class="precheck-panel__title">入场校验</span>
                <span class="precheck-panel__badge" :class="canStartTraining ? 'is-ready' : 'is-checking'">
                  {{ canStartTraining ? '可进入训练' : '校验中' }}
                </span>
              </div>
              <div v-if="cameraOn" class="precheck-camera">
                <video ref="briefingCameraRef" autoplay muted playsinline class="precheck-camera__video" />
                <div class="precheck-camera__hint">
                  请保持单人入镜，并做轻微自然动作完成身份校验。
                </div>
                <div v-if="presenceSupported" class="precheck-metrics">
                  <div class="precheck-metric" :class="singleFaceReady ? 'is-pass' : 'is-checking'">
                    <span class="precheck-metric__label">入镜人数</span>
                    <span class="precheck-metric__value">{{ resolvedFaceCountText }}</span>
                  </div>
                  <div class="precheck-metric" :class="liveReady ? 'is-pass' : 'is-checking'">
                    <span class="precheck-metric__label">活体动作</span>
                    <span class="precheck-metric__value">{{ resolvedLiveMotionText }}</span>
                  </div>
                </div>
              </div>
              <div class="precheck-list">
                <div class="precheck-item" :class="identityBannerClass">
                  <span class="precheck-item__label">身份校验</span>
                  <span class="precheck-item__value">{{ resolvedIdentityStatusText }}</span>
                </div>
                <div class="precheck-item" :class="deviceReady ? 'is-pass' : 'is-warn'">
                  <span class="precheck-item__label">设备校验</span>
                  <span class="precheck-item__value">{{ deviceStatusText }}</span>
                </div>
                <div class="precheck-item" :class="speechSupported ? 'is-pass' : 'is-warn'">
                  <span class="precheck-item__label">语音识别</span>
                  <span class="precheck-item__value">{{ speechSupported ? '节点触发后自动开始识别' : '当前环境语音识别不可用' }}</span>
                </div>
              </div>
              <div v-if="presenceMessage || deviceWarningText" class="precheck-hint">
                {{ resolvedPrecheckHintText }}
              </div>
            </div>

            <!-- 娉ㄦ剰浜嬮」 -->
            <div class="briefing-notices">
              <div class="bn-item bn-item--warn">
                <span class="bn-dot">!</span>
                视频播放期间<strong>禁止拖动进度条</strong>，违规行为将被记录。
              </div>
              <div class="bn-item bn-item--info">
                <span class="bn-dot">i</span>
                节点超时后将触发扣分选项，请保持专注。
              </div>
              <div class="bn-item bn-item--info">
                <span class="bn-dot">i</span>
                切换标签页、离开页面等违规行为将被系统记录。
              </div>
            </div>

            <!-- 璁粌妯″紡閫夋嫨 -->
            <div class="briefing-mode">
              <div class="mode-label">训练模式</div>
              <div class="mode-options">
                <button
                  class="mode-btn"
                  :class="{ active: trainingMode === 'practice' }"
                  @click="trainingMode = 'practice'"
                >
                  <div class="mode-btn__title">练习模式</div>
                  <div class="mode-btn__desc">容错更宽松，适合熟悉流程。</div>
                </button>
                <button
                  class="mode-btn mode-btn--exam"
                  :class="{ active: trainingMode === 'exam' }"
                  @click="trainingMode = 'exam'"
                >
                  <div class="mode-btn__title">考核模式</div>
                  <div class="mode-btn__desc">严格评分，计入正式训练记录</div>
                </button>
              </div>
            </div>

            <!-- 鑺傜偣姒傝 -->
            <div v-if="video.nodes?.length" class="briefing-stats">
              <div class="bs-item">
                <span class="bs-num">{{ video.nodes.length }}</span>
                <span class="bs-label">训练节点</span>
              </div>
              <div v-if="video.duration" class="bs-item">
                <span class="bs-num">{{ formatTime(video.duration) }}</span>
                <span class="bs-label">视频时长</span>
              </div>
              <div class="bs-item">
                <span class="bs-num">{{ video.nodes.reduce((a, n) => a + n.score_weight, 0) }}</span>
                <span class="bs-label">总分</span>
              </div>
            </div>
          </div>

          <div class="briefing-card__foot">
            <el-button @click="router.back()">暂不进入</el-button>
            <el-button type="primary" :disabled="!canStartTraining" @click="confirmBriefing">
              {{ canStartTraining ? '已了解，开始训练' : '请先完成入场校验' }}
            </el-button>
          </div>
        </div>
      </van-popup>

      <div class="training-shell">
        <div class="training-topbar">
          <div class="training-topbar__left">
            <el-button :icon="ArrowLeft" text class="training-back" @click="confirmExit">返回</el-button>
            <el-tag type="primary" effect="dark" size="small">交互实训</el-tag>
            <div class="training-title-wrap">
              <div class="training-title">{{ video.title }}</div>
              <div class="training-subtitle">实训 - 现场处置流程</div>
            </div>
          </div>

          <div class="training-topbar__center">
            <div class="training-step__summary">
              节点 {{ displayNodeNumber }} / {{ video.nodes.length }}
              <span v-if="displayNodeTitle"> {{ displayNodeTitle }}</span>
            </div>
            <div class="training-stepper">
              <span
                v-for="(_, i) in video.nodes"
                :key="i"
                class="training-stepper__dot"
                :class="{
                  'is-done': nodeStatuses[i] === 'pass',
                  'is-skip': nodeStatuses[i] === 'skip' || nodeStatuses[i] === 'timeout',
                  'is-active': displayNodeIndex === i,
                }"
              />
            </div>
          </div>

          <div class="training-topbar__right">
            <div class="training-chip">
              <span class="training-chip__label">本节点剩余</span>
              <strong>{{ topbarTimerText }}</strong>
            </div>
            <div class="training-chip training-chip--mode">
              {{ trainingMode === 'exam' ? '考核模式' : '练习模式' }}
            </div>
            <el-button class="training-exit" @click="confirmExit">退出训练</el-button>
          </div>
        </div>

        <div class="training-main">
          <aside class="training-side training-side--left">
            <section class="glass-panel monitor-card">
              <div class="panel-title-row">
                <div class="panel-title">摄像头画面（镜像）</div>
                <span class="status-pill" :class="cameraOn ? 'is-pass' : 'is-warn'">
                  {{ cameraOn ? '已连接' : '未连接' }}
                </span>
              </div>
              <div class="monitor-camera">
                <video v-if="cameraOn" ref="cameraRef" autoplay muted playsinline class="monitor-camera__video" />
                <div v-else class="monitor-camera__placeholder">等待摄像头接入</div>
              </div>
              <div class="monitor-tools">
                <span>拍照</span>
                <span>语音</span>
                <span>全屏</span>
              </div>
            </section>

            <section class="glass-panel side-status-card">
              <div class="side-status-card__banner" :class="identityBannerClass">
                <span>{{ identityBannerText }}</span>
                <span class="side-status-card__icon">{{ identityBannerIcon }}</span>
              </div>
              <div class="panel-title muted">设备状态</div>
              <div class="side-status-list">
                <div class="side-status-item">
                  <span>摄像头</span>
                  <strong :class="cameraOn ? 'text-pass' : 'text-warn'">{{ cameraOn ? '正常' : '异常' }}</strong>
                </div>
                <div class="side-status-item">
                  <span>麦克风</span>
                  <strong :class="deviceReady ? 'text-pass' : 'text-warn'">{{ deviceReady ? '正常' : '异常' }}</strong>
                </div>
                <div class="side-status-item">
                  <span>环境光线</span>
                  <strong :class="presenceSupported ? 'text-pass' : 'text-warn'">{{ presenceSupported ? (singleFaceReady ? '良好' : '待优化') : '已降级' }}</strong>
                </div>
                <div class="side-status-item">
                  <span>环境噪音</span>
                  <strong :class="speechSupported ? 'text-pass' : 'text-warn'">{{ speechSupported ? '正常' : '受限' }}</strong>
                </div>
              </div>
              <div class="side-status-help">{{ resolvedPrecheckHintText || '设备检测正常，可按任务要求完成动作和话术。' }}</div>
            </section>

            <section class="glass-panel prompt-card">
              <div class="prompt-card__avatar">警</div>
              <div class="prompt-card__body">
                <div class="prompt-card__title">现场提示</div>
                <div class="prompt-card__text">{{ activePromptText }}</div>
              </div>
            </section>
          </aside>

          <section class="training-stage">
            <div class="stage-frame" ref="videoWrapRef">
              <video
                ref="videoRef"
                class="stage-video"
                :src="playbackVideoUrl"
                preload="auto"
                @timeupdate="onTimeUpdate"
                @ended="onVideoEnded"
                @seeking="onSeeking"
                @contextmenu.prevent
              />

              <div class="stage-overlay-top">
                <div class="stage-scene-tag">
                  {{ nodeActive ? `当前节点 ${displayNodeNumber}` : '视频播放中' }}
                </div>
                <div v-if="nodeActive && currentNode" class="stage-scene-task">
                  {{ currentNode.title }}
                </div>
              </div>

              <div class="stage-overlay-prompt">
                <div class="stage-overlay-prompt__title">现场提示</div>
                <div class="stage-overlay-prompt__text">{{ activePromptText }}</div>
              </div>
            </div>

            <div class="stage-controls glass-panel">
              <div class="stage-controls__left">
                <button class="stage-icon-btn" type="button">{{ videoRef?.paused ? '▶' : 'Ⅱ' }}</button>
                <button class="stage-icon-btn" type="button">🔊</button>
              </div>
              <div class="stage-controls__progress">
                <input
                  class="stage-progress"
                  type="range"
                  min="0"
                  max="100"
                  :value="playbackProgress"
                  disabled
                />
              </div>
              <div class="stage-controls__time">
                <div>{{ formatTime(playbackCurrentTime) }}</div>
                <small>/{{ formatTime(video.duration || 0) }}</small>
              </div>
              <div class="stage-controls__meta">
                <span>{{ trainingMode === 'exam' ? '考核' : '练习' }}</span>
                <span>{{ nodeActive ? `${countdown}s` : '待触发' }}</span>
              </div>
            </div>

            <div class="stage-bottom-grid">
              <section class="glass-panel hud-card">
                <div class="panel-title">语音识别</div>
                <div class="hud-status-row">
                  <span class="status-circle" :class="`is-${speechStatus}`" />
                  <span>{{ resolvedSpeechStatusLabel }}</span>
                </div>
                <div class="speech-meter">
                  <span
                    v-for="bar in 16"
                    :key="bar"
                    class="speech-meter__bar"
                    :class="{ 'is-active': bar <= speechMeterLevel }"
                  />
                </div>
                    <div class="hud-note">音量：{{ speechHasTranscript ? '已采集' : speechStatus === 'listening' ? '识别中' : '待命' }}</div>
              </section>

              <section class="glass-panel hud-card">
                <div class="panel-title">动作识别</div>
                <div class="hud-status-row">
                  <span class="status-circle" :class="gestureIndicatorTone" />
                  <span>{{ gestureIndicatorText }}</span>
                </div>
                <div class="gesture-figure">
                  <div class="gesture-figure__head" />
                  <div class="gesture-figure__body" />
                </div>
                <div class="hud-note">检测到：{{ gestureTargetLabel || '0 个动作' }}</div>
              </section>

              <section class="glass-panel hud-card">
                <div class="panel-title">识别节点总览</div>
                <div class="summary-list">
                  <div v-for="item in resolvedTaskSummaryItems" :key="item.label" class="summary-item">
                    <span class="summary-dot" :class="`is-${item.tone}`" />
                    <span>{{ item.label }}</span>
                    <strong>{{ item.value }}</strong>
                  </div>
                </div>
              </section>
            </div>
          </section>

          <aside class="training-side training-side--right">
            <section class="glass-panel rail-panel">
              <div class="rail-panel__tabs">
                <span class="is-active">训练节点</span>
                <span>实训信息</span>
              </div>
              <div class="rail-panel__head">
                <div class="panel-title">节点进度（{{ completedCount }}/{{ video.nodes.length }}）</div>
                <span class="rail-panel__percent">完成 {{ nodeProgress }}%</span>
              </div>
              <div class="rail-panel__list">
                <div
                  v-for="(node, i) in video.nodes"
                  :key="node.id"
                  class="rail-line"
                  :class="{
                    'is-active': displayNodeIndex === i,
                    'is-pass': nodeStatuses[i] === 'pass',
                    'is-skip': nodeStatuses[i] === 'skip' || nodeStatuses[i] === 'timeout',
                  }"
                >
                  <div class="rail-line__index">
                    <el-icon v-if="nodeStatuses[i] === 'pass'"><CircleCheck /></el-icon>
                    <el-icon v-else-if="nodeStatuses[i] === 'skip' || nodeStatuses[i] === 'timeout'"><Remove /></el-icon>
                    <span v-else>{{ i + 1 }}</span>
                  </div>
                  <div class="rail-line__body">
                    <div class="rail-line__title">节点 {{ i + 1 }}</div>
                    <div class="rail-line__name">{{ node.title || ('节点' + (i + 1)) }}</div>
                    <div class="rail-line__meta">
                      <span>{{ nodeStatuses[i] === 'pass' ? '已完成' : nodeStatuses[i] ? resultLabel(nodeStatuses[i]) : (displayNodeIndex === i ? '进行中' : '未开始') }}</span>
                      <span>{{ formatTime(node.trigger_time) }}</span>
                    </div>
                  </div>
                </div>
              </div>
            </section>

            <section class="glass-panel task-panel">
              <div class="panel-title">当前节点任务</div>
              <div v-if="displayNode" class="task-panel__content">
                <div class="task-panel__section">
                  <div class="task-panel__label">任务要求</div>
                  <div class="task-panel__text">{{ displayInstruction }}</div>
                </div>

                <div v-if="displaySceneSummary" class="task-panel__section">
                  <div class="task-panel__label">警情摘要</div>
                  <div class="task-panel__text">{{ displaySceneSummary }}</div>
                </div>

                <div v-if="displayStandardPoints.length" class="task-panel__section">
                  <div class="task-panel__label">评分要点</div>
                  <div class="standard-point-list">
                    <span v-for="point in displayStandardPoints" :key="point" class="standard-point">{{ point }}</span>
                  </div>
                </div>

                <div v-if="displayRiskSignals.length || displayLawPoints.length" class="task-panel__section">
                  <div class="task-panel__label">现场风险与程序要点</div>
                  <div v-if="displayRiskSignals.length" class="standard-point-list">
                    <span v-for="point in displayRiskSignals" :key="`risk-${point}`" class="standard-point standard-point--risk">{{ point }}</span>
                  </div>
                  <div v-if="displayLawPoints.length" class="standard-point-list standard-point-list--stacked">
                    <span v-for="point in displayLawPoints" :key="`law-${point}`" class="standard-point standard-point--law">{{ point }}</span>
                  </div>
                </div>

                <div v-if="displaySpeechHint" class="task-panel__section">
                  <div class="task-panel__label">标准话术参考</div>
                  <div class="task-panel__quote">{{ displaySpeechHint }}</div>
                </div>

                <div v-if="displayGestureHint" class="task-panel__section">
                  <div class="task-panel__label">标准动作参考</div>
                  <div class="task-panel__quote">{{ displayGestureHint }}</div>
                </div>

                <div v-if="effectiveShowPropPanel && currentNode" class="prop-panel" :class="propReady ? 'prop-panel--ready' : 'prop-panel--pending'">
                  <div class="prop-panel__visual" :class="`prop-panel__visual--${propVisualTone}`">
                    <div class="prop-panel__visual-badge">{{ propVisualBadge }}</div>
                    <div class="prop-panel__visual-name">{{ propActionLabel }}</div>
                    <div class="prop-panel__visual-mode">{{ currentNode.prop_mode === 'manual' ? '等待手动取出' : '系统自动提供' }}</div>
                  </div>
                  <div class="prop-panel__meta">
                    <div class="prop-panel__label">{{ propPanelLabel }}</div>
                    <div class="prop-panel__desc">{{ propPanelDescription }}</div>
                  </div>
                  <el-button
                    v-if="currentNode.prop_mode === 'manual' && !propReady"
                    type="primary"
                    size="small"
                    @click="activateVirtualProp"
                  >
                    取出{{ propActionLabel }}
                  </el-button>
                  <span v-else class="prop-panel__status">{{ propReady ? `${propActionLabel}已就绪` : '系统将自动提供道具' }}</span>
                </div>

                <template v-if="nodeActive && currentNode">
                  <div v-if="currentNode.node_type === 'action' || currentNode.node_type === 'voice_qa'" class="task-speech-box">
                    <div class="speech-status speech-status--compact" :class="speechStatus">
                      <span class="speech-dot" :class="'speech-dot--' + speechStatus" />
                      <span>{{ resolvedSpeechStatusLabel }}</span>
                    </div>
                    <div v-if="interimText || finalText" class="speech-transcript speech-transcript--panel">
                      <span class="interim">{{ interimText }}</span>
                      <span v-if="finalText" class="final">{{ finalText }}</span>
                    </div>
                    <el-input
                      v-if="showManualAnswerInput"
                      v-model="manualSpeechText"
                      type="textarea"
                      :rows="3"
                      resize="none"
                      class="speech-manual-input"
                      :placeholder="currentPoliceNode ? '请写下你的现场处置回答，覆盖风险、流程、话术和依法安全要点。' : '语音识别受限时，可手动补录你刚才说出的关键话术。'"
                    />
                    <div class="task-actions">
                      <el-button v-if="speechStatus !== 'listening'" type="primary" size="small" :icon="Microphone" @click="restartSpeechCapture">重新识别</el-button>
                      <el-button v-if="speechStatus === 'listening'" type="warning" size="small" @click="stopSpeech">结束本轮</el-button>
                      <el-button v-if="speechHasTranscript || !requiresSpeechTranscript || gestureFallbackEnabled" type="success" size="small" :icon="Check" @click="submitActionNode">
                        {{ currentPoliceNode ? '提交处置回答' : '确认完成' }}
                      </el-button>
                    </div>
                  </div>

                  <div v-else-if="currentNode.node_type === 'judge'" class="judge-row judge-row--panel">
                    <el-button type="success" size="large" @click="submitJudge(true)">正确</el-button>
                    <el-button type="danger" size="large" @click="submitJudge(false)">错误</el-button>
                  </div>

                  <div v-else-if="currentNode.node_type === 'choice'" class="choice-panel">
                    <div v-if="choiceTimeLimit > 0" class="choice-timer">
                      <el-progress
                        :percentage="choiceTimePct"
                        :stroke-width="4"
                        :show-text="false"
                        :color="choiceTimeLeft <= 5 ? '#ef4444' : '#3b82f6'"
                      />
                      <span class="choice-timer__text" :class="{ 'choice-timer__text--warn': choiceTimeLeft <= 5 }">{{ choiceTimeLeft }}s</span>
                    </div>
                    <div class="choice-list choice-list--panel">
                      <button
                        v-for="(opt, oi) in (currentNode.node_config?.options || [])"
                        :key="oi"
                        class="choice-item"
                        :class="{ selected: choiceSelected === Number(oi) }"
                        @click="choiceSelected = Number(oi)"
                      >
                        <span class="choice-alpha">{{ String.fromCharCode(65 + Number(oi)) }}</span>
                        {{ opt }}
                      </button>
                    </div>
                    <div class="task-actions">
                      <el-button type="primary" :disabled="choiceSelected === null" @click="submitChoice">确认完成</el-button>
                    </div>
                  </div>

                  <div v-if="trainingInterrupted" class="interrupt-panel">
                    <div class="interrupt-panel__title">{{ interruptionTitle }}</div>
                    <div class="interrupt-panel__desc">{{ interruptionMessage }}</div>
                    <div class="interrupt-panel__hint">{{ canResumeInterruptedNode ? '校验条件已恢复，可继续当前节点。' : interruptionRecoverHint }}</div>
                    <div class="interrupt-panel__actions">
                      <el-button size="small" :disabled="!canResumeInterruptedNode" type="primary" @click="resumeInterruptedNode">继续当前节点</el-button>
                      <el-button size="small" @click="skipNode('skip')">跳过当前节点</el-button>
                    </div>
                  </div>

                  <div v-if="showTimeoutOptions && !trainingInterrupted" class="timeout-bar">
                    <span class="timeout-bar__label">已超时，请选择：</span>
                    <el-button v-if="hasReferenceGuide" size="small" type="primary" plain @click="openReferenceGuide">查看标准提示</el-button>
                    <el-button size="small" @click="retryNode">重新识别</el-button>
                    <el-button size="small" type="warning" @click="skipNode('skip')">确认完成</el-button>
                  </div>

                  <div v-if="nodeFailureReasons.length" class="node-failure-reasons">{{ nodeFailureReasons.join(' / ') }}</div>

                  <div v-if="nodeSemanticFeedback" class="semantic-feedback" :class="{ 'semantic-feedback--pass': nodeSemanticFeedback.passed }">
                    <div class="semantic-feedback__head">
                      <strong>处置要点覆盖 {{ nodeSemanticFeedback.semantic_score || 0 }}%</strong>
                      <span>{{ nodeSemanticFeedback.passed ? '已达标' : '待补充' }}</span>
                    </div>
                    <div v-if="nodeSemanticFeedback.hit_points?.length" class="semantic-feedback__row">
                      <span>已覆盖</span>
                      <em>{{ nodeSemanticFeedback.hit_points.slice(0, 4).join('、') }}</em>
                    </div>
                    <div v-if="nodeSemanticFeedback.missed_points?.length" class="semantic-feedback__row">
                      <span>待补充</span>
                      <em>{{ nodeSemanticFeedback.missed_points.slice(0, 4).join('、') }}</em>
                    </div>
                  </div>

                  <transition name="result-fade">
                    <div v-if="nodeResult" class="node-result" :class="'node-result--' + nodeResult">
                      <el-icon :size="20">
                        <CircleCheck v-if="nodeResult === 'pass'" />
                        <CircleClose v-else />
                      </el-icon>
                      {{ nodeResult === 'pass' ? '通过，即将继续...' : '未通过，请重试' }}
                    </div>
                  </transition>
                </template>
                <div v-else class="task-panel__waiting">等待视频触发下一个训练节点。</div>
              </div>
            </section>
          </aside>
        </div>
      </div>

    </template>

    <!-- 璇勪及鎶ュ憡寮圭獥 -->
    <van-popup
      v-model:show="showReport"
      round
      :close-on-click-overlay="false"
      teleport="body"
      class="report-popup"
      :overlay-style="{ backgroundColor: 'rgba(0,0,0,0.75)' }"
    >
      <div v-if="report" class="report-card">
        <div class="report-header">
          <div class="report-grade" :class="report.grade === '优秀' ? 'grade--excellent' : report.grade === '合格' ? 'grade--pass' : 'grade--fail'">
            {{ report.grade }}
          </div>
          <div class="report-score">{{ report.total_score }} <span>/ {{ report.full_score }} 分</span></div>
          <div class="report-pct">得分率 {{ report.percentage }}%</div>
        </div>

        <div class="report-stats">
          <div class="rstat"><div class="rstat__num">{{ report.pass_count }}</div><div class="rstat__label">通过节点</div></div>
          <div class="rstat"><div class="rstat__num rstat__num--warn">{{ report.skip_count }}</div><div class="rstat__label">跳过节点</div></div>
          <div class="rstat"><div class="rstat__num rstat__num--danger">{{ report.total_deducted }}</div><div class="rstat__label">总扣分</div></div>
        </div>

        <div v-if="report.dimension_scores?.length" class="report-dimensions">
          <div v-for="item in report.dimension_scores" :key="item.key" class="rdim">
            <div class="rdim__head">
              <strong>{{ item.label }}</strong>
              <span>{{ item.score }}/{{ item.full_score }}</span>
            </div>
            <el-progress :percentage="item.percentage" :stroke-width="6" :show-text="false" />
            <div class="rdim__foot">{{ item.percentage }}%</div>
          </div>
        </div>

        <div v-if="report.weakness_summary?.length" class="report-advice">
          <div v-for="item in report.weakness_summary" :key="item" class="report-advice__item">
            {{ item }}
          </div>
        </div>

        <div class="report-nodes">
          <div v-for="item in report.node_summaries" :key="item.node_index" class="rnode">
            <span class="rnode__idx">{{ item.node_index + 1 }}</span>
            <span class="rnode__result" :class="'rnode__result--' + item.result">
              {{ resultLabel(item.result) }}
            </span>
            <span class="rnode__score">{{ item.score_earned }}分</span>
            <span v-if="item.score_deducted" class="rnode__deduct">-{{ item.score_deducted }}</span>
            <span v-if="item.retry_count" class="rnode__retry">重试 x{{ item.retry_count }}</span>
          </div>
        </div>

        <div class="report-actions">
          <el-button @click="showReport = false; router.back()">返回展厅</el-button>
          <el-button type="primary" v-if="report.grade === '待重修'" @click="restartTraining">重新训练</el-button>
        </div>
      </div>
    </van-popup>

    <van-popup
      v-model:show="showReferenceGuide"
      round
      teleport="body"
      class="reference-popup"
      :overlay-style="{ backgroundColor: 'rgba(0,0,0,0.6)' }"
    >
      <div v-if="currentNode" class="reference-card">
        <div class="reference-card__head">
          <div class="reference-card__title">标准提示</div>
          <div class="reference-card__subtitle">{{ currentNode.title || `节点 ${currentNodeIndex + 1}` }}</div>
        </div>
        <div class="reference-card__body">
          <div v-if="currentNode.prompt_content?.instruction" class="reference-block">
            <div class="reference-block__label">任务要求</div>
            <div class="reference-block__value">{{ currentNode.prompt_content.instruction }}</div>
          </div>
          <div v-if="currentNode.prompt_content?.scene_summary" class="reference-block">
            <div class="reference-block__label">警情摘要</div>
            <div class="reference-block__value">{{ currentNode.prompt_content.scene_summary }}</div>
          </div>
          <div v-if="currentNode.node_config?.standard_points?.length" class="reference-block">
            <div class="reference-block__label">标准处置点</div>
            <div class="reference-keywords">
              <span v-for="point in currentNode.node_config.standard_points" :key="point" class="reference-keyword">{{ point }}</span>
            </div>
          </div>
          <div v-if="effectiveShowPropPanel" class="reference-block">
            <div class="reference-block__label">道具操作</div>
            <div class="reference-block__value">{{ propPanelDescription }}</div>
          </div>
          <div v-if="currentNode.prompt_content?.gesture_hint || currentNode.required_gesture" class="reference-block">
            <div class="reference-block__label">标准动作</div>
            <div class="reference-block__value">{{ currentNode.prompt_content?.gesture_hint || gestureTargetLabel || currentNode.required_gesture }}</div>
          </div>
          <div v-if="currentNode.prompt_content?.speech_hint" class="reference-block">
            <div class="reference-block__label">标准话术</div>
            <div class="reference-block__value">{{ currentNode.prompt_content.speech_hint }}</div>
          </div>
          <div v-if="referenceKeywords.length" class="reference-block">
            <div class="reference-block__label">关键词</div>
            <div class="reference-keywords">
              <span v-for="keyword in referenceKeywords" :key="keyword" class="reference-keyword">{{ keyword }}</span>
            </div>
          </div>
        </div>
        <div class="reference-card__actions">
          <el-button @click="showReferenceGuide = false">先关闭</el-button>
          <el-button type="primary" @click="retryFromReference">查看完毕，继续重试</el-button>
        </div>
      </div>
    </van-popup>

  </div>
</template>

<script setup lang="ts">
import { ref, computed, nextTick, onMounted, onUnmounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  ArrowLeft, Timer, CircleCheck, CircleClose, Remove,
  Microphone, Check,
} from '@element-plus/icons-vue'
import request from '../utils/request'
import { usePresenceMonitor } from '../composables/usePresenceMonitor'
import { useGestureDetector } from '../composables/useGestureDetector'
import { createSpeechProvider } from '../services/speech/index'
import type { SpeechRecognitionProvider } from '../services/speech/types'

interface VideoNode {
  id: number
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
  required_gesture?: string | null
  required_keywords: string[]
  score_weight: number
}

interface VideoDetail {
  id: number
  title: string
  video_url?: string
  video_type: string
  briefing?: string
  nodes: VideoNode[]
  duration?: number
}

interface ReportItem {
  node_index: number
  result: string
  score_earned: number
  score_deducted: number
  retry_count: number
}

interface Report {
  session_id: number
  video_title: string
  mode: string
  evaluation_status?: string
  report_ready?: boolean
  message?: string
  total_score: number
  full_score: number
  percentage: number
  grade: string
  pass_count: number
  skip_count: number
  fail_count?: number
  total_nodes: number
  total_deducted: number
  dimension_scores?: {
    key: string
    label: string
    score: number
    full_score: number
    percentage: number
  }[]
  multimodal_scores?: {
    expression_score: number
    behavior_score: number
    focus_score: number
    final_ability_score: number
  }
  weakness_summary?: string[]
  node_summaries: ReportItem[]
}

const route = useRoute()
const router = useRouter()
const videoId = Number(route.params.id)
const videoCacheBustToken = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`

// 鈹€鈹€ 瑙嗛 & Session 鈹€鈹€
const video = ref<VideoDetail | null>(null)
const loading = ref(true)
const sessionId = ref<number | null>(null)
const trainingMode = ref<'practice' | 'exam'>('practice')
const showBriefing = ref(false)   // 鍓嶇疆绠€鎶ュ脊绐?
const finishingTraining = ref(false)

// 鈹€鈹€ 鑺傜偣鐘舵€?鈹€鈹€
const currentNodeIndex = ref(-1)
const nodeActive = ref(false)
const nodeStatuses = ref<Record<number, string>>({})
const nodeResult = ref<'pass' | 'fail' | null>(null)
const showTimeoutOptions = ref(false)
const showReferenceGuide = ref(false)
const countdown = ref(0)
const nodeRetryCount = ref(0)
const nodeStartTime = ref(0)
const interruptionReason = ref<'device' | 'identity' | null>(null)
const interruptionMessage = ref('')
const propReady = ref(false)
const propActivatedAt = ref<number | null>(null)
let countdownTimer: ReturnType<typeof setInterval> | null = null
let interruptionViolationKey = ''

// 鈹€鈹€ 绛旈 鈹€鈹€
const choiceSelected = ref<number | null>(null)
const choiceTimeLimit = ref(0)    // 閫夋嫨棰橀檺鏃讹紙绉掞級锛?=涓嶉檺鏃?
const choiceTimeLeft = ref(0)
const choiceTimePct = computed(() =>
  choiceTimeLimit.value > 0 ? Math.round((choiceTimeLeft.value / choiceTimeLimit.value) * 100) : 100
)
let choiceTimer: ReturnType<typeof setInterval> | null = null

// 鈹€鈹€ 璇煶璇嗗埆 鈹€鈹€
const speechProvider = ref<SpeechRecognitionProvider | null>(null)
const speechStatus = ref<'idle' | 'listening' | 'processing' | 'error'>('idle')
const interimText = ref('')
const finalText = ref('')
const manualSpeechText = ref('')
const speechErrorMessage = ref('')
const speechAutoSubmit = ref(false)
const nodeSubmitting = ref(false)
const nodeFailureReasons = ref<string[]>([])
const nodeSemanticFeedback = ref<any | null>(null)
const speechStatusLabel = computed(() => ({
  idle: '节点已自动待命，可直接开口', listening: '正在实时识别...', processing: '正在整理本轮语音', error: '识别出错，请重试',
}[speechStatus.value] || ''))

// 鈹€鈹€ 鎽勫儚澶?鈹€鈹€
const videoRef = ref<HTMLVideoElement | null>(null)
const cameraRef = ref<HTMLVideoElement | null>(null)
const briefingCameraRef = ref<HTMLVideoElement | null>(null)
const videoWrapRef = ref<HTMLElement | null>(null)
const playbackCurrentTime = ref(0)
const cameraOn = ref(false)
const camPos = ref({ x: 16, y: 80 })
const deviceReady = ref(false)
const deviceWarningText = ref('')
let cameraStream: MediaStream | null = null
let mediaRecorder: MediaRecorder | null = null
let recordingChunks: Blob[] = []
let recordingStartedAt = 0
let recordingMimeType = 'video/webm'
let recordingUploadAttempted = false
let recordingUploadUnsupported = false

const {
  status: presenceStatus,
  message: presenceMessage,
  faceCount,
  supported: presenceSupported,
  singleFaceReady,
  liveReady,
  verified: presenceVerified,
  lastMotion,
  attachVideo: attachPresenceVideo,
  stop: stopPresenceMonitor,
} = usePresenceMonitor()

const {
  status: gestureStatus,
  matched: gestureMatched,
  confidence: gestureConfidence,
  streak: gestureStreak,
  message: gestureMessage,
  targetLabel: gestureTargetLabel,
  attachVideo: attachGestureVideo,
  setTargetGesture,
  restart: restartGestureDetection,
  stop: stopGestureDetection,
} = useGestureDetector()

// 鈹€鈹€ 鎶ュ憡 鈹€鈹€
const showReport = ref(false)
const report = ref<Report | null>(null)
const evaluationProgressText = ref('正在生成训练评估报告...')

// 鈹€鈹€ 璁＄畻灞炴€?鈹€鈹€
const currentNode = computed<VideoNode | null>(() =>
  currentNodeIndex.value >= 0 && video.value?.nodes
    ? video.value.nodes[currentNodeIndex.value] ?? null
    : null
)
const playbackVideoUrl = computed(() => withCacheBust(video.value?.video_url, videoCacheBustToken))
const speechSupported = computed(() => Boolean(speechProvider.value?.isSupported()))
const identityReady = computed(() => !presenceSupported.value || presenceVerified.value)
const normalizedTranscript = computed(() => {
  const manual = String(manualSpeechText.value || '').trim()
  const spoken = String(finalText.value || '').trim()
  return spoken || manual
})
const speechHasTranscript = computed(() => Boolean(normalizedTranscript.value))
const gestureDetectionUnavailable = computed(() =>
  gestureRequired.value && ['unsupported', 'error'].includes(String(gestureStatus.value)),
)
const gestureFallbackEnabled = computed(() => gestureDetectionUnavailable.value)
const speechFallbackEnabled = computed(() =>
  Boolean(requiresSpeechTranscript.value && (!speechSupported.value || speechStatus.value === 'error')),
)
const resolvedSpeechStatusLabel = computed(() => {
  if (!speechSupported.value) return '当前环境不支持浏览器语音识别，可直接手动补录关键话术'
  if (speechStatus.value === 'error') return speechErrorMessage.value || '语音识别出错，可重试或手动补录'
  return speechStatusLabel.value
})
const gestureRuleConfig = computed(() => {
  const raw = currentNode.value?.prompt_content?.gesture_config
  return {
    min_confidence: Math.max(Math.min(Number(raw?.min_confidence ?? 0.55), 1), 0),
    hold_frames: Math.max(Number(raw?.hold_frames ?? 5), 1),
    tolerance: ['strict', 'standard', 'relaxed'].includes(String(raw?.tolerance))
      ? String(raw?.tolerance)
      : 'standard',
  }
})
const speechRuleConfig = computed(() => {
  const raw = currentNode.value?.node_config?.speech_rule
  return {
    match_mode: ['any', 'all', 'min_count'].includes(String(raw?.match_mode)) ? String(raw?.match_mode) : 'any',
    min_count: Math.max(Number(raw?.min_count ?? 1), 1),
    min_length: Math.max(Number(raw?.min_length ?? 0), 0),
  }
})
const passRuleMode = computed(() => {
  const raw = String(currentNode.value?.node_config?.pass_rule?.mode || '').trim()
  if (['all', 'either', 'gesture_only', 'speech_only'].includes(raw)) return raw
  if (currentNode.value?.required_gesture && currentNode.value?.required_keywords?.length) return 'all'
  if (currentNode.value?.required_gesture) return 'gesture_only'
  if (currentNode.value?.node_type === 'voice_qa' || currentNode.value?.required_keywords?.length) return 'speech_only'
  return 'all'
})
const identityRuleConfig = computed(() => {
  const raw = currentNode.value?.prompt_content?.identity_config
  return {
    mode: ['presence', 'reference_face'].includes(String(raw?.mode)) ? String(raw?.mode) : 'presence',
    require_single_face: raw?.require_single_face !== false,
    require_live_motion: raw?.require_live_motion !== false,
    backend_cv: Boolean(raw?.backend_cv),
  }
})
const identityStatusText = computed(() => {
  if (!presenceSupported.value) return '当前浏览器不支持本地人脸校验，已降级为设备校验'
  return presenceMessage.value || '正在进行身份校验'
})
const presenceStateClass = computed(() => {
  if (presenceStatus.value === 'error') return 'is-error'
  if (presenceStatus.value === 'warn') return 'is-warn'
  return 'is-checking'
})
const deviceStatusText = computed(() => {
  if (deviceReady.value) return '摄像头、麦克风已就绪'
  return deviceWarningText.value || '正在检查设备权限'
})
const precheckHintText = computed(() => [presenceMessage.value, deviceWarningText.value].filter(Boolean).join('；'))
const canStartTraining = computed(() => deviceReady.value && identityReady.value)
const resolvedIdentityStatusText = computed(() => {
  if (!presenceSupported.value) return '当前浏览器不支持本地人脸检测，已自动降级为设备在场校验'
  if (presenceVerified.value) return '单人入镜与活体状态已通过'
  return presenceMessage.value || '正在进行身份校验'
})
const resolvedPresenceStateClass = computed(() => {
  if (presenceStatus.value === 'ready') return 'is-pass'
  if (presenceStatus.value === 'unsupported') return 'is-warn'
  if (presenceStatus.value === 'error') return 'is-error'
  if (presenceStatus.value === 'warn') return 'is-warn'
  return 'is-checking'
})
const identityBannerClass = computed(() => {
  if (!presenceSupported.value) return 'is-warn'
  return identityReady.value ? 'is-pass' : resolvedPresenceStateClass.value
})
const identityBannerText = computed(() => {
  if (!presenceSupported.value) return '身份校验：已降级为设备校验'
  if (identityReady.value) return '人脸校验：已通过'
  return '人脸校验：校验中'
})
const identityBannerIcon = computed(() => {
  if (!presenceSupported.value) return '!'
  return identityReady.value ? '✓' : '…'
})
const resolvedFaceCountText = computed(() => {
  if (!presenceSupported.value) return '已降级'
  if (!faceCount.value) return '未检测到人脸'
  if (faceCount.value === 1) return '单人入镜'
  return `${faceCount.value} 人入镜`
})
const resolvedLiveMotionText = computed(() => {
  if (!presenceSupported.value) return '已跳过'
  if (liveReady.value) return '自然动作已达标'
  if (singleFaceReady.value) return '请轻微转头或眨眼'
  const motionLevel = Number(lastMotion.value || 0)
  return motionLevel > 0 ? `动作幅度 ${motionLevel.toFixed(3)}` : '等待活体动作'
})
const resolvedPrecheckHintText = computed(() => {
  const hints = [deviceWarningText.value]
  if (!presenceSupported.value) {
    hints.unshift('浏览器不支持本地人脸检测，训练将使用设备在场状态继续进行')
  } else if (presenceMessage.value) {
    hints.unshift(presenceMessage.value)
  }
  return hints.filter(Boolean).join('；')
})
const trainingInterrupted = computed(() => Boolean(interruptionReason.value))
const interruptionTitle = computed(() => {
  if (interruptionReason.value === 'device') return '设备异常，已暂停当前节点'
  if (interruptionReason.value === 'identity') return '身份校验异常，已暂停当前节点'
  return ''
})
const interruptionRecoverHint = computed(() => {
  if (interruptionReason.value === 'device') {
    return deviceWarningText.value || '请恢复摄像头和麦克风后继续。'
  }
  return presenceMessage.value || '请重新保持单人入镜并完成活体校验。'
})
const canResumeInterruptedNode = computed(() =>
  Boolean(trainingInterrupted.value && deviceReady.value && identityReady.value),
)
const faceCountText = computed(() => {
  if (!presenceSupported.value) return '人脸检测已降级'
  if (!faceCount.value) return '未检测到人脸'
  if (faceCount.value === 1) return '单人入镜'
  return `${faceCount.value} 人入镜`
})
const liveMotionText = computed(() => {
  if (!presenceSupported.value) return '已跳过'
  if (liveReady.value) return '自然动作已达标'
  if (singleFaceReady.value) return '请轻微转头或眨眼'
  const motionLevel = Number(lastMotion.value || 0)
  return motionLevel > 0 ? `动作幅度 ${motionLevel.toFixed(3)}` : '等待活体动作'
})
const completedCount = computed(() => Object.keys(nodeStatuses.value).length)
const displayNodeIndex = computed(() => {
  if (nodeActive.value && currentNodeIndex.value >= 0) return currentNodeIndex.value
  const nextIndex = video.value?.nodes.findIndex((_, index) => nodeStatuses.value[index] === undefined) ?? -1
  return nextIndex >= 0 ? nextIndex : Math.max(0, (video.value?.nodes.length || 1) - 1)
})
const displayNode = computed<VideoNode | null>(() => {
  const nodes = video.value?.nodes || []
  return nodes[displayNodeIndex.value] ?? null
})
const displayNodeNumber = computed(() => displayNodeIndex.value + 1)
const displayNodeTitle = computed(() => displayNode.value?.title || '等待下一节点')
const nodeProgress = computed(() => {
  const total = video.value?.nodes?.length || 0
  return total ? Math.round((completedCount.value / total) * 100) : 0
})
const playbackProgress = computed(() => {
  const duration = Number(video.value?.duration || 0)
  if (!duration) return 0
  return Math.min(100, Math.max(0, Math.round((playbackCurrentTime.value / duration) * 100)))
})
const topbarTimerText = computed(() => {
  if (nodeActive.value && countdown.value > 0) return `00:${String(countdown.value).padStart(2, '0')}`
  const duration = Number(video.value?.duration || 0)
  const remaining = Math.max(0, duration - playbackCurrentTime.value)
  return formatTime(remaining)
})
const displayInstruction = computed(() =>
  displayNode.value?.prompt_content?.police_question
  || displayNode.value?.prompt_content?.instruction
  || displayNode.value?.node_config?.question
  || '等待视频播放至触发点后开始交互。',
)
const displaySceneSummary = computed(() => String(displayNode.value?.prompt_content?.scene_summary || '').trim())
const displayStandardPoints = computed(() => {
  const points = displayNode.value?.node_config?.standard_points
  return Array.isArray(points) ? points.map((item) => String(item).trim()).filter(Boolean).slice(0, 5) : []
})
const displayRiskSignals = computed(() => {
  const points = displayNode.value?.node_config?.risk_signals
  return Array.isArray(points) ? points.map((item) => String(item).trim()).filter(Boolean).slice(0, 4) : []
})
const displayLawPoints = computed(() => {
  const points = displayNode.value?.node_config?.law_points
  return Array.isArray(points) ? points.map((item) => String(item).trim()).filter(Boolean).slice(0, 4) : []
})
const displaySpeechHint = computed(() => displayNode.value?.prompt_content?.speech_hint || '')
const displayGestureHint = computed(() =>
  displayNode.value?.prompt_content?.gesture_hint
  || gestureTargetLabel.value
  || displayNode.value?.required_gesture
  || '',
)
const activePromptText = computed(() =>
  displaySpeechHint.value
  || displayInstruction.value
  || '请根据现场情况，规范完成当前节点。',
)
const speechMeterLevel = computed(() => {
  if (speechStatus.value === 'listening') return 12
  if (finalText.value.trim()) return Math.min(12, Math.max(4, Math.ceil(finalText.value.trim().length / 4)))
  if (speechStatus.value === 'processing') return 6
  return 2
})
const gestureIndicatorText = computed(() => {
  if (!gestureRequired.value) return '本节点无需动作识别'
  if (gestureFallbackEnabled.value) return '动作识别受限，已切换为人工确认补位'
  if (gestureMatched.value) return '动作已达标'
  return gestureMessage.value || '正在识别中...'
})
const gestureIndicatorTone = computed(() => {
  if (!gestureRequired.value) return 'is-muted'
  if (gestureFallbackEnabled.value) return 'is-warn'
  if (gestureMatched.value) return 'is-pass'
  return 'is-processing'
})
const taskSummaryItems = computed(() => [
  {
    label: '动作识别',
    value: gestureRequired.value ? (gestureMatched.value ? '待完成' : '进行中') : '已跳过',
    tone: gestureRequired.value ? (gestureMatched.value ? 'pass' : 'processing') : 'muted',
  },
  {
    label: '语音识别',
    value: finalText.value.trim() ? '待完成' : (speechStatus.value === 'error' ? '异常' : '进行中'),
    tone: speechStatus.value === 'error' ? 'warn' : finalText.value.trim() ? 'pass' : 'processing',
  },
  {
    label: '流程把控',
    value: nodeActive.value ? '进行中' : (completedCount.value >= (video.value?.nodes.length || 0) ? '已完成' : '待触发'),
    tone: nodeActive.value ? 'processing' : (completedCount.value >= (video.value?.nodes.length || 0) ? 'pass' : 'muted'),
  },
])
const resolvedTaskSummaryItems = computed(() => [
  {
    label: '动作识别',
    value: !gestureRequired.value ? '已跳过' : gestureFallbackEnabled.value ? '已降级' : gestureMatched.value ? '已达标' : '进行中',
    tone: !gestureRequired.value ? 'muted' : gestureFallbackEnabled.value ? 'warn' : gestureMatched.value ? 'pass' : 'processing',
  },
  {
    label: '语音识别',
    value: speechHasTranscript.value ? '已采集' : speechFallbackEnabled.value ? '待补录' : (speechStatus.value === 'error' ? '异常' : '进行中'),
    tone: speechHasTranscript.value ? 'pass' : (speechFallbackEnabled.value || speechStatus.value === 'error') ? 'warn' : 'processing',
  },
  {
    label: '流程把控',
    value: nodeActive.value ? '进行中' : (completedCount.value >= (video.value?.nodes.length || 0) ? '已完成' : '待触发'),
    tone: nodeActive.value ? 'processing' : (completedCount.value >= (video.value?.nodes.length || 0) ? 'pass' : 'muted'),
  },
])
const requiresSpeechTranscript = computed(() =>
  Boolean(
    passRuleMode.value !== 'gesture_only' &&
    (
      currentPoliceNode.value ||
      currentNode.value?.node_type === 'voice_qa' ||
      currentNode.value?.required_keywords?.length ||
      speechRuleConfig.value.min_length > 0
    )
  ),
)
const gestureRequired = computed(() => Boolean(currentNode.value?.required_gesture))
const referenceKeywords = computed(() => currentNode.value?.required_keywords || [])
const currentPoliceNode = computed(() => isPoliceTrainingNode(currentNode.value))
const showManualAnswerInput = computed(() => Boolean(currentPoliceNode.value || speechFallbackEnabled.value))
const showPropPanel = computed(() => Boolean(
  currentNode.value &&
  (currentNode.value.node_type === 'action' || currentNode.value.node_type === 'voice_qa')
))
const effectiveShowPropPanel = computed(() => Boolean(
  currentNode.value &&
  (
    currentNode.value.prop_mode === 'manual'
    || currentNode.value.required_gesture === 'show_id'
    || String(currentNode.value.prompt_content?.prop_label || '').trim()
  )
))
const propActionLabel = computed(() => {
  const raw = currentNode.value?.prompt_content?.prop_label
  if (raw) return String(raw)
  if (currentNode.value?.required_gesture === 'show_id') return '虚拟证件'
  return '训练道具'
})
const propPanelLabel = computed(() =>
  currentNode.value?.prop_mode === 'manual' ? '手动道具操作' : '自动道具辅助',
)
const propPanelDescription = computed(() => {
  if (!currentNode.value) return ''
  const customHint = String(currentNode.value?.prompt_content?.prop_hint || '').trim()
  if (customHint) return customHint
  if (currentNode.value.prop_mode === 'manual') {
    return `考核模式下，请先手动取出${propActionLabel.value}，再完成动作与话术。`
  }
  return `练习模式下，系统会自动提供${propActionLabel.value}参考。`
})
const propVisualTone = computed(() => {
  const label = propActionLabel.value
  if (label.includes('证') || currentNode.value?.required_gesture === 'show_id') return 'id'
  if (label.includes('对讲') || label.includes('记录仪')) return 'device'
  if (label.includes('警') || label.includes('装备')) return 'gear'
  return 'default'
})
const propVisualBadge = computed(() => {
  const tone = propVisualTone.value
  if (tone === 'id') return '证件'
  if (tone === 'device') return '设备'
  if (tone === 'gear') return '装备'
  return '道具'
})
const hasReferenceGuide = computed(() => Boolean(
  currentNode.value?.prompt_content?.instruction ||
  currentNode.value?.prompt_content?.scene_summary ||
  currentNode.value?.prompt_content?.police_question ||
  currentNode.value?.prompt_content?.gesture_hint ||
  currentNode.value?.prompt_content?.speech_hint ||
  currentNode.value?.node_config?.standard_points?.length ||
  effectiveShowPropPanel.value ||
  currentNode.value?.required_gesture ||
  referenceKeywords.value.length,
))

function isPoliceTrainingNode(node?: VideoNode | null) {
  return Boolean(node?.node_config?.police_node_type || node?.prompt_content?.police_question)
}

// 鈹€鈹€ 鐢熷懡鍛ㄦ湡 鈹€鈹€
onMounted(async () => {
  await fetchVideo()
  if (video.value) {
    await startCamera()
    // 鏄剧ず绠€鎶ュ脊绐楋紝绛夌敤鎴风‘璁ゅ悗鍐嶅垵濮嬪寲 Session
    showBriefing.value = true
    setupVisibilityDetection()
  }
})

watch(
  [nodeActive, showBriefing, deviceReady, identityReady, presenceMessage, deviceWarningText],
  ([active, briefing, deviceOk, identityOk, presenceText, deviceText]) => {
    if (!active || briefing || nodeSubmitting.value) return
    if (!deviceOk) {
      pauseNodeForInterruption('device', String(deviceText || '训练过程中检测到摄像头或麦克风异常'))
      return
    }
    if (!identityOk) {
      pauseNodeForInterruption('identity', String(presenceText || '训练过程中身份校验未通过'))
    }
  },
)

async function confirmBriefing() {
  if (!canStartTraining.value) {
    ElMessage.warning(resolvedPrecheckHintText.value || '请先完成入场校验')
    return
  }
  showBriefing.value = false
  await nextTick()
  if (cameraStream && cameraRef.value) {
    await bindCameraStream(cameraRef.value)
    await attachPresenceVideo(cameraRef.value)
    await attachGestureVideo(cameraRef.value)
  }
  await initSession()
  await startTrainingRecording()
  await playTrainingVideo()
}

onUnmounted(() => {
  void stopTrainingRecording(false)
  stopCamera()
  stopPresenceMonitor()
  stopGestureDetection()
  clearCountdown()
  clearChoiceTimer()
  speechProvider.value?.stop()
  document.removeEventListener('visibilitychange', onVisibilityChange)
})

// 鈹€鈹€ 鏁版嵁鍔犺浇 鈹€鈹€
async function fetchVideo() {
  loading.value = true
  try {
    const res: any = await request.get(`/videos/${videoId}`)
    video.value = res
  } catch (error: any) {
    ElMessage.error('加载视频失败')
    video.value = null
  } finally {
    loading.value = false
  }
}

async function initSession() {
  try {
    const res: any = await request.post(`/video-training/start/${videoId}`, null, {
      params: { mode: trainingMode.value },
    } as any)
    sessionId.value = res.id
    trainingMode.value = res.mode || 'practice'
    // 鎭㈠宸叉湁鑺傜偣鐘舵€?
    if (res.node_results?.length) {
      for (const r of res.node_results) {
        nodeStatuses.value[r.node_index] = r.result
      }
    }
    if (res.resumed) ElMessage.info('已恢复上次未完成的实训')
  } catch {
    ElMessage.warning('无法创建训练记录，进度不会保存')
  }
}

// 鈹€鈹€ 鎽勫儚澶?鈹€鈹€
async function startCamera() {
  try {
    cameraStream = await navigator.mediaDevices.getUserMedia({
      video: {
        width: { ideal: 960 },
        height: { ideal: 540 },
        facingMode: 'user',
      },
      audio: {
        channelCount: 1,
        echoCancellation: true,
        noiseSuppression: true,
      },
    })
    cameraOn.value = true
    speechProvider.value = createSpeechProvider()
    deviceReady.value = Boolean(cameraStream.getVideoTracks().length && cameraStream.getAudioTracks().length)
    deviceWarningText.value = deviceReady.value ? '' : '请同时开启摄像头和麦克风'
    await nextTick()
    if (briefingCameraRef.value) {
      await bindCameraStream(briefingCameraRef.value)
      await attachPresenceVideo(briefingCameraRef.value)
    }
    if (cameraRef.value) {
      await bindCameraStream(cameraRef.value)
      if (!showBriefing.value) {
        await attachPresenceVideo(cameraRef.value)
        await attachGestureVideo(cameraRef.value)
      }
    }
    cameraStream.getTracks().forEach((track) => {
      track.addEventListener('ended', () => {
        deviceReady.value = false
        deviceWarningText.value = '训练过程中检测到摄像头或麦克风中断'
        pauseNodeForInterruption('device', '训练过程中检测到摄像头或麦克风中断')
      })
    })
  } catch {
    deviceReady.value = false
    deviceWarningText.value = '摄像头或麦克风权限未开启，请检查浏览器授权'
    ElMessage.warning('无法获取摄像头和麦克风，AI识别不可用')
    cameraOn.value = false
    speechProvider.value = createSpeechProvider()
  }
}

function stopCamera() {
  if (briefingCameraRef.value?.srcObject) {
    briefingCameraRef.value.srcObject = null
  }
  if (cameraRef.value?.srcObject) {
    const s = cameraRef.value.srcObject as MediaStream
    s.getTracks().forEach(t => t.stop())
    cameraRef.value.srcObject = null
  }
  cameraStream = null
  cameraOn.value = false
}

// 鈹€鈹€ 杩濊妫€娴?鈹€鈹€
function setupVisibilityDetection() {
  document.addEventListener('visibilitychange', onVisibilityChange)
}

async function onVisibilityChange() {
  if (document.hidden && sessionId.value && nodeActive.value) {
    try {
      await request.post(`/video-training/session/${sessionId.value}/violation`, {
        type: 'tab_switch',
          detail: '训练期间切换标签页',
      })
    } catch {}
    ElMessage.warning('检测到切换标签页，已记录违规')
  }
}

// 鈹€鈹€ 瑙嗛鏃堕棿鐩戝惉 鈹€鈹€
// 鈹€鈹€ 绂佹杩涘害鏉℃嫋鎷?鈹€鈹€
// 璁板綍鏈€鍚庝竴娆″悎娉曟椂闂寸偣锛堣妭鐐硅Е鍙戝墠锛?
let lastAllowedTime = 0

function onTimeUpdate() {
  if (!videoRef.value) return
  playbackCurrentTime.value = Math.floor(videoRef.value.currentTime)
  if (!video.value?.nodes || nodeActive.value) return
  // 鏇存柊鍚堟硶鏃堕棿鐐?
  lastAllowedTime = videoRef.value.currentTime
  const t = Math.floor(videoRef.value.currentTime)
  for (let i = 0; i < video.value.nodes.length; i++) {
    if (nodeStatuses.value[i] !== undefined) continue
    if (t >= video.value.nodes[i].trigger_time) {
      triggerNode(i)
      break
    }
  }
}

function onSeeking() {
  if (!videoRef.value) return
  const current = videoRef.value.currentTime
  // 鍙厑璁稿悜鍓?seek 涓嶈秴杩?1 绉掔殑璇樊锛堟祻瑙堝櫒鑷韩鐨勭紦鍐茶涓猴級锛?
  // 鎴?seek 鍒版瘮宸叉挱鏀句綅缃洿鏃╋紙涓嶅厑璁歌烦杩囨湭瀹屾垚鑺傜偣锛?
  if (current > lastAllowedTime + 1.5) {
    // 寮哄埗鍥為€€鍒版渶鍚庡悎娉曚綅缃?
    videoRef.value.currentTime = lastAllowedTime
    ElMessage.warning('训练进行中禁止拖动进度条')
  }
}

function onVideoEnded() {
  playbackCurrentTime.value = Number(video.value?.duration || playbackCurrentTime.value)
  if (video.value && completedCount.value < video.value.nodes.length) {
    // 瑙嗛缁撴潫浣嗚繕鏈夋湭瑙﹀彂鑺傜偣锛屾爣璁颁负璺宠繃
    for (let i = 0; i < video.value.nodes.length; i++) {
      if (nodeStatuses.value[i] === undefined) {
        nodeStatuses.value[i] = 'skip'
      }
    }
  }
  finishTraining()
}

async function bindCameraStream(videoEl: HTMLVideoElement) {
  if (!cameraStream) return
  videoEl.srcObject = cameraStream
  videoEl.autoplay = true
  videoEl.muted = true
  videoEl.playsInline = true
  try {
    await videoEl.play()
  } catch {
    await new Promise<void>((resolve) => {
      const onReady = () => {
        videoEl.removeEventListener('loadedmetadata', onReady)
        resolve()
      }
      videoEl.addEventListener('loadedmetadata', onReady, { once: true })
      window.setTimeout(() => resolve(), 300)
    })
    try {
      await videoEl.play()
    } catch (error) {
      console.warn('Camera preview play failed', error)
    }
  }
}

function getSupportedRecordingMimeType(): string {
  if (typeof MediaRecorder === 'undefined') return ''
  const candidates = [
    'video/webm;codecs=vp9,opus',
    'video/webm;codecs=vp8,opus',
    'video/webm',
    'video/mp4',
  ]
  return candidates.find((item) => MediaRecorder.isTypeSupported(item)) || ''
}

async function startTrainingRecording() {
  if (!sessionId.value || !cameraStream || typeof MediaRecorder === 'undefined') return
  if (mediaRecorder && mediaRecorder.state !== 'inactive') return

  try {
    const supportedMimeType = getSupportedRecordingMimeType()
    mediaRecorder = supportedMimeType
      ? new MediaRecorder(cameraStream, { mimeType: supportedMimeType })
      : new MediaRecorder(cameraStream)
    recordingMimeType = mediaRecorder.mimeType || supportedMimeType || 'video/webm'
    recordingChunks = []
    recordingStartedAt = Date.now()
    recordingUploadAttempted = false
    mediaRecorder.ondataavailable = (event: BlobEvent) => {
      if (event.data && event.data.size > 0) {
        recordingChunks.push(event.data)
      }
    }
    mediaRecorder.onerror = () => {
      ElMessage.warning('训练录制中断，系统将继续保留当前训练进度')
    }
    mediaRecorder.start(1000)
  } catch (error) {
    console.warn('MediaRecorder init failed', error)
  }
}

async function uploadTrainingRecording() {
  if (!sessionId.value || !recordingChunks.length || recordingUploadAttempted || recordingUploadUnsupported) return

  const blob = new Blob(recordingChunks, { type: recordingMimeType || 'video/webm' })
  if (!blob.size) return

  const formData = new FormData()
  const extension = blob.type.includes('mp4') ? 'mp4' : 'webm'
  const durationSeconds = recordingStartedAt ? Math.max(1, Math.round((Date.now() - recordingStartedAt) / 1000)) : undefined
  formData.append('artifact_file', blob, `session-recording.${extension}`)
  formData.append('artifact_type', 'camera_recording')
  if (durationSeconds) {
    formData.append('duration_seconds', String(durationSeconds))
  }

  try {
    await request.post(
      `/video-training/session/${sessionId.value}/artifacts/upload`,
      formData,
      {
        headers: { 'Content-Type': 'multipart/form-data' },
        _skipErrorToast: true,
      } as any,
    )
    recordingUploadAttempted = true
    recordingChunks = []
  } catch (error) {
    const status = (error as any)?.response?.status
    if (status === 404 || status === 405) {
      recordingUploadUnsupported = true
      recordingUploadAttempted = true
      recordingChunks = []
      console.info('Training recording upload is not supported by current backend service')
      return
    }
    console.warn('Training recording upload failed', error)
  }
}

async function stopTrainingRecording(uploadAfterStop = true) {
  if (!mediaRecorder) {
    if (uploadAfterStop) {
      await uploadTrainingRecording()
    }
    return
  }

  const recorder = mediaRecorder
  if (recorder.state === 'inactive') {
    mediaRecorder = null
    if (uploadAfterStop) {
      await uploadTrainingRecording()
    }
    return
  }

  await new Promise<void>((resolve) => {
    recorder.addEventListener(
      'stop',
      () => {
        mediaRecorder = null
        resolve()
      },
      { once: true },
    )
    recorder.stop()
  })

  if (uploadAfterStop) {
    await uploadTrainingRecording()
  }
}

async function playTrainingVideo() {
  if (!videoRef.value) return
  try {
    await videoRef.value.play()
  } catch (error) {
    console.warn('Training video play failed', error)
    ElMessage.warning('视频未自动开始播放，请检查浏览器自动播放权限')
  }
}

async function recordRuntimeViolation(type: 'device_lost' | 'identity_lost', detail: string) {
  if (!sessionId.value || !nodeActive.value) return
  const key = `${type}:${detail}`
  if (interruptionViolationKey === key) return
  interruptionViolationKey = key
  try {
    await request.post(`/video-training/session/${sessionId.value}/violation`, { type, detail })
  } catch {
    // 忽略记录失败，不阻断训练流程。
  }
}

function pauseNodeForInterruption(reason: 'device' | 'identity', detail: string) {
  if (!nodeActive.value || nodeSubmitting.value) return
  if (interruptionReason.value === reason && interruptionMessage.value === detail) return

  interruptionReason.value = reason
  interruptionMessage.value = detail
  showTimeoutOptions.value = false
  clearCountdown()
  clearChoiceTimer()
  stopSpeech()
  stopGestureDetection()
  videoRef.value?.pause()

  void recordRuntimeViolation(
    reason === 'device' ? 'device_lost' : 'identity_lost',
    detail,
  )
}

function resumeInterruptedNode() {
  if (!canResumeInterruptedNode.value || !currentNode.value) return
  interruptionReason.value = null
  interruptionMessage.value = ''
  interruptionViolationKey = ''
  startCountdown()
  if (currentNode.value.node_type === 'choice' && choiceTimeLimit.value > 0 && choiceTimeLeft.value > 0) {
    startChoiceTimer()
  }
  void restartGestureDetection()
  if (currentNode.value.node_type === 'action' || currentNode.value.node_type === 'voice_qa') {
    void startSpeech(!isPoliceTrainingNode(currentNode.value))
  }
}

// 鈹€鈹€ 鑺傜偣瑙﹀彂 鈹€鈹€
function triggerNode(index: number) {
  currentNodeIndex.value = index
  nodeActive.value = true
  nodeResult.value = null
  nodeFailureReasons.value = []
  nodeSemanticFeedback.value = null
  nodeSubmitting.value = false
  interruptionReason.value = null
  interruptionMessage.value = ''
  interruptionViolationKey = ''
  propReady.value = false
  propActivatedAt.value = null
  showTimeoutOptions.value = false
  choiceSelected.value = null
  interimText.value = ''
  finalText.value = ''
  manualSpeechText.value = ''
  nodeRetryCount.value = 0
  nodeStartTime.value = Date.now()

  videoRef.value?.pause()

  const node = video.value!.nodes[index]
  void setTargetGesture(node.required_gesture || null, node.prompt_content?.gesture_config || null)
  if (node.prop_mode !== 'manual') {
    propReady.value = true
  }
  countdown.value = node.timeout_seconds
  startCountdown()

  // 濡傛灉鏄€夋嫨棰樹笖閰嶇疆浜嗛鐩檺鏃讹紝鍚姩鐙珛鍊掕鏃?
  clearChoiceTimer()
  if (node.node_type === 'choice') {
    const tl = Number(node.node_config?.time_limit ?? 0)
    choiceTimeLimit.value = tl
    choiceTimeLeft.value = tl
    if (tl > 0) {
      startChoiceTimer()
    }
  } else {
    choiceTimeLimit.value = 0
    choiceTimeLeft.value = 0
  }

  if (node.node_type === 'action' || node.node_type === 'voice_qa') {
    window.setTimeout(() => {
      void startSpeech(!isPoliceTrainingNode(node))
    }, 260)
  }
}

function startCountdown() {
  clearCountdown()
  countdownTimer = setInterval(() => {
    countdown.value--
    if (countdown.value <= 0) {
      clearCountdown()
      speechProvider.value?.stop()
      showTimeoutOptions.value = true
    }
  }, 1000)
}

function clearCountdown() {
  if (countdownTimer) { clearInterval(countdownTimer); countdownTimer = null }
}

function startChoiceTimer() {
  clearChoiceTimer()
  if (choiceTimeLimit.value <= 0 || choiceTimeLeft.value <= 0) return
  choiceTimer = setInterval(() => {
    choiceTimeLeft.value--
    if (choiceTimeLeft.value <= 0) {
      clearChoiceTimer()
      nodeResult.value = 'fail'
      nodeRetryCount.value++
      ElMessage.warning('答题超时，请重新选择')
    }
  }, 1000)
}

function clearChoiceTimer() {
  if (choiceTimer) { clearInterval(choiceTimer); choiceTimer = null }
}

// 鈹€鈹€ 璇煶璇嗗埆 鈹€鈹€
async function startSpeech(autoSubmit = false) {
  if (!speechProvider.value || !speechSupported.value) return
  interimText.value = ''
  finalText.value = ''
  if (!currentPoliceNode.value) {
    manualSpeechText.value = ''
  }
  speechErrorMessage.value = ''
  speechAutoSubmit.value = autoSubmit
  speechStatus.value = 'processing'
  speechProvider.value.start({ lang: 'zh-CN', continuous: false, mediaStream: cameraStream ?? undefined }, {
    onInterim: (t) => { interimText.value = t },
    onFinal: (t) => { finalText.value = (finalText.value + ' ' + t).trim() },
    onAutoEnd: () => {
      speechStatus.value = 'idle'
      if (speechAutoSubmit.value && finalText.value.trim()) {
        submitActionNode()
      }
    },
    onUtteranceEnd: (t) => {
      finalText.value = (finalText.value || t).trim()
      if (speechAutoSubmit.value && finalText.value.trim()) {
        submitActionNode()
      }
    },
    onError: (message) => {
      speechStatus.value = 'error'
      speechErrorMessage.value = String(message || '语音识别失败')
    },
    onStatusChange: (s) => { speechStatus.value = s },
  })
}

function stopSpeech() {
  speechProvider.value?.stop()
  speechStatus.value = 'idle'
}

function restartSpeechCapture() {
  speechErrorMessage.value = ''
  void startSpeech(false)
}

// 鈹€鈹€ 鑺傜偣鎻愪氦 鈹€鈹€
async function submitNodeToBackend(
  action: 'pass' | 'skip' | 'timeout',
  extra: Record<string, any> = {},
) {
  if (!sessionId.value || !currentNode.value) return
  const timeUsed = Math.round((Date.now() - nodeStartTime.value) / 1000)
  try {
    return await request.post(`/video-training/session/${sessionId.value}/node/submit`, {
      node_id: currentNode.value.id,
      node_index: currentNodeIndex.value,
      action,
      retry_count: nodeRetryCount.value,
      time_used: timeUsed,
      ...extra,
    })
  } catch {
    return null
  }
}

async function passNode(extra: Record<string, any> = {}) {
  if (nodeSubmitting.value) return
  nodeSubmitting.value = true
  clearCountdown()
  clearChoiceTimer()
  stopSpeech()
  const response: any = await submitNodeToBackend('pass', extra)
  const result = response?.result || 'pass'
  const failureReasons = Array.isArray(response?.feedback?.reasons) ? response.feedback.reasons : []
  const failureReasonTexts = failureReasons.map(failureReasonLabel)
  nodeFailureReasons.value = failureReasonTexts
  nodeSemanticFeedback.value = response?.feedback?.police_semantic || null
  nodeResult.value = result === 'pass' ? 'pass' : 'fail'

  if (result === 'pass') {
    nodeStatuses.value[currentNodeIndex.value] = 'pass'
    window.setTimeout(() => {
      stopGestureDetection()
      nodeActive.value = false
      nodeResult.value = null
      nodeFailureReasons.value = []
      nodeSemanticFeedback.value = null
      nodeSubmitting.value = false
      void playTrainingVideo()
      checkAllNodesDone()
    }, 1200)
    return
  }

  if (failureReasonTexts.length) {
    ElMessage.warning(`未通过：${failureReasonTexts.join('、')}`)
  } else {
    ElMessage.warning('当前节点未通过，请调整动作或话术后重试')
  }
  nodeRetryCount.value++
  window.setTimeout(() => {
    nodeResult.value = null
    nodeSubmitting.value = false
    countdown.value = currentNode.value?.timeout_seconds || 60
    startCountdown()
    void restartGestureDetection()
    if (currentNode.value?.node_type === 'action' || currentNode.value?.node_type === 'voice_qa') {
      void startSpeech(!isPoliceTrainingNode(currentNode.value))
    }
  }, 1200)
}

async function skipNode(type: 'skip' | 'timeout' = 'skip') {
  if (nodeSubmitting.value) return
  nodeSubmitting.value = true
  clearCountdown()
  clearChoiceTimer()
  stopSpeech()
  stopGestureDetection()
  nodeStatuses.value[currentNodeIndex.value] = type
  await submitNodeToBackend(type)
  ElMessage.warning(`已${type === 'timeout' ? '超时跳过' : '跳过'}，扣 ${currentNode.value?.skip_score_deduct ?? 20} 分`)
  nodeActive.value = false
  nodeResult.value = null
  nodeFailureReasons.value = []
  nodeSemanticFeedback.value = null
  nodeSubmitting.value = false
  interruptionReason.value = null
  interruptionMessage.value = ''
  void playTrainingVideo()
  checkAllNodesDone()
}

function retryNode() {
  showReferenceGuide.value = false
  showTimeoutOptions.value = false
  interruptionReason.value = null
  interruptionMessage.value = ''
  interruptionViolationKey = ''
  nodeResult.value = null
  nodeFailureReasons.value = []
  nodeSemanticFeedback.value = null
  propReady.value = currentNode.value?.prop_mode !== 'manual'
  propActivatedAt.value = propReady.value ? Date.now() : null
  nodeRetryCount.value++
  countdown.value = currentNode.value?.timeout_seconds || 60
  startCountdown()
  void restartGestureDetection()
  void startSpeech(!isPoliceTrainingNode(currentNode.value))
  ElMessage.warning(`重新练习，本次重试扣 ${currentNode.value?.retry_score_deduct ?? 5} 分`)
}

function openReferenceGuide() {
  showReferenceGuide.value = true
}

function retryFromReference() {
  showReferenceGuide.value = false
  retryNode()
}

function activateVirtualProp() {
  propReady.value = true
  propActivatedAt.value = Date.now()
  ElMessage.success(`${propActionLabel.value}已取出，请继续完成动作与话术`)
}

function failureReasonLabel(reason: string) {
  return ({
    gesture_mismatch: '动作未达标',
    keyword_mismatch: '话术未匹配',
    identity_mismatch: '身份校验未通过',
    judge_incorrect: '判断题错误',
    choice_incorrect: '选择题错误',
    prop_missed: '未先完成道具操作',
    police_answer_empty: '警情回答为空',
    police_points_missing: '处置要点覆盖不足',
  } as Record<string, string>)[reason] || reason
}

function submitActionNode() {
  if (requiresSpeechTranscript.value && !normalizedTranscript.value.trim()) {
    ElMessage.warning(
      speechFallbackEnabled.value
        ? '请先手动补录关键话术'
        : currentPoliceNode.value
          ? '请先填写或说出你的现场处置回答'
          : '尚未识别到有效语音，请直接开口或重新识别',
    )
    return
  }
  stopSpeech()
  const transcript = normalizedTranscript.value.trim()
  const keywordHits = referenceKeywords.value.filter(keyword =>
    transcript.toLowerCase().includes(String(keyword).toLowerCase()),
  )
  void passNode({
    speech_transcript: transcript,
    answer_data: gestureRequired.value ? {
      answer_text: transcript,
      gesture_result: {
        required_gesture: currentNode.value?.required_gesture,
        matched: gestureFallbackEnabled.value ? true : gestureMatched.value,
        confidence: gestureFallbackEnabled.value
          ? Number(gestureRuleConfig.value.min_confidence || 0.55)
          : Number(gestureConfidence.value || 0),
        streak: gestureFallbackEnabled.value
          ? Number(gestureRuleConfig.value.hold_frames || 5)
          : Number(gestureStreak.value || 0),
        status: gestureFallbackEnabled.value ? 'manual_fallback' : gestureStatus.value,
        message: gestureFallbackEnabled.value
          ? `动作识别受限，已按“${displayGestureHint.value || gestureTargetLabel.value || '标准动作'}”执行人工确认补位`
          : gestureMessage.value,
        rule_config: gestureRuleConfig.value,
        fallback_reason: gestureFallbackEnabled.value ? gestureMessage.value : undefined,
      },
      identity_result: {
        mode: identityRuleConfig.value.mode,
        backend_cv: identityRuleConfig.value.backend_cv,
        verified: identityReady.value,
        single_face: singleFaceReady.value,
        live_ready: liveReady.value,
        matched: identityRuleConfig.value.mode === 'reference_face' ? false : identityReady.value,
      },
      focus_result: {
        focus_score: singleFaceReady.value ? (liveReady.value ? 92 : 76) : 54,
        camera_ready: cameraOn.value,
        visibility_state: document.hidden ? 'hidden' : 'visible',
      },
      face_result: {
        expression_score: singleFaceReady.value ? (liveReady.value ? 88 : 72) : 46,
        dominant_emotion: liveReady.value ? 'focused' : 'neutral',
        confidence: liveReady.value ? 0.82 : 0.58,
      },
      speech_analysis: {
        transcript_length: transcript.length,
        transcript_source: finalText.value.trim() ? 'browser_speech' : manualSpeechText.value.trim() ? 'manual_fallback' : 'none',
        status: speechStatus.value,
        error_message: speechErrorMessage.value || undefined,
        match_mode: speechRuleConfig.value.match_mode,
        min_count: speechRuleConfig.value.min_count,
        min_length: speechRuleConfig.value.min_length,
        keyword_hits: keywordHits,
        pass_rule_mode: passRuleMode.value,
      },
      prop_interaction: {
        mode: currentNode.value?.prop_mode,
        ready: propReady.value,
        activated_at: propActivatedAt.value,
        label: propActionLabel.value,
      },
      model_status: {
        gesture: gestureFallbackEnabled.value ? 'manual_fallback' : gestureStatus.value,
        speech: !speechSupported.value ? 'unsupported' : speechStatus.value,
        presence: presenceSupported.value ? presenceStatus.value : 'unsupported',
      },
      tool_evidence: {
        gesture_source: gestureFallbackEnabled.value ? 'manual_confirm' : 'mediapipe',
        speech_source: finalText.value.trim() ? 'browser_speech' : manualSpeechText.value.trim() ? 'manual_input' : 'none',
        presence_source: presenceSupported.value ? 'mediapipe_presence' : 'device_check',
      },
    } : {
      answer_text: transcript,
      identity_result: {
        mode: identityRuleConfig.value.mode,
        backend_cv: identityRuleConfig.value.backend_cv,
        verified: identityReady.value,
        single_face: singleFaceReady.value,
        live_ready: liveReady.value,
        matched: identityRuleConfig.value.mode === 'reference_face' ? false : identityReady.value,
      },
      focus_result: {
        focus_score: singleFaceReady.value ? (liveReady.value ? 92 : 76) : 54,
        camera_ready: cameraOn.value,
        visibility_state: document.hidden ? 'hidden' : 'visible',
      },
      face_result: {
        expression_score: singleFaceReady.value ? (liveReady.value ? 88 : 72) : 46,
        dominant_emotion: liveReady.value ? 'focused' : 'neutral',
        confidence: liveReady.value ? 0.82 : 0.58,
      },
      speech_analysis: {
        transcript_length: transcript.length,
        transcript_source: finalText.value.trim() ? 'browser_speech' : manualSpeechText.value.trim() ? 'manual_fallback' : 'none',
        status: speechStatus.value,
        error_message: speechErrorMessage.value || undefined,
        match_mode: speechRuleConfig.value.match_mode,
        min_count: speechRuleConfig.value.min_count,
        min_length: speechRuleConfig.value.min_length,
        keyword_hits: keywordHits,
        pass_rule_mode: passRuleMode.value,
      },
      prop_interaction: {
        mode: currentNode.value?.prop_mode,
        ready: propReady.value,
        activated_at: propActivatedAt.value,
        label: propActionLabel.value,
      },
      model_status: {
        gesture: 'not_required',
        speech: !speechSupported.value ? 'unsupported' : speechStatus.value,
        presence: presenceSupported.value ? presenceStatus.value : 'unsupported',
      },
      tool_evidence: {
        gesture_source: 'not_required',
        speech_source: finalText.value.trim() ? 'browser_speech' : manualSpeechText.value.trim() ? 'manual_input' : 'none',
        presence_source: presenceSupported.value ? 'mediapipe_presence' : 'device_check',
      },
    },
    prop_missed: currentNode.value?.prop_mode === 'manual' && !propReady.value,
  })
}

function submitJudge(answer: boolean) {
  const correct = currentNode.value?.node_config?.correct_answer
  if (answer === correct) {
    void passNode({ answer_data: { answer } })
  } else {
    nodeResult.value = 'fail'
    const exp = currentNode.value?.node_config?.explanation
    if (exp) ElMessage.info(exp)
    nodeRetryCount.value++
  }
}

function submitChoice() {
  if (choiceSelected.value === null) return
  const correct = currentNode.value?.node_config?.correct_index
  if (choiceSelected.value === correct) {
    void passNode({ answer_data: { selected: choiceSelected.value } })
  } else {
    nodeResult.value = 'fail'
    const exp = currentNode.value?.node_config?.explanation
    if (exp) ElMessage.info(exp)
    nodeRetryCount.value++
  }
}

function checkAllNodesDone() {
  const total = video.value?.nodes?.length || 0
  if (completedCount.value >= total) finishTraining()
}

function isVideoReportReady(payload: any): payload is Report {
  return Boolean(payload?.report_ready || (payload?.evaluation_status === 'completed' && payload?.node_summaries))
}

async function waitForVideoReportReady(nextSessionId: number) {
  for (let attempt = 0; attempt < 12; attempt += 1) {
    await new Promise(resolve => window.setTimeout(resolve, attempt < 3 ? 1200 : 2000))
    const res: any = await request.get(`/video-training/session/${nextSessionId}/report`, { _skipErrorToast: true } as any)
    if (isVideoReportReady(res)) return res
    if (res?.evaluation_status === 'failed') {
      throw new Error(res?.message || '评估报告生成失败')
    }
    evaluationProgressText.value = res?.message || '正在整理多模态证据并生成评估报告...'
  }
  throw new Error('评估报告生成超时，请稍后到实训记录查看')
}

// 鈹€鈹€ 瀹屾垚璁粌 鈹€鈹€
async function finishTraining() {
  if (!sessionId.value || finishingTraining.value) return
  finishingTraining.value = true
  stopGestureDetection()
  try {
    await stopTrainingRecording(true)
    const res: any = await request.post(`/video-training/session/${sessionId.value}/finish`)
    if (!isVideoReportReady(res)) {
      await waitForVideoReportReady(sessionId.value)
    }
    router.replace(`/student/video-report/${sessionId.value}`)
  } catch {
    ElMessage.error('生成报告失败，请稍后查看历史记录')
    router.back()
  } finally {
    evaluationProgressText.value = '正在生成训练评估报告...'
    finishingTraining.value = false
  }
}

function restartTraining() {
  showReport.value = false
  router.replace(`/student/video-training/${videoId}`)
}

// 鈹€鈹€ 閫€鍑虹‘璁?鈹€鈹€
async function confirmExit() {
  if (!sessionId.value && !nodeActive.value && completedCount.value === 0) { router.back(); return }
  try {
    await ElMessageBox.confirm('退出后本次训练进度将保留，下次可继续。确认退出？', '退出实训', {
      confirmButtonText: '确认退出', cancelButtonText: '继续训练', type: 'warning',
    })
    await stopTrainingRecording(true)
    router.back()
  } catch {}
}

// 鈹€鈹€ 鎽勫儚澶存嫋鎷?鈹€鈹€
function startDrag(e: MouseEvent) {
  const sx = e.clientX - camPos.value.x
  const sy = e.clientY - camPos.value.y
  const mv = (ev: MouseEvent) => { camPos.value = { x: ev.clientX - sx, y: ev.clientY - sy } }
  const up = () => { window.removeEventListener('mousemove', mv); window.removeEventListener('mouseup', up) }
  window.addEventListener('mousemove', mv)
  window.addEventListener('mouseup', up)
}

// 鈹€鈹€ 宸ュ叿鍑芥暟 鈹€鈹€
function formatTime(sec: number) {
  return `${String(Math.floor(sec / 60)).padStart(2, '0')}:${String(sec % 60).padStart(2, '0')}`
}

function resultLabel(r: string) {
  return ({ pass: '通过', skip: '跳过', timeout: '超时', fail: '未完成' } as any)[r] || r
}

function withCacheBust(url?: string, token = videoCacheBustToken) {
  if (!url) return ''
  const separator = url.includes('?') ? '&' : '?'
  return `${url}${separator}codex_no_cache=${encodeURIComponent(token)}`
}
</script>

<style scoped lang="scss">
/* 鈹€鈹€ 鏁翠綋甯冨眬 鈹€鈹€ */
.video-training-page {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: #0a0f1a;
  color: #fff;
  overflow: hidden;
  user-select: none;
}

.state-center {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px;
}

.training-shell {
  display: flex;
  flex: 1;
  min-height: 0;
  flex-direction: column;
  gap: 12px;
  padding: 10px;
  background:
    radial-gradient(circle at top left, rgba(29, 78, 216, 0.18), transparent 28%),
    radial-gradient(circle at top right, rgba(14, 165, 233, 0.1), transparent 24%),
    linear-gradient(180deg, #050b17 0%, #081120 100%);
}

.glass-panel {
  background: linear-gradient(180deg, rgba(8, 20, 41, 0.94), rgba(5, 14, 30, 0.96));
  border: 1px solid rgba(77, 120, 191, 0.24);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.04), 0 20px 40px rgba(0, 0, 0, 0.24);
  border-radius: 12px;
}

.panel-title-row,
.panel-title {
  color: #dbeafe;
}

.panel-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 10px;
  font-size: 12px;
  font-weight: 700;
}

.panel-title {
  font-size: 14px;
  font-weight: 700;
}

.panel-title.muted {
  margin-top: 12px;
  margin-bottom: 10px;
  font-size: 12px;
  color: #94a3b8;
}

.training-topbar {
  display: grid;
  grid-template-columns: minmax(240px, 1.4fr) minmax(220px, 1fr) auto;
  align-items: center;
  gap: 18px;
  padding: 10px 16px;
  border-radius: 14px;
  background: linear-gradient(180deg, rgba(8, 18, 36, 0.98), rgba(6, 14, 28, 0.94));
  border: 1px solid rgba(83, 120, 181, 0.22);
  box-shadow: 0 14px 30px rgba(0, 0, 0, 0.22);
}

.training-topbar__left,
.training-topbar__right,
.training-topbar__center {
  display: flex;
  align-items: center;
}

.training-topbar__left {
  gap: 12px;
  min-width: 0;
}

.training-topbar__center {
  flex-direction: column;
  justify-content: center;
  gap: 8px;
}

.training-topbar__right {
  justify-content: flex-end;
  gap: 12px;
}

.training-back,
.training-exit {
  border-radius: 10px;
  border: 1px solid rgba(88, 123, 188, 0.24);
  background: rgba(10, 25, 49, 0.88);
  color: #e2e8f0 !important;
  padding-inline: 14px;
}

.training-title-wrap {
  min-width: 0;
}

.training-title {
  color: #f8fafc;
  font-size: 24px;
  font-weight: 800;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.training-subtitle {
  color: #7dd3fc;
  font-size: 12px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.training-step__summary {
  color: #e2e8f0;
  font-size: 14px;
  font-weight: 700;
}

.training-stepper {
  display: flex;
  align-items: center;
  gap: 10px;
}

.training-stepper__dot {
  width: 34px;
  height: 6px;
  border-radius: 999px;
  background: rgba(87, 110, 146, 0.4);
  transition: all 0.2s ease;
}

.training-stepper__dot.is-active {
  background: linear-gradient(90deg, #60a5fa, #3b82f6);
  box-shadow: 0 0 0 4px rgba(59, 130, 246, 0.12);
}

.training-stepper__dot.is-done {
  background: linear-gradient(90deg, #22c55e, #16a34a);
}

.training-stepper__dot.is-skip {
  background: linear-gradient(90deg, #f59e0b, #d97706);
}

.training-chip {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  border-radius: 10px;
  background: rgba(8, 22, 43, 0.94);
  border: 1px solid rgba(87, 120, 173, 0.26);
  color: #e2e8f0;
}

.training-chip__label {
  color: #94a3b8;
  font-size: 12px;
}

.training-chip--mode {
  color: #60a5fa;
  font-weight: 700;
}

.training-main {
  display: grid;
  grid-template-columns: 240px minmax(0, 1fr) 300px;
  gap: 12px;
  flex: 1;
  min-height: 0;
}

.training-side {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-height: 0;
}

.training-stage {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-width: 0;
  min-height: 0;
}

.monitor-card,
.side-status-card,
.prompt-card,
.rail-panel,
.task-panel,
.hud-card,
.stage-controls {
  padding: 14px;
}

.monitor-camera {
  position: relative;
  overflow: hidden;
  border-radius: 10px;
  border: 1px solid rgba(80, 132, 215, 0.24);
  background: rgba(2, 6, 23, 0.92);
}

.monitor-camera__video,
.stage-video {
  width: 100%;
  display: block;
  background: #000;
  object-fit: cover;
}

.monitor-camera__video {
  aspect-ratio: 4 / 5;
  transform: scaleX(-1);
}

.monitor-camera__placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  aspect-ratio: 4 / 5;
  color: #64748b;
  font-size: 13px;
}

.monitor-tools {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
  margin-top: 10px;
  font-size: 12px;
  color: #94a3b8;
  text-align: center;
}

.status-pill {
  padding: 3px 10px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 700;
}

.status-pill.is-pass {
  background: rgba(34, 197, 94, 0.14);
  color: #4ade80;
}

.status-pill.is-warn {
  background: rgba(245, 158, 11, 0.14);
  color: #fbbf24;
}

.side-status-card__banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 10px 12px;
  border-radius: 10px;
  margin-bottom: 12px;
  border: 1px solid rgba(34, 197, 94, 0.18);
  background: rgba(34, 197, 94, 0.08);
  color: #86efac;
  font-weight: 700;
}

.side-status-card__banner.is-checking,
.side-status-card__banner.is-warn,
.side-status-card__banner.is-error {
  border-color: rgba(59, 130, 246, 0.18);
  background: rgba(59, 130, 246, 0.08);
  color: #93c5fd;
}

.side-status-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.side-status-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  font-size: 13px;
  color: #cbd5e1;
}

.text-pass {
  color: #4ade80;
}

.text-warn {
  color: #fbbf24;
}

.side-status-help {
  margin-top: 12px;
  color: #7dd3fc;
  font-size: 12px;
  line-height: 1.6;
}

.prompt-card {
  display: flex;
  align-items: center;
  gap: 12px;
}

.prompt-card__avatar {
  width: 50px;
  height: 50px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(180deg, rgba(37, 99, 235, 0.8), rgba(30, 64, 175, 0.84));
  color: #fff;
  font-size: 18px;
  font-weight: 800;
  flex-shrink: 0;
}

.prompt-card__title {
  color: #f8fafc;
  font-size: 14px;
  font-weight: 700;
  margin-bottom: 4px;
}

.prompt-card__text {
  color: #cbd5e1;
  font-size: 13px;
  line-height: 1.6;
}

.stage-frame {
  position: relative;
  min-height: 0;
  flex: 1;
  overflow: hidden;
  border-radius: 14px;
  border: 1px solid rgba(77, 120, 191, 0.24);
  background: #010611;
  box-shadow: inset 0 1px 0 rgba(255,255,255,0.04);
}

.stage-video {
  height: 100%;
  min-height: 520px;
}

.stage-overlay-top {
  position: absolute;
  top: 18px;
  left: 18px;
  right: 18px;
  display: flex;
  justify-content: space-between;
  gap: 12px;
  pointer-events: none;
}

.stage-scene-tag,
.stage-scene-task {
  padding: 8px 12px;
  border-radius: 10px;
  background: rgba(3, 10, 24, 0.72);
  border: 1px solid rgba(83, 120, 181, 0.2);
  backdrop-filter: blur(10px);
}

.stage-scene-tag {
  color: #e2e8f0;
  font-size: 12px;
  font-weight: 700;
}

.stage-scene-task {
  color: #93c5fd;
  font-size: 13px;
  font-weight: 700;
}

.stage-overlay-prompt {
  position: absolute;
  left: 18px;
  bottom: 18px;
  width: min(320px, calc(100% - 36px));
  padding: 14px;
  border-radius: 12px;
  background: rgba(4, 12, 28, 0.72);
  border: 1px solid rgba(83, 120, 181, 0.22);
  backdrop-filter: blur(10px);
}

.stage-overlay-prompt__title {
  color: #f8fafc;
  font-size: 14px;
  font-weight: 700;
  margin-bottom: 6px;
}

.stage-overlay-prompt__text {
  color: #dbeafe;
  font-size: 13px;
  line-height: 1.7;
}

.stage-controls {
  display: grid;
  grid-template-columns: auto 1fr auto auto;
  align-items: center;
  gap: 14px;
}

.stage-controls__left,
.stage-controls__meta {
  display: flex;
  align-items: center;
  gap: 8px;
}

.stage-icon-btn {
  width: 34px;
  height: 34px;
  border-radius: 999px;
  border: 1px solid rgba(88, 123, 188, 0.22);
  background: rgba(11, 26, 50, 0.88);
  color: #fff;
  cursor: default;
}

.stage-progress {
  width: 100%;
  accent-color: #3b82f6;
}

.stage-controls__time {
  display: flex;
  align-items: baseline;
  gap: 4px;
  color: #f8fafc;
  font-weight: 700;
}

.stage-controls__time small,
.stage-controls__meta {
  color: #94a3b8;
  font-size: 12px;
}

.stage-bottom-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.hud-card {
  min-height: 132px;
}

.hud-status-row {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #cbd5e1;
  font-size: 13px;
  margin-top: 10px;
}

.status-circle {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: #475569;
  box-shadow: 0 0 10px transparent;
}

.status-circle.is-listening,
.status-circle.is-processing {
  background: #3b82f6;
  box-shadow: 0 0 12px rgba(59, 130, 246, 0.4);
}

.status-circle.is-pass {
  background: #22c55e;
  box-shadow: 0 0 12px rgba(34, 197, 94, 0.35);
}

.status-circle.is-idle,
.status-circle.is-muted {
  background: #64748b;
}

.status-circle.is-error,
.status-circle.is-warn {
  background: #f59e0b;
}

.speech-meter {
  display: grid;
  grid-template-columns: repeat(16, minmax(0, 1fr));
  gap: 4px;
  margin: 18px 0 10px;
  align-items: end;
  min-height: 36px;
}

.speech-meter__bar {
  height: 12px;
  border-radius: 999px;
  background: rgba(59, 130, 246, 0.18);
}

.speech-meter__bar.is-active {
  background: linear-gradient(180deg, #60a5fa, #2563eb);
}

.gesture-figure {
  position: relative;
  width: 54px;
  height: 60px;
  margin: 16px auto 8px;
}

.gesture-figure__head,
.gesture-figure__body {
  position: absolute;
  left: 50%;
  transform: translateX(-50%);
  background: linear-gradient(180deg, #3b82f6, #1d4ed8);
}

.gesture-figure__head {
  top: 0;
  width: 18px;
  height: 18px;
  border-radius: 50%;
}

.gesture-figure__body {
  top: 20px;
  width: 26px;
  height: 36px;
  clip-path: polygon(50% 0%, 100% 28%, 84% 100%, 16% 100%, 0% 28%);
}

.hud-note {
  color: #94a3b8;
  font-size: 12px;
}

.summary-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-top: 12px;
}

.summary-item {
  display: grid;
  grid-template-columns: auto 1fr auto;
  align-items: center;
  gap: 8px;
  color: #cbd5e1;
  font-size: 13px;
}

.summary-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #475569;
}

.summary-dot.is-pass { background: #22c55e; }
.summary-dot.is-processing { background: #3b82f6; }
.summary-dot.is-warn { background: #f59e0b; }
.summary-dot.is-muted { background: #64748b; }

.rail-panel {
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.rail-panel__tabs {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  margin: -14px -14px 14px;
  border-bottom: 1px solid rgba(77, 120, 191, 0.18);
}

.rail-panel__tabs span {
  padding: 14px 10px;
  text-align: center;
  color: #64748b;
  font-size: 13px;
  font-weight: 700;
}

.rail-panel__tabs .is-active {
  color: #60a5fa;
  border-bottom: 2px solid #3b82f6;
}

.rail-panel__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 12px;
}

.rail-panel__percent {
  font-size: 12px;
  color: #64748b;
}

.rail-panel__list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  overflow-y: auto;
  min-height: 0;
}

.rail-line {
  display: grid;
  grid-template-columns: 30px 1fr;
  gap: 10px;
  padding: 10px;
  border-radius: 10px;
  background: rgba(10, 22, 42, 0.7);
  border: 1px solid rgba(77, 120, 191, 0.12);
}

.rail-line.is-active {
  background: linear-gradient(180deg, rgba(22, 76, 170, 0.34), rgba(12, 32, 67, 0.94));
  border-color: rgba(59, 130, 246, 0.3);
}

.rail-line__index {
  width: 30px;
  height: 30px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(148, 163, 184, 0.16);
  color: #e2e8f0;
  font-weight: 800;
}

.rail-line.is-pass .rail-line__index {
  background: rgba(34, 197, 94, 0.16);
  color: #4ade80;
}

.rail-line.is-skip .rail-line__index {
  background: rgba(245, 158, 11, 0.16);
  color: #fbbf24;
}

.rail-line__title {
  color: #cbd5e1;
  font-size: 12px;
  font-weight: 700;
}

.rail-line__name {
  color: #f8fafc;
  font-size: 13px;
  font-weight: 600;
  line-height: 1.5;
  margin-top: 2px;
}

.rail-line__meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  color: #64748b;
  font-size: 11px;
  margin-top: 4px;
}

.task-panel__content {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.task-panel__section {
  padding: 12px;
  border-radius: 10px;
  background: rgba(10, 22, 42, 0.68);
  border: 1px solid rgba(77, 120, 191, 0.12);
}

.task-panel__label {
  color: #94a3b8;
  font-size: 12px;
  margin-bottom: 6px;
}

.task-panel__text,
.task-panel__quote,
.task-panel__waiting {
  color: #e2e8f0;
  font-size: 13px;
  line-height: 1.7;
}

.task-panel__quote {
  border-left: 2px solid #3b82f6;
  padding-left: 10px;
}

.standard-point-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.standard-point {
  display: inline-flex;
  max-width: 100%;
  padding: 4px 8px;
  border-radius: 6px;
  background: rgba(59, 130, 246, 0.12);
  color: #bfdbfe;
  font-size: 12px;
  line-height: 1.5;
  word-break: break-word;
}

.standard-point-list--stacked {
  margin-top: 6px;
}

.standard-point--risk {
  background: rgba(245, 158, 11, 0.14);
  color: #fde68a;
}

.standard-point--law {
  background: rgba(34, 197, 94, 0.14);
  color: #bbf7d0;
}

.semantic-feedback {
  padding: 10px 12px;
  border-radius: 10px;
  background: rgba(127, 29, 29, 0.34);
  border: 1px solid rgba(248, 113, 113, 0.28);
  color: #fecaca;
}

.semantic-feedback--pass {
  background: rgba(20, 83, 45, 0.32);
  border-color: rgba(74, 222, 128, 0.28);
  color: #bbf7d0;
}

.semantic-feedback__head,
.semantic-feedback__row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
}

.semantic-feedback__head {
  margin-bottom: 6px;
  font-size: 13px;
}

.semantic-feedback__head span,
.semantic-feedback__row span {
  flex-shrink: 0;
  color: #e2e8f0;
}

.semantic-feedback__row {
  font-size: 12px;
  line-height: 1.6;
}

.semantic-feedback__row em {
  font-style: normal;
  text-align: right;
}

.task-speech-box {
  padding: 12px;
  border-radius: 10px;
  background: rgba(4, 12, 28, 0.76);
  border: 1px solid rgba(77, 120, 191, 0.14);
}

.speech-status--compact {
  margin-bottom: 10px;
}

.speech-transcript--panel {
  max-height: 112px;
  overflow-y: auto;
}

.task-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 12px;
}

.choice-panel .task-actions {
  margin-top: 10px;
}

.choice-list--panel {
  grid-template-columns: 1fr;
}

@media (max-width: 1280px) {
  .training-main {
    grid-template-columns: 220px minmax(0, 1fr) 280px;
  }
}

@media (max-width: 1100px) {
  .training-topbar {
    grid-template-columns: 1fr;
    justify-items: stretch;
  }

  .training-topbar__left,
  .training-topbar__center,
  .training-topbar__right {
    justify-content: space-between;
    flex-wrap: wrap;
  }

  .training-main {
    grid-template-columns: 1fr;
  }

  .stage-video {
    min-height: 360px;
  }

  .stage-bottom-grid {
    grid-template-columns: 1fr;
  }
}

/* 鈹€鈹€ 椤堕儴鐘舵€佹爮 鈹€鈹€ */
.topbar {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 8px 16px;
  background: rgba(255,255,255,0.04);
  border-bottom: 1px solid rgba(255,255,255,0.07);
  flex-shrink: 0;
  min-height: 44px;

  &__back { color: rgba(255,255,255,0.7) !important; }

  &__center {
    display: flex;
    align-items: center;
    gap: 8px;
    flex: 1;
    min-width: 0;
  }

  &__title {
    font-size: 14px;
    font-weight: 600;
    color: #f1f5f9;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  &__right {
    display: flex;
    align-items: center;
    gap: 10px;
    flex-shrink: 0;
  }

  &__stat {
    font-size: 12px;
    color: rgba(255,255,255,0.45);
    white-space: nowrap;
  }

  &__mode-tag {
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 11px;
    font-weight: 600;
  }
}

.mode-practice { background: rgba(59,130,246,0.2); color: #60a5fa; }
.mode-exam     { background: rgba(239,68,68,0.2);  color: #f87171; }

/* 鈹€鈹€ 涓讳綋鍖哄煙 鈹€鈹€ */
.main-area {
  display: flex;
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

/* 鈹€鈹€ 瑙嗛鍖?鈹€鈹€ */
.video-wrap {
  position: relative;
  flex: 1;
  min-width: 0;
  background: #000;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}

.main-video {
  max-width: 100%;
  max-height: 100%;
  display: block;
  object-fit: contain;
  /* 绂佹杩涘害鏉℃嫋鎷斤細閫氳繃 JS 闃绘锛孋SS 鏃犳硶瀹屽叏灞忚斀鍘熺敓鎺т欢 */
}

/* 鈹€鈹€ 鑺傜偣閬僵 鈹€鈹€ */
.node-overlay {
  position: absolute;
  inset: 0;
  background: linear-gradient(180deg, rgba(5,10,18,0.28) 0%, rgba(5,10,18,0.04) 28%, rgba(5,10,18,0) 100%);
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding-top: 24px;
  z-index: 20;
  pointer-events: none;
}

.node-card {
  width: min(560px, calc(100% - 32px));
  background: rgba(15,23,42,0.9);
  border: 1px solid rgba(255,255,255,0.1);
  border-radius: 14px;
  overflow: hidden;
  box-shadow: 0 20px 60px rgba(0,0,0,0.6);
  backdrop-filter: blur(14px);
  pointer-events: auto;

  &__head {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 12px 16px;
    background: rgba(255,255,255,0.03);
    border-bottom: 1px solid rgba(255,255,255,0.07);
  }

  &__index {
    font-size: 11px;
    color: rgba(255,255,255,0.4);
    flex-shrink: 0;
  }

  &__title {
    flex: 1;
    font-size: 14px;
    font-weight: 600;
    color: #f1f5f9;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  &__timer {
    display: flex;
    align-items: center;
    gap: 4px;
    font-size: 13px;
    font-weight: 700;
    color: #94a3b8;
    flex-shrink: 0;
    min-width: 48px;
    justify-content: flex-end;

    &.warn { color: #f87171; }
  }

  &__body { padding: 16px; }
}

.node-instruction {
  margin: 0 0 12px;
  font-size: 14px;
  color: #e2e8f0;
  line-height: 1.7;
}

.hint-row {
  display: flex;
  gap: 8px;
  align-items: flex-start;
  padding: 9px 12px;
  border-radius: 6px;
  margin-bottom: 8px;
  font-size: 13px;

  &--gesture { background: rgba(59,130,246,0.1); border-left: 3px solid #3b82f6; }
  &--speech  { background: rgba(16,185,129,0.08); border-left: 3px solid #10b981; }
}

.hint-label {
  font-weight: 700;
  font-size: 11px;
  color: rgba(255,255,255,0.45);
  white-space: nowrap;
  padding-top: 1px;
}

.hint-text {
  color: #cbd5e1;
  line-height: 1.6;
}

/* 鈹€鈹€ 璇煶鍖?鈹€鈹€ */
.speech-area {
  margin-top: 12px;
  padding: 12px;
  background: rgba(255,255,255,0.03);
  border: 1px solid rgba(255,255,255,0.07);
  border-radius: 8px;
}

.gesture-status {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 8px 10px;
  margin-bottom: 8px;
  border-radius: 6px;
  background: rgba(255,255,255,0.04);
  border: 1px solid rgba(255,255,255,0.08);

  &--matched {
    border-color: rgba(34,197,94,0.4);
    background: rgba(34,197,94,0.08);
  }
}

.gesture-status__label {
  font-size: 11px;
  font-weight: 700;
  color: rgba(255,255,255,0.5);
  white-space: nowrap;
}

.gesture-status__value {
  font-size: 12px;
  color: #cbd5e1;
  text-align: right;
  line-height: 1.5;
}

.speech-status {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: rgba(255,255,255,0.45);
  margin-bottom: 8px;

  &.listening { color: #34d399; }
  &.error     { color: #f87171; }
  &.processing { color: #fbbf24; }
}

/* 鐘舵€佹寚绀虹偣 */
.speech-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  flex-shrink: 0;
  background: rgba(255,255,255,0.2);

  &--listening {
    background: #34d399;
    box-shadow: 0 0 0 0 rgba(52,211,153,0.5);
    animation: pulse-dot 1.2s infinite;
  }
  &--error { background: #f87171; }
  &--processing { background: #fbbf24; }
}

@keyframes pulse-dot {
  0%   { box-shadow: 0 0 0 0 rgba(52,211,153,0.5); }
  70%  { box-shadow: 0 0 0 6px rgba(52,211,153,0); }
  100% { box-shadow: 0 0 0 0 rgba(52,211,153,0); }
}

/* 璇煶娉㈠舰鍔ㄦ晥锛?鏉＄珫绾匡級 */
.speech-wave {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  height: 14px;
  margin-left: 4px;

  span {
    display: inline-block;
    width: 3px;
    border-radius: 2px;
    background: #34d399;
    animation: wave-bar 0.8s ease-in-out infinite;

    &:nth-child(1) { height: 4px;  animation-delay: 0s; }
    &:nth-child(2) { height: 8px;  animation-delay: 0.1s; }
    &:nth-child(3) { height: 12px; animation-delay: 0.2s; }
    &:nth-child(4) { height: 8px;  animation-delay: 0.3s; }
    &:nth-child(5) { height: 4px;  animation-delay: 0.4s; }
  }
}

@keyframes wave-bar {
  0%, 100% { transform: scaleY(1); }
  50%       { transform: scaleY(1.8); }
}

.speech-transcript {
  min-height: 32px;
  margin-bottom: 10px;
  font-size: 13px;
  line-height: 1.6;

  .interim { color: rgba(255,255,255,0.4); }
  .final   { color: #e2e8f0; margin-left: 4px; }
}

.speech-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

/* 鈹€鈹€ 鍒ゆ柇棰?鈹€鈹€ */
.judge-row {
  display: flex;
  gap: 12px;
  margin-top: 8px;
}

/* 鈹€鈹€ 鍗曢€夐 鈹€鈹€ */
.choice-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-top: 8px;
}

.choice-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 9px 14px;
  background: rgba(255,255,255,0.04);
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 6px;
  color: #cbd5e1;
  font-size: 13px;
  cursor: pointer;
  text-align: left;
  transition: background 0.15s, border-color 0.15s;

  &:hover { background: rgba(59,130,246,0.1); border-color: rgba(59,130,246,0.3); }

  &.selected {
    background: rgba(59,130,246,0.2);
    border-color: #3b82f6;
    color: #93c5fd;
  }
}

.choice-alpha {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: rgba(255,255,255,0.1);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 700;
  flex-shrink: 0;
}

/* 閫夋嫨棰橀檺鏃惰繘搴︽潯 */
.choice-timer {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;

  :deep(.el-progress) { flex: 1; }

  &__text {
    font-size: 12px;
    font-weight: 700;
    color: #94a3b8;
    min-width: 28px;
    text-align: right;

    &--warn { color: #f87171; }
  }
}

/* 鈹€鈹€ 瓒呮椂鎻愮ず鏍?鈹€鈹€ */
.timeout-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  padding: 10px 16px;
  border-top: 1px solid rgba(255,255,255,0.07);
  background: rgba(239,68,68,0.06);

  &__label {
    font-size: 12px;
    color: #f87171;
    font-weight: 600;
  }
}

.node-failure-reasons {
  padding: 8px 16px 0;
  font-size: 12px;
  color: #fca5a5;
  line-height: 1.6;
}

.reference-popup {
  width: min(520px, calc(100vw - 24px));
  background: transparent;
}

.reference-card {
  background: #1e293b;
  border-radius: 14px;
  border: 1px solid rgba(255,255,255,0.1);
  color: #e2e8f0;
  overflow: hidden;
}

.reference-card__head {
  padding: 18px 20px 12px;
  border-bottom: 1px solid rgba(255,255,255,0.08);
}

.reference-card__title {
  font-size: 16px;
  font-weight: 700;
}

.reference-card__subtitle {
  margin-top: 6px;
  font-size: 12px;
  color: #94a3b8;
}

.reference-card__body {
  padding: 16px 20px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.reference-block {
  padding: 12px 14px;
  border-radius: 10px;
  background: rgba(255,255,255,0.04);
  border: 1px solid rgba(255,255,255,0.06);
}

.reference-block__label {
  font-size: 11px;
  font-weight: 700;
  color: #93c5fd;
  margin-bottom: 6px;
}

.reference-block__value {
  font-size: 13px;
  line-height: 1.7;
  color: #e2e8f0;
}

.reference-keywords {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.reference-keyword {
  display: inline-flex;
  align-items: center;
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 12px;
  color: #bfdbfe;
  background: rgba(59,130,246,0.14);
  border: 1px solid rgba(96,165,250,0.24);
}

.reference-card__actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  padding: 0 20px 20px;
}

.prop-panel {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 12px;
  margin-bottom: 12px;
  border-radius: 10px;
  border: 1px solid rgba(255,255,255,0.08);
  background: rgba(255,255,255,0.04);
}

.prop-panel--ready {
  border-color: rgba(34,197,94,0.3);
  background: rgba(34,197,94,0.08);
}

.prop-panel--pending {
  border-color: rgba(251,191,36,0.26);
  background: rgba(251,191,36,0.08);
}

.prop-panel__meta {
  display: flex;
  flex-direction: column;
  gap: 4px;
  flex: 1;
  min-width: 0;
}

.prop-panel__label {
  font-size: 12px;
  font-weight: 700;
  color: #f8fafc;
}

.prop-panel__desc {
  font-size: 12px;
  line-height: 1.6;
  color: #cbd5e1;
}

.prop-panel__status {
  font-size: 12px;
  font-weight: 700;
  color: #86efac;
  white-space: nowrap;
}

.prop-panel__visual {
  width: 120px;
  min-height: 92px;
  border-radius: 12px;
  padding: 10px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  flex-shrink: 0;
  border: 1px solid rgba(148, 163, 184, 0.22);
  background:
    linear-gradient(180deg, rgba(30, 41, 59, 0.96), rgba(15, 23, 42, 0.92));
}

.prop-panel__visual--id {
  border-color: rgba(96, 165, 250, 0.32);
  background:
    linear-gradient(180deg, rgba(30, 64, 175, 0.28), rgba(15, 23, 42, 0.96));
}

.prop-panel__visual--device {
  border-color: rgba(45, 212, 191, 0.28);
  background:
    linear-gradient(180deg, rgba(13, 148, 136, 0.24), rgba(15, 23, 42, 0.96));
}

.prop-panel__visual--gear {
  border-color: rgba(251, 191, 36, 0.3);
  background:
    linear-gradient(180deg, rgba(180, 83, 9, 0.24), rgba(15, 23, 42, 0.96));
}

.prop-panel__visual-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: fit-content;
  padding: 3px 8px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.1);
  color: #e2e8f0;
  font-size: 11px;
  font-weight: 700;
}

.prop-panel__visual-name {
  font-size: 15px;
  font-weight: 800;
  color: #f8fafc;
  line-height: 1.35;
  word-break: break-word;
}

.prop-panel__visual-mode {
  font-size: 11px;
  color: #cbd5e1;
  line-height: 1.4;
}

@media (max-width: 900px) {
  .prop-panel {
    flex-direction: column;
    align-items: stretch;
  }

  .prop-panel__visual {
    width: 100%;
    min-height: 84px;
  }
}

/* 鈹€鈹€ 鍒ゅ畾缁撴灉 鈹€鈹€ */
.node-result {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  padding: 10px;
  font-size: 13px;
  font-weight: 600;
  border-top: 1px solid rgba(255,255,255,0.07);

  &--pass { color: #22c55e; background: rgba(34,197,94,0.08); }
  &--fail { color: #f87171; background: rgba(248,113,113,0.08); }
}

/* 鈹€鈹€ 鎽勫儚澶存偓娴獥 鈹€鈹€ */
.cam-float {
  position: absolute;
  width: 148px;
  border-radius: 8px;
  overflow: hidden;
  border: 2px solid rgba(59,130,246,0.5);
  cursor: move;
  z-index: 30;
  box-shadow: 0 4px 16px rgba(0,0,0,0.5);
}

.cam-video {
  width: 100%;
  display: block;
  transform: scaleX(-1);
  background: #000;
  aspect-ratio: 4/3;
}

.cam-label {
  padding: 3px 8px;
  background: rgba(0,0,0,0.7);
  font-size: 10px;
  color: rgba(255,255,255,0.6);
  text-align: center;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;

  .cam-dot--active { color: #22c55e; }
}

/* 鈹€鈹€ 鍙充晶鑺傜偣杩涘害鏍?鈹€鈹€ */
.node-rail {
  width: 188px;
  flex-shrink: 0;
  background: #111827;
  border-left: 1px solid rgba(255,255,255,0.07);
  overflow-y: auto;
  padding: 10px 0;

  &__head {
    padding: 0 12px 8px;
    font-size: 10px;
    font-weight: 700;
    color: rgba(255,255,255,0.3);
    text-transform: uppercase;
    letter-spacing: 0.1em;
    border-bottom: 1px solid rgba(255,255,255,0.06);
    margin-bottom: 4px;
  }
}

.rail-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 7px 12px;
  border-left: 3px solid transparent;
  transition: background 0.12s;

  &--active {
    background: rgba(59,130,246,0.1);
    border-left-color: #3b82f6;
  }
  &--pass .rail-dot  { background: rgba(34,197,94,0.15); color: #22c55e; }
  &--skip .rail-dot  { background: rgba(234,179,8,0.12);  color: #eab308; }
  &--pass .rail-name { color: rgba(255,255,255,0.35); }
  &--skip .rail-name { color: rgba(255,255,255,0.25); }
}

.rail-dot {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  background: rgba(255,255,255,0.07);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 10px;
  font-weight: 700;
  color: rgba(255,255,255,0.35);
  flex-shrink: 0;
  margin-top: 1px;
}

.rail-info { flex: 1; min-width: 0; }

.rail-name {
  font-size: 12px;
  color: rgba(255,255,255,0.65);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.rail-time {
  font-size: 10px;
  color: rgba(255,255,255,0.25);
  margin-top: 1px;
}

/* 鈹€鈹€ 璇勪及鎶ュ憡寮圭獥 鈹€鈹€ */
.report-popup {
  width: min(480px, calc(100vw - 24px));
  background: transparent;
}

.report-card {
  background: #1e293b;
  border-radius: 14px;
  border: 1px solid rgba(255,255,255,0.1);
  overflow: hidden;
  padding: 24px;
  color: #e2e8f0;
}

.report-header {
  text-align: center;
  padding-bottom: 20px;
  border-bottom: 1px solid rgba(255,255,255,0.07);
  margin-bottom: 16px;
}

.report-grade {
  font-size: 28px;
  font-weight: 900;
  letter-spacing: 0.04em;
  margin-bottom: 6px;

  &.grade--excellent { color: #22c55e; }
  &.grade--pass      { color: #3b82f6; }
  &.grade--fail      { color: #f87171; }
}

.report-score {
  font-size: 36px;
  font-weight: 700;
  color: #f1f5f9;

  span { font-size: 16px; color: rgba(255,255,255,0.4); }
}

.report-pct {
  font-size: 13px;
  color: rgba(255,255,255,0.4);
  margin-top: 4px;
}

.report-stats {
  display: flex;
  justify-content: space-around;
  gap: 12px;
  padding: 14px 0;
  border-bottom: 1px solid rgba(255,255,255,0.07);
  margin-bottom: 14px;
}

.report-dimensions {
  display: grid;
  grid-template-columns: 1fr;
  gap: 10px;
  margin-bottom: 14px;
}

.rdim,
.report-advice__item {
  background: rgba(255,255,255,0.03);
  border: 1px solid rgba(255,255,255,0.06);
  border-radius: 10px;
}

.rdim {
  padding: 12px;
}

.rdim__head,
.rdim__foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.rdim__head {
  margin-bottom: 8px;
  font-size: 12px;
  color: #f1f5f9;
}

.rdim__foot {
  margin-top: 8px;
  font-size: 11px;
  color: rgba(255,255,255,0.48);
}

.report-advice {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 14px;
}

.report-advice__item {
  padding: 12px;
  font-size: 12px;
  color: #cbd5e1;
  line-height: 1.7;
}

.rstat {
  text-align: center;

  &__num {
    font-size: 22px;
    font-weight: 700;
    color: #f1f5f9;

    &--warn   { color: #eab308; }
    &--danger { color: #f87171; }
  }

  &__label {
    font-size: 11px;
    color: rgba(255,255,255,0.4);
    margin-top: 3px;
  }
}

.report-nodes {
  display: flex;
  flex-direction: column;
  gap: 4px;
  max-height: 220px;
  overflow-y: auto;
  margin-bottom: 20px;
}

.rnode {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  background: rgba(255,255,255,0.03);
  border-radius: 6px;
  font-size: 12px;

  &__idx {
    width: 20px;
    height: 20px;
    border-radius: 50%;
    background: rgba(255,255,255,0.08);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 10px;
    font-weight: 700;
    color: rgba(255,255,255,0.4);
    flex-shrink: 0;
  }

  &__result {
    font-weight: 600;
    min-width: 40px;

    &--pass    { color: #22c55e; }
    &--skip,
    &--timeout { color: #eab308; }
    &--fail    { color: #f87171; }
  }

  &__score  { color: #94a3b8; margin-left: auto; }
  &__deduct { color: #f87171; font-size: 11px; }
  &__retry  { color: #eab308; font-size: 11px; }
}

.report-actions {
  display: flex;
  gap: 10px;
  justify-content: center;
}

/* 鈹€鈹€ 鍔ㄧ敾 鈹€鈹€ */
.node-fade-enter-active,
.node-fade-leave-active { transition: opacity 0.22s ease; }
.node-fade-enter-from,
.node-fade-leave-to     { opacity: 0; }

.result-fade-enter-active,
.result-fade-leave-active { transition: opacity 0.2s, transform 0.2s; }
.result-fade-enter-from,
.result-fade-leave-to     { opacity: 0; transform: translateY(4px); }

/* 鈹€鈹€ 鍓嶇疆绠€鎶ュ脊绐?鈹€鈹€ */
.briefing-popup {
  width: min(760px, calc(100vw - 24px));
  background: transparent;
}

.briefing-card {
  background: #ffffff;
  border-radius: 14px;
  border: 1px solid #e5e6eb;
  overflow: hidden;
  color: #1d2129;
  box-shadow: 0 20px 52px rgba(15, 23, 42, 0.16);

  &__head {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 18px 22px;
    border-bottom: 1px solid #eef0f4;
    background: #fff;
  }

  &__title {
    font-size: 22px;
    font-weight: 800;
    color: #0f1419;
    flex: 1;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  &__body {
    padding: 18px 22px;
    max-height: 72vh;
    overflow-y: auto;
    background:
      linear-gradient(180deg, rgba(248,250,252,0.92) 0%, rgba(255,255,255,1) 28%);
  }

  &__foot {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 10px;
    padding: 16px 22px;
    border-top: 1px solid #eef0f4;
    background: #fff;
  }
}

.briefing-content {
  font-size: 16px;
  color: #1a1f26;
  line-height: 1.8;
  white-space: pre-wrap;
  margin-bottom: 18px;
  padding: 14px 16px;
  background: #f6f7f9;
  border-radius: 10px;
  border-left: 4px solid #165dff;
}

.briefing-default {
  font-size: 16px;
  color: #1a1f26;
  line-height: 1.8;
  margin-bottom: 18px;

  p { margin: 0 0 8px; }
}

.precheck-panel {
  margin-bottom: 18px;
  padding: 16px;
  border-radius: 12px;
  background: #ffffff;
  border: 1px solid #e5e6eb;
}

.precheck-camera {
  margin-bottom: 12px;
  padding: 10px;
  border-radius: 10px;
  background: #f8fafc;
  border: 1px solid #e5e7eb;
}

.precheck-camera__video {
  width: 100%;
  max-height: 220px;
  border-radius: 8px;
  background: #0f172a;
  object-fit: cover;
}

.precheck-camera__hint {
  margin-top: 8px;
  font-size: 12px;
  color: #165dff;
  line-height: 1.6;
}

.precheck-metrics {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
  margin-top: 10px;
}

.precheck-metric {
  padding: 8px 10px;
  border-radius: 8px;
  background: #fff;
  border: 1px solid #e5e7eb;

  &.is-pass {
    border-color: rgba(34, 197, 94, 0.26);
    background: rgba(34, 197, 94, 0.06);
  }

  &.is-checking {
    border-color: rgba(59, 130, 246, 0.22);
    background: rgba(59, 130, 246, 0.06);
  }
}

.precheck-metric__label {
  display: block;
  font-size: 11px;
  color: #86909c;
  margin-bottom: 4px;
}

.precheck-metric__value {
  font-size: 13px;
  font-weight: 700;
  color: #1d2129;
}

.precheck-panel__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 10px;
}

.precheck-panel__title {
  font-size: 16px;
  font-weight: 800;
  color: #0f1419;
}

.precheck-panel__badge {
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 700;
}

.precheck-panel__badge.is-ready {
  background: rgba(34, 197, 94, 0.12);
  color: #15803d;
}

.precheck-panel__badge.is-checking {
  background: rgba(59, 130, 246, 0.16);
  color: #165dff;
}

.precheck-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.precheck-item {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 12px;
  border-radius: 8px;
  background: #fff;
  border: 1px solid #e5e7eb;
}

.precheck-item.is-pass {
  border-color: rgba(34, 197, 94, 0.24);
  background: rgba(34, 197, 94, 0.05);
}

.precheck-item.is-warn,
.precheck-item.is-checking,
.precheck-item.is-error {
  border-color: rgba(245, 158, 11, 0.24);
  background: rgba(245, 158, 11, 0.06);
}

.precheck-item__label {
  font-size: 13px;
  font-weight: 700;
  color: #1d2129;
  white-space: nowrap;
}

.precheck-item__value {
  font-size: 13px;
  color: #4e5969;
  line-height: 1.5;
  text-align: right;
}

.precheck-hint {
  margin-top: 10px;
  font-size: 13px;
  color: #165dff;
  line-height: 1.6;
}

.interrupt-panel {
  margin-top: 14px;
  padding: 12px 14px;
  border-radius: 10px;
  background: rgba(127, 29, 29, 0.2);
  border: 1px solid rgba(248, 113, 113, 0.28);
}

.interrupt-panel__title {
  font-size: 13px;
  font-weight: 700;
  color: #fecaca;
}

.interrupt-panel__desc {
  margin-top: 6px;
  font-size: 12px;
  color: #fca5a5;
  line-height: 1.6;
}

.interrupt-panel__hint {
  margin-top: 6px;
  font-size: 12px;
  color: #fde68a;
  line-height: 1.6;
}

.interrupt-panel__actions {
  display: flex;
  gap: 8px;
  margin-top: 10px;
}

.briefing-notices {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-bottom: 18px;
}

.bn-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 12px 14px;
  border-radius: 10px;
  font-size: 13px;
  line-height: 1.7;
  color: #4e5969;
  border: 1px solid #e5e6eb;
  background: #fff;

  &--warn {
    color: #92400e;
    border-color: rgba(245, 158, 11, 0.24);
    background: rgba(245, 158, 11, 0.08);
  }

  &--info {
    color: #1e40af;
    border-color: rgba(59, 130, 246, 0.2);
    background: rgba(59, 130, 246, 0.06);
  }
}

.bn-dot {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  font-size: 10px;
  font-weight: 700;
  flex-shrink: 0;
  margin-top: 1px;

  .bn-item--warn & { background: rgba(251,191,36,0.2); }
  .bn-item--info & { background: rgba(96,165,250,0.16); }
}

.briefing-mode {
  margin-bottom: 18px;
}

.mode-label {
  font-size: 14px;
  font-weight: 800;
  color: #0f1419;
  margin-bottom: 10px;
}

.mode-options {
  display: flex;
  gap: 10px;
}

.mode-btn {
  flex: 1;
  padding: 14px 16px;
  border: 1px solid #e5e6eb;
  border-radius: 12px;
  background: #fff;
  color: #4e5969;
  cursor: pointer;
  text-align: left;
  transition: border-color 0.15s, background 0.15s;

  &:hover {
    border-color: rgba(22,93,255,0.42);
    background: rgba(22,93,255,0.05);
  }

  &.active {
    border-color: #165dff;
    background: rgba(22,93,255,0.08);
    color: #165dff;
  }

  &--exam:hover { border-color: rgba(239,68,68,0.4); background: rgba(239,68,68,0.06); }
  &--exam.active { border-color: #ef4444; background: rgba(239,68,68,0.08); color: #b91c1c; }

  &__title {
    font-size: 15px;
    font-weight: 800;
    margin-bottom: 4px;
  }

  &__desc {
    font-size: 12px;
    opacity: 0.86;
  }
}

.briefing-stats {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  padding: 0;
  background: transparent;
  border-radius: 0;
  border: 0;
}

.cam-status {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  padding: 0 10px 10px;
}

.cam-chip {
  display: inline-flex;
  align-items: center;
  padding: 3px 8px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 600;
  background: rgba(15, 23, 42, 0.8);
  color: #cbd5e1;
  border: 1px solid rgba(148, 163, 184, 0.18);

  &.is-pass {
    color: #86efac;
    border-color: rgba(34, 197, 94, 0.26);
  }

  &.is-warn,
  &.is-error {
    color: #fbbf24;
    border-color: rgba(251, 191, 36, 0.24);
  }

  &.is-checking {
    color: #93c5fd;
    border-color: rgba(59, 130, 246, 0.24);
  }
}

.bs-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 3px;
  flex: 1;
  padding: 14px 12px;
  border-radius: 12px;
  background: #ffffff;
  border: 1px solid #e5e6eb;
}

.bs-num {
  font-size: 24px;
  font-weight: 800;
  color: #0f1419;
}

.bs-label {
  font-size: 12px;
  color: #86909c;
}
</style>

