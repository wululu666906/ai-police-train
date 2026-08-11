<template>
  <div class="tz-field" :class="{ 'tz-field--mono': mono, 'tz-field--readonly': readonly }">
    <component
      :is="type === 'input' ? 'input' : 'textarea'"
      class="tz-field__control"
      :value="modelValue"
      :rows="type === 'textarea' ? rows : undefined"
      :placeholder="placeholder"
      :readonly="readonly"
      @input="onInput"
    />
    <button type="button" class="tz-field__zoom" :title="zoomTitle" @click="showPopup = true">
      <van-icon name="search" />
    </button>
  </div>

  <van-popup v-model:show="showPopup" position="center" round teleport="body" class="tz-popup">
    <div class="tz-popup__panel">
      <header class="tz-popup__head">
        <div>
          <div class="tz-popup__eyebrow">{{ label || '文本详情' }}</div>
          <h3>{{ title || label || '放大查看' }}</h3>
        </div>
        <van-button plain size="small" icon="cross" @click="showPopup = false">关闭</van-button>
      </header>
      <textarea
        class="tz-popup__textarea"
        :class="{ 'tz-popup__textarea--mono': mono }"
        :value="modelValue"
        :placeholder="placeholder"
        :readonly="readonly"
        @input="onInput"
      ></textarea>
    </div>
  </van-popup>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'

const props = withDefaults(defineProps<{
  modelValue?: string
  label?: string
  title?: string
  placeholder?: string
  type?: 'input' | 'textarea'
  rows?: number
  readonly?: boolean
  mono?: boolean
}>(), {
  modelValue: '',
  label: '',
  title: '',
  placeholder: '',
  type: 'textarea',
  rows: 3,
  readonly: false,
  mono: false,
})

const emit = defineEmits<{
  (event: 'update:modelValue', value: string): void
}>()

const showPopup = ref(false)
const zoomTitle = computed(() => `放大查看${props.label ? `：${props.label}` : ''}`)

const onInput = (event: Event) => {
  if (props.readonly) return
  emit('update:modelValue', (event.target as HTMLInputElement | HTMLTextAreaElement).value)
}
</script>

<style scoped>
.tz-field {
  position: relative;
  width: 100%;
}

.tz-field__control {
  width: 100%;
  min-height: 44px;
  padding: 0.48rem 2.25rem 0.48rem 0.72rem;
  border: 1px solid rgb(226 232 240);
  border-radius: 0.55rem;
  background: #fff;
  color: #263244;
  font-size: 14px;
  line-height: 1.65;
  outline: none;
  resize: vertical;
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}

input.tz-field__control {
  resize: none;
}

.tz-field--mono .tz-field__control {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
}

.tz-field__control:focus {
  border-color: #1d3557;
  box-shadow: 0 0 0 3px rgb(29 53 87 / 10%);
}

.tz-field__zoom {
  position: absolute;
  top: 8px;
  right: 8px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border: 1px solid #cbd5e1;
  border-radius: 999px;
  background: rgba(248, 250, 252, 0.94);
  color: #1d3557;
  cursor: pointer;
  transition: background 0.15s ease, border-color 0.15s ease, transform 0.15s ease;
}

.tz-field__zoom:hover {
  border-color: #1d3557;
  background: #eff6ff;
  transform: translateY(-1px);
}

.tz-popup {
  width: min(980px, calc(100vw - 32px));
  max-height: calc(100vh - 40px);
  overflow: hidden;
}

.tz-popup__panel {
  display: flex;
  flex-direction: column;
  height: min(760px, calc(100vh - 40px));
  background: #fff;
}

.tz-popup__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 16px 18px;
  border-bottom: 1px solid #e2e8f0;
}

.tz-popup__head h3 {
  margin: 2px 0 0;
  color: #0f172a;
  font-size: 18px;
  font-weight: 900;
}

.tz-popup__eyebrow {
  color: #64748b;
  font-size: 12px;
  font-weight: 800;
}

.tz-popup__textarea {
  flex: 1;
  width: 100%;
  min-height: 0;
  border: 0;
  outline: none;
  resize: none;
  padding: 18px 20px;
  color: #1f2937;
  font-size: 16px;
  line-height: 1.9;
}

.tz-popup__textarea--mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 14px;
}
</style>
