<template>
  <div class="space-y-6">
    <div class="flex justify-between items-center">
      <div>
        <h1 class="text-2xl font-bold text-gray-800">案件剧本库</h1>
        <p class="text-sm text-gray-500 mt-1">管理训练案件、校验场景人物配置，并支持案件二次编辑与 AI 补全。</p>
      </div>
      <van-button type="primary" icon="plus" class="!bg-[#1D3557] !border-none px-6" @click="openAddModal">
        录入新案件
      </van-button>
    </div>

    <div class="bg-white rounded-[2rem] shadow-sm border border-gray-100 p-6">
      <div class="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <h2 class="text-lg font-bold text-gray-800">场景人物校验</h2>
          <p class="text-sm text-gray-500 mt-1">检查是否把死者放进可对话场景、是否缺少主说话人、是否存在未绑定人物。</p>
        </div>
        <div class="flex gap-3">
          <van-button plain type="primary" :loading="auditLoading" @click="fetchSceneRoleAudit">重新校验</van-button>
          <van-button type="warning" :loading="repairing" @click="repairSceneRoles">一键修复</van-button>
        </div>
      </div>

      <div class="grid grid-cols-1 md:grid-cols-3 gap-4 mt-5">
        <div class="rounded-2xl bg-slate-50 border border-slate-100 px-5 py-4">
          <div class="text-[11px] uppercase tracking-widest text-slate-400 font-black">案件数</div>
          <div class="text-2xl font-black text-slate-700 mt-2">{{ auditSummary.caseCount }}</div>
        </div>
        <div class="rounded-2xl bg-amber-50 border border-amber-100 px-5 py-4">
          <div class="text-[11px] uppercase tracking-widest text-amber-400 font-black">问题场景</div>
          <div class="text-2xl font-black text-amber-700 mt-2">{{ auditSummary.issueSceneCount }}</div>
        </div>
        <div class="rounded-2xl bg-emerald-50 border border-emerald-100 px-5 py-4">
          <div class="text-[11px] uppercase tracking-widest text-emerald-400 font-black">最近修复</div>
          <div class="text-2xl font-black text-emerald-700 mt-2">{{ auditSummary.lastRepairCount }}</div>
        </div>
      </div>
    </div>

    <div v-if="cases.length > 0" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
      <div
        v-for="caseItem in cases"
        :key="caseItem.id"
        class="bg-white rounded-[2rem] shadow-sm border border-gray-100 hover:shadow-xl hover:-translate-y-1 transition-all duration-300 p-8 flex flex-col group cursor-pointer"
        @click="editCase(caseItem)"
      >
        <div class="flex justify-between items-start mb-6">
          <div class="w-12 h-12 bg-blue-50 rounded-2xl flex items-center justify-center border border-blue-100/50">
            <van-icon name="balance-o" class="text-xl text-blue-600" />
          </div>
          <van-tag round :type="getTagType(caseItem.case_type)" class="px-3 py-1 font-bold">
            {{ caseItem.case_type || '未分类' }}
          </van-tag>
        </div>

        <div class="flex-1 mb-6">
          <h3 class="text-lg font-black text-gray-800 leading-tight mb-2 group-hover:text-[#1D3557] transition-colors">
            {{ caseItem.title }}
          </h3>
          <p class="text-[10px] text-gray-300 font-bold uppercase tracking-widest mb-4">
            CASE_IDENTIFIER: #{{ caseItem.id }}
          </p>
          <p class="text-gray-500 text-sm line-clamp-2 leading-relaxed italic">
            "{{ caseItem.background || '系统正在等待案件背景补充...' }}"
          </p>
        </div>

        <div class="flex items-center justify-between pt-6 border-t border-gray-50">
          <div class="flex items-center space-x-4">
            <div class="flex flex-col">
              <span class="text-[9px] text-gray-400 font-black uppercase">场景数量</span>
              <span class="text-sm font-bold text-gray-700">{{ caseItem.scenes?.length || 0 }} SCENES</span>
            </div>
            <div v-if="getCaseIssueCount(caseItem.id) > 0" class="flex flex-col">
              <span class="text-[9px] text-amber-400 font-black uppercase">校验问题</span>
              <span class="text-sm font-bold text-amber-600">{{ getCaseIssueCount(caseItem.id) }} ISSUES</span>
            </div>
          </div>
          <van-button
            size="small"
            plain
            round
            @click.stop="deleteCase(caseItem)"
            class="!text-red-400 !border-red-50 !bg-red-50/30 opacity-0 group-hover:opacity-100 transition-opacity"
          >
            删除剧本
          </van-button>
        </div>
      </div>
    </div>

    <div v-else class="py-32 text-center flex flex-col items-center">
      <div class="w-24 h-24 bg-gray-50 rounded-[2.5rem] flex items-center justify-center mb-6 border border-dashed border-gray-200">
        <van-icon name="plus" size="30" class="text-gray-200" />
      </div>
      <h3 class="text-gray-400 font-bold mb-2">暂无剧本数据</h3>
      <p class="text-gray-300 text-xs italic max-w-xs mx-auto">点击右上角“录入新案件”，通过 AI 解析快速生成训练案件。</p>
    </div>

    <van-popup v-model:show="showAdd" position="right" :style="{ width: '680px', height: '100%' }" class="flex flex-col">
      <div class="h-16 border-b border-gray-100 flex items-center justify-between px-6 flex-shrink-0 bg-white z-10">
        <h3 class="font-bold text-gray-700">录入新警情案件</h3>
        <van-icon name="cross" class="cursor-pointer text-gray-400" @click="showAdd = false" />
      </div>

      <div class="px-8 py-6 bg-gray-50/50 flex-shrink-0">
        <van-steps :active="currentStep" active-color="#1D3557">
          <van-step>基础录入</van-step>
          <van-step>AI 结构化</van-step>
          <van-step>场景生成</van-step>
        </van-steps>
      </div>

      <div class="flex-1 overflow-y-auto p-8">
        <div v-if="currentStep === 0" class="space-y-6">
          <div class="p-4 bg-blue-50 rounded-lg text-blue-700 text-sm flex items-start leading-relaxed">
            <van-icon name="info-o" class="mr-2 mt-0.5" />
            标题允许纯数字或纯符号，但系统会提醒你确认；案件类型建议先选大类，再选小类。
          </div>

          <div class="space-y-4">
            <div>
              <label class="block text-sm font-bold text-gray-700 mb-2">案件标题</label>
              <input v-model="form.title" type="text" placeholder="例如：某小区邻里纠纷调解" class="form-input" />
            </div>

            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label class="block text-sm font-bold text-gray-700 mb-2">案件大类</label>
                <select v-model="form.caseTypeGroup" class="form-input">
                  <option value="">请选择案件大类</option>
                  <option v-for="group in caseTypeGroups" :key="group.label" :value="group.label">{{ group.label }}</option>
                </select>
              </div>
              <div>
                <label class="block text-sm font-bold text-gray-700 mb-2">案件类型</label>
                <select v-model="form.caseType" class="form-input">
                  <option value="">请选择案件类型</option>
                  <option v-for="type in getTypesByGroup(form.caseTypeGroup)" :key="type" :value="type">{{ type }}</option>
                </select>
              </div>
            </div>

            <div>
              <label class="block text-sm font-bold text-gray-700 mb-2">原始描述 / 文本输入</label>
              <textarea
                v-model="form.rawText"
                rows="10"
                placeholder="请粘贴案件原文、警情摘要、接处警记录、笔录或其他材料..."
                class="form-textarea"
              ></textarea>
            </div>
          </div>
        </div>

        <div v-if="currentStep === 1" class="space-y-6">
          <div v-if="parsing" class="flex flex-col items-center justify-center py-20 space-y-4">
            <van-loading color="#1D3557" vertical>正在进行 AI 解析...</van-loading>
            <p class="text-sm text-gray-400">正在提取案件背景、结构化事实和人物信息</p>
          </div>

          <div v-else class="space-y-6 animate-in fade-in duration-500">
            <div class="bg-indigo-50/50 border border-indigo-100 rounded-xl p-5 space-y-4">
              <div class="flex justify-between items-center pb-3 border-b border-indigo-100/50">
                <span class="font-bold text-indigo-900 flex items-center">
                  <van-icon name="award-o" class="mr-2" /> AI 解析结果预览
                </span>
                <van-button size="mini" plain @click="reparse">重新解析</van-button>
              </div>

              <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <p class="text-xs text-indigo-400 uppercase font-bold">AI 识别类型</p>
                  <p class="text-gray-700 font-medium">{{ aiParsedData.ai_case_type_raw || aiParsedData.case_type || '-' }}</p>
                </div>
                <div>
                  <p class="text-xs text-indigo-400 uppercase font-bold">最终标准类型</p>
                  <p class="text-gray-700 font-medium">{{ aiParsedData.case_type || '-' }}</p>
                </div>
                <div>
                  <p class="text-xs text-indigo-400 uppercase font-bold">所属大类</p>
                  <p class="text-gray-700 font-medium">{{ getCaseTypeGroup(aiParsedData.case_type) || '-' }}</p>
                </div>
                <div>
                  <p class="text-xs text-indigo-400 uppercase font-bold">主要责任方</p>
                  <p class="text-gray-700 font-medium">{{ aiParsedData.main_culprit || '未明确' }}</p>
                </div>
              </div>

              <div
                v-if="showTypeNormalizationHint(aiParsedData)"
                class="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs leading-6 text-amber-700"
              >
                <span class="font-bold">类型纠偏提示：</span>
                AI 原始识别为“{{ aiParsedData.ai_case_type_raw || '未识别' }}”，系统标准化后归类为“{{ aiParsedData.case_type || '其他' }}”。
              </div>

              <div>
                <p class="text-xs text-indigo-400 uppercase font-bold mb-1">案件背景</p>
                <div class="bg-white rounded-lg border border-indigo-100 p-3 text-sm text-gray-600 leading-relaxed">
                  {{ aiParsedData.case_background || '未提取到案件背景' }}
                </div>
              </div>

              <div>
                <p class="text-xs text-indigo-400 uppercase font-bold mb-1">涉及人物</p>
                <div class="flex flex-wrap gap-1 mt-1">
                  <span
                    v-for="person in aiParsedData.persons || []"
                    :key="person.name"
                    class="px-2 py-0.5 bg-white text-xs rounded border border-indigo-100"
                  >
                    {{ person.name }} ({{ person.role || person.status || '未标注' }})
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div v-if="currentStep === 2" class="space-y-6">
          <div v-if="generating" class="flex flex-col items-center justify-center py-20 space-y-4">
            <van-loading color="#1D3557" vertical>AI 正在生成训练场景...</van-loading>
          </div>
          <div v-else class="space-y-4">
            <div
              v-for="(scene, idx) in generatedScenes"
              :key="idx"
              class="border border-gray-100 rounded-xl p-4 bg-gray-50 space-y-3"
            >
              <div class="flex justify-between items-start">
                <h4 class="font-bold text-gray-700">{{ scene.scene_name }}</h4>
                <van-tag type="primary" plain>{{ scene.difficulty }}</van-tag>
              </div>
              <p class="text-sm text-gray-500">{{ scene.scene_description }}</p>
              <div class="grid grid-cols-1 gap-3">
                <div class="bg-white rounded-lg border border-gray-100 p-3">
                  <div class="text-xs font-bold text-gray-500 mb-1">接警简报</div>
                  <div class="text-sm text-gray-600 leading-relaxed">{{ scene.dispatch_brief || '未生成' }}</div>
                </div>
                <div class="bg-white rounded-lg border border-gray-100 p-3">
                  <div class="text-xs font-bold text-gray-500 mb-1">现场第一印象</div>
                  <div class="text-sm text-gray-600 leading-relaxed">{{ scene.first_impression || '未生成' }}</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div class="h-20 border-t border-gray-100 px-8 flex items-center justify-between bg-white flex-shrink-0">
        <van-button v-show="currentStep > 0" plain class="!border-gray-200 !text-gray-500 px-8" @click="currentStep--">
          上一步
        </van-button>
        <div v-show="currentStep === 0"></div>
        <van-button type="primary" class="!bg-[#1D3557] !border-none px-12" :loading="parsing || generating || savingCreate" @click="handleNext">
          {{ currentStep === 2 ? '完成并发布' : '下一步' }}
        </van-button>
      </div>
    </van-popup>

    <van-popup v-model:show="showDetail" position="right" :style="{ width: '920px', height: '100%' }" class="flex flex-col">
      <div class="h-16 border-b border-gray-100 flex items-center justify-between px-6 flex-shrink-0 bg-white z-10">
        <div>
          <h3 class="font-bold text-gray-700">案件详情与二次编辑</h3>
          <p class="text-xs text-gray-400 mt-1">保留原始文本，在缺失时可用 AI 自动补全案件背景和场景关键信息。</p>
        </div>
        <div class="flex items-center gap-3">
          <van-button plain size="small" @click="resetEditableCase" :disabled="!editableCase">重置修改</van-button>
          <van-button type="primary" size="small" class="!bg-[#1D3557] !border-none" :loading="savingDetail" :disabled="!editableCase" @click="saveCaseDetail">
            保存修改
          </van-button>
          <van-icon name="cross" class="cursor-pointer text-gray-400" @click="closeDetail" />
        </div>
      </div>

      <div class="flex-1 overflow-y-auto p-8 bg-[#F8F9FA]">
        <div v-if="editableCase" class="max-w-4xl mx-auto space-y-8 pb-20">
          <section class="bg-white rounded-2xl border border-gray-100 shadow-sm p-6 space-y-5">
            <div class="flex items-center justify-between gap-4">
              <div class="flex items-center space-x-3">
                <van-tag type="primary" size="large" round>{{ editableCase.case_type || '未分类' }}</van-tag>
                <span class="text-xs text-gray-400 font-bold uppercase tracking-widest">ID: #{{ editableCase.id }}</span>
              </div>
              <span class="text-xs text-gray-400">角色与阶段暂为只读，案件基础信息与场景内容可编辑。</span>
            </div>

            <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <label class="block text-sm font-bold text-gray-700 mb-2">案件标题</label>
                <input v-model="editableCase.title" type="text" class="form-input" />
              </div>
              <div>
                <label class="block text-sm font-bold text-gray-700 mb-2">案件大类</label>
                <select v-model="editableCase.case_type_group" class="form-input">
                  <option value="">请选择案件大类</option>
                  <option v-for="group in caseTypeGroups" :key="group.label" :value="group.label">{{ group.label }}</option>
                </select>
              </div>
              <div>
                <label class="block text-sm font-bold text-gray-700 mb-2">案件类型</label>
                <select v-model="editableCase.case_type" class="form-input">
                  <option value="">请选择案件类型</option>
                  <option v-for="type in getTypesByGroup(editableCase.case_type_group)" :key="type" :value="type">{{ type }}</option>
                </select>
              </div>
            </div>

            <div
              v-if="showTypeNormalizationHint(editableCase)"
              class="rounded-lg border border-sky-200 bg-sky-50 px-3 py-2 text-xs leading-6 text-sky-700"
            >
              <span class="font-bold">当前类型状态：</span>
              AI 原始识别为“{{ editableCase.ai_case_type_raw || '未识别' }}”，当前标准类型为“{{ editableCase.case_type || '其他' }}”。
            </div>

            <div class="space-y-3">
              <div class="flex items-center justify-between gap-3">
                <label class="block text-sm font-bold text-gray-700">案件背景</label>
                <span v-if="hasMissingAiFields(editableCase)" class="text-xs text-amber-500">检测到缺失字段，可用 AI 自动补全</span>
              </div>
              <textarea
                v-model="editableCase.background"
                rows="4"
                class="form-textarea"
                placeholder="如录入时未生成成功，可点击下方 AI 补全。"
              ></textarea>
              <div class="supplement-toolbar">
                <div class="supplement-toolbar__text">
                  <div class="supplement-toolbar__title">AI 补全</div>
                  <div class="supplement-toolbar__desc">基于案件原始文本，自动补全案件背景、场景描述、接警简报和现场第一印象。</div>
                </div>
                <van-button size="small" plain type="primary" :loading="supplementingAi" :disabled="!canRunAiSupplement" @click="runAiSupplement">
                  AI 补全背景与场景信息
                </van-button>
              </div>
              <p v-if="!canRunAiSupplement" class="text-xs text-gray-400">
                需要先保留案件原始文本，AI 才能重新解析并补全背景、场景描述、接警简报和第一印象。
              </p>
            </div>

            <div>
              <label class="block text-sm font-bold text-gray-700 mb-2">案件原始文本</label>
              <textarea
                v-model="editableCase.original_content"
                rows="10"
                class="form-textarea original-source-kaiti"
                placeholder="这里保留案件原始文本，AI 补全会基于这段内容重新生成。"
              ></textarea>
            </div>
          </section>

          <section class="space-y-4">
            <h4 class="text-xs font-black text-[#1D3557] uppercase tracking-[0.2em] flex items-center leading-none">
              <span class="w-8 h-px bg-[#1D3557]/20 mr-3"></span> AI 角色建模
            </h4>
            <div class="grid grid-cols-1 gap-4">
              <div
                v-for="role in getStructuredData(editableCase).persons || []"
                :key="role.name"
                class="bg-white p-6 rounded-2xl border border-gray-100 shadow-sm"
              >
                <div class="flex justify-between items-start mb-4">
                  <div class="flex items-center space-x-3">
                    <div class="w-10 h-10 bg-indigo-50 rounded-xl flex items-center justify-center text-indigo-600 font-bold">
                      {{ role.name?.[0] || '?' }}
                    </div>
                    <div>
                      <div class="font-bold text-gray-800">{{ role.name }}</div>
                      <div class="text-[10px] text-gray-400 uppercase font-black">{{ role.role }}</div>
                    </div>
                  </div>
                  <van-tag plain type="primary">{{ role.status || role.role_type || '未标注' }}</van-tag>
                </div>
                <p class="text-xs text-gray-500 leading-relaxed"><span class="font-bold text-gray-700">性格：</span>{{ role.personality || '未填写' }}</p>
              </div>
            </div>
          </section>

          <section class="space-y-4">
            <h4 class="text-xs font-black text-[#1D3557] uppercase tracking-[0.2em] flex items-center leading-none">
              <span class="w-8 h-px bg-[#1D3557]/20 mr-3"></span> 训练场景编辑
            </h4>
            <div class="space-y-4">
              <div
                v-for="scene in editableCase.scenes"
                :key="scene.id"
                class="bg-white p-6 rounded-2xl border border-gray-100 shadow-sm space-y-4"
              >
                <div class="flex justify-between items-center">
                  <h5 class="font-bold text-gray-800 flex items-center">
                    <van-icon name="play-circle-o" class="mr-2 text-blue-500" /> 场景 #{{ scene.id }}
                  </h5>
                  <van-tag type="warning" plain size="medium">{{ scene.difficulty || '中等' }}</van-tag>
                </div>

                <div v-if="getSceneAudit(scene.id)" class="p-3 rounded-xl bg-amber-50 border border-amber-100 text-xs text-amber-700">
                  当前校验：
                  <span v-if="getSceneAudit(scene.id)?.issues?.length">{{ getSceneAudit(scene.id)?.issues.join(' / ') }}</span>
                  <span v-else>未发现问题</span>
                </div>

                <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label class="block text-sm font-bold text-gray-700 mb-2">场景名称</label>
                    <input v-model="scene.name" type="text" class="form-input" />
                  </div>
                  <div>
                    <label class="block text-sm font-bold text-gray-700 mb-2">难度</label>
                    <select v-model="scene.difficulty" class="form-input">
                      <option value="简单">简单</option>
                      <option value="中等">中等</option>
                      <option value="困难">困难</option>
                    </select>
                  </div>
                </div>

                <div>
                  <label class="block text-sm font-bold text-gray-700 mb-2">场景描述</label>
                  <textarea v-model="scene.description" rows="3" class="form-textarea" placeholder="如为空，可通过上方 AI 补全自动生成。"></textarea>
                </div>

                <div>
                  <label class="block text-sm font-bold text-gray-700 mb-2">接警简报</label>
                  <textarea v-model="scene.dispatch_brief" rows="3" class="form-textarea" placeholder="如为空，可通过上方 AI 补全自动生成。"></textarea>
                </div>

                <div>
                  <label class="block text-sm font-bold text-gray-700 mb-2">现场第一印象</label>
                  <textarea v-model="scene.first_impression" rows="3" class="form-textarea" placeholder="如为空，可通过上方 AI 补全自动生成。"></textarea>
                </div>

                <div>
                  <label class="block text-sm font-bold text-gray-700 mb-2">阶段配置（JSON）</label>
                  <textarea v-model="scene.stagesText" rows="6" class="form-textarea font-mono text-xs"></textarea>
                </div>
              </div>
            </div>
          </section>
        </div>
      </div>
    </van-popup>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { showConfirmDialog, showToast } from 'vant'
