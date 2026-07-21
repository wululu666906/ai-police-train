<template>
  <div class="evaluation-page">
    <header class="report-topbar no-print">
      <div class="report-brand">
        <span class="brand-mark">评</span>
        <strong>训练评估报告</strong>
      </div>
      <div class="report-crumb">{{ breadcrumb }}</div>
      <div class="page-actions">
        <slot name="actions">
          <el-button type="primary" size="small" :icon="Printer" @click="emit('print')">打印 / 保存 PDF</el-button>
          <el-button plain size="small" :icon="ArrowLeft" @click="emit('back')">返回列表</el-button>
        </slot>
      </div>
    </header>

    <div v-if="loading" class="loading-state">
      <el-skeleton :rows="10" animated />
    </div>

    <slot v-else-if="hasContent" />

    <div v-else class="empty-state">
      <el-empty :description="emptyTitle">
        <template #description>
          <p>{{ emptyTitle }}</p>
          <span>{{ emptyDescription }}</span>
        </template>
        <div class="empty-actions">
          <slot name="empty-actions">
            <el-button type="primary" size="small" @click="emit('back')">返回列表</el-button>
          </slot>
        </div>
      </el-empty>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ArrowLeft, Printer } from '@element-plus/icons-vue'

withDefaults(defineProps<{
  breadcrumb: string
  loading?: boolean
  hasContent?: boolean
  emptyTitle?: string
  emptyDescription?: string
}>(), {
  loading: false,
  hasContent: false,
  emptyTitle: '暂无评估数据',
  emptyDescription: '当前会话可能还未完成评估，或评估结果暂未写入。',
})

const emit = defineEmits<{
  back: []
  print: []
}>()
</script>

<style scoped src="../../styles/training-report-shell.css"></style>
