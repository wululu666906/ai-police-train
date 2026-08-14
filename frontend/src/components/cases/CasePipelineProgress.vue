<script setup lang="ts">
import { computed } from 'vue'
import type { CasePipelineJob } from '../../composables/useCasePipeline'

const props = defineProps<{ job: CasePipelineJob | null }>()

const stages = [
  { key: 'cleaning', label: '文本清洗', threshold: 20 },
  { key: 'story', label: '完整案件剧情', threshold: 40 },
  { key: 'facts', label: '事实抽取', threshold: 52 },
  { key: 'roles', label: '人物与角色记忆', threshold: 58 },
  { key: 'world', label: '案件故事世界', threshold: 68 },
  { key: 'scenes', label: '场景蓝图', threshold: 90 },
  { key: 'validating', label: '边界校验', threshold: 100 },
]

const progress = computed(() => Math.max(0, Math.min(100, Number(props.job?.progress || 0))))
</script>

<template>
  <section class="pipeline" aria-live="polite">
    <div class="pipeline__heading">
      <div>
        <h4>正在整理案件</h4>
        <p>{{ job?.message || '任务正在后台准备' }}</p>
      </div>
      <van-loading v-if="job?.status !== 'failed'" size="20" color="#007aff" />
      <van-icon v-else name="warning-o" size="21" color="#ff3b30" />
    </div>
    <div class="pipeline__bar" role="progressbar" :aria-valuenow="progress" aria-valuemin="0" aria-valuemax="100">
      <span :style="{ width: `${progress}%` }"></span>
    </div>
    <div class="pipeline__list">
      <div v-for="stage in stages" :key="stage.key" class="pipeline__row">
        <van-icon v-if="progress >= stage.threshold" name="success" color="#34c759" />
        <span v-else class="pipeline__dot"></span>
        <span>{{ stage.label }}</span>
      </div>
    </div>
    <p class="pipeline__footer">可以关闭此窗口，整理会在后台继续。</p>
  </section>
</template>

<style scoped>
.pipeline { max-width: 680px; margin: 28px auto; color: #1c1c1e; background: #fff; }
.pipeline__heading { min-height: 60px; padding: 10px 16px 14px; display: flex; align-items: center; justify-content: space-between; }
.pipeline__heading h4 { margin: 0; font-size: 17px; line-height: 24px; font-weight: 600; letter-spacing: 0; }
.pipeline__heading p { margin: 3px 0 0; color: #8e8e93; font-size: 14px; line-height: 20px; }
.pipeline__bar { height: 3px; margin: 0 16px 8px; overflow: hidden; background: #e5e5ea; border-radius: 2px; }
.pipeline__bar span { display: block; height: 100%; background: #007aff; transition: width 240ms ease; }
.pipeline__list { padding-left: 16px; }
.pipeline__row { min-height: 48px; display: flex; align-items: center; gap: 12px; border-bottom: 1px solid #e5e5ea; font-size: 15px; }
.pipeline__row:last-child { border-bottom: 0; }
.pipeline__dot { width: 16px; height: 16px; border: 1.5px solid #c7c7cc; border-radius: 50%; }
.pipeline__footer { margin: 0; padding: 12px 16px 4px; color: #8e8e93; font-size: 13px; line-height: 18px; }
@media (prefers-reduced-motion: reduce) { .pipeline__bar span { transition: none; } }
</style>
