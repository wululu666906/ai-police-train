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

      <!-- 三步向导 briefing 弹窗 -->
      <van-popup
        v-model:show="showBriefing"
        :close-on-click-overlay="false"
        :lazy-render="false"
        round
        teleport="body"
        class="briefing-popup"
        :overlay-style="{ backgroundColor: 'rgba(0,0,0,0.85)' }"
        @opened="onBriefingOpened"
      >
        <div class="briefing-card briefing-card--dark">
          <!-- Step indicator -->
          <div class="briefing-steps">
            <span class="briefing-step" :class="{ 'briefing-step--active': briefingStep === 1, 'briefing-step--done': briefingStep > 1 }">{{ briefingStep > 1 ? '✓' : '1' }}</span>
            <span class="briefing-step-line" :class="{ 'briefing-step-line--done': briefingStep > 1 }"></span>
            <span class="briefing-step" :class="{ 'briefing-step--active': briefingStep === 2, 'briefing-step--done': briefingStep > 2 }">{{ briefingStep > 2 ? '✓' : '2' }}</span>
            <span class="briefing-step-line" :class="{ 'briefing-step-line--done': briefingStep > 2 }"></span>
            <span class="briefing-step" :class="{ 'briefing-step--active': briefingStep === 3 }">3</span>
            <span class="briefing-steps__labels">
              <span :class="{ 'is-active': briefingStep === 1 }">人脸识别</span>
              <span :class="{ 'is-active': briefingStep === 2 }">设备检测</span>
              <span :class="{ 'is-active': briefingStep === 3 }">训练简报</span>
            </span>
          </div>

          <!-- Step 1: Face Recognition -->
          <div v-if="briefingStep === 1" class="briefing-body">
            <h3 class="briefing-body__title">身份校验</h3>
            <p class="briefing-body__desc">请正对摄像头，将面部保持在圆形区域内即可，无需精确对准。</p>
            <div class="face-preview">
              <div class="face-preview__camera">
                <video
                  ref="briefingCameraRef"
                  autoplay
                  muted
                  playsinline
                  class="face-preview__video"
                  :class="{ 'face-preview__video--hidden': !cameraOn }"
                />
                <div v-if="cameraOn" class="face-preview__ring" aria-hidden="true"></div>
                <div v-if="!cameraOn" class="face-preview__placeholder">
                  <svg viewBox="0 0 24 24" width="48" height="48" fill="#475569"><path d="M18 10.48V6c0-1.1-.9-2-2-2H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2v-4.48l4 3.98v-11l-4 3.98z"/></svg>
                  <span>{{ deviceWarningText || '正在启动摄像头...' }}</span>
                </div>
              </div>
              <div class="face-preview__hint">请将面部保持在圆形区域内，正对摄像头并保持画面清晰。</div>
            </div>
            <div v-if="cameraOn" class="face-metrics">
              <div class="face-metric" :class="(identityReady || singleFaceReady) ? 'face-metric--pass' : ''">
                <span class="face-metric__label">入镜人数</span>
                <span class="face-metric__value">{{ resolvedFaceCountText }}</span>
              </div>
              <div class="face-metric" :class="(identityReady || liveReady) ? 'face-metric--pass' : ''">
                <span class="face-metric__label">活体动作</span>
                <span class="face-metric__value">{{ resolvedLiveMotionText }}</span>
              </div>
              <div class="face-metric" :class="identityReady ? 'face-metric--pass' : ''">
                <span class="face-metric__label">本人匹配</span>
                <span class="face-metric__value">{{ resolvedFaceMatchText }}</span>
              </div>
            </div>
            <div class="face-status">
              <span class="face-status__badge" :class="identityReady ? 'face-status__badge--pass' : ''">
                {{ identityReady ? '✓ 身份校验通过' : resolvedIdentityStatusText }}
              </span>
              <p v-if="!faceProfileRegistered" class="face-status__fallback">当前账号尚未注册人脸档案，请先在个人设置中上传本人正脸照片。</p>
              <p v-else-if="!presenceSupported && !identityReady" class="face-status__fallback">本地检测不可用，已切换为后端人脸识别校验。</p>
              <p v-else-if="faceIdentityVerifying" class="face-status__hint">{{ faceIdentityStatusText }}</p>
            </div>
            <canvas ref="faceCanvasRef" class="face-capture-canvas" />
            <div class="briefing-actions">
              <el-button @click="router.back()">暂不进入</el-button>
              <el-button type="primary" :disabled="!identityReady" @click="briefingStep = 2">
                {{ identityReady ? '下一步' : '请完成人脸校验' }}
              </el-button>
            </div>
          </div>

          <!-- Step 2: Device Check -->
          <div v-if="briefingStep === 2" class="briefing-body">
            <h3 class="briefing-body__title">设备检测</h3>
            <p class="briefing-body__desc">确保摄像头和麦克风正常工作，以便系统进行 AI 识别。</p>
            <div class="device-check-list">
              <div class="device-check-item" :class="cameraOn ? 'device-check-item--pass' : 'device-check-item--fail'">
                <span class="device-check-item__icon">{{ cameraOn ? '✓' : '✗' }}</span>
                <span class="device-check-item__label">摄像头</span>
                <span class="device-check-item__status">{{ cameraOn ? '已连接' : '未检测到' }}</span>
              </div>
              <div class="device-check-item" :class="deviceReady ? 'device-check-item--pass' : 'device-check-item--fail'">
                <span class="device-check-item__icon">{{ deviceReady ? '✓' : '✗' }}</span>
                <span class="device-check-item__label">麦克风</span>
                <span class="device-check-item__status">{{ deviceReady ? '已就绪' : '未检测到或未授权' }}</span>
              </div>
              <div class="device-check-item" :class="speechSupported ? 'device-check-item--pass' : 'device-check-item--warn'">
                <span class="device-check-item__icon">{{ speechSupported ? '✓' : '⚠' }}</span>
                <span class="device-check-item__label">语音识别</span>
                <span class="device-check-item__status">{{ speechSupported ? '支持，节点触发后自动识别' : '不支持，将使用手动输入替代' }}</span>
              </div>
            </div>
            <div v-if="!deviceReady || !cameraOn" class="device-check-hint">
              <p>{{ resolvedPrecheckHintText || '请检查浏览器是否已授权摄像头和麦克风权限。' }}</p>
              <el-button size="small" plain @click="retryDeviceCheck">重新检测</el-button>
            </div>
            <div v-else class="device-check-hint device-check-hint--ok">
              <p>所有设备检测通过，可进入下一步。</p>
            </div>
            <div class="briefing-actions">
              <el-button @click="briefingStep = 1">上一步</el-button>
              <el-button type="primary" :disabled="!deviceReady" @click="briefingStep = 3">
                {{ deviceReady ? '下一步' : '请先完成设备检测' }}
              </el-button>
            </div>
          </div>

          <!-- Step 3: Briefing + Mode Selection -->
          <div v-if="briefingStep === 3" class="briefing-body">
            <h3 class="briefing-body__title">训练简报</h3>
            <div class="briefing-content-block">
              <div v-if="video.briefing" class="briefing-text">{{ video.briefing }}</div>
              <div v-else class="briefing-text">本次训练为第一视角交互式实训，系统会在关键节点自动暂停并检测你的动作与话术。完成全部节点后会生成评估报告。</div>
            </div>
            <div v-if="video.nodes?.length" class="briefing-stat-row">
              <div class="briefing-stat"><span class="briefing-stat__num">{{ video.nodes.length }}</span><span class="briefing-stat__label">训练节点</span></div>
              <div v-if="video.duration" class="briefing-stat"><span class="briefing-stat__num">{{ formatTime(video.duration) }}</span><span class="briefing-stat__label">视频时长</span></div>
              <div class="briefing-stat"><span class="briefing-stat__num">{{ video.nodes.reduce((a, n) => a + n.score_weight, 0) }}</span><span class="briefing-stat__label">总分</span></div>
            </div>
            <div class="briefing-mode-section">
              <div class="briefing-mode-label">选择训练模式</div>
              <div class="briefing-mode-options">
                <button class="briefing-mode-btn" :class="{ 'briefing-mode-btn--active': trainingMode === 'practice' }" @click="trainingMode = 'practice'">
                  <span class="briefing-mode-btn__title">练习模式</span>
                  <span class="briefing-mode-btn__desc">提供操作提示和标准话术参考</span>
                </button>
                <button class="briefing-mode-btn" :class="{ 'briefing-mode-btn--active': trainingMode === 'exam' }" @click="trainingMode = 'exam'">
                  <span class="briefing-mode-btn__title">考核模式</span>
                  <span class="briefing-mode-btn__desc">无提示，严格评分，计入记录</span>
                </button>
              </div>
            </div>
            <div class="briefing-notices-section">
              <div class="bn-item bn-item--warn"><span class="bn-dot">!</span>视频播放期间<strong>禁止拖动进度条</strong>，违规将被记录。</div>
              <div class="bn-item bn-item--info"><span class="bn-dot">i</span>节点超时触发扣分，请保持专注。</div>
              <div class="bn-item bn-item--info"><span class="bn-dot">i</span>切换标签页、离开页面等行为将被系统记录。</div>
            </div>
            <div class="briefing-actions">
              <el-button @click="briefingStep = 2">上一步</el-button>
              <el-button type="primary" @click="confirmBriefing">已了解，开始训练</el-button>
            </div>
          </div>
        </div>
      </van-popup>
      <!-- ========== 沉浸式全屏布局（考核模式） ========== -->
      <div v-if="immersiveMode" class="imm-shell" @keydown.space.prevent="toggleFullscreen" @keydown.esc="confirmExit">
        <!-- Top Header (overlay on top of video) -->
        <header class="imm-header">
          <div class="imm-header__left">
            <span class="imm-header__rec" :class="{ 'imm-header__rec--active': nodeActive }">●</span>
            <span class="imm-header__title">{{ video.title }}（{{ trainingMode === 'exam' ? '考核模式' : '练习模式' }}）</span>
          </div>
          <div class="imm-header__center">
            <span class="imm-header__node">节点 {{ String(displayNodeNumber).padStart(2, '0') }} / {{ String(video.nodes.length).padStart(2, '0') }}</span>
            <span class="imm-header__node-name">{{ displayNodeTitle }}</span>
          </div>
          <div class="imm-header__right">
            <span class="imm-header__timer">
              <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor"><path d="M11.99 2C6.47 2 2 6.48 2 12s4.47 10 9.99 10C17.52 22 22 17.52 22 12S17.52 2 11.99 2zM12 20c-4.42 0-8-3.58-8-8s3.58-8 8-8 8 3.58 8 8-3.58 8-8 8zm.5-13H11v6l5.25 3.15.75-1.23-4.5-2.67V7z"/></svg>
              {{ trainingMode === 'exam' ? '考核剩余时间' : (nodeActive ? '本节点剩余' : '训练进度') }} {{ topbarTimerText }}
            </span>
            <button class="imm-header__fullscreen-btn" @click="toggleFullscreen" title="全屏">⛶</button>
            <button class="imm-header__end-btn" @click="confirmExit">退出训练</button>
          </div>
        </header>

        <!-- Full-screen video background -->
        <div class="imm-video-layer" @click="!nodeActive && playTrainingVideo()">
          <video
            ref="videoRef"
            class="imm-video-layer__video"
            :poster="video?.thumbnail_url || undefined"
            preload="auto"
            @play="playbackPaused = false; markPlaybackPlaying()"
            @pause="playbackPaused = true"
            @waiting="markPlaybackWaiting()"
            @timeupdate="onTimeUpdate"
            @ended="onVideoEnded"
            @seeking="onSeeking"
            @contextmenu.prevent
          />
        </div>

        <!-- Overlays on top of video -->
        <div class="imm-overlays">
          <button
            v-if="playbackPaused && !nodeActive && !showBriefing"
            type="button"
            class="imm-play-retry"
            @click.stop="playTrainingVideo"
          >
            {{ playbackState === 'preparing' ? '视频准备中...' : '▶ 播放视频并进入训练' }}
          </button>
          <!-- Camera PIP (draggable, auto-snap) -->
          <div
            class="imm-pip"
            :class="{ 'imm-pip--breathing': cameraOn }"
            :style="{ top: camPos.y + 'px', left: camPos.x + 'px' }"
            @mousedown.prevent="startCamDrag"
          >
            <div class="imm-pip__label">
              <span class="imm-pip__drag-hint">▲ 拖动可移动</span>
              <span class="imm-pip__check">✓</span>
            </div>
            <div class="imm-pip__video-wrap">
              <video
                ref="cameraRef"
                autoplay
                muted
                playsinline
                class="imm-pip__video"
                :class="{ 'imm-pip__video--hidden': !cameraOn }"
              />
              <div v-if="!cameraOn" class="imm-pip__placeholder" @click="retryCamera" title="点击重试摄像头">
                <svg viewBox="0 0 24 24" width="48" height="48" fill="#475569">
                  <path d="M18 10.48V6c0-1.1-.9-2-2-2H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2v-4.48l4 3.98v-11l-4 3.98zM16 18H4V6h12v12z"/>
                  <path d="M2.5 3.5L1 5l19 19 1.5-1.5L2.5 3.5z" fill="#94a3b8"/>
                </svg>
                <span class="imm-pip__retry-hint">点击重试</span>
              </div>
            </div>
          </div>

          <!-- 练习模式：统一节点面板（教官提示 + 答题交互 + 超时/反馈，同一弹窗流转） -->
          <transition name="imm-fade-slide">
            <div
              v-if="trainingMode === 'practice' && nodeActive && displayNode"
              class="imm-node-panel"
              :class="{
                'imm-node-panel--timeout': showTimeoutOptions && !showNodeFeedback,
                'imm-node-panel--feedback': showNodeFeedback,
                'imm-node-panel--pass': showNodeFeedback && nodeFeedbackData?.passed,
                'imm-node-panel--fail': showNodeFeedback && nodeFeedbackData && !nodeFeedbackData.passed,
              }"
            >
              <div class="imm-node-panel__header">
                <div class="imm-node-panel__avatar">
                  <svg viewBox="0 0 24 24" width="24" height="24" fill="#fff"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 3c1.66 0 3 1.34 3 3s-1.34 3-3 3-3-1.34-3-3 1.34-3 3-3zm0 14.2c-2.5 0-4.71-1.28-6-3.22.03-1.99 4-3.08 6-3.08 1.99 0 5.97 1.09 6 3.08-1.29 1.94-3.5 3.22-6 3.22z"/></svg>
                </div>
                <div class="imm-node-panel__header-text">
                  <span class="imm-node-panel__title">AI教官提示</span>
                  <span v-if="showNodeFeedback && nodeFeedbackData" class="imm-node-panel__status">
                    {{ nodeFeedbackData.passed ? '✓ 回答正确' : '✗ 未通过' }}
                  </span>
                  <span v-else-if="showTimeoutOptions" class="imm-node-panel__status imm-node-panel__status--timeout">⏱ 本节点已超时</span>
                  <span v-else-if="nodePhase === 'observe'" class="imm-node-panel__status">观察现场</span>
                </div>
              </div>

              <!-- 阶段：答题交互（上移，优先展示） -->
              <div v-if="!showNodeFeedback && !showTimeoutOptions && nodePhase === 'interact'" class="imm-node-panel__interaction">
                <!-- 题目描述（场景，突出显示） -->
                <div class="imm-node-panel__question">
                  <p v-if="displaySceneSummary" class="imm-node-panel__question-text">{{ displaySceneSummary }}</p>
                  <p v-else-if="resolvedAiInstructorHint" class="imm-node-panel__question-text">{{ resolvedAiInstructorHint }}</p>
                  <p v-else-if="displayInstruction" class="imm-node-panel__question-text">{{ displayInstruction }}</p>
                </div>
                <div class="imm-node-panel__divider"></div>
                <div v-if="resolvedInteractionType === 'judgment'" class="imm-interaction__judge">
                  <div class="imm-interaction__title">请判断以下做法是否正确</div>
                  <div class="imm-interaction__options">
                    <button
                      v-for="(opt, oi) in resolvedJudgmentOptions"
                      :key="`${opt.label}-${oi}`"
                      class="imm-judge-btn"
                      :class="opt.label === '对' ? 'imm-judge-btn--correct' : 'imm-judge-btn--wrong'"
                      @click="submitJudge(opt.label === '对', `${opt.label}：${opt.text || opt.label}`)"
                    >
                      <span class="imm-judge-btn__icon">{{ opt.label === '对' ? '✓' : '✗' }}</span>
                      <span class="imm-judge-btn__text">{{ opt.text || opt.label }}</span>
                    </button>
                  </div>
                </div>
                <div v-else-if="resolvedInteractionType === 'choice' || resolvedInteractionType === 'prop_select'" class="imm-interaction__choice">
                  <div class="imm-interaction__title">{{ resolvedInteractionType === 'prop_select' ? '请选择正确的执法装备' : '请选择正确答案' }}</div>
                  <div class="imm-interaction__options">
                    <button
                      v-for="(opt, oi) in resolvedChoiceOptions"
                      :key="oi"
                      class="imm-choice-btn"
                      :class="{ 'imm-choice-btn--selected': choiceSelected === Number(oi) }"
                      @click="choiceSelected = Number(oi)"
                    >
                      <span class="imm-choice-btn__label">{{ opt.label || String.fromCharCode(65 + Number(oi)) }}</span>
                      <span class="imm-choice-btn__text">{{ opt.text || opt }}</span>
                    </button>
                  </div>
                  <el-button
                    v-if="choiceSelected !== null"
                    type="primary"
                    class="imm-interaction__submit"
                    @click="submitChoice"
                  >
                    确认选择
                  </el-button>
                </div>
                <div v-else class="imm-interaction__voice">
                  <p v-if="currentNode?.prop_mode === 'manual' && !propReady" class="imm-interaction__prop-hint">
                    请先在右侧虚拟道具中点击「{{ propActionLabel }}」
                  </p>
                  <div class="imm-interaction__speech-status">
                    <span class="imm-speech-dot" :class="'imm-speech-dot--' + speechStatus"></span>
                    <span>{{ resolvedSpeechStatusLabel }}</span>
                  </div>
                  <div v-if="interimText || finalText" class="imm-interaction__transcript">
                    <span v-if="finalText" class="imm-transcript-final">{{ finalText }}</span>
                    <span v-if="interimText" class="imm-transcript-interim">{{ interimText }}</span>
                  </div>
                  <div v-if="finalText" class="imm-interaction__voice-actions">
                    <el-button type="success" size="small" @click="submitActionNode">提交回答</el-button>
                  </div>
                </div>
              </div>

              <!-- 教官引导（下移到交互区后面，仅显示参考话术） -->
              <div v-if="!showNodeFeedback && nodePhase !== 'observe' && displaySpeechHint" class="imm-node-panel__hint">
                <!-- 参考话术：练习模式下直接展示，不再折叠 -->
                <div class="imm-node-panel__speech-ref imm-node-panel__speech-ref--revealed">
                  <div class="imm-node-panel__speech-ref-header">
                    <span class="imm-node-panel__speech-ref-icon">💡</span>
                    <span class="imm-node-panel__speech-ref-label">参考话术</span>
                  </div>
                  <div class="imm-node-panel__speech-ref-body">
                    <p>{{ displaySpeechHint }}</p>
                  </div>
                </div>
              </div>

              <!-- 阶段：答案反馈 -->
              <div v-if="showNodeFeedback && nodeFeedbackData" class="imm-node-panel__feedback">
                <div v-if="nodeFeedbackData.userAnswer" class="imm-node-panel__feedback-row">
                  <span>你的回答：</span>{{ nodeFeedbackData.userAnswer }}
                </div>
                <div class="imm-node-panel__feedback-row imm-node-panel__feedback-row--answer">
                  <span>正确答案：</span>{{ nodeFeedbackData.correctAnswer }}
                </div>
                <div class="imm-node-panel__feedback-row">
                  <span>解析：</span>{{ nodeFeedbackData.explanation }}
                </div>
                <div v-if="!nodeFeedbackData.passed" class="imm-node-panel__feedback-actions">
                  <el-button size="small" type="primary" @click="feedbackRetry">再试一次</el-button>
                  <el-button size="small" @click="feedbackContinue">继续下一节点</el-button>
                </div>
                <div v-else class="imm-node-panel__feedback-actions">
                  <el-button size="small" type="primary" @click="feedbackContinue">继续下一节点</el-button>
                </div>
              </div>

              <!-- 阶段：超时 -->
              <div v-else-if="showTimeoutOptions" class="imm-node-panel__timeout">
                <p class="imm-node-panel__timeout-desc">倒计时已结束，请重新练习本节点，或跳过继续后续训练。</p>
                <div class="imm-node-panel__timeout-actions">
                  <el-button type="primary" @click="retryNode">再来一次</el-button>
                  <el-button @click="skipNode('timeout')">跳过此节点</el-button>
                </div>
              </div>

              <!-- 阶段：现场观察 -->
              <div v-else-if="nodePhase === 'observe'" class="imm-node-panel__observe">
                <p class="imm-node-panel__observe-title">请先观察现场，判断局势后再作答</p>
                <p class="imm-node-panel__observe-timer">{{ observeCountdown }} 秒后开始答题</p>
                <el-button type="primary" size="small" @click="skipObservePhase">我已看清，开始答题</el-button>
              </div>

              <!-- 底部倒计时（仅答题阶段显示） -->
              <div v-if="!showNodeFeedback && !showTimeoutOptions && nodePhase === 'interact'" class="imm-node-panel__footer">
                <div class="imm-node-panel__countdown" :class="{ 'imm-node-panel__countdown--urgent': countdown <= 5 }">
                  <span class="imm-node-panel__countdown-num">{{ countdown }}s</span>
                </div>
                <div class="imm-node-panel__countdown-info">
                  <p class="imm-node-panel__countdown-main">请在倒计时内完成操作</p>
                  <p class="imm-node-panel__countdown-sub">完成后系统将展示标准答案和解析</p>
                </div>
              </div>
            </div>
          </transition>

          <!-- 考核模式：底部紧凑提示（无标准话术/操作步骤，仅显示节点名） -->
          <transition name="imm-fade-slide">
            <div v-if="trainingMode === 'exam' && nodeActive && displayNode" class="imm-bubble">
              <div class="imm-bubble__icon">
                <svg viewBox="0 0 24 24" width="36" height="36" fill="#fbbf24"><path d="M12 1L3 5v6c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V5l-9-4z"/></svg>
              </div>
              <div class="imm-bubble__content">
                <p class="imm-bubble__main">{{ displayNodeTitle }} — 请独立完成规范执法操作</p>
              </div>
            </div>
          </transition>

          <!-- ═══ 考核模式：沉浸式交互区域（判断/选择/语音） ═══ -->
          <transition name="imm-fade-slide">
            <div v-if="trainingMode === 'exam' && nodeActive && currentNode && !showNodeFeedback" class="imm-interaction">
              <!-- 题目描述 -->
              <div v-if="displayInstruction" class="imm-interaction__question">
                <p class="imm-interaction__question-text">{{ displayInstruction }}</p>
              </div>

              <!-- 判断题 -->
              <div v-if="resolvedInteractionType === 'judgment'" class="imm-interaction__judge">
                <div class="imm-interaction__title">请判断以下做法是否正确</div>
                <div class="imm-interaction__options">
                  <button
                    v-for="(opt, oi) in resolvedJudgmentOptions"
                    :key="`${opt.label}-${oi}`"
                    class="imm-judge-btn"
                    :class="opt.label === '对' ? 'imm-judge-btn--correct' : 'imm-judge-btn--wrong'"
                    @click="submitJudge(opt.label === '对', `${opt.label}：${opt.text || opt.label}`)"
                  >
                    <span class="imm-judge-btn__icon">{{ opt.label === '对' ? '✓' : '✗' }}</span>
                    <span class="imm-judge-btn__text">{{ opt.text || opt.label }}</span>
                  </button>
                </div>
              </div>

              <!-- 选择题 -->
              <div v-else-if="resolvedInteractionType === 'choice' || resolvedInteractionType === 'prop_select'" class="imm-interaction__choice">
                <div class="imm-interaction__title">{{ resolvedInteractionType === 'prop_select' ? '请选择正确的执法装备' : '请选择正确答案' }}</div>
                <div class="imm-interaction__options">
                  <button
                    v-for="(opt, oi) in resolvedChoiceOptions"
                    :key="oi"
                    class="imm-choice-btn"
                    :class="{ 'imm-choice-btn--selected': choiceSelected === Number(oi) }"
                    @click="choiceSelected = Number(oi)"
                  >
                    <span class="imm-choice-btn__label">{{ opt.label || String.fromCharCode(65 + Number(oi)) }}</span>
                    <span class="imm-choice-btn__text">{{ opt.text || opt }}</span>
                  </button>
                </div>
                <el-button
                  v-if="choiceSelected !== null"
                  type="primary"
                  class="imm-interaction__submit"
                  @click="submitChoice"
                >
                  确认选择
                </el-button>
              </div>

              <!-- 语音问答（自动开启，精简UI） -->
              <div v-else class="imm-interaction__voice">
                <div class="imm-interaction__speech-status">
                  <span class="imm-speech-dot" :class="'imm-speech-dot--' + speechStatus"></span>
                  <span>{{ resolvedSpeechStatusLabel }}</span>
                </div>
                <div v-if="interimText || finalText" class="imm-interaction__transcript">
                  <span v-if="finalText" class="imm-transcript-final">{{ finalText }}</span>
                  <span v-if="interimText" class="imm-transcript-interim">{{ interimText }}</span>
                </div>
                <div v-if="finalText" class="imm-interaction__voice-actions">
                  <el-button type="success" size="small" @click="submitActionNode">提交回答</el-button>
                </div>
              </div>
            </div>
          </transition>

          <!-- 考核模式：节点答案反馈 -->
          <transition name="imm-fade-slide">
            <div v-if="trainingMode === 'exam' && showNodeFeedback && nodeFeedbackData" class="imm-feedback" :class="nodeFeedbackData.passed ? 'imm-feedback--pass' : 'imm-feedback--fail'">
              <div class="imm-feedback__header">
                <span class="imm-feedback__icon">{{ nodeFeedbackData.passed ? '✓' : '✗' }}</span>
                <span class="imm-feedback__title">{{ nodeFeedbackData.passed ? '回答正确' : '未通过' }}</span>
              </div>
              <div class="imm-feedback__body">
                <div v-if="nodeFeedbackData.userAnswer" class="imm-feedback__row"><span>你的回答：</span>{{ nodeFeedbackData.userAnswer }}</div>
                <div class="imm-feedback__row imm-feedback__row--answer"><span>正确答案：</span>{{ nodeFeedbackData.correctAnswer }}</div>
                <div class="imm-feedback__row"><span>解析：</span>{{ nodeFeedbackData.explanation }}</div>
              </div>
              <div v-if="!nodeFeedbackData.passed" class="imm-feedback__actions">
                <el-button size="small" type="primary" @click="feedbackRetry">再试一次</el-button>
                <el-button size="small" @click="feedbackContinue">继续下一节点</el-button>
              </div>
            </div>
          </transition>

          <!-- 道具使用浮动反馈 -->
          <transition name="imm-prop-toast">
            <div v-if="immPropToast" class="imm-prop-toast">
              {{ immPropToast }}
            </div>
          </transition>

          <!-- 节点倒计时（考核模式右上角显示，练习模式已整合进统一面板） -->
          <div v-if="trainingMode === 'exam' && nodeActive && countdown > 0" class="imm-countdown-badge">
            <span class="imm-countdown-badge__label">剩余时间</span>
            <span class="imm-countdown-badge__value" :class="{ 'imm-countdown-badge__value--urgent': countdown <= 5 }">{{ countdown }}s</span>
          </div>

          <!-- Virtual Props Panel (right side) -->
          <aside class="imm-props" :class="{ 'imm-props--collapsed': immPropsCollapsed }">
            <div class="imm-props__header">
              <span class="imm-props__title">虚拟道具</span>
              <button class="imm-props__toggle" @click="immPropsCollapsed = !immPropsCollapsed">
                {{ immPropsCollapsed ? '展开' : '∧ 收起' }}
              </button>
            </div>
            <div v-show="!immPropsCollapsed" class="imm-props__list">
              <div
                v-for="prop in immersiveProps"
                :key="prop.key"
                class="imm-props__item"
                :class="{ 'imm-props__item--active': prop.key === immActiveProp }"
                @click="handlePropClick(prop)"
              >
                <div class="imm-props__item-icon">{{ prop.icon }}</div>
                <span class="imm-props__item-name">{{ prop.label }}</span>
                <span v-if="prop.key === immActiveProp" class="imm-props__item-badge">● 已选中</span>
              </div>
            </div>
            <div class="imm-props__footer">ⓘ 点击道具进行使用</div>
          </aside>

          <!-- Bottom Progress Steps (overlay on video) -->
          <div class="imm-progress">
            <div class="imm-progress__track" ref="immProgressTrackRef">
              <div
                v-for="(node, i) in video.nodes"
                :key="node.id"
                class="imm-progress__step"
                :class="{
                  'imm-progress__step--done': nodeStatuses[i] === 'pass',
                  'imm-progress__step--fail': nodeStatuses[i] === 'fail',
                  'imm-progress__step--skip': nodeStatuses[i] === 'skip' || nodeStatuses[i] === 'timeout',
                  'imm-progress__step--active': displayNodeIndex === i,
                  'imm-progress__step--locked': !nodeStatuses[i] && displayNodeIndex !== i,
                }"
                @click="handleNodeReview(i)"
              >
                <!-- 连接线 -->
                <div v-if="i > 0" class="imm-progress__line" :class="{ 'imm-progress__line--done': nodeStatuses[i - 1] === 'pass' }"></div>
                <div class="imm-progress__icon">
                  <svg v-if="nodeStatuses[i] === 'pass'" viewBox="0 0 24 24" width="18" height="18" fill="#22c55e"><path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41L9 16.17z"/></svg>
                  <svg v-else-if="nodeStatuses[i] === 'fail'" viewBox="0 0 24 24" width="18" height="18" fill="#ef4444"><path d="M18.3 5.71 12 12l6.3 6.29-1.41 1.41L10.59 13.41 4.29 19.7 2.88 18.29 9.17 12 2.88 5.71 4.29 4.3l6.3 6.29 6.3-6.29z"/></svg>
                  <svg v-else-if="nodeStatuses[i] === 'skip' || nodeStatuses[i] === 'timeout'" viewBox="0 0 24 24" width="18" height="18" fill="#f59e0b"><path d="M19 13H5v-2h14z"/></svg>
                  <span v-else-if="displayNodeIndex === i" class="imm-progress__num">{{ String(i + 1).padStart(2, '0') }}</span>
                  <svg v-else viewBox="0 0 24 24" width="16" height="16" fill="#94a3b8"><path d="M18 8h-1V6c0-2.76-2.24-5-5-5S7 3.24 7 6v2H6c-1.1 0-2 .9-2 2v10c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V10c0-1.1-.9-2-2-2zm-6 9c-1.1 0-2-.9-2-2s.9-2 2-2 2 .9 2 2-.9 2-2 2zm3.1-9H8.9V6c0-1.71 1.39-3.1 3.1-3.1 1.71 0 3.1 1.39 3.1 3.1v2z"/></svg>
                </div>
                <span class="imm-progress__label">{{ node.title || ('节点' + (i + 1)) }}</span>
                <span class="imm-progress__status">{{ nodeStatusText(i) }}</span>
              </div>
            </div>
            <button class="imm-progress__arrow" @click="scrollProgressTrack">›</button>
          </div>

          <!-- Bottom Status Bar (overlay on video) -->
          <footer class="imm-status-bar">
            <div class="imm-status-bar__left">
              <span class="imm-status-bar__label">AI识别状态</span>
              <span class="imm-status-bar__tag">（实时）</span>
            </div>
            <div class="imm-status-bar__indicators">
              <span class="imm-status-bar__indicator">
                <i class="imm-dot" :class="gestureIndicatorTone === 'is-pass' ? 'imm-dot--green' : gestureIndicatorTone === 'is-warn' ? 'imm-dot--yellow' : 'imm-dot--green'"></i>
                动作识别
                <span v-if="gestureConfidence > 0" class="imm-status-bar__confidence">{{ Math.round(gestureConfidence * 100) }}%</span>
              </span>
              <span class="imm-status-bar__indicator">
                <i class="imm-dot" :class="speechStatus === 'error' ? 'imm-dot--red' : speechStatus === 'listening' ? 'imm-dot--green' : 'imm-dot--yellow'"></i>
                语音识别
                <span class="imm-waveform">
                  <i v-for="bar in 5" :key="bar" class="imm-waveform__bar" :class="{ 'imm-waveform__bar--active': speechStatus === 'listening' && bar <= immWaveLevel }"></i>
                </span>
              </span>
              <span class="imm-status-bar__indicator">
                <i class="imm-dot" :class="nodeActive ? 'imm-dot--yellow' : 'imm-dot--green'"></i>
                流程合规
              </span>
            </div>
            <div class="imm-status-bar__actions">
              <button class="imm-status-bar__btn imm-status-bar__btn--ghost" @click="showReferenceGuide = true">
                ◎ 查看标准示范
              </button>
              <button class="imm-status-bar__btn imm-status-bar__btn--outline" @click="skipNode('skip')">
                申请跳过节点
              </button>
              <button
                class="imm-status-bar__btn imm-status-bar__btn--finish"
                :disabled="!sessionId || finishingTraining"
                @click="confirmFinishTraining"
              >
                ⚑ {{ finishingTraining ? '正在生成报告...' : '结束训练并生成评估报告' }}
              </button>
            </div>
          </footer>
        </div>

        <!-- 节点回顾弹窗 -->
        <van-popup v-model:show="immNodeReviewVisible" round position="bottom" :style="{ maxHeight: '40vh' }">
          <div class="imm-node-review" v-if="immReviewNode !== null">
            <h3>节点 {{ immReviewNode + 1 }}：{{ video.nodes[immReviewNode]?.title }}</h3>
            <div class="imm-node-review__status">
              <span v-if="nodeStatuses[immReviewNode] === 'pass'" class="imm-node-review__badge imm-node-review__badge--pass">✓ 已通过</span>
              <span v-else-if="nodeStatuses[immReviewNode] === 'fail'" class="imm-node-review__badge imm-node-review__badge--fail">未通过</span>
              <span v-else-if="nodeStatuses[immReviewNode]" class="imm-node-review__badge imm-node-review__badge--skip">{{ resultLabel(nodeStatuses[immReviewNode]) }}</span>
              <span v-else class="imm-node-review__badge">未完成</span>
            </div>
            <p class="imm-node-review__hint">{{ video.nodes[immReviewNode]?.prompt_content?.instruction || '暂无详细信息' }}</p>
          </div>
        </van-popup>
      </div>

      <!-- ========== 原三栏布局（练习模式） ========== -->
      <div v-else class="training-shell">
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
                  'is-fail': nodeStatuses[i] === 'fail',
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
            <el-button
              type="primary"
              class="training-finish-report"
              :loading="finishingTraining"
              :disabled="!sessionId"
              @click="confirmFinishTraining"
            >
              结束训练并生成评估报告
            </el-button>
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
                  <strong :class="(identityReady || presenceSupported) ? 'text-pass' : 'text-warn'">{{ identityReady ? '正常' : presenceSupported ? (singleFaceReady ? '良好' : '待优化') : '检测中' }}</strong>
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
                :poster="video?.thumbnail_url || undefined"
                preload="auto"
                @play="playbackPaused = false; markPlaybackPlaying()"
                @pause="playbackPaused = true"
                @waiting="markPlaybackWaiting()"
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
                <button class="stage-icon-btn" type="button" @click="toggleTrainingPlayback">{{ playbackPaused ? '▶' : 'Ⅱ' }}</button>
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
                    'is-fail': nodeStatuses[i] === 'fail',
                  }"
                >
                  <div class="rail-line__index">
                    <el-icon v-if="nodeStatuses[i] === 'pass'"><CircleCheck /></el-icon>
                    <el-icon v-else-if="nodeStatuses[i] === 'fail'"><CircleClose /></el-icon>
                    <el-icon v-else-if="nodeStatuses[i] === 'skip' || nodeStatuses[i] === 'timeout'"><Remove /></el-icon>
                    <span v-else>{{ i + 1 }}</span>
                  </div>
                  <div class="rail-line__body">
                    <div class="rail-line__title">节点 {{ i + 1 }}</div>
                    <div class="rail-line__name">{{ node.title || ('节点' + (i + 1)) }}</div>
                    <div class="rail-line__meta">
                      <span>{{ nodeStatusText(i) }}</span>
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

                <div v-if="trainingMode === 'practice' && displayStandardPoints.length" class="task-panel__section">
                  <div class="task-panel__label">评分要点</div>
                  <div class="standard-point-list">
                    <span v-for="point in displayStandardPoints" :key="point" class="standard-point">{{ point }}</span>
                  </div>
                </div>

                <div v-if="trainingMode === 'practice' && (displayRiskSignals.length || displayLawPoints.length)" class="task-panel__section">
                  <div class="task-panel__label">现场风险与程序要点</div>
                  <div v-if="displayRiskSignals.length" class="standard-point-list">
                    <span v-for="point in displayRiskSignals" :key="`risk-${point}`" class="standard-point standard-point--risk">{{ point }}</span>
                  </div>
                  <div v-if="displayLawPoints.length" class="standard-point-list standard-point-list--stacked">
                    <span v-for="point in displayLawPoints" :key="`law-${point}`" class="standard-point standard-point--law">{{ point }}</span>
                  </div>
                </div>

                <div v-if="trainingMode === 'practice' && displaySpeechHint" class="task-panel__section">
                  <div class="task-panel__label">标准话术参考</div>
                  <div class="task-panel__quote">{{ displaySpeechHint }}</div>
                </div>

                <div v-if="trainingMode === 'practice' && displayGestureHint" class="task-panel__section">
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
                  <div v-if="resolvedInteractionType === 'voice_qa' || resolvedInteractionType === 'action'" class="task-speech-box">
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

                  <div v-else-if="resolvedInteractionType === 'judgment'" class="judge-row judge-row--panel">
                    <el-button type="success" size="large" @click="submitJudge(true, '正确')">正确</el-button>
                    <el-button type="danger" size="large" @click="submitJudge(false, '错误')">错误</el-button>
                  </div>

                  <div v-else-if="resolvedInteractionType === 'choice' || resolvedInteractionType === 'prop_select'" class="choice-panel">
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
                        v-for="(opt, oi) in resolvedChoiceOptions"
                        :key="oi"
                        class="choice-item"
                        :class="{ selected: choiceSelected === Number(oi) }"
                        @click="choiceSelected = Number(oi)"
                      >
                        <span class="choice-alpha">{{ opt.label || String.fromCharCode(65 + Number(oi)) }}</span>
                        {{ opt.text || opt }}
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
                    <el-button size="small" @click="retryNode">再来一次</el-button>
                    <el-button size="small" type="warning" @click="skipNode('skip')">跳过此节点</el-button>
                  </div>

                  <!-- 训练模式：节点完成后的答案反馈面板 -->
                  <div v-if="showNodeFeedback && nodeFeedbackData" class="node-feedback-panel" :class="nodeFeedbackData.passed ? 'node-feedback-panel--pass' : 'node-feedback-panel--fail'">
                    <div class="node-feedback-panel__header">
                      <span class="node-feedback-panel__icon">{{ nodeFeedbackData.passed ? '✓' : '✗' }}</span>
                      <span class="node-feedback-panel__title">{{ nodeFeedbackData.passed ? '回答正确' : '未通过' }} - {{ nodeFeedbackData.nodeTitle }}</span>
                    </div>
                    <div class="node-feedback-panel__body">
                      <div v-if="nodeFeedbackData.userAnswer" class="node-feedback-panel__row">
                        <span class="node-feedback-panel__label">你的回答：</span>
                        <span>{{ nodeFeedbackData.userAnswer }}</span>
                      </div>
                      <div class="node-feedback-panel__row node-feedback-panel__row--answer">
                        <span class="node-feedback-panel__label">正确答案：</span>
                        <span>{{ nodeFeedbackData.correctAnswer }}</span>
                      </div>
                      <div class="node-feedback-panel__row">
                        <span class="node-feedback-panel__label">解析：</span>
                        <span>{{ nodeFeedbackData.explanation }}</span>
                      </div>
                    </div>
                    <div v-if="!nodeFeedbackData.passed" class="node-feedback-panel__actions">
                      <el-button size="small" type="primary" @click="feedbackRetry">再试一次（扣{{ currentNode?.retry_score_deduct || 2 }}分）</el-button>
                      <el-button size="small" @click="feedbackContinue">继续下一节点</el-button>
                    </div>
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
import { useRoute, useRouter, onBeforeRouteLeave } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  ArrowLeft, Timer, CircleCheck, CircleClose, Remove,
  Microphone, Check,
} from '@element-plus/icons-vue'
import request from '../utils/request'
import { usePresenceMonitor } from '../composables/usePresenceMonitor'
import { useFaceIdentityVerify } from '../composables/useFaceIdentityVerify'
import { useGestureDetector } from '../composables/useGestureDetector'
import { useSegmentedVideoPlayback } from '../composables/useSegmentedVideoPlayback'
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
  thumbnail_url?: string
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