import request from '../utils/request'

const route = useRoute()
const router = useRouter()

const caseTypeGroups = [
  { label: '纠纷求助类', options: ['邻里纠纷', '家庭纠纷', '感情纠纷', '劳资纠纷', '消费纠纷', '噪音扰民', '失踪求助', '自杀干预', '校园警情', '宠物纠纷'] },
  { label: '治安案件类', options: ['打架斗殴', '寻衅滋事', '故意伤害', '损毁财物', '醉酒闹事', '赌博', '卖淫嫖娼', '非法侵入住宅'] },
  { label: '刑事案件类', options: ['故意杀人', '盗窃', '扒窃', '诈骗', '电信网络诈骗', '入室盗窃', '抢夺抢劫', '敲诈勒索', '涉毒'] },
  { label: '交通警情类', options: ['交通事故', '酒驾醉驾', '肇事逃逸'] },
  { label: '其他', options: ['其他'] },
]

const caseTypeGroupMap = Object.fromEntries(caseTypeGroups.map((group) => [group.label, group.options]))

const cases = ref<any[]>([])
const showAdd = ref(false)
const currentStep = ref(0)
const parsing = ref(false)
const generating = ref(false)
const savingCreate = ref(false)
const auditLoading = ref(false)
const repairing = ref(false)
const showDetail = ref(false)
const selectedCase = ref<any>(null)
const editableCase = ref<any>(null)
const savingDetail = ref(false)
const supplementingAi = ref(false)

