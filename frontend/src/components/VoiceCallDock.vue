<template>
  <div class="voice-call-dock">
    <div class="voice-call-dock__caption">
      <span v-if="isEnding" class="voice-call-dock__hint">正在发送…</span>
      <span v-else-if="isMuted" class="voice-call-dock__hint">麦克风已关闭</span>
      <span v-else-if="liveText" class="voice-call-dock__live">{{ liveText }}</span>
      <span v-else class="voice-call-dock__hint">{{ idleHint }}</span>
    </div>

    <div class="voice-call-dock__controls">
      <button
        type="button"
        class="voice-call-dock__btn voice-call-dock__btn--mic"
        :class="{ 'is-muted': isMuted, 'is-active': inCall }"
        :disabled="disabled || isEnding"
        :title="inCall ? (isMuted ? '开启麦克风' : '关闭麦克风') : '开始说话'"
        @click="emit('toggle-mic')"
      >
        <svg viewBox="0 0 24 24" fill="none" aria-hidden="true" class="voice-call-dock__icon">
          <rect x="9" y="3" width="6" height="11" rx="3" stroke="currentColor" stroke-width="1.8" />
          <path
            d="M6 11a6 6 0 0 0 12 0"
            stroke="currentColor"
            stroke-width="1.8"
            stroke-linecap="round"
          />
          <path d="M12 17v3" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" />
        </svg>
      </button>

      <button
        type="button"
        class="voice-call-dock__btn voice-call-dock__btn--close"
        :disabled="disabled || !inCall || isEnding"
        title="结束通话"
        @click="emit('close')"
      >
        <van-icon name="cross" size="22" color="#fff" />
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
withDefaults(
  defineProps<{
    inCall?: boolean
    isMuted?: boolean
    isEnding?: boolean
    disabled?: boolean
    liveText?: string
    idleHint?: string
  }>(),
  {
    inCall: false,
    isMuted: false,
    isEnding: false,
    disabled: false,
    liveText: '',
    idleHint: '你可以开始说话',
  }
)

const emit = defineEmits<{
  'toggle-mic': []
  close: []
}>()
</script>

<style scoped>
.voice-call-dock {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 14px;
  min-height: 72px;
  padding: 10px 14px;
  border-radius: 10px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
}

.voice-call-dock__caption {
  flex: 1;
  min-width: 0;
  display: flex;
  align-items: center;
  justify-content: flex-start;
  text-align: left;
  padding: 0;
}

.voice-call-dock__hint {
  font-size: 13px;
  color: #64748b;
  font-weight: 600;
}

.voice-call-dock__live {
  font-size: 13px;
  line-height: 1.5;
  color: #0f172a;
  font-weight: 600;
  max-height: 44px;
  overflow-y: auto;
  word-break: break-word;
}

.voice-call-dock__controls {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  width: auto;
  margin: 0;
  gap: 10px;
}

.voice-call-dock__btn {
  border-radius: 999px;
  border: none;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: transform 0.12s ease, opacity 0.15s ease, background 0.15s ease;
}

.voice-call-dock__btn:active:not(:disabled) {
  transform: scale(0.96);
}

.voice-call-dock__btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.voice-call-dock__btn--mic {
  width: 48px;
  height: 48px;
  background: #334155;
  color: #fff;
  box-shadow: 0 5px 12px rgba(15, 23, 42, 0.16);
}

.voice-call-dock__btn--mic.is-active {
  background: #165dff;
}

.voice-call-dock__btn--mic.is-muted {
  background: #94a3b8;
}

.voice-call-dock__icon {
  width: 22px;
  height: 22px;
}

.voice-call-dock__btn--close {
  width: 48px;
  height: 48px;
  background: #ef4444;
  box-shadow: 0 5px 12px rgba(239, 68, 68, 0.2);
}

@media (max-width: 768px) {
  .voice-call-dock {
    min-height: 68px;
    padding: 8px 10px;
  }

  .voice-call-dock__caption {
    flex-basis: auto;
  }

  .voice-call-dock__controls {
    flex-basis: auto;
    width: auto;
    gap: 8px;
  }

  .voice-call-dock__btn--mic {
    width: 44px;
    height: 44px;
  }

  .voice-call-dock__btn--close {
    width: 44px;
    height: 44px;
  }
}
</style>
