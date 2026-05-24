import fs from 'fs'
import path from 'path'
import { fileURLToPath } from 'url'

const filePath = path.join(path.dirname(fileURLToPath(import.meta.url)), 'src/views/Cases.vue')
let text = fs.readFileSync(filePath, 'utf8')

// remove refs and editCase lines
text = text.replace(/\nconst showAdvancedEditor = ref\(false\)/, '')
text = text.replace(/\nconst showFullOriginalText = ref\(false\)/, '')
text = text.replace(
  /\n  showAdvancedEditor\.value = false\n  showFullOriginalText\.value = false\n  if \(Array\.isArray\(editableCase\.value\?\.persons\)\) \{\n    editableCase\.value\.persons\.forEach\(\(person: any\) => \{\n      person\._collapsed = true\n    \}\)\n  \}/,
  '\n  if (Array.isArray(editableCase.value?.persons)) {\n    editableCase.value.persons.forEach((person: any) => {\n      person._collapsed = true\n    })\n  }'
)

// remove advanced toggle button block
text = text.replace(
  /\n          <van-button plain size="small" @click="showAdvancedEditor = !showAdvancedEditor">\n            \{\{ showAdvancedEditor \? '收起高级' : '高级配置' \}\}\n          <\/van-button>/,
  ''
)

// remove role-compact-table block
text = text.replace(
  /\n              <div v-if="!showAdvancedEditor && editableCase\.persons\?\.length" class="role-compact-table space-y-2">[\s\S]*?\n              <\/motion>\n              <div v-if="showAdvancedEditor && editableCase\.persons\?\.length" class="persona-stack-list">/,
  '\n              <motion v-if="editableCase.persons?.length" class="persona-stack-list">'
)
text = text.replace(
  /\n              <div v-if="!showAdvancedEditor && editableCase\.persons\?\.length" class="role-compact-table space-y-2">[\s\S]*?\n              <\/div>\n              <motion v-if="showAdvancedEditor && editableCase\.persons\?\.length" class="persona-stack-list">/,
  '\n              <div v-if="editableCase.persons?.length" class="persona-stack-list">'
)

// attribute cleanups
text = text.replace(/\s+v-if="showAdvancedEditor && /g, ' v-if="')
text = text.replace(/\s+v-if="!showAdvancedEditor && /g, ' v-if="')
text = text.replace(/\s+v-if="showAdvancedEditor"/g, '')
text = text.replace(/\s+:class="showAdvancedEditor \? 'md:grid-cols-3' : 'md:grid-cols-2'"/g, ' class="grid grid-cols-1 gap-4 md:grid-cols-3"')
text = text.replace(/class="grid grid-cols-1 gap-4" class="grid grid-cols-1 gap-4 md:grid-cols-3"/g, 'class="grid grid-cols-1 gap-4 md:grid-cols-3"')

// remove duplicate supplement inline toolbar
text = text.replace(
  /\n            <div v-if="!showAdvancedEditor" class="supplement-toolbar supplement-toolbar--inline">[\s\S]*?\n            <\/div>\n            <p v-if="!canRunAiSupplement"/,
  '\n            <p v-if="!canRunAiSupplement"'
)

// remove compact original in basic
text = text.replace(
  /\n            <div v-if="!showAdvancedEditor" class="source-panel source-panel--compact">[\s\S]*?\n            <\/motion>\n            <\/section>/,
  '\n            </section>'
)
text = text.replace(
  /\n            <div v-if="!showAdvancedEditor" class="source-panel source-panel--compact">[\s\S]*?\n            <\/motion>\n            <\/section>/,
  '\n            </section>'
)

// amber section always visible
text = text.replace(
  '<section v-if="showAdvancedEditor" class="workspace-panel workspace-panel--amber">',
  '<section class="workspace-panel workspace-panel--amber">'
)

// fix mistaken motion tags
const bad = ['m', 'o', 't', 'i', 'o', 'n'].join('')
text = text.split('<' + bad).join('<div')
text = text.split('</' + bad + '>').join('</div>')

// remove orphaned v-else hint lines (simple)
text = text.replace(/\n                <p v-else class="mb-2 text-xs text-slate-500">勾选到场角色并指定主对话人。<\/p>/g, '')
text = text.replace(
  /\n                <p v-if="!showAdvancedEditor" class="mb-3 text-xs text-slate-500">\n                  已配置 \{\{ scene\.stagesModel\?\.length \|\| 0 \}\} 个阶段；考察点与动作由 AI 补全，需调整请打开「高级配置」。\n                <\/p>/g,
  ''
)

// remove css blocks added for advanced mode
text = text.replace(/\n\.supplement-toolbar--inline \{[\s\S]*?\n\.role-compact-table \.role-compact-row \{[\s\S]*?\n\}/, '')

fs.writeFileSync(filePath, text)
console.log('stripped advanced mode')