const form = reactive({
  title: '',
  caseTypeGroup: '',
  caseType: '',
  rawText: ''
})

const aiParsedData = ref<any>({})
const generatedScenes = ref<any[]>([])
const auditCases = ref<any[]>([])

const auditSummary = reactive({
  caseCount: 0,
  issueSceneCount: 0,
  lastRepairCount: 0
})

const shouldWarnOnTitle = (title: string) => {
  const trimmed = (title || '').trim()
  if (!trimmed) return false
  const allDigits = /^\d+$/.test(trimmed)
  const hasWordLikeChar = /[\p{L}\p{N}]/u.test(trimmed)
  const allSymbols = !hasWordLikeChar
  return allDigits || allSymbols
}

const safeJsonParse = (value: any, fallback: any) => {
  if (Array.isArray(fallback) && Array.isArray(value)) return value
  if (!Array.isArray(fallback) && value && typeof value === 'object') return value
  if (!value) return fallback
  try {
    return typeof value === 'string' ? JSON.parse(value) : value
  } catch {
    return fallback
  }
}

const stringifyStages = (value: any) => JSON.stringify(safeJsonParse(value, []), null, 2)
const getStructuredData = (caseItem: any) => safeJsonParse(caseItem?.structured_data, {})

const getCaseTypeGroup = (caseType: string) => {
  const target = String(caseType || '').trim()
  if (!target) return ''
  const match = caseTypeGroups.find((group) => group.options.includes(target))
  return match?.label || ''
}

