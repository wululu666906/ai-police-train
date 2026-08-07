<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(defineProps<{ content?: string; title?: string; mode?: 'narrative' | 'event-ledger' }>(), {
  content: '',
  title: '案件完整剧情',
  mode: 'narrative',
})

type DocumentBlock = { type: 'title' | 'heading' | 'paragraph' | 'list' | 'event'; text: string }

const cleanDocumentContent = (value: string) => String(value || '')
  .replace(/\r/g, '')
  .replace(/(?:---\s*)?块\s*\d+\s*\/\s*(?:docx_xml_text|docx_xml|image_ocr|ocr|table|image|paragraph|body|段落|正文)[^\n。；]*(?:---)?/gi, '')
  .replace(/(?:---\s*)?\d+\s*\/\s*(?:docx_xml_text|docx_xml|image_ocr|ocr|table|paragraph|body|段落|正文)[^\n。；]*(?:---)?/gi, '')
  .replace(/(?:---\s*)?(?:docx_xml_text|docx_xml|paragraph|body|段落|正文)\s*\/\s*(?:docx_xml|body|正文)[^\n。；]*(?:---)?/gi, '')
  .replace(/```(?:json|markdown|text)?|```/gi, '')
  .replace(/【文档识别结果】/g, '')
  .replace(/说明：以下内容按\s*(?:DOCX|PDF|OCR)[^\n]*/gi, '')
  .split('\n')
  .filter((line) => {
    const trimmed = line.trim()
    if (!trimmed) return true
    if (/^(?:块\s*)?\d+$/.test(trimmed)) return false
    if (/^[（(]?[一二三四五六七八九十]+[）)]?$/.test(trimmed)) return false
    return !/^(?:（[一二三四五六七八九十]+）|\([一二三四五六七八九十]+\)|[一二三四五六七八九十]+[、.．]|第[一二三四五六七八九十]+组)\s*(?:证据|书证|物证|证人证言|被害人供述|被告人供述|鉴定意见|勘验|检查|辨认|视听资料|电子数据|到案经过|户籍证明|前科材料|判决书|裁定书)\s*$/.test(trimmed)
  })
  .join('\n')
  .replace(/\n{3,}/g, '\n\n')

const blocks = computed<DocumentBlock[]>(() => {
  const lines = cleanDocumentContent(props.content || '').split('\n')
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
    if (/^\d+[、.．]\s*【[^】]+】/.test(normalized)) {
      flushList()
      output.push({ type: 'event', text: normalized })
      continue
    }
    if (/^[-*]\s+/.test(line)) {
      listBuffer.push(normalized.replace(/^[-*]\s+/, ''))
      continue
    }
    flushList()
    if (/^案件还原剧情$|^案件完整剧情$/.test(normalized)) {
      output.push({ type: 'title', text: normalized })
    } else if (/^#{2,6}\s+/.test(line) || /^(故事概览|时空与人物导图|完整故事正文|人物心理与行为变化|剧情结束与案件结果|事件全流程|人物证言与还原记忆|证据|案件背景|后续处置)/.test(normalized)) {
      output.push({ type: 'heading', text: normalized })
    } else {
      output.push({ type: 'paragraph', text: normalized })
    }
  }
  flushList()
  return output.length ? output : [{ type: 'paragraph', text: '暂无案件剧情' }]
})
const headings = computed(() => blocks.value.filter((block) => block.type === 'heading' || block.type === 'title'))
const eventParts = (text: string) => {
  const match = text.match(/^(\d+)[、.．]\s*【([^】]+)】(.*)$/)
  return match ? { index: match[1], meta: match[2], content: match[3] } : { index: '', meta: '', content: text }
}
</script>

<template>
  <article class="word-document" aria-label="案件完整剧情文档">
    <header class="word-document__toolbar">
      <span class="word-document__file">{{ title }}</span>
      <span class="word-document__format">Word 文档视图</span>
    </header>
    <div class="word-document__page">
      <nav v-if="headings.length > 1" class="word-document__toc" aria-label="文档目录">
        <strong>目录</strong>
        <span v-for="(heading, index) in headings" :key="`${heading.text}-${index}`">{{ heading.text }}</span>
      </nav>
      <template v-for="(block, index) in blocks" :key="`${block.type}-${index}`">
        <h1 v-if="block.type === 'title'" class="word-document__title">{{ block.text }}</h1>
        <h2 v-else-if="block.type === 'heading'" class="word-document__heading">{{ block.text }}</h2>
        <ul v-else-if="block.type === 'list'" class="word-document__list">
          <li v-for="item in block.text.split('\n')" :key="item">{{ item }}</li>
        </ul>
        <div v-else-if="block.type === 'event'" class="word-document__event">
          <span class="word-document__event-index">{{ eventParts(block.text).index }}.</span>
          <div>
            <span class="word-document__event-meta">【{{ eventParts(block.text).meta }}】</span>
            <span class="word-document__event-content">{{ eventParts(block.text).content }}</span>
          </div>
        </div>
        <p v-else class="word-document__paragraph">{{ block.text }}</p>
      </template>
    </div>
  </article>
</template>

<style scoped>
.word-document { overflow: visible; border: 1px solid #dbe3ee; border-radius: 8px; background: #eef2f7; color: #27364b; }
.word-document__toolbar { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 12px 16px; border-bottom: 1px solid #dbe3ee; background: #f8fafc; color: #64748b; font-size: 12px; }
.word-document__file { overflow: hidden; color: #334155; font-weight: 700; text-overflow: ellipsis; white-space: nowrap; }
.word-document__format { flex: none; color: #94a3b8; }
.word-document__page { overflow: visible; margin: 18px auto; padding: 42px 56px 58px; width: min(100% - 36px, 860px); box-sizing: border-box; background: #fff; box-shadow: 0 3px 14px rgba(30, 41, 59, .12); font-family: 'Aptos', '等线', 'Microsoft YaHei', sans-serif; }
.word-document__toc { display: grid; gap: 7px; margin: 0 0 32px; padding: 18px 0; border-top: 1px solid #d1d1d6; border-bottom: 1px solid #d1d1d6; color: #636366; font-size: 13px; }
.word-document__toc strong { color: #1c1c1e; font-size: 16px; }
.word-document__title { margin: 0 0 28px; color: #172033; font-size: 25px; font-weight: 700; line-height: 1.35; text-align: center; }
.word-document__heading { margin: 25px 0 12px; color: #1e3a5f; font-size: 17px; font-weight: 700; line-height: 1.5; }
.word-document__paragraph { overflow: visible; margin: 0 0 11px; color: #334155; font-size: 14px; line-height: 1.95; text-align: justify; text-indent: 2em; overflow-wrap: anywhere; }
.word-document__list { margin: 0 0 14px; padding-left: 24px; color: #334155; font-size: 14px; line-height: 1.9; }
.word-document__event { display: grid; grid-template-columns: 44px minmax(0, 1fr); gap: 6px; margin: 0; padding: 10px 0; border-bottom: 1px solid #ececf0; color: #1c1c1e; font-size: 14px; line-height: 1.9; }
.word-document__event-index { color: #636366; font-variant-numeric: tabular-nums; text-align: right; }
.word-document__event-meta { color: #52647b; }
.word-document__event-content { overflow-wrap: anywhere; }
@media (max-width: 720px) { .word-document__page { width: calc(100% - 20px); margin: 10px auto; padding: 28px 22px 38px; } .word-document__toolbar { align-items: flex-start; flex-direction: column; gap: 4px; } }
</style>