// 鈹€鈹€ 瑙嗛 & Session 鈹€鈹€
const video = ref<VideoDetail | null>(null)
const loading = ref(true)
const sessionId = ref<number | null>(null)
const trainingMode = ref<'practice' | 'exam'>(
  (route.query.mode === 'exam' ? 'exam' : 'practice') as 'practice' | 'exam'
)
const immersiveMode = computed(() => true)
const immPropsCollapsed = ref(false)
const immActiveProp = ref('badge')
const immersiveProps = ref([
  { key: 'badge', label: '执法证', icon: '🪪' },
  { key: 'cuffs', label: '手铐', icon: '⛓️' },
  { key: 'radio', label: '对讲机', icon: '📻' },
  { key: 'notebook', label: '笔录本', icon: '📓' },
])

// -- Immersive enhanced state --
const immPropToast = ref('')
const immCurrentScore = ref(0)
const immDeducted = ref(0)
const immWaveLevel = ref(0)
const immNodeReviewVisible = ref(false)
const immReviewNode = ref<number | null>(null)
const immProgressTrackRef = ref<HTMLElement | null>(null)
let immWaveTimer: ReturnType<typeof setInterval> | null = null

// Simulate waveform when speech is active
function startWaveSimulation() {
  if (immWaveTimer) return
  immWaveTimer = setInterval(() => {
    immWaveLevel.value = speechStatus.value === 'listening' ? Math.floor(Math.random() * 5) + 1 : 0
  }, 150)
}