const getTypesByGroup = (groupLabel: string) => {
  if (!groupLabel) return caseTypeGroups.flatMap((group) => group.options)
  return caseTypeGroupMap[groupLabel] || []
}

const showTypeNormalizationHint = (item: any) => {
  const rawType = String(item?.ai_case_type_raw || '').trim()
  const normalizedType = String(item?.case_type || '').trim()
  return !!rawType && !!normalizedType && rawType !== normalizedType
}

const normalizeEditableCase = (caseItem: any) => {
  const cloned = JSON.parse(JSON.stringify(caseItem))
  cloned.case_type_group = getCaseTypeGroup(cloned.case_type)
  cloned.scenes = (cloned.scenes || []).map((scene: any) => ({
    ...scene,
    stagesText: stringifyStages(scene.stages)
  }))
  return cloned
}

const isBlank = (value: any) => !String(value || '').trim()

const hasMissingAiFields = (caseItem: any) => {
  if (!caseItem) return false
  if (isBlank(caseItem.background)) return true
  return (caseItem.scenes || []).some((scene: any) => isBlank(scene.description) || isBlank(scene.dispatch_brief) || isBlank(scene.first_impression))
}

const canRunAiSupplement = () => !isBlank(editableCase.value?.original_content)

const syncCaseFromQuery = () => {
  const rawCaseId = route.query.case_id
  const caseId = Number(rawCaseId)
  if (!rawCaseId || Number.isNaN(caseId) || caseId <= 0) return
  const targetCase = cases.value.find((item: any) => item.id === caseId)
  if (targetCase) {
    selectedCase.value = targetCase
    editableCase.value = normalizeEditableCase(targetCase)
    showDetail.value = true
  }
}

