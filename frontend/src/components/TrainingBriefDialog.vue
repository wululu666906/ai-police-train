<template>
  <van-popup
    v-model:show="popupVisible"
    :close-on-click-overlay="false"
    teleport="body"
    class="training-brief-popup"
    :overlay-style="{ backgroundColor: 'rgba(0,0,0,0.82)' }"
  >
    <div class="training-brief-card">
      <div class="training-brief-card__head">
        <el-tag :type="tagType" effect="dark" size="small">{{ tagLabel }}</el-tag>
        <span class="training-brief-card__title">{{ title }}</span>
      </div>

      <div class="training-brief-card__body">
        <section class="training-brief-hero">
          <span class="training-brief-hero__type">{{ heroType }}</span>
          <h2>{{ title }}</h2>
          <p>{{ subtitle }}</p>
        </section>

        <section class="training-brief-section">
          <h3>{{ summaryTitle }}</h3>
          <div v-if="briefing" class="training-brief-text">{{ briefing }}</div>
          <div v-else class="training-brief-text training-brief-text--muted">{{ fallbackBriefing }}</div>
        </section>

        <section v-if="notices.length" class="training-brief-section">
          <h3>训练提示</h3>
          <div class="training-brief-notices">
            <div v-for="item in notices" :key="item.title" class="training-brief-notice" :class="`training-brief-notice--${item.level || 'info'}`">
              <div class="training-brief-notice__title">{{ item.title }}</div>
              <div class="training-brief-notice__text">{{ item.text }}</div>
            </div>
          </div>
        </section>

        <section v-if="allowModeSwitch" class="training-brief-section">
          <h3>训练模式</h3>
          <div class="training-brief-modes">
            <button
              type="button"
              class="training-brief-mode"
              :class="{ 'training-brief-mode--active': modelValue === 'practice' }"
              @click="emit('update:modelValue', 'practice')"
            >
              <strong>练习模式</strong>
              <span>容错更高，适合熟悉流程和节点要求</span>
            </button>
            <button
              type="button"
              class="training-brief-mode"
              :class="{ 'training-brief-mode--active training-brief-mode--danger': modelValue === 'exam' }"
              @click="emit('update:modelValue', 'exam')"
            >
              <strong>考核模式</strong>
              <span>判定更严格，违规和失误都会被完整记录</span>
            </button>
          </div>
        </section>

        <slot />
      </div>

      <div class="training-brief-card__foot">
        <el-button @click="emit('cancel')">{{ cancelText }}</el-button>
        <el-button type="primary" @click="emit('confirm')">{{ confirmText }}</el-button>
      </div>
    </div>
  </van-popup>
</template>

<script setup lang="ts">
import { computed } from 'vue'

interface BriefNotice {
  title: string
  text: string
  level?: 'info' | 'warn' | 'danger'
}

const props = withDefaults(defineProps<{
  show: boolean
  title: string
  subtitle?: string
  heroType?: string
  tagLabel?: string
  tagType?: '' | 'success' | 'info' | 'warning' | 'danger'
  summaryTitle?: string
  briefing?: string
  fallbackBriefing?: string
  notices?: BriefNotice[]
  allowModeSwitch?: boolean
  modelValue?: 'practice' | 'exam'
  cancelText?: string
  confirmText?: string
}>(), {
  subtitle: '请在进入训练前完成信息确认，明确本次训练目标与考核要求。',
  heroType: '视频实训',
  tagLabel: '训练简报',
  tagType: 'danger',
  summaryTitle: '案情背景',
  fallbackBriefing: '本次训练将按预设节点推进，系统会在关键时刻给出识别和判定。',
  notices: () => [],
  allowModeSwitch: false,
  modelValue: 'practice',
  cancelText: '取消',
  confirmText: '确认并开始',
})

const emit = defineEmits<{
  'update:show': [boolean]
  'update:modelValue': ['practice' | 'exam']
  confirm: []
  cancel: []
}>()

const popupVisible = computed({
  get: () => props.show,
  set: (value: boolean) => emit('update:show', value),
})
</script>