function stopWaveSimulation() {
  if (immWaveTimer) { clearInterval(immWaveTimer); immWaveTimer = null }
  immWaveLevel.value = 0
}

function normalizeInteractionType(raw?: string | null) {
  const value = String(raw || 'voice_qa').trim()
  if (value === 'judge') return 'judgment'
  return value
}

type ChoiceOption = { label: string; text: string }

function normalizeChoiceOption(opt: unknown, index: number): ChoiceOption {
  if (typeof opt === 'string') {
    const trimmed = opt.trim()
    const match = trimmed.match(/^([A-Za-z])[.、:：)\]]\s*(.+)$/) || trimmed.match(/^([A-Za-z])\s+(.+)$/)
    if (match) {
      return { label: match[1].toUpperCase(), text: match[2].trim() }
    }
    return { label: String.fromCharCode(65 + index), text: trimmed }
  }
  if (opt && typeof opt === 'object') {
    const item = opt as Record<string, unknown>
    const label = String(item.label ?? item.value ?? '').trim()
    const text = String(item.text ?? item.content ?? item.description ?? '').trim()
    if (label && text) return { label, text }
    if (text) return { label: label || String.fromCharCode(65 + index), text }
    if (label) return { label, text: label }
  }
  return { label: String.fromCharCode(65 + index), text: String(opt ?? '').trim() }
}

function readRawChoiceOptions(node: VideoNode | null | undefined): unknown[] {
  if (!node) return []
  const direct = (node as VideoNode & { choice_options?: unknown }).choice_options
  if (Array.isArray(direct) && direct.length) return direct
  if (typeof direct === 'string' && direct.trim()) {
    try {
      const parsed = JSON.parse(direct)
      if (Array.isArray(parsed)) return parsed
    } catch {
      // ignore malformed JSON
    }
  }
  const configOptions = node.node_config?.options
  if (Array.isArray(configOptions)) return configOptions
  return []
}

function isTrueJudgmentOptions(options: ChoiceOption[]): boolean {
  if (options.length !== 2) return false
  const labels = new Set(options.map((item) => item.label))
  return labels.has('对') && labels.has('错')
}

function resolveInteractionTypeForNode(node: VideoNode | null | undefined): string {
  if (!node) return 'voice_qa'
  const declared = normalizeInteractionType(
    (node as VideoNode & { node_interaction_type?: string }).node_interaction_type || node.node_type,
  )
  if (declared !== 'judgment') return declared

  const options = readRawChoiceOptions(node)
    .map((opt, index) => normalizeChoiceOption(opt, index))
    .filter((item) => item.text || item.label)
  if (!options.length || isTrueJudgmentOptions(options)) return 'judgment'
  return 'choice'
}

function resolveRequiredPropKey() {
  const node = currentNode.value
  if (!node) return null
  const explicit = node.node_config?.required_prop_key || node.prompt_content?.prop_key
  if (explicit) return String(explicit)
  const label = propActionLabel.value
  if (label.includes('证')) return 'badge'
  if (label.includes('对讲') || label.includes('电台')) return 'radio'
  if (label.includes('笔录') || label.includes('记录')) return 'notebook'
  if (label.includes('手铐') || label.includes('约束')) return 'cuffs'
  if (node.required_gesture === 'show_id') return 'badge'
  return null
}

function getObserveSeconds(node: VideoNode) {
  const configured = Number(node.node_config?.observe_seconds ?? 0)
  if (configured > 0) return configured
  if (resolveInteractionTypeForNode(node) === 'judgment') {
    return trainingMode.value === 'practice' ? 10 : 0
  }
  return 0
}

function getNextPendingNodeTitle() {
  const nodes = video.value?.nodes || []
  for (let i = 0; i < nodes.length; i += 1) {
    if (nodeStatuses.value[i] === undefined) return nodes[i]?.title || `节点 ${i + 1}`
  }
  return ''
}

function announceNextNode() {
  const nextTitle = getNextPendingNodeTitle()
  if (nextTitle) {
    ElMessage.success(`即将进入下一环节：${nextTitle}`)
  } else {
    ElMessage.success('所有节点已完成，训练即将结束')
  }
}

function handlePropClick(prop: { key: string; label: string }) {
  immActiveProp.value = prop.key
  const requiredKey = resolveRequiredPropKey()
  const manualPropNode = Boolean(nodeActive.value && currentNode.value?.prop_mode === 'manual')

  if (manualPropNode) {
    if (!requiredKey || requiredKey === prop.key) {
      propReady.value = true
      propActivatedAt.value = Date.now()
      immPropToast.value = `${prop.label}已取出，请继续完成话术与动作`
    } else {
      const requiredLabel = immersiveProps.value.find((item) => item.key === requiredKey)?.label || propActionLabel.value
      immPropToast.value = `当前节点需使用：${requiredLabel}`
      ElMessage.warning(`请先选择：${requiredLabel}`)
      window.setTimeout(() => { immPropToast.value = '' }, 2200)
      return
    }
  } else {
    immPropToast.value = `已出示：${prop.label}`
  }

  window.setTimeout(() => { immPropToast.value = '' }, 2200)
}