const fetchCases = async () => {
  try {
    const res: any = await request.get('/cases/')
    cases.value = res || []
    syncCaseFromQuery()
  } catch (error) {
    console.error('Fetch cases failed:', error)
  }
}

const fetchSceneRoleAudit = async () => {
  auditLoading.value = true
  try {
    const res: any = await request.get('/cases/scene-role-audit')
    auditCases.value = res.cases || []
    auditSummary.caseCount = res.case_count || 0
    auditSummary.issueSceneCount = res.issue_scene_count || 0
  } catch {
    showToast('校验失败')
  } finally {
    auditLoading.value = false
  }
}

const repairSceneRoles = async () => {
  showConfirmDialog({
    title: '确认修复',
    message: '系统会按案件信息重新整理场景主说话人，确保活人说话、死者不说话，并避免主角色缺失。'
  }).then(async () => {
    repairing.value = true
    try {
      const res: any = await request.post('/cases/scene-role-repair', {})
      auditCases.value = res.audit?.cases || []
      auditSummary.caseCount = res.audit?.case_count || 0
      auditSummary.issueSceneCount = res.audit?.issue_scene_count || 0
      auditSummary.lastRepairCount = res.repaired_scene_count || 0
      showToast({ type: 'success', message: `修复完成，处理 ${res.repaired_scene_count || 0} 个场景` })
      await fetchCases()
    } catch {
      showToast('修复失败')
    } finally {
      repairing.value = false
    }
  }).catch(() => {})
}