<style scoped lang="scss">
.training-brief-popup {
  width: min(680px, calc(100vw - 48px));
  max-width: calc(100vw - 48px);
  height: min(760px, calc(100vh - 48px));
  max-height: calc(100vh - 48px);
  /* 覆盖全局 .van-popup 的浅色描边/阴影，避免透明外壳在深色遮罩上显出白边 */
  background: transparent !important;
  border: none !important;
  box-shadow: none !important;
  overflow: visible;
  scrollbar-gutter: auto;
}

.training-brief-card {
  display: grid;
  grid-template-rows: auto minmax(0, 1fr) auto;
  height: 100%;
  min-height: 0;
  background: #fff;
  border-radius: 18px;
  border: 1px solid #e5e7eb;
  color: #1f2937;
  overflow: hidden;
  box-shadow: 0 24px 56px rgb(15 23 42 / 18%);
}

.training-brief-card__head,
.training-brief-card__foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 16px 18px;
}

.training-brief-card__head {
  border-bottom: 1px solid #eef2f7;
  background: #fff;
}

.training-brief-card__title {
  flex: 1;
  min-width: 0;
  font-size: 16px;
  font-weight: 800;
  color: #111827;
}

.training-brief-card__body {
  padding: 18px;
  display: grid;
  align-content: start;
  gap: 18px;
  min-height: 0;
  overflow-x: hidden;
  overflow-y: auto;
}

.training-brief-hero {
  padding: 18px;
  border-radius: 16px;
  background: #f8fafc;
  border: 1px solid #e5e7eb;
}

.training-brief-hero__type {
  display: inline-flex;
  padding: 4px 10px;
  border-radius: 999px;
  background: #eef2ff;
  color: #1d4ed8;
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.08em;
}

.training-brief-hero h2 {
  margin: 10px 0 6px;
  font-size: 24px;
  color: #111827;
}

.training-brief-hero p {
  margin: 0;
  font-size: 13px;
  line-height: 1.7;
  color: #475569;
}

.training-brief-section h3 {
  margin: 0 0 10px;
  font-size: 14px;
  font-weight: 800;
  color: #111827;
}

.training-brief-text {
  white-space: pre-wrap;
  line-height: 1.85;
  font-size: 13px;
  color: #334155;
}

.training-brief-text--muted {
  color: #64748b;
}

.training-brief-notices {
  display: grid;
  gap: 10px;
}

.training-brief-notice {
  padding: 12px 14px;
  border-radius: 12px;
  background: #f8fafc;
  border: 1px solid #e5e7eb;
}

.training-brief-notice--warn {
  background: #fffbeb;
  border-color: #fde68a;
}

.training-brief-notice--danger {
  background: #fef2f2;
  border-color: #fecaca;
}

.training-brief-notice__title {
  font-size: 12px;
  font-weight: 800;
  margin-bottom: 4px;
  color: #111827;
}

.training-brief-notice__text {
  font-size: 12px;
  line-height: 1.7;
  color: #475569;
}

.training-brief-modes {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.training-brief-mode {
  border: 1px solid #e5e7eb;
  background: #fff;
  color: #475569;
  border-radius: 14px;
  padding: 14px;
  text-align: left;
  cursor: pointer;
}

.training-brief-mode strong {
  display: block;
  font-size: 14px;
  color: #111827;
  margin-bottom: 6px;
}

.training-brief-mode span {
  display: block;
  font-size: 12px;
  line-height: 1.7;
}

.training-brief-mode--active {
  border-color: #93c5fd;
  background: #eff6ff;
}

.training-brief-mode--danger.training-brief-mode--active {
  border-color: #fca5a5;
  background: #fef2f2;
}

.training-brief-card__foot {
  border-top: 1px solid #eef2f7;
  background: #fff;
  justify-content: flex-end;
}

@media (max-width: 640px) {
  .training-brief-popup {
    width: calc(100vw - 24px);
    max-width: calc(100vw - 24px);
    height: calc(100vh - 24px);
    max-height: calc(100vh - 24px);
  }

  .training-brief-modes {
    grid-template-columns: 1fr;
  }
}
</style>