function handleNodeReview(index: number) {
  if (!nodeStatuses.value[index]) return
  immReviewNode.value = index
  immNodeReviewVisible.value = true
}

function scrollProgressTrack() {
  if (immProgressTrackRef.value) {
    immProgressTrackRef.value.scrollBy({ left: 240, behavior: 'smooth' })
  }
}

function toggleFullscreen() {
  if (!document.fullscreenElement) {
    document.documentElement.requestFullscreen?.()
  } else {
    document.exitFullscreen?.()
  }
}
const showBriefing = ref(false)
const briefingStep = ref(1)
const briefingIdentityPassed = ref(false)
const finishingTraining = ref(false)
let playbackWarningShown = false
let playAttempt: Promise<void> | null = null

// 鈹€鈹€ 鑺傜偣鐘舵€?鈹€鈹€
const currentNodeIndex = ref(-1)
const nodeActive = ref(false)
const nodeStatuses = ref<Record<number, string>>({})
const nodeResult = ref<'pass' | 'fail' | null>(null)
const showTimeoutOptions = ref(false)
const showReferenceGuide = ref(false)
const countdown = ref(0)
const nodePhase = ref<'observe' | 'interact'>('interact')
const observeCountdown = ref(0)
const nodeRetryCount = ref(0)
const showSpeechHintRevealed = ref(false)
const nodeStartTime = ref(0)
const interruptionReason = ref<'device' | 'identity' | null>(null)
const interruptionMessage = ref('')
const propReady = ref(false)
const propActivatedAt = ref<number | null>(null)
let countdownTimer: ReturnType<typeof setInterval> | null = null
let observeTimer: ReturnType<typeof setInterval> | null = null
let passContinueTimer: ReturnType<typeof setTimeout> | null = null
let interruptionViolationKey = ''

// 考核模式总时间 & 训练模式答案展示
const examTotalCountdown = ref(0)
let examTimer: ReturnType<typeof setInterval> | null = null
const showNodeFeedback = ref(false)
const nodeFeedbackData = ref<{
  passed: boolean
  correctAnswer: string
  explanation: string
  userAnswer: string
  nodeTitle: string
} | null>(null)

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
const faceCanvasRef = ref<HTMLCanvasElement | null>(null)
const videoWrapRef = ref<HTMLElement | null>(null)
const playbackCurrentTime = ref(0)
const playbackPaused = ref(true)
const cameraOn = ref(false)
const camPos = ref({ x: 16, y: 80 })
const deviceReady = ref(false)
const deviceWarningText = ref('')
let cameraStream: MediaStream | null = null
const {
  state: playbackState,
  attach: attachPlayback,
  markPlaying: markPlaybackPlaying,
  markWaiting: markPlaybackWaiting,
} = useSegmentedVideoPlayback(videoRef)
let playbackPreparePromise: Promise<void> | null = null

const {
  status: presenceStatus,
  message: presenceMessage,
  faceCount,
  supported: presenceSupported,
  singleFaceReady,
  liveReady,
  lastMotion,
  preload: preloadPresenceMonitor,
  attachVideo: attachPresenceVideo,
  stop: stopPresenceMonitor,
} = usePresenceMonitor()

const {
  registered: faceProfileRegistered,
  verified: faceIdentityVerified,
  verifying: faceIdentityVerifying,
  terminated: faceIdentityTerminated,
  statusText: faceIdentityStatusText,
  similarityText: faceIdentitySimilarityText,
  startVerify: startFaceIdentityVerify,
  startHeartbeat: startFaceIdentityHeartbeat,
  beginVideoSessionMonitoring,
  fetchProfileStatus,
  stop: stopFaceIdentityVerify,
} = useFaceIdentityVerify()

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
const speechSupported = computed(() => Boolean(speechProvider.value?.isSupported()))
const identityReady = computed(() =>
  Boolean(
    faceProfileRegistered.value
    && faceIdentityVerified.value,
  ),
)
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
  if (currentNode.value?.node_type === 'voice_qa' || currentNode.value?.node_interaction_type === 'voice_qa' || currentNode.value?.required_keywords?.length) return 'speech_only'
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
const resolvedFaceMatchText = computed(() => {
  if (!faceProfileRegistered.value) return '未注册档案'
  if (identityReady.value) return faceIdentitySimilarityText.value || '本人匹配'
  if (faceIdentityVerifying.value) {
    return faceIdentitySimilarityText.value || faceIdentityStatusText.value || '比对中'
  }
  return '待匹配'
})
const deviceStatusText = computed(() => {
  if (deviceReady.value) return '摄像头、麦克风已就绪'
  return deviceWarningText.value || '正在检查设备权限'
})
const canStartTraining = computed(() => deviceReady.value && (identityReady.value || briefingIdentityPassed.value))
const resolvedIdentityStatusText = computed(() => {
  if (!faceProfileRegistered.value) return '请先注册人脸档案'
  if (faceIdentityVerifying.value) return faceIdentityStatusText.value || '正在通过后端比对人脸'
  if (!faceIdentityVerified.value) return faceIdentityStatusText.value || '正在启动后端人脸识别'
  return '本人身份核验通过'
})
const identityBannerClass = computed(() => {
  if (!faceProfileRegistered.value) return 'is-warn'
  return identityReady.value ? 'is-pass' : 'is-checking'
})
const identityBannerText = computed(() => {
  if (!faceProfileRegistered.value) return '身份校验：待注册人脸档案'
  if (identityReady.value) return '人脸校验：已通过'
  return '人脸校验：校验中'
})
const identityBannerIcon = computed(() => {
  if (!faceProfileRegistered.value) return '!'
  return identityReady.value ? '✓' : '…'
})
const resolvedFaceCountText = computed(() => {
  if (identityReady.value) return '已通过'
  if (!presenceSupported.value && faceIdentityVerifying.value) return '后端识别中'
  if (presenceStatus.value === 'loading') return '模型加载中'
  if (!presenceSupported.value) return '后端校验'
  if (!faceCount.value) return '未检测到人脸'
  if (faceCount.value === 1) return '已检测到人脸'
  return `${faceCount.value} 人入镜`
})
const resolvedLiveMotionText = computed(() => {
  if (identityReady.value) return '已通过'
  if (!presenceSupported.value && faceIdentityVerifying.value) return '比对中'
  if (presenceStatus.value === 'loading') return '等待模型就绪'
  if (!presenceSupported.value) return '已跳过'
  if (liveReady.value) return '动作已识别'
  if (singleFaceReady.value) return '请轻微转头或眨眼'
  const motionLevel = Number(lastMotion.value || 0)
  return motionLevel > 0 ? '正在识别动作' : '等待轻微动作'
})
const resolvedPrecheckHintText = computed(() => {
  const hints = [deviceWarningText.value]
  if (!faceProfileRegistered.value) {
    hints.unshift('请先在个人设置中上传本人正脸照片以完成身份核验')
  } else if (!identityReady.value) {
    hints.unshift(resolvedIdentityStatusText.value)
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
  return faceIdentityStatusText.value || '请正对摄像头并重新完成本人身份核验。'
})
const canResumeInterruptedNode = computed(() =>
  Boolean(trainingInterrupted.value && deviceReady.value && identityReady.value),
)
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
  // 考核模式：显示总考核剩余时间
  if (trainingMode.value === 'exam' && examTotalCountdown.value > 0) {
    return formatTime(examTotalCountdown.value)
  }
  // 节点激活时：显示节点倒计时
  if (nodeActive.value && countdown.value > 0) return `00:${String(countdown.value).padStart(2, '0')}`
  // 非节点时：显示节点进度
  return `${completedCount.value}/${video.value?.nodes?.length || 0} 完成`
})
const displayInstruction = computed(() =>
  displayNode.value?.prompt_content?.police_question
  || displayNode.value?.prompt_content?.instruction
  || displayNode.value?.node_config?.question
  || (nodeActive.value
    ? '当前训练节点缺少任务说明，请联系管理员重新分析或编辑该视频节点。'
    : `视频播放至 ${formatTime(Number(displayNode.value?.trigger_time || 0))} 后将自动进入本节点。`),
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
// 新增：使用数据库中的 ai_instructor_hint 字段
const resolvedAiInstructorHint = computed(() =>
  displayNode.value?.ai_instructor_hint || '',
)
// 新增：使用 node_interaction_type 字段，回退到 node_type
const resolvedInteractionType = computed(() => resolveInteractionTypeForNode(currentNode.value))
// 从 choice_options / node_config.options 获取并规范化选项
const resolvedChoiceOptions = computed(() => {
  const node = currentNode.value
  if (!node) return []
  return readRawChoiceOptions(node)
    .map((opt, index) => normalizeChoiceOption(opt, index))
    .filter((item) => item.text || item.label)
})
const resolvedJudgmentOptions = computed(() => {
  const options = resolvedChoiceOptions.value
  if (isTrueJudgmentOptions(options)) return options
  return [
    { label: '对', text: '正确' },
    { label: '错', text: '错误' },
  ]
})
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
      currentNode.value?.node_interaction_type === 'voice_qa' ||
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
  (currentNode.value.node_interaction_type === 'action' || currentNode.value.node_interaction_type === 'voice_qa' || currentNode.value.node_interaction_type === 'prop_select' || currentNode.value.node_type === 'action' || currentNode.value.node_type === 'voice_qa')
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
  await fetchProfileStatus()
  if (video.value) {
    showBriefing.value = true
    void preloadPresenceMonitor()
    await nextTick()
    await startCamera()
    setupVisibilityDetection()
    startWaveSimulation()
  }
})

watch([showBriefing, briefingStep, cameraOn], async ([briefing, step, cameraReady]) => {
  if (!briefing || step !== 1 || !cameraReady) return
  await bindBriefingCameraIfNeeded()
})

watch(
  [showBriefing, briefingStep, cameraOn, faceIdentityVerified, faceProfileRegistered],
  async ([briefing, step, cameraReady, identityOk, profileReady]) => {
    if (!briefing || step !== 1 || !cameraReady || !profileReady || identityOk) return
    await nextTick()
    const videoEl = briefingCameraRef.value
    const canvasEl = faceCanvasRef.value
    if (!videoEl || !canvasEl || faceIdentityVerifying.value) return
    await startFaceIdentityVerify({
      video: videoEl,
      canvas: canvasEl,
      mode: 'me',
      requireRegistered: true,
    })
  },
)

watch(identityReady, (ready) => {
  if (showBriefing.value && briefingStep.value === 1 && ready) {
    briefingIdentityPassed.value = true
  }
})

watch(faceIdentityTerminated, (terminated) => {
  if (!terminated || showBriefing.value) return
  pauseNodeForInterruption('identity', '训练过程中人脸验证连续异常')
})

