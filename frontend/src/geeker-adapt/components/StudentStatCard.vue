<template>
  <div class="stat-card" :class="`stat-card--${tone}`">
    <div class="stat-card__label sle">{{ label }}</div>
    <div class="stat-card__value sle">{{ value }}</div>
    <div v-if="hint" class="stat-card__hint sle">{{ hint }}</div>
  </div>
</template>

<script setup lang="ts">
withDefaults(
  defineProps<{
    label: string
    value: string | number
    hint?: string
    tone?: 'primary' | 'success' | 'warning' | 'neutral'
  }>(),
  {
    tone: 'primary',
  },
)
</script>

<style scoped lang="scss">
.stat-card {
  box-sizing: border-box;
  min-height: 96px;
  padding: 18px 20px;
  border-radius: 10px;
  border: 1px solid var(--el-border-color-light);
  background: var(--el-bg-color);
  box-shadow: 0 0 12px rgb(0 0 0 / 4%);
}

.stat-card__label {
  font-size: 13px;
  color: var(--el-text-color-secondary);
}

.stat-card__value {
  margin-top: 8px;
  font-size: 28px;
  font-weight: 700;
  line-height: 1.1;
  color: var(--el-text-color-primary);
}

.stat-card__hint {
  margin-top: 6px;
  font-size: 12px;
  color: var(--el-text-color-placeholder);
}

.stat-card--primary .stat-card__value {
  color: var(--el-color-primary);
}

.stat-card--success .stat-card__value {
  color: #047857;
}

.stat-card--warning .stat-card__value {
  color: #c2410c;
}

.stat-card--neutral .stat-card__value {
  color: #64748b;
}
</style>