const openAddModal = () => {
  showAdd.value = true
  currentStep.value = 0
  form.title = ''
  form.caseTypeGroup = ''
  form.caseType = ''
  form.rawText = ''
  aiParsedData.value = {}
  generatedScenes.value = []
}

const startParsing = async () => {
  parsing.value = true
  try {
    const res: any = await request.post('/cases/parse', { text: form.rawText })
    aiParsedData.value = res || {}
    if (res?.case_type) {
      form.caseType = res.case_type
      form.caseTypeGroup = getCaseTypeGroup(res.case_type)
    }
  } catch {
    showToast('AI 解析失败')
  } finally {
    parsing.value = false
  }
}

const startGenerating = async () => {
  generating.value = true
  try {
    const res: any = await request.post('/cases/generate-scenes', { case_info: aiParsedData.value })
    generatedScenes.value = res.scenes || []
  } catch {
    showToast('场景生成失败')
  } finally {
    generating.value = false
  }
}

const submitFinal = async () => {
  savingCreate.value = true
  try {
    await request.post('/cases/full-create', {
      case: {
        ...form,
        ...aiParsedData.value,
        case_type: form.caseType || aiParsedData.value.case_type,
        original_content: form.rawText
      },
      scenes: generatedScenes.value
    })
    showToast({ type: 'success', message: '发布成功' })
    showAdd.value = false
    await fetchCases()
    await fetchSceneRoleAudit()
  } catch {
    showToast('发布失败')
  } finally {
    savingCreate.value = false
  }
}