watch(
  [nodeActive, showBriefing, deviceReady, identityReady, faceIdentityStatusText, deviceWarningText],
  ([active, briefing, deviceOk, identityOk, identityText, deviceText]) => {
    if (!active || briefing || nodeSubmitting.value) return
    if (!deviceOk) {
      pauseNodeForInterruption('device', String(deviceText || '训练过程中检测到摄像头或麦克风异常'))
      return
    }
    if (!identityOk) {
      pauseNodeForInterruption('identity', String(identityText || '训练过程中身份校验未通过'))
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
    void attachPresenceVideo(cameraRef.value)
    await attachGestureVideo(cameraRef.value)
  } else {
    await bindTrainingCameraIfNeeded()
  }
  await initSession()
  if (sessionId.value && cameraRef.value && faceCanvasRef.value) {
    beginVideoSessionMonitoring(sessionId.value, cameraRef.value, faceCanvasRef.value)
  }
  if (trainingMode.value === 'exam') {
    startExamTimer()
  }
  await playTrainingVideo()
}

// 路由离开时立即释放摄像头和麦克风（不等过渡动画结束）
onBeforeRouteLeave((_to, _from, next) => {
  stopCamera()
  stopPresenceMonitor()
  stopFaceIdentityVerify()
  stopGestureDetection()
  speechProvider.value?.stop()
  stopWaveSimulation()
  next()
})

onUnmounted(() => {
  stopCamera()
  stopPresenceMonitor()
  stopFaceIdentityVerify()
  stopGestureDetection()
  clearCountdown()
  clearChoiceTimer()
  clearExamTimer()
  speechProvider.value?.stop()
  stopWaveSimulation()
  document.removeEventListener('visibilitychange', onVisibilityChange)
})

// 鈹€鈹€ 鏁版嵁鍔犺浇 鈹€鈹€
async function fetchVideo() {
  loading.value = true
  try {
    const res: any = await request.get(`/videos/${videoId}`)
    video.value = res
    await nextTick()
    playbackPreparePromise = attachPlayback(videoId, String(res.video_url || ''))
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
  // 检查安全上下文（非 localhost + 非 HTTPS 时 getUserMedia 不可用）
  if (!window.isSecureContext) {
    deviceReady.value = false
    deviceWarningText.value = '当前访问地址不支持摄像头（需要 HTTPS 或 localhost），请使用 localhost 访问'
    ElMessage.warning('摄像头需要安全上下文（HTTPS 或 localhost）才能使用')
    cameraOn.value = false
    speechProvider.value = createSpeechProvider()
    return
  }
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    deviceReady.value = false
    deviceWarningText.value = '当前浏览器不支持摄像头 API'
    ElMessage.warning('浏览器不支持摄像头，请使用最新版 Chrome / Edge')
    cameraOn.value = false
    speechProvider.value = createSpeechProvider()
    return
  }
  try {
    cameraStream = await navigator.mediaDevices.getUserMedia({
      video: {
        width: { ideal: 640, max: 960 },
        height: { ideal: 480, max: 720 },
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
    await bindBriefingCameraIfNeeded()
    await bindTrainingCameraIfNeeded()
    if (cameraRef.value) {
      await bindCameraStream(cameraRef.value)
      if (!showBriefing.value) {
        void attachPresenceVideo(cameraRef.value)
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
  } catch (err: any) {
    deviceReady.value = false
    const errName = err?.name || ''
    const errMsg = err?.message || ''
    if (errName === 'NotAllowedError') {
      deviceWarningText.value = '摄像头/麦克风权限被拒绝，请在浏览器地址栏左侧点击锁图标开启权限后刷新'
      ElMessage.warning('摄像头权限被拒绝，请在地址栏左侧开启摄像头权限')
    } else if (errName === 'NotFoundError' || errName === 'DevicesNotFoundError') {
      deviceWarningText.value = '未检测到摄像头或麦克风设备，请确认已连接'
      ElMessage.warning('未检测到摄像头设备')
    } else if (errName === 'NotReadableError' || errName === 'TrackStartError') {
      deviceWarningText.value = '摄像头可能被其他应用占用，请关闭其他使用摄像头的程序后重试'
      ElMessage.warning('摄像头被占用，请关闭其他程序后重试')
    } else {
      deviceWarningText.value = `摄像头启动失败：${errMsg || errName || '未知错误'}，请检查浏览器设置`
      ElMessage.warning('无法获取摄像头和麦克风，AI识别不可用')
    }
    console.warn('[Camera] startCamera failed:', errName, errMsg, err)
    cameraOn.value = false
    speechProvider.value = createSpeechProvider()
  }
}

function stopCamera() {
  // 先停止所有底层 track（摄像头 + 麦克风），确保即使 DOM 元素已销毁也能释放硬件
  if (cameraStream) {
    cameraStream.getTracks().forEach(t => t.stop())
  }
  if (briefingCameraRef.value?.srcObject) {
    const s = briefingCameraRef.value.srcObject as MediaStream
    if (s !== cameraStream) {
      s.getTracks().forEach(t => t.stop())
    }
    briefingCameraRef.value.srcObject = null
  }
  if (cameraRef.value?.srcObject) {
    const s = cameraRef.value.srcObject as MediaStream
    if (s !== cameraStream) {
      s.getTracks().forEach(t => t.stop())
    }
    cameraRef.value.srcObject = null
  }
  cameraStream = null
  cameraOn.value = false
}

async function retryCamera() {
  // 先停掉旧的（如果有）
  if (cameraStream) {
    cameraStream.getTracks().forEach(t => t.stop())
    cameraStream = null
  }
  cameraOn.value = false
  await nextTick()
  await startCamera()
  await nextTick()
  await bindBriefingCameraIfNeeded()
  if (cameraOn.value && cameraRef.value) {
    await bindCameraStream(cameraRef.value)
    void attachPresenceVideo(cameraRef.value)
    await attachGestureVideo(cameraRef.value)
  }
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
  playbackPaused.value = false
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
  markUnfinishedNodesAsSkipped()
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

async function bindBriefingCameraIfNeeded(retryCount = 0) {
  if (!showBriefing.value || briefingStep.value !== 1 || !cameraStream) return
  await nextTick()
  const videoEl = briefingCameraRef.value
  if (!videoEl) {
    if (retryCount < 8) {
      window.setTimeout(() => {
        void bindBriefingCameraIfNeeded(retryCount + 1)
      }, 120)
    }
    return
  }
  await bindCameraStream(videoEl)
  void attachPresenceVideo(videoEl)
}

async function onBriefingOpened() {
  await bindBriefingCameraIfNeeded()
}

async function bindTrainingCameraIfNeeded(retryCount = 0) {
  if (!cameraStream || showBriefing.value) return
  await nextTick()
  const videoEl = cameraRef.value
  if (!videoEl) {
    if (retryCount < 8) {
      window.setTimeout(() => {
        void bindTrainingCameraIfNeeded(retryCount + 1)
      }, 120)
    }
    return
  }
  await bindCameraStream(videoEl)
  void attachPresenceVideo(videoEl)
  await attachGestureVideo(videoEl)
}

async function playTrainingVideo() {
  if (!videoRef.value) return
  if (playAttempt) return playAttempt
  const videoEl = videoRef.value
  playAttempt = (async () => {
    try {
      if (playbackPreparePromise) await playbackPreparePromise
      await videoEl.play()
      playbackPaused.value = false
      playbackWarningShown = false
    } catch (error) {
      playbackPaused.value = true
      console.warn('Training video play failed', error)
      if (!playbackWarningShown) {
        playbackWarningShown = true
        ElMessage.warning('视频未能开始播放，请检查网络后点击播放按钮重试')
      }
    } finally {
      playAttempt = null
    }
  })()
  return playAttempt
}

async function toggleTrainingPlayback() {
  if (!videoRef.value || nodeActive.value) return
  if (videoRef.value.paused) {
    await playTrainingVideo()
  } else {
    videoRef.value.pause()
    playbackPaused.value = true
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
  const resumeType = resolveInteractionTypeForNode(currentNode.value)
  if ((resumeType === 'choice' || resumeType === 'prop_select') && choiceTimeLimit.value > 0 && choiceTimeLeft.value > 0) {
    startChoiceTimer()
  }
  void restartGestureDetection()
  if (resumeType === 'voice_qa' || resumeType === 'action') {
    void startSpeech(!isPoliceTrainingNode(currentNode.value))
  }
}

// 节点触发
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
  showNodeFeedback.value = false
  nodeFeedbackData.value = null
  choiceSelected.value = null
  interimText.value = ''
  finalText.value = ''
  manualSpeechText.value = ''
  nodeRetryCount.value = 0
  showSpeechHintRevealed.value = false
  nodeStartTime.value = Date.now()
  nodePhase.value = 'interact'
  observeCountdown.value = 0
  clearObservePhase()
  clearPassContinueTimer()

  const node = video.value!.nodes[index]
  void setTargetGesture(node.required_gesture || null, node.prompt_content?.gesture_config || null)
  if (node.prop_mode !== 'manual') {
    propReady.value = true
    propActivatedAt.value = Date.now()
  }

  const observeSeconds = getObserveSeconds(node)
  if (observeSeconds > 0) {
    nodePhase.value = 'observe'
    observeCountdown.value = observeSeconds
    if (node.pause_mode === 'light_motion') {
      void playTrainingVideo()
    } else {
      videoRef.value?.pause()
    }
    ElMessage.info(`请先观察现场，${observeSeconds} 秒后开始答题`)
    startObservePhase(node)
    return
  }

  if (node.pause_mode === 'light_motion') {
    void playTrainingVideo()
  } else {
    videoRef.value?.pause()
  }
  beginNodeInteraction(node)
}

function startObservePhase(node: VideoNode) {
  clearObservePhase()
  observeTimer = setInterval(() => {
    observeCountdown.value -= 1
    if (observeCountdown.value <= 0) {
      clearObservePhase()
      beginNodeInteraction(node)
    }
  }, 1000)
}

function clearObservePhase() {
  if (observeTimer) {
    clearInterval(observeTimer)
    observeTimer = null
  }
}

function clearPassContinueTimer() {
  if (passContinueTimer) {
    clearTimeout(passContinueTimer)
    passContinueTimer = null
  }
}

function skipObservePhase() {
  if (nodePhase.value !== 'observe' || !currentNode.value) return
  clearObservePhase()
  observeCountdown.value = 0
  beginNodeInteraction(currentNode.value)
}

function beginNodeInteraction(node: VideoNode) {
  nodePhase.value = 'interact'
  if (node.pause_mode !== 'light_motion') {
    videoRef.value?.pause()
  }
  countdown.value = node.timeout_seconds
  startCountdown()

  clearChoiceTimer()
  const interactionType = resolveInteractionTypeForNode(node)
  if (interactionType === 'choice' || interactionType === 'prop_select') {
    const tl = Number(node.node_config?.time_limit ?? 0)
    choiceTimeLimit.value = tl
    choiceTimeLeft.value = tl
    if (tl > 0) startChoiceTimer()
  } else {
    choiceTimeLimit.value = 0
    choiceTimeLeft.value = 0
  }

  if (interactionType === 'voice_qa' || interactionType === 'action') {
    window.setTimeout(() => {
      void startSpeech(!isPoliceTrainingNode(node))
    }, 260)
  }
}

function handleNodeTimeout() {
  if (!nodeActive.value || showNodeFeedback.value || showTimeoutOptions.value) return
  clearCountdown()
  clearObservePhase()
  speechProvider.value?.stop()
  countdown.value = 0
  if (trainingMode.value === 'exam') {
    void skipNode('timeout')
    return
  }
  showTimeoutOptions.value = true
  ElMessage.warning('本节点已超时，请选择重新练习或跳过')
}

function startCountdown() {
  clearCountdown()
  countdownTimer = setInterval(() => {
    if (countdown.value <= 1) {
      handleNodeTimeout()
      return
    }
    countdown.value -= 1
  }, 1000)
}

function clearCountdown() {
  if (countdownTimer) { clearInterval(countdownTimer); countdownTimer = null }
}

function startExamTimer() {
  clearExamTimer()
  // 考核总时间 = 每个节点时间之和，或视频时长的1.5倍（取较小值），最少3分钟
  const nodeTimeSum = (video.value?.nodes || []).reduce((sum: number, n: any) => sum + (n.timeout_seconds || 30), 0)
  const videoDuration = Number(video.value?.duration || 0)
  const totalTime = Math.max(180, Math.min(nodeTimeSum + 30, Math.round(videoDuration * 1.5)))
  examTotalCountdown.value = totalTime
  examTimer = setInterval(() => {
    examTotalCountdown.value--
    if (examTotalCountdown.value <= 0) {
      clearExamTimer()
      // 考核时间到，强制结束
      ElMessage.error('考核时间已到，训练自动结束')
      void finishTrainingSession()
    }
  }, 1000)
}

function clearExamTimer() {
  if (examTimer) { clearInterval(examTimer); examTimer = null }
}

async function finishTrainingSession() {
  clearExamTimer()
  clearCountdown()
  clearObservePhase()
  clearPassContinueTimer()
  clearChoiceTimer()
  stopSpeech()
  stopGestureDetection()
  if (nodeActive.value) {
    nodeActive.value = false
    nodeStatuses.value[currentNodeIndex.value] = nodeStatuses.value[currentNodeIndex.value] || 'timeout'
  }
  await finishTraining()
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
      showSpeechHintRevealed.value = true
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

  if (trainingMode.value === 'exam') {
    // ═══ 考核模式：通过/未通过都不显示答案，直接继续 ═══
    nodeStatuses.value[currentNodeIndex.value] = result === 'pass' ? 'pass' : 'fail'
    window.setTimeout(() => {
      stopGestureDetection()
      nodeActive.value = false
      nodeResult.value = null
      nodeFailureReasons.value = []
      nodeSemanticFeedback.value = null
      nodeSubmitting.value = false
      void playTrainingVideo()
      checkAllNodesDone()
    }, 800)
    return
  }

  // ═══ 训练模式：显示结果+答案解释 ═══
  if (result === 'pass') {
    nodeStatuses.value[currentNodeIndex.value] = 'pass'
    // 训练模式通过：显示答案和解释，然后继续
    _showFeedbackPanel(true, extra)
    clearPassContinueTimer()
    passContinueTimer = window.setTimeout(() => {
      passContinueTimer = null
      showNodeFeedback.value = false
      nodeFeedbackData.value = null
      stopGestureDetection()
      nodeActive.value = false
      nodeResult.value = null
      nodeFailureReasons.value = []
      nodeSemanticFeedback.value = null
      nodeSubmitting.value = false
      announceNextNode()
      void playTrainingVideo()
      checkAllNodesDone()
    }, 3500)
    return
  }

  // 训练模式未通过：显示答案+解释+重试/跳过选项
  _showFeedbackPanel(false, extra)
  nodeSubmitting.value = false
}

function _showFeedbackPanel(passed: boolean, extra: Record<string, any> = {}) {
  const node = currentNode.value
  if (!node) return
  const interactionType = resolveInteractionTypeForNode(node)
  let correctAnswer = ''
  let explanation = ''
  let userAnswer = ''

  if (interactionType === 'choice' || interactionType === 'judgment' || interactionType === 'prop_select') {
    const options = resolvedChoiceOptions.value
    if (interactionType === 'judgment') {
      const correctLabel = node.correct_answer || (resolveJudgmentCorrectBoolean() ? '对' : '错')
      const correctOpt = options.find((o) => o.label === correctLabel)
      correctAnswer = correctOpt ? `${correctOpt.label}：${correctOpt.text || correctOpt.label}` : String(correctLabel)
    } else {
      const correctIdx = resolveChoiceCorrectIndex()
      const correctOpt = correctIdx !== null ? options[correctIdx] : options.find((o) => o.label === node.correct_answer)
      correctAnswer = correctOpt
        ? `${correctOpt.label || ''}：${correctOpt.text || correctOpt.label}`
        : String(node.correct_answer || '')
    }
    explanation = node.node_config?.explanation
      || node.prompt_content?.explanation
      || `正确答案是 ${correctAnswer}`
    userAnswer = extra.selected_label || extra.answer || ''
  } else {
    const keywords = node.required_keywords || []
    correctAnswer = node.prompt_content?.speech_hint || keywords.join('、') || ''
    explanation = node.node_config?.explanation || `标准话术：${correctAnswer}`
    userAnswer = finalText.value || manualSpeechText.value || ''
  }

  nodeFeedbackData.value = {
    passed,
    correctAnswer,
    explanation,
    userAnswer,
    nodeTitle: node.title || `节点 ${currentNodeIndex.value + 1}`,
  }
  showNodeFeedback.value = true
}

function resolveJudgmentCorrectBoolean(): boolean | null {
  const node = currentNode.value
  if (!node) return null
  const cfgAnswer = node.node_config?.correct_answer
  if (typeof cfgAnswer === 'boolean') return cfgAnswer
  const label = String(node.correct_answer || '').trim()
  if (label === '对' || label === '正确') return true
  if (label === '错' || label === '错误') return false
  return null
}

function resolveChoiceCorrectIndex(): number | null {
  const node = currentNode.value
  if (!node) return null
  if (typeof node.node_config?.correct_index === 'number') return node.node_config.correct_index
  const answer = String(node.correct_answer || '').trim()
  if (!answer) return null
  const idx = resolvedChoiceOptions.value.findIndex((o: any) =>
    o.label === answer || String(o.text || '').trim() === answer,
  )
  return idx >= 0 ? idx : null
}

function showPracticeWrongFeedback(extra: Record<string, any> = {}) {
  clearCountdown()
  clearChoiceTimer()
  stopSpeech()
  nodeResult.value = 'fail'
  nodeRetryCount.value++
  showSpeechHintRevealed.value = true
  _showFeedbackPanel(false, extra)
}

function feedbackRetry() {
  showNodeFeedback.value = false
  nodeFeedbackData.value = null
  retryNode()
}

function feedbackContinue() {
  clearPassContinueTimer()
  const wasPassed = nodeFeedbackData.value?.passed
  showNodeFeedback.value = false
  nodeFeedbackData.value = null
  nodeStatuses.value[currentNodeIndex.value] = wasPassed ? 'pass' : 'fail'
  stopGestureDetection()
  nodeActive.value = false
  nodeResult.value = null
  nodeFailureReasons.value = []
  nodeSemanticFeedback.value = null
  announceNextNode()
  void playTrainingVideo()
  checkAllNodesDone()
}

async function skipNode(type: 'skip' | 'timeout' = 'skip') {
  if (nodeSubmitting.value) return
  nodeSubmitting.value = true
  clearCountdown()
  clearChoiceTimer()
  stopSpeech()
  stopGestureDetection()
  showTimeoutOptions.value = false
  showNodeFeedback.value = false
  nodeFeedbackData.value = null
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
  announceNextNode()
  void playTrainingVideo()
  checkAllNodesDone()
}

function retryNode() {
  showReferenceGuide.value = false
  showTimeoutOptions.value = false
  showNodeFeedback.value = false
  nodeFeedbackData.value = null
  choiceSelected.value = null
  interruptionReason.value = null
  interruptionMessage.value = ''
  interruptionViolationKey = ''
  nodeResult.value = null
  nodeFailureReasons.value = []
  nodeSemanticFeedback.value = null
  clearCountdown()
  clearChoiceTimer()
  stopSpeech()

  const node = currentNode.value
  if (!node) return

  propReady.value = node.prop_mode !== 'manual'
  propActivatedAt.value = propReady.value ? Date.now() : null
  nodeRetryCount.value++

  const observeSeconds = getObserveSeconds(node)
  if (observeSeconds > 0) {
    nodePhase.value = 'observe'
    observeCountdown.value = observeSeconds
    if (node.pause_mode === 'light_motion') {
      void playTrainingVideo()
    } else {
      videoRef.value?.pause()
    }
    startObservePhase(node)
  } else {
    beginNodeInteraction(node)
  }

  void restartGestureDetection()
  ElMessage.warning(`重新练习，本次重试扣 ${node.retry_score_deduct ?? 5} 分`)
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
        matched: faceIdentityVerified.value,
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
        matched: faceIdentityVerified.value,
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

function submitJudge(answer: boolean, selectedLabel?: string) {
  const correct = resolveJudgmentCorrectBoolean()
  const userLabel = selectedLabel || (answer ? '对' : '错')
  const extra = { answer_data: { answer }, answer: userLabel }
  if (answer === correct) {
    void passNode(extra)
  } else if (trainingMode.value === 'practice') {
    showPracticeWrongFeedback(extra)
  } else {
    nodeResult.value = 'fail'
    const exp = currentNode.value?.node_config?.explanation
    if (exp) ElMessage.info(exp)
    nodeRetryCount.value++
  }
}

function submitChoice() {
  if (choiceSelected.value === null) return
  const correct = resolveChoiceCorrectIndex()
  const opt = resolvedChoiceOptions.value[choiceSelected.value]
  const extra = {
    answer_data: { selected: choiceSelected.value },
    selected_label: opt ? `${opt.label || ''}：${opt.text || opt.label || opt}` : String(choiceSelected.value),
  }
  if (choiceSelected.value === correct) {
    void passNode(extra)
  } else if (trainingMode.value === 'practice') {
    showPracticeWrongFeedback(extra)
  } else {
    // 考核模式答错：显示反馈并重置选中状态允许重试
    nodeResult.value = 'fail'
    const exp = currentNode.value?.node_config?.explanation
    ElMessage.error(exp || '回答错误，请重新选择')
    choiceSelected.value = null
    nodeRetryCount.value++
  }
}

function checkAllNodesDone() {
  const total = video.value?.nodes?.length || 0
  if (completedCount.value >= total) {
    // 所有节点已完成，但不立即结束训练——让视频继续播放至结束
    // 视频播放结束后 onVideoEnded 会自动触发 finishTraining
    ElMessage.success('所有训练节点已完成，视频播放结束后将自动生成评估报告')
    void playTrainingVideo()
  }
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
function markUnfinishedNodesAsSkipped() {
  const nodes = video.value?.nodes || []
  for (let i = 0; i < nodes.length; i++) {
    if (nodeStatuses.value[i] === undefined) {
      nodeStatuses.value[i] = 'skip'
    }
  }
}

async function confirmFinishTraining() {
  if (!sessionId.value || finishingTraining.value) return
  try {
    await ElMessageBox.confirm(
      '系统将基于当前已完成、未通过、跳过和未触发节点生成评估报告。未触发节点会计入本次结果。',
      '确认结束训练？',
      {
        confirmButtonText: '结束并生成报告',
        cancelButtonText: '继续训练',
        type: 'warning',
      },
    )
    markUnfinishedNodesAsSkipped()
    await finishTraining()
  } catch {}
}

async function finishTraining() {
  if (!sessionId.value || finishingTraining.value) return
  finishingTraining.value = true
  stopGestureDetection()
  videoRef.value?.pause()
  const targetReportUrl = `/student/evaluation?session_id=${sessionId.value}&type=video`
  try {
    const res: any = await request.post(`/video-training/session/${sessionId.value}/finish`)
    if (!isVideoReportReady(res)) {
      await waitForVideoReportReady(sessionId.value)
    }
    router.replace(targetReportUrl)
  } catch (error: any) {
    const message = error?.message || ''
    if (message.includes('评估报告生成超时')) {
      ElMessage.warning('报告仍在生成中，已为你打开报告页')
    } else {
      ElMessage.warning('报告可能仍在生成，请稍后在报告页刷新查看')
    }
    router.replace(targetReportUrl)
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

const startCamDrag = startDrag

async function retryDeviceCheck() {
  if (!cameraOn.value) {
    await startCamera()
  }
  await bindBriefingCameraIfNeeded()
}

// 鈹€鈹€ 宸ュ叿鍑芥暟 鈹€鈹€
function formatTime(sec: number) {
  return `${String(Math.floor(sec / 60)).padStart(2, '0')}:${String(sec % 60).padStart(2, '0')}`
}

function resultLabel(r: string) {
  return ({ pass: '通过', skip: '跳过', timeout: '超时', fail: '未通过' } as any)[r] || r
}

function nodeStatusText(index: number) {
  const status = nodeStatuses.value[index]
  if (status === 'pass') return '已完成'
  if (status === 'skip') return '已跳过'
  if (status === 'timeout') return '已超时'
  if (status === 'fail') return '未通过'
  return displayNodeIndex.value === index ? '进行中' : '未开始'
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
  grid-template-columns: minmax(0, 1.35fr) minmax(180px, 0.9fr) minmax(0, auto);
  align-items: center;
  gap: 18px;
  padding: 10px 16px;
  border-radius: 14px;
  background: linear-gradient(180deg, rgba(8, 18, 36, 0.98), rgba(6, 14, 28, 0.94));
  border: 1px solid rgba(83, 120, 181, 0.22);
  box-shadow: 0 14px 30px rgba(0, 0, 0, 0.22);
  min-width: 0;
  overflow: hidden;
}

.training-topbar__left,
.training-topbar__right,
.training-topbar__center {
  display: flex;
  align-items: center;
  min-width: 0;
}

.training-topbar__left {
  gap: 12px;
  min-width: 0;
}

.training-topbar__center {
  flex-direction: column;
  justify-content: center;
  gap: 8px;
  overflow: hidden;
}

.training-topbar__right {
  justify-content: flex-end;
  flex-wrap: wrap;
  gap: 12px;
  flex-wrap: wrap;
  max-width: 100%;
}

.training-back,
.training-exit {
  border-radius: 10px;
  border: 1px solid rgba(88, 123, 188, 0.24);
  background: rgba(10, 25, 49, 0.88);
  color: #e2e8f0 !important;
  padding-inline: 14px;
}

.training-finish-report {
  border-radius: 10px;
  background: #0f1f3d !important;
  border-color: rgba(96, 165, 250, 0.28) !important;
  font-weight: 700;
  max-width: 220px;
  white-space: normal;
  line-height: 1.25;
}

.training-title-wrap {
  flex: 1 1 auto;
  min-width: 0;
  max-width: 100%;
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
  width: 100%;
  color: #e2e8f0;
  font-size: 14px;
  font-weight: 700;
  text-align: center;
  overflow-wrap: anywhere;
}

.training-stepper {
  display: flex;
  align-items: center;
  gap: 10px;
  max-width: 100%;
  overflow: hidden;
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

.training-stepper__dot.is-fail {
  background: linear-gradient(90deg, #ef4444, #dc2626);
}

.training-chip {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  padding: 10px 14px;
  border-radius: 10px;
  background: rgba(8, 22, 43, 0.94);
  border: 1px solid rgba(87, 120, 173, 0.26);
  color: #e2e8f0;
  line-height: 1.25;
  overflow-wrap: anywhere;
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

.rail-line.is-fail .rail-line__index {
  background: rgba(239, 68, 68, 0.16);
  color: #f87171;
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

/* ========== 三步向导暗色样式 ========== */
.briefing-card--dark {
  background: #0f172a !important;
  border: 1px solid rgba(59, 130, 246, 0.2) !important;
  color: #e2e8f0 !important;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5) !important;
}

.briefing-steps {
  display: flex;
  align-items: center;
  gap: 0;
  padding: 20px 24px 0;
  position: relative;
}

.briefing-steps__labels {
  position: absolute;
  top: 50px;
  left: 24px;
  right: 24px;
  display: flex;
  justify-content: space-between;
  font-size: 11px;
  color: #64748b;
  padding: 0 4px;

  .is-active { color: #60a5fa; font-weight: 600; }
}

.briefing-step {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 700;
  background: #1e293b;
  color: #64748b;
  border: 2px solid #334155;
  transition: all 0.3s;

  &--active {
    background: #2563eb;
    color: #fff;
    border-color: #3b82f6;
    box-shadow: 0 0 12px rgba(59, 130, 246, 0.4);
  }

  &--done {
    background: #22c55e;
    color: #fff;
    border-color: #22c55e;
  }
}

.briefing-step-line {
  flex: 1;
  height: 2px;
  background: #334155;
  transition: background 0.3s;

  &--done { background: #22c55e; }
}

.briefing-body {
  padding: 36px 24px 24px;

  &__title {
    margin: 0 0 8px;
    font-size: 18px;
    font-weight: 700;
    color: #f1f5f9;
  }

  &__desc {
    margin: 0 0 18px;
    font-size: 13px;
    color: #94a3b8;
    line-height: 1.6;
  }
}

.face-preview {
  display: flex;
  flex-direction: column;
  align-items: center;
  margin-bottom: 16px;
}

.face-preview__camera {
  position: relative;
  width: 220px;
  height: 220px;
  max-width: 220px;
  margin: 0 auto;
  border-radius: 50%;
  overflow: hidden;
  background: #1e293b;
  border: 3px solid rgba(59, 130, 246, 0.45);
  box-shadow: 0 0 0 6px rgba(59, 130, 246, 0.12);
}

.face-preview__video {
  width: 100%;
  height: 100%;
  object-fit: cover;
  object-position: center 28%;
  transform: scaleX(-1) scale(1.45);
}

.face-preview__ring {
  position: absolute;
  inset: 14px;
  border: 2px dashed rgba(147, 197, 253, 0.55);
  border-radius: 50%;
  pointer-events: none;
}

.face-preview__video--hidden {
  opacity: 0;
  pointer-events: none;
}

.face-preview__placeholder {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  background: #0f172a;
  color: #94a3b8;
  font-size: 13px;
  text-align: center;
  padding: 0 16px;
}

.face-preview__hint {
  max-width: 260px;
  margin-top: 10px;
  text-align: center;
  font-size: 12px;
  color: #60a5fa;
  line-height: 1.5;
}

.face-metrics {
  display: flex;
  gap: 12px;
  margin-bottom: 14px;
}

.face-metric {
  flex: 1;
  padding: 10px 14px;
  border-radius: 8px;
  background: #1e293b;
  border: 1px solid #334155;
  display: flex;
  justify-content: space-between;
  align-items: center;

  &--pass {
    border-color: rgba(34, 197, 94, 0.4);
    background: rgba(34, 197, 94, 0.08);
  }
}

.face-metric__label {
  font-size: 13px;
  color: #94a3b8;
}

.face-metric__value {
  font-size: 13px;
  font-weight: 600;
  color: #e2e8f0;

  .face-metric--pass & { color: #4ade80; }
}

.face-status {
  text-align: center;
  margin-bottom: 18px;
}

.face-status__badge {
  display: inline-block;
  padding: 6px 16px;
  border-radius: 20px;
  font-size: 13px;
  font-weight: 600;
  background: #1e293b;
  color: #94a3b8;
  border: 1px solid #334155;

  &--pass {
    background: rgba(34, 197, 94, 0.1);
    color: #4ade80;
    border-color: rgba(34, 197, 94, 0.3);
  }
}

.face-status__fallback {
  margin: 8px 0 0;
  font-size: 12px;
  color: #fbbf24;
}

.face-status__hint {
  margin: 8px 0 0;
  font-size: 12px;
  color: #93c5fd;
}

.face-capture-canvas {
  display: none;
}

.device-check-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-bottom: 16px;
}

.device-check-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  border-radius: 10px;
  background: #1e293b;
  border: 1px solid #334155;

  &--pass {
    border-color: rgba(34, 197, 94, 0.3);
    background: rgba(34, 197, 94, 0.06);
  }

  &--fail {
    border-color: rgba(239, 68, 68, 0.3);
    background: rgba(239, 68, 68, 0.06);
  }

  &--warn {
    border-color: rgba(234, 179, 8, 0.3);
    background: rgba(234, 179, 8, 0.06);
  }
}

.device-check-item__icon {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 700;
  flex-shrink: 0;

  .device-check-item--pass & { background: rgba(34, 197, 94, 0.2); color: #4ade80; }
  .device-check-item--fail & { background: rgba(239, 68, 68, 0.2); color: #f87171; }
  .device-check-item--warn & { background: rgba(234, 179, 8, 0.2); color: #fbbf24; }
}

.device-check-item__label {
  font-size: 14px;
  font-weight: 600;
  color: #e2e8f0;
  min-width: 70px;
}

.device-check-item__status {
  font-size: 13px;
  color: #94a3b8;
  margin-left: auto;
}

.device-check-hint {
  padding: 12px 16px;
  border-radius: 8px;
  background: rgba(239, 68, 68, 0.06);
  border: 1px solid rgba(239, 68, 68, 0.2);
  margin-bottom: 16px;

  p { margin: 0 0 8px; font-size: 13px; color: #fca5a5; }

  &--ok {
    background: rgba(34, 197, 94, 0.06);
    border-color: rgba(34, 197, 94, 0.2);
    p { color: #86efac; }
  }
}

.briefing-content-block {
  margin-bottom: 16px;
}

.briefing-text {
  font-size: 14px;
  color: #cbd5e1;
  line-height: 1.8;
  padding: 14px 16px;
  background: #1e293b;
  border-radius: 10px;
  border-left: 4px solid #3b82f6;
}

.briefing-stat-row {
  display: flex;
  gap: 10px;
  margin-bottom: 14px;
}

.briefing-stat {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  padding: 8px 6px;
  background: #1e293b;
  border: 1px solid #334155;
  border-radius: 6px;
}

.briefing-stat__num {
  font-size: 16px;
  font-weight: 800;
  color: #60a5fa;
}

.briefing-stat__label {
  font-size: 10px;
  color: #94a3b8;
}

.briefing-mode-section {
  margin-bottom: 16px;
}

.briefing-mode-label {
  font-size: 14px;
  font-weight: 600;
  color: #e2e8f0;
  margin-bottom: 10px;
}

.briefing-mode-options {
  display: flex;
  gap: 12px;
}

.briefing-mode-btn {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 14px;
  border-radius: 10px;
  border: 2px solid #334155;
  background: #1e293b;
  cursor: pointer;
  text-align: left;
  transition: all 0.2s;

  &:hover {
    border-color: rgba(59, 130, 246, 0.4);
    background: rgba(59, 130, 246, 0.05);
  }

  &--active {
    border-color: #3b82f6 !important;
    background: rgba(59, 130, 246, 0.1) !important;
    box-shadow: 0 0 14px rgba(59, 130, 246, 0.2);
  }

  &__title {
    font-size: 14px;
    font-weight: 600;
    color: #f1f5f9;
  }

  &__desc {
    font-size: 12px;
    color: #94a3b8;
    line-height: 1.4;
  }
}

.briefing-notices-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 16px;

  .bn-item {
    background: #1e293b;
    border-color: #334155;
    color: #94a3b8;

    &--warn {
      color: #fbbf24;
      border-color: rgba(234, 179, 8, 0.2);
      background: rgba(234, 179, 8, 0.06);
    }

    &--info {
      color: #93c5fd;
      border-color: rgba(59, 130, 246, 0.2);
      background: rgba(59, 130, 246, 0.04);
    }

    strong { color: #e2e8f0; }
  }
}

.briefing-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  padding-top: 8px;
}

/* ========== 沉浸式全屏布局样式 ========== */
.imm-shell {
  position: relative;
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
  background: #000;
  overflow: hidden;
  outline: none;
}

.imm-header {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 48px;
  padding: 0 20px;
  background: linear-gradient(180deg, rgba(0, 0, 0, 0.7) 0%, transparent 100%);
  z-index: 20;
}

/* Video fills entire shell */
.imm-video-layer {
  position: absolute;
  inset: 0;
  z-index: 0;
}

.imm-video-layer__video {
  width: 100%;
  height: 100%;
  object-fit: contain;
  background: #000;
}

/* All overlays sit on top of video */
.imm-overlays {
  position: absolute;
  inset: 0;
  z-index: 10;
  pointer-events: none;

  > * {
    pointer-events: auto;
  }
}

.imm-play-retry {
  position: absolute;
  left: 50%;
  top: 50%;
  z-index: 30;
  transform: translate(-50%, -50%);
  padding: 13px 22px;
  border: 1px solid rgba(96, 165, 250, 0.65);
  border-radius: 10px;
  background: rgba(15, 23, 42, 0.9);
  color: #dbeafe;
  font-size: 16px;
  font-weight: 700;
  cursor: pointer;
  box-shadow: 0 12px 32px rgba(0, 0, 0, 0.35);
}

.imm-play-retry:hover {
  background: rgba(30, 64, 175, 0.92);
}

.imm-header__left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.imm-header__rec {
  color: #64748b;
  font-size: 12px;
  transition: color 0.3s;

  &--active {
    color: #ef4444;
    animation: imm-pulse 1.2s ease-in-out infinite;
  }
}

.imm-header__title {
  font-size: 14px;
  font-weight: 600;
  letter-spacing: 0.3px;
}

.imm-header__center {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 14px;
}

.imm-header__node {
  color: #94a3b8;
}

.imm-header__node-name {
  color: #e2e8f0;
  font-weight: 500;
}

.imm-header__right {
  display: flex;
  align-items: center;
  gap: 12px;
  flex: 0 1 auto;
  flex-wrap: wrap;
  justify-content: flex-end;
  min-width: 0;
  max-width: 100%;
}

.imm-header__timer {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: #94a3b8;

  svg { color: #60a5fa; }
}

.imm-header__fullscreen-btn {
  width: 32px;
  height: 32px;
  border-radius: 6px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  background: rgba(255, 255, 255, 0.04);
  color: #94a3b8;
  font-size: 16px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;

  &:hover {
    background: rgba(59, 130, 246, 0.15);
    color: #60a5fa;
  }
}

.imm-header__end-btn {
  padding: 6px 16px;
  border-radius: 6px;
  border: 1px solid #3b82f6;
  background: transparent;
  color: #60a5fa;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;

  &:hover {
    background: rgba(59, 130, 246, 0.15);
  }
}

/* Main scene - removed, video is now direct layer */

/* Camera PIP with breathing border */
.imm-pip {
  position: absolute;
  z-index: 10;
  width: 200px;
  border-radius: 10px;
  overflow: hidden;
  border: 3px solid #3b82f6;
  background: #000;
  cursor: grab;
  user-select: none;
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.6);
  transition: box-shadow 0.3s;

  &:active { cursor: grabbing; }

  &--breathing {
    animation: imm-pip-breathe 2.5s ease-in-out infinite;
  }
}

.imm-pip__label {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 4px 10px;
  font-size: 11px;
  color: rgba(255, 255, 255, 0.8);
  background: rgba(0, 0, 0, 0.7);
}

.imm-pip__drag-hint { color: #60a5fa; }
.imm-pip__check { color: #22c55e; font-size: 14px; font-weight: bold; }

.imm-pip__video-wrap {
  position: relative;
  width: 100%;
  aspect-ratio: 3/4;
  background: #1e293b;
}

.imm-pip__video {
  width: 100%;
  height: 100%;
  object-fit: cover;
  transform: scaleX(-1);
}

.imm-pip__video--hidden {
  opacity: 0;
  pointer-events: none;
}

.imm-pip__placeholder {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: #0a0e1a;
  cursor: pointer;
  gap: 6px;
}

.imm-pip__placeholder:hover {
  background: #141a2e;
}

.imm-pip__retry-hint {
  font-size: 11px;
  color: #64748b;
}

/* AI Bubble - Exam mode (bottom compact bar, no hints) */
.imm-bubble {
  position: absolute;
  bottom: 20px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 8;
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 14px 28px;
  max-width: 680px;
  background: rgba(15, 23, 42, 0.88);
  backdrop-filter: blur(16px);
  border: 1px solid rgba(234, 179, 8, 0.25);
  border-radius: 12px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.5);
}

.imm-bubble__icon {
  flex-shrink: 0;
}

.imm-bubble__content {
  flex: 1;
  min-width: 0;
}

.imm-bubble__main {
  margin: 0;
  font-size: 18px;
  font-weight: 700;
  color: #f1f5f9;
  line-height: 1.4;
}

/* 练习模式：统一节点面板 */
.imm-node-panel {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  z-index: 8;
  width: 560px;
  max-width: 92vw;
  max-height: 85vh;
  overflow-y: auto;
  background: rgba(15, 23, 42, 0.92);
  backdrop-filter: blur(20px);
  border: 1px solid rgba(96, 165, 250, 0.3);
  border-radius: 14px;
  padding: 24px 28px;
  box-shadow: 0 12px 48px rgba(0, 0, 0, 0.6);
  transition: border-color 0.3s;

  &--timeout {
    border-color: rgba(245, 158, 11, 0.45);
  }

  &--pass {
    border-color: rgba(34, 197, 94, 0.45);
  }

  &--fail {
    border-color: rgba(239, 68, 68, 0.45);
  }
}

.imm-node-panel__header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}

.imm-node-panel__avatar {
  width: 42px;
  height: 42px;
  border-radius: 50%;
  background: linear-gradient(135deg, #3b82f6, #1d4ed8);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.imm-node-panel__header-text {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.imm-node-panel__title {
  font-size: 17px;
  font-weight: 600;
  color: #60a5fa;
}

.imm-node-panel__status {
  font-size: 14px;
  font-weight: 600;
  color: #22c55e;

  &--timeout {
    color: #fbbf24;
  }
}

.imm-node-panel--fail .imm-node-panel__status {
  color: #ef4444;
}

.imm-node-panel__hint {
  margin-bottom: 4px;

  p {
    margin: 0 0 10px;
    font-size: 17px;
    line-height: 1.75;
    color: #e2e8f0;
  }
}

.imm-node-panel__observe {
  margin-top: 8px;
  padding: 20px 16px;
  text-align: center;
  background: rgba(59, 130, 246, 0.08);
  border: 1px solid rgba(59, 130, 246, 0.22);
  border-radius: 10px;
}

.imm-node-panel__observe-title {
  margin: 0 0 10px;
  font-size: 15px;
  line-height: 1.6;
  color: #e2e8f0;
}

.imm-node-panel__observe-timer {
  margin: 0 0 16px;
  font-size: 22px;
  font-weight: 700;
  color: #60a5fa;
}

.imm-interaction__prop-hint {
  margin: 0 0 10px;
  padding: 8px 10px;
  font-size: 13px;
  line-height: 1.5;
  color: #fbbf24;
  background: rgba(245, 158, 11, 0.1);
  border-radius: 6px;
}

.imm-node-panel__scene {
  font-size: 14px !important;
  color: #94a3b8 !important;
  font-style: italic;
}

/* 参考话术引导区域 */
.imm-node-panel__speech-ref {
  margin-top: 12px;
  padding: 10px 14px;
  background: rgba(59, 130, 246, 0.06);
  border: 1px solid rgba(59, 130, 246, 0.18);
  border-radius: 8px;
  transition: all 0.3s ease;
}

.imm-node-panel__speech-ref--revealed {
  background: rgba(59, 130, 246, 0.1);
  border-color: rgba(59, 130, 246, 0.3);
}

.imm-node-panel__speech-ref-header {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  user-select: none;
}

.imm-node-panel__speech-ref-icon {
  font-size: 16px;
}

.imm-node-panel__speech-ref-label {
  font-size: 14px;
  font-weight: 600;
  color: #93c5fd;
}

.imm-node-panel__speech-ref-toggle {
  margin-left: auto;
  font-size: 12px;
  color: #64748b;
  transition: color 0.2s;
}

.imm-node-panel__speech-ref-header:hover .imm-node-panel__speech-ref-toggle {
  color: #93c5fd;
}

.imm-node-panel__speech-ref-body {
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px solid rgba(59, 130, 246, 0.15);

  p {
    margin: 0;
    font-size: 15px;
    line-height: 1.7;
    color: #bfdbfe;
    letter-spacing: 0.02em;
  }
}

/* 参考话术展开动画 */
.imm-speech-expand-enter-active,
.imm-speech-expand-leave-active {
  transition: all 0.3s ease;
  max-height: 200px;
  overflow: hidden;
}

.imm-speech-expand-enter-from,
.imm-speech-expand-leave-to {
  opacity: 0;
  max-height: 0;
  margin-top: 0;
  padding-top: 0;
}

.imm-node-panel__divider {
  height: 1px;
  background: rgba(255, 255, 255, 0.08);
  margin: 16px 0;
}

.imm-node-panel__question {
  margin-bottom: 4px;
}

.imm-node-panel__question-text {
  margin: 0 0 8px;
  font-size: 17px;
  font-weight: 700;
  line-height: 1.7;
  color: #e2e8f0;
}

.imm-node-panel__question-instruction {
  margin: 0;
  font-size: 13px;
  font-weight: 500;
  line-height: 1.6;
  color: #94a3b8;
  padding: 6px 12px;
  border-radius: 6px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.imm-node-panel__interaction {
  .imm-interaction__title {
    text-align: left;
    font-size: 16px;
    font-weight: 600;
    color: #cbd5e1;
    margin-bottom: 12px;
  }
}

.imm-node-panel__timeout {
  margin-top: 16px;
  padding: 16px;
  background: rgba(245, 158, 11, 0.08);
  border: 1px solid rgba(245, 158, 11, 0.25);
  border-radius: 10px;
  text-align: center;
}

.imm-node-panel__timeout-desc {
  margin: 0 0 14px;
  font-size: 15px;
  color: #cbd5e1;
  line-height: 1.7;
}

.imm-node-panel__timeout-actions {
  display: flex;
  gap: 10px;
  justify-content: center;
}

.imm-node-panel__feedback {
  margin-top: 8px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.imm-node-panel__feedback-row {
  font-size: 15px;
  color: #cbd5e1;
  line-height: 1.7;

  span:first-child {
    color: #64748b;
  }

  &--answer {
    font-weight: 600;
    color: #22c55e;
  }
}

.imm-node-panel--fail .imm-node-panel__feedback-row--answer {
  color: #fbbf24;
}

.imm-node-panel__feedback-actions {
  display: flex;
  gap: 10px;
  margin-top: 8px;
}

.imm-node-panel__footer {
  display: flex;
  align-items: center;
  gap: 16px;
  padding-top: 18px;
  margin-top: 16px;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
}

.imm-node-panel__countdown {
  width: 52px;
  height: 52px;
  border-radius: 50%;
  border: 3px solid #3b82f6;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: border-color 0.3s;

  &--urgent {
    border-color: #ef4444;
    animation: imm-pulse 0.8s ease-in-out infinite;
  }
}

.imm-node-panel__countdown-num {
  font-size: 18px;
  font-weight: 800;
  color: #60a5fa;

  .imm-node-panel__countdown--urgent & {
    color: #ef4444;
  }
}

.imm-node-panel__countdown-info p {
  margin: 0;
  font-size: 13px;
  color: #e2e8f0;
}

.imm-node-panel__countdown-main {
  font-weight: 600;
}

.imm-node-panel__countdown-sub {
  color: #64748b !important;
  font-size: 12px !important;
  margin-top: 4px !important;
}

/* AI Coach Panel - legacy / exam reference */
.imm-coach-panel {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  z-index: 8;
  width: 540px;
  max-width: 90vw;
  background: rgba(15, 23, 42, 0.9);
  backdrop-filter: blur(20px);
  border: 1px solid rgba(96, 165, 250, 0.3);
  border-radius: 14px;
  padding: 28px;
  box-shadow: 0 12px 48px rgba(0, 0, 0, 0.6);
}

.imm-coach-panel__header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 18px;
}

.imm-coach-panel__avatar {
  width: 42px;
  height: 42px;
  border-radius: 50%;
  background: linear-gradient(135deg, #3b82f6, #1d4ed8);
  display: flex;
  align-items: center;
  justify-content: center;
}

.imm-coach-panel__title {
  font-size: 17px;
  font-weight: 600;
  color: #60a5fa;
}

.imm-coach-panel__body {
  margin-bottom: 20px;
}

.imm-coach-panel__intro {
  margin: 0 0 10px;
  font-size: 15px;
  color: #e2e8f0;
}

.imm-coach-panel__steps {
  margin: 8px 0 14px 22px;
  padding: 0;
  font-size: 14px;
  color: #cbd5e1;
  line-height: 2;
}

.imm-coach-panel__speech {
  margin-top: 14px;
  padding: 14px;
  background: rgba(59, 130, 246, 0.08);
  border-radius: 8px;
  border-left: 3px solid #3b82f6;
}

.imm-coach-panel__speech-label {
  font-size: 13px;
  color: #22c55e;
  font-weight: 600;
}

.imm-coach-panel__speech-text {
  margin: 6px 0 0;
  font-size: 15px;
  color: #e2e8f0;
  line-height: 1.6;
}

.imm-coach-panel__footer {
  display: flex;
  align-items: center;
  gap: 16px;
  padding-top: 18px;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
}

.imm-coach-panel__countdown {
  width: 52px;
  height: 52px;
  border-radius: 50%;
  border: 3px solid #3b82f6;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: border-color 0.3s;

  &--urgent {
    border-color: #ef4444;
    animation: imm-pulse 0.8s ease-in-out infinite;
  }
}

.imm-coach-panel__countdown-num {
  font-size: 18px;
  font-weight: 800;
  color: #60a5fa;

  .imm-coach-panel__countdown--urgent & {
    color: #ef4444;
  }
}

.imm-coach-panel__countdown-info p {
  margin: 0;
  font-size: 13px;
  color: #e2e8f0;
}

.imm-coach-panel__countdown-main {
  font-weight: 600;
}

.imm-coach-panel__countdown-sub {
  color: #64748b !important;
  font-size: 12px !important;
  margin-top: 4px !important;
}

/* Prop toast feedback */
.imm-prop-toast {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  z-index: 30;
  padding: 12px 28px;
  background: rgba(34, 197, 94, 0.9);
  color: #fff;
  font-size: 15px;
  font-weight: 600;
  border-radius: 8px;
  box-shadow: 0 4px 20px rgba(34, 197, 94, 0.4);
  pointer-events: none;
}

/* Countdown badge */
.imm-countdown-badge {
  position: absolute;
  top: 14px;
  right: 130px;
  z-index: 9;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  background: rgba(15, 23, 42, 0.85);
  backdrop-filter: blur(8px);
  border: 1px solid rgba(59, 130, 246, 0.3);
  border-radius: 20px;
}

.imm-countdown-badge__label {
  font-size: 12px;
  color: #94a3b8;
}

.imm-countdown-badge__value {
  font-size: 18px;
  font-weight: 800;
  color: #60a5fa;
}

.imm-countdown-badge__value--urgent {
  color: #ef4444;
  animation: pulse-urgent 0.5s infinite;
}

@keyframes pulse-urgent {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.6; }
}


/* Virtual Props */
.imm-props {
  position: absolute;
  top: 60px;
  right: 0;
  bottom: 120px;
  z-index: 12;
  width: 120px;
  background: rgba(15, 23, 42, 0.85);
  backdrop-filter: blur(12px);
  border-left: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 8px 0 0 8px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.imm-props--collapsed {
  width: auto;
  bottom: auto;
}

.imm-props__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

.imm-props__title {
  font-size: 13px;
  font-weight: 600;
  color: #60a5fa;
}

.imm-props__toggle {
  background: none;
  border: none;
  color: #94a3b8;
  font-size: 12px;
  cursor: pointer;

  &:hover {
    color: #e2e8f0;
  }
}

.imm-props__list {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 8px;
}

.imm-props__item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 5px;
  padding: 10px 8px;
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.06);
  background: rgba(30, 41, 59, 0.6);
  cursor: pointer;
  transition: all 0.2s;

  &:hover {
    background: rgba(59, 130, 246, 0.15);
    border-color: rgba(59, 130, 246, 0.3);
    transform: scale(1.03);
  }

  &--active {
    background: rgba(59, 130, 246, 0.2);
    border-color: rgba(59, 130, 246, 0.5);
    box-shadow: 0 0 12px rgba(59, 130, 246, 0.2);
  }
}

.imm-props__item-icon {
  width: 38px;
  height: 38px;
  border-radius: 6px;
  background: rgba(30, 41, 59, 0.8);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
}

.imm-props__item-name {
  font-size: 11px;
  color: #e2e8f0;
}

.imm-props__item-badge {
  font-size: 10px;
  color: #22c55e;
}

.imm-props__footer {
  padding: 8px 10px;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
  font-size: 11px;
  color: #64748b;
  text-align: center;
}

/* Bottom Progress - overlay at bottom of video */
.imm-progress {
  position: absolute;
  bottom: 44px;
  left: 0;
  right: 0;
  display: flex;
  align-items: center;
  height: 72px;
  padding: 0 20px;
  background: linear-gradient(0deg, rgba(0, 0, 0, 0.75) 0%, rgba(0, 0, 0, 0.5) 70%, transparent 100%);
  z-index: 12;
}

.imm-progress__track {
  display: flex;
  align-items: center;
  flex: 1;
  overflow-x: auto;
  scroll-behavior: smooth;
  overscroll-behavior: contain;
}

.imm-progress__step {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  min-width: 120px;
  padding: 8px 14px;
  position: relative;
  cursor: pointer;
  transition: opacity 0.2s;

  &:hover { opacity: 0.85; }
}

.imm-progress__line {
  position: absolute;
  top: 22px;
  left: -24px;
  width: 44px;
  height: 2px;
  background: #334155;
  transition: background 0.6s ease;

  &--done {
    background: #22c55e;
    box-shadow: 0 0 4px rgba(34, 197, 94, 0.4);
  }
}

.imm-progress__step--done {
  .imm-progress__icon {
    background: #22c55e;
    border-color: #22c55e;
  }
  .imm-progress__label { color: #e2e8f0; }
  .imm-progress__status { color: #22c55e; }
}

.imm-progress__step--fail {
  .imm-progress__icon {
    background: rgba(127, 29, 29, 0.86);
    border-color: #ef4444;
    box-shadow: 0 0 12px rgba(239, 68, 68, 0.28);
  }
  .imm-progress__label { color: #fecaca; }
  .imm-progress__status { color: #f87171; }
}

.imm-progress__step--skip {
  .imm-progress__icon {
    background: rgba(120, 53, 15, 0.86);
    border-color: #f59e0b;
  }
  .imm-progress__label { color: #fde68a; }
  .imm-progress__status { color: #fbbf24; }
}

.imm-progress__step--active {
  .imm-progress__icon {
    background: #1d4ed8;
    border-color: #3b82f6;
    box-shadow: 0 0 16px rgba(59, 130, 246, 0.5);
    animation: imm-node-pulse 2s ease-in-out infinite;
  }
  .imm-progress__num { color: #fff; }
  .imm-progress__label { color: #fff; font-weight: 600; }
  .imm-progress__status { color: #60a5fa; }
}

.imm-progress__step--locked {
  .imm-progress__icon {
    background: rgba(30, 41, 59, 0.8);
    border-color: #475569;
  }
  .imm-progress__label { color: #64748b; }
  .imm-progress__status { color: #475569; }
}

.imm-progress__icon {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  border: 2px solid #475569;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.3s;
}

.imm-progress__num {
  font-size: 13px;
  font-weight: 700;
  color: #60a5fa;
}

.imm-progress__label {
  font-size: 12px;
  color: #94a3b8;
  white-space: nowrap;
  text-align: center;
  max-width: 100px;
  overflow: hidden;
  text-overflow: ellipsis;
}

.imm-progress__status {
  font-size: 10px;
  color: #64748b;
}

.imm-progress__arrow {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  border: 1px solid #334155;
  background: rgba(30, 41, 59, 0.8);
  color: #94a3b8;
  font-size: 20px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  margin-left: 12px;
  transition: all 0.2s;

  &:hover {
    background: rgba(59, 130, 246, 0.2);
    color: #60a5fa;
    transform: translateX(2px);
  }
}

/* Bottom Status Bar - overlay at very bottom */
.imm-status-bar {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  display: flex;
  align-items: center;
  height: 44px;
  padding: 0 20px;
  background: rgba(0, 0, 0, 0.8);
  backdrop-filter: blur(8px);
  z-index: 12;
}

.imm-status-bar__left {
  display: flex;
  align-items: center;
  gap: 4px;
}

.imm-status-bar__label {
  font-size: 13px;
  color: #e2e8f0;
  font-weight: 600;
}

.imm-status-bar__tag {
  font-size: 12px;
  color: #64748b;
}

.imm-status-bar__indicators {
  display: flex;
  align-items: center;
  gap: 24px;
  margin-left: 28px;
}

.imm-status-bar__indicator {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: #cbd5e1;
}

.imm-status-bar__confidence {
  font-size: 11px;
  color: #94a3b8;
  margin-left: 2px;
}

.imm-status-bar__actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  flex-wrap: wrap;
  gap: 12px;
  margin-left: auto;
}

.imm-status-bar__btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 16px;
  border-radius: 6px;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;

  &--ghost {
    background: rgba(255, 255, 255, 0.06);
    border: 1px solid rgba(255, 255, 255, 0.12);
    color: #e2e8f0;
    &:hover { background: rgba(255, 255, 255, 0.1); }
  }

  &--outline {
    background: rgba(59, 130, 246, 0.1);
    border: 1px solid #3b82f6;
    color: #60a5fa;
    font-weight: 500;
    &:hover { background: rgba(59, 130, 246, 0.2); }
  }

  &--finish {
    background: #0f1f3d;
    border: 1px solid rgba(96, 165, 250, 0.28);
    color: #fff;
    font-weight: 700;
    box-shadow: 0 8px 20px rgba(0, 0, 0, 0.24);

    &:hover:not(:disabled) {
      background: #17315f;
      border-color: rgba(96, 165, 250, 0.48);
    }

    &:disabled {
      cursor: not-allowed;
      opacity: 0.58;
      box-shadow: none;
    }
  }
}

/* Waveform */
.imm-waveform {
  display: inline-flex;
  align-items: flex-end;
  gap: 2px;
  height: 14px;
  margin-left: 4px;
}

.imm-waveform__bar {
  display: block;
  width: 3px;
  height: 4px;
  border-radius: 1px;
  background: #475569;
  transition: height 0.1s ease, background 0.15s;

  &--active {
    background: #22c55e;
    animation: imm-wave-bar 0.4s ease-in-out infinite alternate;
  }

  &:nth-child(1) { height: 5px; }
  &:nth-child(2) { height: 8px; }
  &:nth-child(3) { height: 12px; }
  &:nth-child(4) { height: 8px; }
  &:nth-child(5) { height: 5px; }

  &--active:nth-child(1) { animation-delay: 0s; }
  &--active:nth-child(2) { animation-delay: 0.1s; }
  &--active:nth-child(3) { animation-delay: 0.15s; }
  &--active:nth-child(4) { animation-delay: 0.2s; }
  &--active:nth-child(5) { animation-delay: 0.25s; }
}

/* Status dots */
.imm-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;

  &--green {
    background: #22c55e;
    box-shadow: 0 0 6px rgba(34, 197, 94, 0.5);
  }

  &--yellow {
    background: #eab308;
    box-shadow: 0 0 6px rgba(234, 179, 8, 0.5);
  }

  &--red {
    background: #ef4444;
    box-shadow: 0 0 6px rgba(239, 68, 68, 0.5);
  }
}

/* Node review popup */
.imm-node-review {
  padding: 24px;

  h3 {
    margin: 0 0 12px;
    font-size: 16px;
    color: #1e293b;
  }

  &__status {
    margin-bottom: 12px;
  }

  &__badge {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 4px;
    font-size: 12px;
    background: #f1f5f9;
    color: #64748b;

    &--pass { background: #dcfce7; color: #16a34a; }
    &--skip { background: #fef3c7; color: #d97706; }
    &--fail { background: #fee2e2; color: #dc2626; }
  }

  &__hint {
    margin: 0;
    font-size: 14px;
    color: #475569;
    line-height: 1.6;
  }
}

/* ========== Animations ========== */
@keyframes imm-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.3; }
}

@keyframes imm-pip-breathe {
  0%, 100% { box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5), 0 0 0 0 rgba(59, 130, 246, 0); }
  50% { box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5), 0 0 0 4px rgba(59, 130, 246, 0.15); }
}

@keyframes imm-node-pulse {
  0%, 100% { box-shadow: 0 0 14px rgba(59, 130, 246, 0.4); }
  50% { box-shadow: 0 0 20px rgba(59, 130, 246, 0.6); }
}

@keyframes imm-line-glow {
  from { opacity: 0.5; }
  to { opacity: 1; }
}

@keyframes imm-wave-bar {
  from { transform: scaleY(0.6); }
  to { transform: scaleY(1.4); }
}

/* Transitions */
.imm-fade-slide-enter-active,
.imm-fade-slide-leave-active {
  transition: all 0.35s ease;
}

.imm-fade-slide-enter-from {
  opacity: 0;
  transform: translateY(12px);
}

.imm-fade-slide-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}

.imm-prop-toast-enter-active,
.imm-prop-toast-leave-active {
  transition: all 0.3s ease;
}

.imm-prop-toast-enter-from,
.imm-prop-toast-leave-to {
  opacity: 0;
  transform: translate(-50%, -50%) scale(0.85);
}

/* 节点答案反馈面板 */
.node-feedback-panel {
  margin-top: 12px;
  padding: 14px 16px;
  border-radius: 10px;
  border: 1px solid #e2e8f0;
  background: #f8fafc;
}

.node-feedback-panel--pass {
  border-color: #86efac;
  background: #f0fdf4;
}

.node-feedback-panel--fail {
  border-color: #fca5a5;
  background: #fef2f2;
}

.node-feedback-panel__header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
  font-weight: 700;
  font-size: 14px;
}

.node-feedback-panel--pass .node-feedback-panel__icon {
  color: #16a34a;
  font-size: 18px;
}

.node-feedback-panel--fail .node-feedback-panel__icon {
  color: #dc2626;
  font-size: 18px;
}

.node-feedback-panel__body {
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 13px;
  color: #334155;
}

.node-feedback-panel__row {
  display: flex;
  gap: 6px;
}

.node-feedback-panel__row--answer {
  font-weight: 600;
  color: #16a34a;
}

.node-feedback-panel--fail .node-feedback-panel__row--answer {
  color: #dc2626;
}

.node-feedback-panel__label {
  color: #64748b;
  white-space: nowrap;
}

.node-feedback-panel__actions {
  display: flex;
  gap: 10px;
  margin-top: 12px;
}

/* AI教官提示面板新增样式 */
.imm-coach-panel__hint {
  font-size: 15px;
  line-height: 1.7;
  color: #e2e8f0;
  margin: 0 0 6px;
}

.imm-coach-panel__scene {
  font-size: 13px;
  color: #94a3b8;
  margin: 4px 0 0;
  font-style: italic;
}

/* ═══ 沉浸式交互区域 ═══ */
.imm-interaction {
  position: absolute;
  bottom: 80px;
  left: 50%;
  transform: translateX(-50%);
  width: 480px;
  max-width: 90%;
  background: rgba(15, 23, 42, 0.92);
  backdrop-filter: blur(12px);
  border: 1px solid rgba(59, 130, 246, 0.3);
  border-radius: 12px;
  padding: 14px 18px;
  z-index: 30;
}

.imm-interaction__title {
  font-size: 14px;
  color: #94a3b8;
  margin-bottom: 14px;
  text-align: center;
}

.imm-interaction__question {
  margin-bottom: 14px;
  padding-bottom: 12px;
  border-bottom: 1px solid rgba(148, 163, 184, 0.15);
}

.imm-interaction__question-text {
  font-size: 15px;
  font-weight: 600;
  color: #e2e8f0;
  line-height: 1.6;
  margin: 0;
}

.imm-interaction__options {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.imm-interaction__submit {
  margin-top: 14px;
  width: 100%;
}

/* 判断题按钮 */
.imm-judge-btn {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 20px;
  border-radius: 10px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  background: rgba(255, 255, 255, 0.05);
  color: #e2e8f0;
  font-size: 16px;
  cursor: pointer;
  transition: all 0.2s;
}

.imm-judge-btn:hover {
  border-color: rgba(255, 255, 255, 0.3);
  background: rgba(255, 255, 255, 0.1);
}

.imm-judge-btn--correct:hover {
  border-color: #22c55e;
  background: rgba(34, 197, 94, 0.15);
}

.imm-judge-btn--wrong:hover {
  border-color: #ef4444;
  background: rgba(239, 68, 68, 0.15);
}

.imm-judge-btn__icon {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  font-size: 18px;
  font-weight: 700;
}

.imm-judge-btn--correct .imm-judge-btn__icon {
  background: rgba(34, 197, 94, 0.2);
  color: #22c55e;
}

.imm-judge-btn--wrong .imm-judge-btn__icon {
  background: rgba(239, 68, 68, 0.2);
  color: #ef4444;
}

/* 选择题按钮 */
.imm-choice-btn {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  border-radius: 10px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  background: rgba(255, 255, 255, 0.05);
  color: #e2e8f0;
  font-size: 15px;
  cursor: pointer;
  text-align: left;
  transition: all 0.2s;
}

.imm-choice-btn:hover {
  border-color: rgba(59, 130, 246, 0.5);
  background: rgba(59, 130, 246, 0.1);
}

.imm-choice-btn--selected {
  border-color: #3b82f6;
  background: rgba(59, 130, 246, 0.2);
}

.imm-choice-btn__label {
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: rgba(59, 130, 246, 0.2);
  color: #60a5fa;
  font-weight: 700;
  font-size: 13px;
  flex-shrink: 0;
}

.imm-choice-btn--selected .imm-choice-btn__label {
  background: #3b82f6;
  color: #fff;
}

/* 语音交互区 */
.imm-interaction__speech-status {
  display: flex;
  align-items: center;
  gap: 8px;
  justify-content: center;
  color: #94a3b8;
  font-size: 13px;
  margin-bottom: 10px;
}

.imm-speech-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #64748b;
}

.imm-speech-dot--listening {
  background: #22c55e;
  animation: pulse-dot 1s infinite;
}

.imm-speech-dot--processing {
  background: #f59e0b;
}

@keyframes pulse-dot {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

.imm-interaction__transcript {
  padding: 10px 14px;
  background: rgba(0, 0, 0, 0.3);
  border-radius: 8px;
  margin-bottom: 12px;
  min-height: 40px;
  font-size: 14px;
  color: #e2e8f0;
}

.imm-transcript-interim {
  color: #94a3b8;
  font-style: italic;
}

.imm-interaction__voice-actions {
  display: flex;
  gap: 10px;
  justify-content: center;
}

/* 反馈面板 */
.imm-feedback {
  position: absolute;
  bottom: 100px;
  left: 50%;
  transform: translateX(-50%);
  width: 90%;
  max-width: 520px;
  background: rgba(15, 23, 42, 0.95);
  backdrop-filter: blur(12px);
  border-radius: 14px;
  padding: 20px 24px;
  z-index: 35;
}

.imm-feedback--pass {
  border: 1px solid rgba(34, 197, 94, 0.4);
}

.imm-feedback--fail {
  border: 1px solid rgba(239, 68, 68, 0.4);
}

.imm-feedback__header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
  font-size: 16px;
  font-weight: 700;
}

.imm-feedback--pass .imm-feedback__icon { color: #22c55e; font-size: 20px; }
.imm-feedback--fail .imm-feedback__icon { color: #ef4444; font-size: 20px; }
.imm-feedback--pass .imm-feedback__title { color: #22c55e; }
.imm-feedback--fail .imm-feedback__title { color: #ef4444; }

.imm-feedback__body {
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 13px;
  color: #cbd5e1;
}

.imm-feedback__row {
  display: flex;
  gap: 6px;
}

.imm-feedback__row span:first-child {
  color: #64748b;
  white-space: nowrap;
}

.imm-feedback__row--answer {
  font-weight: 600;
  color: #22c55e;
}

.imm-feedback--fail .imm-feedback__row--answer {
  color: #fbbf24;
}

.imm-feedback__actions {
  display: flex;
  gap: 10px;
  margin-top: 14px;
}

/* 超时面板 */
.imm-timeout {
  position: absolute;
  bottom: 120px;
  left: 50%;
  transform: translateX(-50%);
  background: rgba(15, 23, 42, 0.92);
  backdrop-filter: blur(10px);
  border: 1px solid rgba(245, 158, 11, 0.4);
  border-radius: 12px;
  padding: 16px 24px;
  text-align: center;
  z-index: 30;
}

.imm-timeout__title {
  color: #fbbf24;
  font-size: 15px;
  font-weight: 600;
  margin-bottom: 12px;
}

.imm-timeout__actions {
  display: flex;
  gap: 10px;
  justify-content: center;
}
</style>

