<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(defineProps<{ content?: string; title?: string }>(), {
  content: '',
  title: '案件完整剧情',
})

type DocumentBlock = { type: 'title' | 'heading' | 'paragraph' | 'list'; text: string }

const blocks = computed<DocumentBlock[]>(() => {
  const lines = String(props.content || '').replace(/\r/g, '').split('\n')
  const output: DocumentBlock[] = []
  let listBuffer: string[] = []
  const flushList = () => {
    if (listBuffer.length) {
      output.push({ type: 'list', text: listBuffer.join('\n') })
      listBuffer = []
    }
  }
  for (const raw of lines) {
    const line = raw.trim()
    if (!line) {
      flushList()
      continue
    }
    const normalized = line
      .replace(/^#{1,6}\s*/, '')
      .replace(/^\*\*(.+)\*\*$/, '$1')
      .replace(/\*\*(.+?)\*\*/g, '$1')
    if (/^[-*]\s+/.test(line)) {
      listBuffer.push(normalized.replace(/^[-*]\s+/, ''))
      continue
    }
    flushList()
    if (/^案件还原剧情$|^案件完整剧情$/.test(normalized)) {
      output.push({ type: 'title', text: normalized })
    } else if (/^(事件全流程|人物证言与还原记忆|证据|案件背景|后续处置)/.test(normalized) || /^\d+[、.．]/.test(normalized)) {
      output.push({ type: 'heading', text: normalized })
    } else {
      output.push({ type: 'paragraph', text: normalized })
    }
  }
  flushList()
  return output.length ? output : [{ type: 'paragraph', text: '暂无案件剧情' }]
})
</script>

<template>
  <article class="word-document" aria-label="案件完整剧情文档">
    <header class="word-document__toolbar">
      <span class="word-document__file">{{ title }}</span>
      <span class="word-document__format">Word 文档视图</span>
    </header>
    <div class="word-document__page">
      <template v-for="(block, index) in blocks" :key="`${block.type}-${index}`">
        <h1 v-if="block.type === 'title'" class="word-document__title">{{ block.text }}</h1>
        <h2 v-else-if="block.type === 'heading'" class="word-document__heading">{{ block.text }}</h2>
        <ul v-else-if="block.type === 'list'" class="word-document__list">
          <li v-for="item in block.text.split('\n')" :key="item">{{ item }}</li>
        </ul>
        <p v-else class="word-document__paragraph">{{ block.text }}</p>
      </template>
    </div>
  </article>
</template>

<style scoped>
.word-document { overflow: hidden; border: 1px solid #dbe3ee; border-radius: 8px; background: #eef2f7; color: #27364b; }
.word-document__toolbar { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 12px 16px; border-bottom: 1px solid #dbe3ee; background: #f8fafc; color: #64748b; font-size: 12px; }
.word-document__file { overflow: hidden; color: #334155; font-weight: 700; text-overflow: ellipsis; white-space: nowrap; }
.word-document__format { flex: none; color: #94a3b8; }
.word-document__page { max-height: 680px; overflow: auto; margin: 18px auto; padding: 42px 56px 58px; width: min(100% - 36px, 860px); box-sizing: border-box; background: #fff; box-shadow: 0 3px 14px rgba(30, 41, 59, .12); font-family: 'Aptos', '等线', 'Microsoft YaHei', sans-serif; }
.word-document__title { margin: 0 0 28px; color: #172033; font-size: 25px; font-weight: 700; line-height: 1.35; text-align: center; }
.word-document__heading { margin: 25px 0 12px; color: #1e3a5f; font-size: 17px; font-weight: 700; line-height: 1.5; }
.word-document__paragraph { margin: 0 0 11px; color: #334155; font-size: 14px; line-height: 1.95; text-align: justify; text-indent: 2em; }
.word-document__list { margin: 0 0 14px; padding-left: 24px; color: #334155; font-size: 14px; line-height: 1.9; }
@media (max-width: 720px) { .word-document__page { width: calc(100% - 20px); margin: 10px auto; padding: 28px 22px 38px; } .word-document__toolbar { align-items: flex-start; flex-direction: column; gap: 4px; } }
</style>