const handleNext = async () => {
  if (currentStep.value === 0) {
    if (!form.title || !form.rawText) {
      showToast('请填写完整')
      return
    }
    if (shouldWarnOnTitle(form.title)) {
      try {
        await showConfirmDialog({
          title: '标题提示',
          message: '当前案件标题看起来是纯数字或纯符号。系统允许继续保存，但建议确认这就是最终展示标题。'
        })
      } catch {
        return
      }
    }
    currentStep.value = 1
    await startParsing()
    return
  }

  if (currentStep.value === 1) {
    currentStep.value = 2
    await startGenerating()
    return
  }

  await submitFinal()
}

const reparse = async () => {
  await startParsing()
}

const editCase = (caseItem: any) => {
  selectedCase.value = caseItem
  editableCase.value = normalizeEditableCase(caseItem)
  showDetail.value = true
  if (caseItem?.id) {
    router.replace(`/admin/cases?case_id=${caseItem.id}`)
  }
}

const closeDetail = () => {
  showDetail.value = false
  selectedCase.value = null
  editableCase.value = null
  router.replace('/admin/cases')
}

const resetEditableCase = () => {
  if (!selectedCase.value) return
  editableCase.value = normalizeEditableCase(selectedCase.value)
}

const runAiSupplement = async () => {
  if (!editableCase.value) return
  const rawText = String(editableCase.value.original_content || '').trim()
  if (!rawText) {
    showToast('请先保留案件原始文本，再执行 AI 补全')
    return
  }

  supplementingAi.value = true
  try {
    const parsed: any = await request.post('/cases/parse', { text: rawText })
    const mergedCaseInfo = {
      ...parsed,
      case_name: editableCase.value.title || parsed.case_name,
      case_type: editableCase.value.case_type || parsed.case_type,
      case_background: parsed.case_background || editableCase.value.background,
    }
    const generated: any = await request.post('/cases/generate-scenes', { case_info: mergedCaseInfo })
    const generatedScenesByIndex = generated.scenes || []

    editableCase.value.background = parsed.case_background || editableCase.value.background
    editableCase.value.ai_case_type_raw = parsed.ai_case_type_raw || editableCase.value.ai_case_type_raw
    if (!editableCase.value.case_type && parsed.case_type) {
      editableCase.value.case_type = parsed.case_type
    }
    editableCase.value.case_type_group = getCaseTypeGroup(editableCase.value.case_type)

    editableCase.value.scenes = (editableCase.value.scenes || []).map((scene: any, index: number) => {
      const aiScene = generatedScenesByIndex[index] || {}
      return {
        ...scene,
        description: aiScene.scene_description || scene.description,
        dispatch_brief: aiScene.dispatch_brief || scene.dispatch_brief,
        first_impression: aiScene.first_impression || scene.first_impression,
        stagesText: scene.stagesText || stringifyStages(scene.stages),
      }
    })

    const structuredData = {
      ...getStructuredData(editableCase.value),
      ...parsed,
      case_name: editableCase.value.title,
      case_type: editableCase.value.case_type,
      case_background: editableCase.value.background,
      rawText,
    }
    editableCase.value.structured_data = JSON.stringify(structuredData, null, 2)

    showToast({ type: 'success', message: 'AI 已根据案件原文补全背景与场景信息' })
  } catch {
    showToast('AI 补全失败')
  } finally {
    supplementingAi.value = false
  }
}

const saveCaseDetail = async () => {
  if (!editableCase.value?.id) return
  if (!editableCase.value.title?.trim()) {
    showToast('案件标题不能为空')
    return
  }

  const scenesPayload = []
  for (const scene of editableCase.value.scenes || []) {
    let parsedStages = []
    try {
      parsedStages = JSON.parse(scene.stagesText || '[]')
      if (!Array.isArray(parsedStages)) throw new Error('not_array')
    } catch {
      showToast(`场景「${scene.name || scene.id}」的阶段配置不是合法 JSON 数组`)
      return
    }

    scenesPayload.push({
      id: scene.id,
      name: scene.name,
      description: scene.description,
      difficulty: scene.difficulty,
      dispatch_brief: scene.dispatch_brief,
      first_impression: scene.first_impression,
      stages: parsedStages
    })
  }

  savingDetail.value = true
  try {
    const structuredData = {
      ...getStructuredData(editableCase.value),
      case_name: editableCase.value.title,
      case_type: editableCase.value.case_type,
      case_background: editableCase.value.background,
      rawText: editableCase.value.original_content
    }

    const res: any = await request.put(`/cases/${editableCase.value.id}`, {
      case: {
        title: editableCase.value.title,
        case_type: editableCase.value.case_type,
        background: editableCase.value.background,
        original_content: editableCase.value.original_content,
        structured_data: structuredData
      },
      scenes: scenesPayload
    })

    showToast({ type: 'success', message: '案件已更新' })
    selectedCase.value = res
    editableCase.value = normalizeEditableCase(res)
    await fetchCases()
    await fetchSceneRoleAudit()
  } catch {
    showToast('保存失败')
  } finally {
    savingDetail.value = false
  }
}

const deleteCase = (caseItem: any) => {
  showConfirmDialog({
    title: '确认删除',
    message: `确定要删除《${caseItem.title}》吗？此操作不可撤销。`
  }).then(async () => {
    try {
      await request.delete(`/cases/${caseItem.id}`)
      showToast({ type: 'success', message: '剧本已删除' })
      if (selectedCase.value?.id === caseItem.id) {
        closeDetail()
      }
      await fetchCases()
      await fetchSceneRoleAudit()
    } catch {
      showToast('删除失败')
    }
  }).catch(() => {})
}

const getTagType = (type: string) => {
  if (['邻里纠纷', '家庭纠纷', '感情纠纷', '劳资纠纷', '消费纠纷'].includes(type)) return 'success'
  if (['打架斗殴', '寻衅滋事', '故意伤害', '故意杀人'].includes(type)) return 'danger'
  if (['盗窃', '诈骗', '电信网络诈骗', '入室盗窃', '抢夺抢劫'].includes(type)) return 'warning'
  return 'primary'
}

const getCaseAudit = (caseId: number) => auditCases.value.find((item: any) => item.case_id === caseId)
const getCaseIssueCount = (caseId: number) => getCaseAudit(caseId)?.issue_scene_count || 0

const getSceneAudit = (sceneId: number) => {
  for (const caseAudit of auditCases.value) {
    const sceneAudit = (caseAudit.scenes || []).find((item: any) => item.scene_id === sceneId)
    if (sceneAudit) return sceneAudit
  }
  return null
}

onMounted(async () => {
  await fetchCases()
  await fetchSceneRoleAudit()
})
</script>

<style scoped>
.line-clamp-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.form-input {
  width: 100%;
  padding: 0.65rem 1rem;
  background: white;
  border: 1px solid rgb(229 231 235);
  border-radius: 0.75rem;
  transition: all 0.2s ease;
  outline: none;
}

.form-input:focus {
  border-color: #1d3557;
  box-shadow: 0 0 0 3px rgb(29 53 87 / 10%);
}

.form-textarea {
  width: 100%;
  padding: 0.8rem 1rem;
  background: white;
  border: 1px solid rgb(229 231 235);
  border-radius: 0.75rem;
  transition: all 0.2s ease;
  outline: none;
  resize: vertical;
}

.form-textarea:focus {
  border-color: #1d3557;
  box-shadow: 0 0 0 3px rgb(29 53 87 / 10%);
}

.original-source-kaiti {
  font-family: "PingFang SC", "Microsoft YaHei", "Heiti SC", "SimHei", sans-serif;
  font-size: 15px;
  line-height: 1.9;
  letter-spacing: 0.02em;
}

.supplement-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 14px 16px;
  border: 1px solid rgb(219 234 254);
  border-radius: 14px;
  background: rgb(248 251 255);
}

.supplement-toolbar__text {
  min-width: 0;
}

.supplement-toolbar__title {
  font-size: 13px;
  font-weight: 700;
  color: #1d3557;
}

.supplement-toolbar__desc {
  margin-top: 4px;
  font-size: 12px;
  line-height: 1.6;
  color: #64748b;
}
</style>
