<template>
  <div class="space-y-6">
    <section class="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
      <div>
        <h1 class="text-2xl font-black text-slate-800">案件管理</h1>
        <p class="mt-1 text-sm text-slate-500">管理训练案件、校验场景人物关系，并支持普通文本或笔录文件导入。</p>
      </div>
      <van-button type="primary" icon="plus" class="!bg-[#1D3557] !border-none px-6" @click="openAddModal">
        录入新案件
      </van-button>
    </section>

    <section class="rounded-[2rem] border border-slate-100 bg-white p-6 shadow-sm">
      <div class="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <h2 class="text-lg font-bold text-slate-800">场景人物校验</h2>
          <p class="mt-1 text-sm text-slate-500">检查场景主对话人是否缺失，以及是否存在不适合进入训练场景的角色分配。</p>
        </div>
        <div class="flex gap-3">
          <van-button plain type="primary" :loading="auditLoading" @click="fetchSceneRoleAudit">重新校验</van-button>
          <van-button type="warning" :loading="repairing" @click="repairSceneRoles">一键修复</van-button>
        </div>
      </div>

      <div class="mt-5 grid grid-cols-1 gap-4 md:grid-cols-3">
        <div class="rounded-2xl border border-slate-100 bg-slate-50 px-5 py-4">
          <div class="stat-label">案件数</div>
          <div class="stat-value text-slate-700">{{ auditSummary.caseCount }}</div>
        </div>
        <div class="rounded-2xl border border-amber-100 bg-amber-50 px-5 py-4">
          <div class="stat-label text-amber-500">问题场景</div>
          <div class="stat-value text-amber-700">{{ auditSummary.issueSceneCount }}</div>
        </div>
        <div class="rounded-2xl border border-emerald-100 bg-emerald-50 px-5 py-4">
          <div class="stat-label text-emerald-500">最近修复数</div>
          <div class="stat-value text-emerald-700">{{ auditSummary.lastRepairCount }}</div>
        </div>
      </div>
    </section>

    <section v-if="casesLoading" class="rounded-[2rem] border border-slate-100 bg-white py-24 shadow-sm">
      <div class="flex justify-center">
        <van-loading color="#1D3557" vertical>正在加载案件列表...</van-loading>
      </div>
    </section>

    <section v-else-if="casesError" class="rounded-[2rem] border border-amber-200 bg-amber-50 px-8 py-16 text-center">
      <van-icon name="warning-o" size="32" class="text-amber-500" />
      <h3 class="mt-4 text-lg font-bold text-amber-700">{{ casesError }}</h3>
      <p class="mt-2 text-sm text-amber-600">你可以先重新加载列表，不会影响已有的数据。</p>
      <van-button plain type="primary" class="mt-5" @click="refreshCasesPage">重新加载</van-button>
    </section>

    <section v-else-if="cases.length" class="grid grid-cols-1 gap-6 md:grid-cols-2 xl:grid-cols-3">
      <article
        v-for="caseItem in cases"
        :key="caseItem.id"
        class="flex h-full cursor-pointer flex-col rounded-[2rem] border border-slate-100 bg-white p-6 shadow-sm transition hover:shadow-lg"
        @click="editCase(caseItem)"
      >
        <div class="flex items-start justify-between gap-4">
          <div class="min-w-0">
            <div class="text-xs font-black uppercase tracking-[0.18em] text-slate-300">Case #{{ caseItem.id }}</div>
            <h3 class="mt-2 break-all text-lg font-black text-slate-800">{{ caseItem.title || '未命名案件' }}</h3>
          </div>
          <van-tag round :type="getTagType(caseItem.case_type)" class="shrink-0 px-3 py-1 font-bold">
            {{ caseItem.case_type || '未分类' }}
          </van-tag>
        </div>

        <p class="line-clamp-3 mt-4 text-sm leading-7 text-slate-500">
          {{ caseItem.background || '暂无案件背景描述。' }}
        </p>

        <div class="mt-5 flex items-center justify-between text-sm text-slate-500">
          <span>场景 {{ caseItem.scenes?.length || 0 }}</span>
          <span v-if="getCaseIssueCount(caseItem.id)" class="font-bold text-amber-600">问题 {{ getCaseIssueCount(caseItem.id) }}</span>
        </div>

        <div class="mt-auto pt-5 flex justify-end">
          <van-button size="small" plain round class="!border-red-200 !text-red-500" @click.stop="deleteCase(caseItem)">
            删除
          </van-button>
        </div>
      </article>
    </section>

    <section v-else class="rounded-[2rem] border border-dashed border-slate-200 bg-white py-24 text-center">
      <van-icon name="notes-o" size="32" class="text-slate-300" />
      <h3 class="mt-4 text-lg font-bold text-slate-500">暂无案件数据</h3>
      <p class="mt-2 text-sm text-slate-400">点击右上角“录入新案件”开始创建案件。</p>
    </section>

    <van-popup v-model:show="showAdd" position="right" :style="{ width: 'min(96vw, 940px)', height: '100%' }" class="flex flex-col">
      <div class="flex h-16 items-center justify-between border-b border-slate-100 bg-white px-6">
        <div>
          <h3 class="font-bold text-slate-800">录入新案件</h3>
        </div>
        <van-icon name="cross" class="cursor-pointer text-slate-400" @click="showAdd = false" />
      </div>

      <div class="border-b border-slate-100 bg-slate-50/70 px-6 py-4">
        <van-steps :active="currentStep" active-color="#1D3557">
          <van-step>基础录入</van-step>
          <van-step>AI 解析预览</van-step>
          <van-step>场景生成</van-step>
        </van-steps>
      </div>

      <div class="cases-compact flex-1 overflow-y-auto bg-[#F8FAFC] p-4">
        <div v-if="currentStep === 0" class="space-y-3">
          <section class="space-y-3 rounded-2xl border border-slate-100 bg-white p-4">
            <div>
              <label class="form-label">导入方式</label>
              <div class="grid grid-cols-2 gap-3">
                <button type="button" class="mode-card" :class="{ active: importMode === 'plain_case' }" @click="switchImportMode('plain_case')">
                  <span class="mode-card__title">普通案件文本录入</span>
                </button>
                <button type="button" class="mode-card" :class="{ active: importMode === 'transcript_file' }" @click="switchImportMode('transcript_file')">
                  <span class="mode-card__title">笔录文件导入</span>
                </button>
              </div>
            </div>

            <template v-if="importMode === 'plain_case'">
              <div>
                <label class="form-label">案件标题</label>
                <input v-model="form.title" type="text" class="form-input" placeholder="例如：某小区邻里纠纷调解" />
              </div>

              <div class="grid grid-cols-1 gap-4 md:grid-cols-2">
                <div>
                  <label class="form-label">案件大类</label>
                  <select v-model="form.caseTypeGroup" class="form-input">
                    <option value="">请选择案件大类</option>
                    <option v-for="group in caseTypeGroups" :key="group.label" :value="group.label">{{ group.label }}</option>
                  </select>
                </div>
                <div>
                  <label class="form-label">案件类型</label>
                  <select v-model="form.caseType" class="form-input">
                    <option value="">请选择案件类型</option>
                    <option v-for="type in getTypesByGroup(form.caseTypeGroup)" :key="type" :value="type">{{ type }}</option>
                  </select>
                </div>
              </div>

              <div>
                <label class="form-label">原始文本</label>
                <textarea v-model="form.rawText" rows="6" class="form-textarea" placeholder="请粘贴案件原文、警情摘要、接处警记录等内容..."></textarea>
              </div>
            </template>

            <template v-else>
              <div class="file-hint">
                <div class="font-bold text-slate-800">笔录文件导入说明</div>
                <div class="mt-1 text-sm leading-6 text-slate-600">当前支持 PDF、DOCX、MD，单次仅上传 1 个文件，大小不超过 20MB。扫描版 PDF 暂不支持 OCR。</div>
              </div>

              <div class="file-dropzone">
                <input ref="fileInputRef" type="file" accept=".pdf,.docx,.md" class="hidden" @change="handleFileChange" />
                <div v-if="!uploadedFile" class="text-center">
                  <van-icon name="description" size="34" class="text-slate-300" />
                  <div class="mt-3 text-base font-bold text-slate-700">上传笔录文件</div>
                  <div class="mt-2 text-sm text-slate-500">支持 PDF / DOCX / MD</div>
                  <van-button plain type="primary" class="mt-4" @click="chooseFile">选择文件</van-button>
                </div>
                <div v-else class="space-y-3">
                  <div class="flex items-start justify-between gap-4">
                    <div>
                      <div class="break-all text-base font-bold text-slate-800">{{ uploadedFile.name }}</div>
                      <div class="mt-1 text-sm text-slate-500">{{ uploadedFileExtLabel }} · {{ formatFileSize(uploadedFile.size) }}</div>
                    </div>
                    <span class="status-pill" :class="fileParseStatusClass">{{ fileParseStatusText }}</span>
                  </div>
                  <div class="flex gap-3">
                    <van-button plain size="small" @click="chooseFile">重新上传</van-button>
                    <van-button plain size="small" type="danger" @click="clearUploadedFile">移除文件</van-button>
                  </div>
                </div>
              </div>

              <div class="grid grid-cols-1 gap-4 md:grid-cols-3">
                <div>
                  <label class="form-label">案件标题</label>
                  <input v-model="form.title" type="text" class="form-input" placeholder="可先留空，解析后在下一步确认最终标题" />
                  <p class="mt-2 text-xs leading-5 text-slate-400">文件导入时可先不填，解析完成后请在下一步确认最终展示标题。</p>
                </div>
                <div>
                  <label class="form-label">案件大类</label>
                  <select v-model="form.caseTypeGroup" class="form-input">
                    <option value="">AI 识别后可修正</option>
                    <option v-for="group in caseTypeGroups" :key="group.label" :value="group.label">{{ group.label }}</option>
                  </select>
                </div>
                <div>
                  <label class="form-label">案件类型</label>
                  <select v-model="form.caseType" class="form-input">
                    <option value="">AI 识别后可修正</option>
                    <option v-for="type in getTypesByGroup(form.caseTypeGroup)" :key="type" :value="type">{{ type }}</option>
                  </select>
                </div>
              </div>
            </template>
          </section>
        </div>

        <div v-else-if="currentStep === 1" class="space-y-3">
          <div v-if="parsing" class="flex justify-center rounded-2xl border border-slate-100 bg-white py-24">
            <van-loading color="#1D3557" vertical>正在进行 AI 解析...</van-loading>
          </div>
          <div v-else class="space-y-3">
            <section class="space-y-4 rounded-2xl border border-slate-100 bg-white p-5">
              <div class="flex items-center justify-between">
                <div class="text-base font-bold text-slate-800">AI 解析结果预览</div>
                <van-button size="small" plain @click="reparse">重新解析</van-button>
              </div>

              <div class="rounded-xl border border-sky-100 bg-sky-50 px-4 py-3 text-sm text-sky-700">
                这一页用于确认“AI 建议值”和“最终发布值”。
                你在下方输入框里修改的是最终发布内容；上面的识别卡片和下方建议文案仅作为参考。
              </div>

              <div v-if="fileMeta.name" class="grid grid-cols-1 gap-4 md:grid-cols-3">
                <div class="preview-card">
                  <div class="preview-label">上传文件</div>
                  <div class="preview-value break-all">{{ fileMeta.name }}</div>
                </div>
                <div class="preview-card">
                  <div class="preview-label">文件类型</div>
                  <div class="preview-value">{{ fileMeta.type || '-' }}</div>
                </div>
                <div class="preview-card">
                  <div class="preview-label">文件大小</div>
                  <div class="preview-value">{{ formatFileSize(fileMeta.size || 0) }}</div>
                </div>
              </div>

              <div class="section-block section-block--blue">
                <div class="section-block__header">
                  <div>
                    <div class="section-block__eyebrow">第一步</div>
                    <div class="section-block__title">识别概览与最终发布值</div>
                  </div>
                </div>
                <div class="grid grid-cols-1 gap-4 md:grid-cols-2">
                  <div class="preview-card">
                  <div class="preview-label">AI 建议标题</div>
                  <div class="preview-value">{{ aiParsedData.case_name || '未识别' }}</div>
                  </div>
                  <div class="preview-card">
                  <div class="preview-label">解析来源</div>
                  <div class="preview-value">{{ parseEngineLabel(aiParsedData) }}</div>
                  </div>
                  <div class="preview-card">
                  <div class="preview-label">导入来源</div>
                  <div class="preview-value">{{ aiParsedData.source_classification || '-' }}</div>
                  </div>
                  <div class="preview-card">
                  <div class="preview-label">主要责任方</div>
                  <div class="preview-value">{{ aiParsedData.main_culprit || '未明确' }}</div>
                  </div>
                  <div class="preview-card">
                  <div class="preview-label">AI 原始识别类型</div>
                  <div class="preview-value">{{ aiParsedData.ai_case_type_raw || aiParsedData.case_type || '-' }}</div>
                  </div>
                  <div class="preview-card">
                  <div class="preview-label">标准化后类型</div>
                  <div class="preview-value">{{ aiParsedData.case_type || '-' }}</div>
                  </div>
                </div>
              </div>

              <div v-if="parseWarnings(aiParsedData).length" class="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-700">
                <div class="font-bold">复核提醒</div>
                <div v-for="warning in parseWarnings(aiParsedData)" :key="warning" class="mt-1">{{ warning }}</div>
              </div>

              <div v-if="showTypeNormalizationHint(aiParsedData)" class="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-700">
                AI 原始识别为“{{ aiParsedData.ai_case_type_raw || '未识别' }}”，系统标准化后归类为“{{ aiParsedData.case_type || '其他' }}”。
              </div>

              <div class="section-block section-block--neutral">
                <div class="section-block__header">
                  <div>
                    <div class="section-block__eyebrow">第二步</div>
                    <div class="section-block__title">发布信息确认</div>
                  </div>
                </div>
                <div class="grid grid-cols-1 gap-4 md:grid-cols-2">
                  <div>
                  <label class="form-label">最终发布标题</label>
                  <input v-model="form.title" type="text" class="form-input" placeholder="可在发布前调整" />
                  </div>
                  <div>
                  <label class="form-label">最终发布类型</label>
                  <select v-model="form.caseType" class="form-input">
                    <option value="">请选择案件类型</option>
                    <option v-for="type in getTypesByGroup(form.caseTypeGroup || getCaseTypeGroup(aiParsedData.case_type))" :key="type" :value="type">
                      {{ type }}
                    </option>
                  </select>
                  </div>
                </div>
                <div class="mt-4">
                  <label class="form-label">最终案件背景</label>
                  <textarea v-model="aiParsedData.case_background" rows="2" class="form-textarea"></textarea>
                  <p class="mt-2 text-xs leading-5 text-slate-400">这里保存的是最终背景描述；下方“接警简报建议”和“现场第一印象建议”属于 AI 草案。</p>
                </div>
              </div>

              <section v-if="aiParsedData && currentStep >= 1" class="space-y-4 rounded-2xl border border-slate-100 bg-white p-5">
                <div class="flex items-center justify-between gap-3">
                  <div>
                    <div class="section-block__eyebrow">第三步</div>
                    <div class="section-title">AI 角色模板预览</div>
                    <p class="mt-1 text-sm text-slate-500">AI 已为案件人物补出更完整的人设草案。发布前请完成最后一轮人工审核，可直接删角色、改姓名、改身份和人物设定。</p>
                  </div>
                  <div class="flex items-center gap-2">
                    <van-tag type="primary" plain>{{ parsedPersons(aiParsedData).length }} 人</van-tag>
                    <van-button
                      v-if="parsedPersons(aiParsedData).length"
                      size="small"
                      class="persona-toolbar-button"
                      :plain="!areAllParsedPersonsExpanded"
                      type="primary"
                      @click="toggleAllParsedPersons"
                    >
                      {{ areAllParsedPersonsExpanded ? '全部收起' : '全部展开' }}
                    </van-button>
                    <van-button size="small" plain type="primary" class="persona-toolbar-button" @click="addParsedPerson">手动新增角色</van-button>
                  </div>
                </div>
                <div v-if="parsedPersons(aiParsedData).length" class="persona-stack-list">
                  <div
                    v-for="(person, index) in parsedPersons(aiParsedData)"
                    :key="person._editor_id || `person-${index}`"
                    class="persona-stack-card"
                    :class="{ 'is-collapsed': person._collapsed, 'is-expanded': !person._collapsed }"
                    :style="getParsedPersonCardStyle(Number(index), person)"
                  >
                    <div class="persona-stack-shell">
                      <div class="persona-stack-layer persona-stack-layer--back"></div>
                      <div class="persona-stack-layer persona-stack-layer--mid"></div>
                      <div
                        class="persona-stack-surface"
                        :class="{ 'persona-stack-surface--clickable': person._collapsed }"
                        @click="person._collapsed && openParsedPersonCard(person)"
                      >
                        <div class="persona-stack-header">
                          <div class="flex min-w-0 items-center gap-3">
                            <div class="text-base font-bold text-slate-800">{{ person.name || '未命名角色' }}</div>
                            <van-tag plain type="primary">{{ person.role_type || person.role || '相关人员' }}</van-tag>
                            <van-tag plain>{{ person.behavior_archetype || '求助配合型' }}</van-tag>
                          </div>
                          <div class="flex items-center gap-2">
                            <span class="persona-stack-toggle" @click.stop="togglePersonCollapsed(person)">{{ person._collapsed ? '展开详情' : '收起详情' }}</span>
                            <van-button size="small" type="danger" plain @click.stop="removeParsedPerson(Number(index))">删除角色</van-button>
                          </div>
                        </div>
                        <div v-if="person._collapsed" class="persona-stack-summary">
                          <span v-for="item in getCompactPersonaSummary(person)" :key="item">{{ item }}</span>
                        </div>
                        <div v-else class="persona-stack-expanded" @click.stop>
                          <div class="mt-4 grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
                            <div>
                              <label class="form-label form-label--muted">角色姓名</label>
                              <input :value="person.name" type="text" class="form-input" @input="renameParsedPerson(person, ($event.target as HTMLInputElement).value)" />
                            </div>
                            <div>
                              <label class="form-label form-label--muted">人物身份</label>
                              <input v-model="person.role" type="text" class="form-input" placeholder="如报警人、家属、围观者" />
                            </div>
                            <div>
                              <label class="form-label form-label--muted">角色类型</label>
                              <select v-model="person.role_type" class="form-input">
                                <option v-for="option in roleTypeOptions" :key="option" :value="option">{{ option }}</option>
                              </select>
                            </div>
                            <div>
                              <label class="form-label form-label--muted">当前状态</label>
                              <select v-model="person.status" class="form-input">
                                <option v-for="option in statusOptions" :key="option" :value="option">{{ option }}</option>
                              </select>
                            </div>
                            <div>
                              <label class="form-label form-label--muted">行为原型</label>
                              <select v-model="person.behavior_archetype" class="form-input">
                                <option v-for="option in behaviorArchetypeOptions" :key="option.value" :value="option.value">{{ option.value }}</option>
                              </select>
                            </div>
                            <div>
                              <label class="form-label form-label--muted">对警方态度</label>
                              <select v-model="person.police_attitude" class="form-input">
                                <option v-for="option in policeAttitudeOptions" :key="option.value" :value="option.value">{{ option.value }}</option>
                              </select>
                            </div>
                            <div>
                              <label class="form-label form-label--muted">场景行为模式</label>
                              <select v-model="person.scene_behavior_mode" class="form-input">
                                <option v-for="option in sceneBehaviorModeOptions" :key="option.value" :value="option.value">{{ option.value }}</option>
                              </select>
                            </div>
                          </div>
                          <div class="persona-role-summary mt-3">
                            <div class="font-bold text-slate-700">{{ getBehaviorArchetypeSummary(person.behavior_archetype) }}</div>
                            <div class="mt-1 text-xs text-slate-500">{{ getPoliceAttitudeSummary(person.police_attitude) }}</div>
                          </div>
                          <div class="persona-compact-grid mt-3">
                            <section class="persona-compact-panel">
                              <div class="persona-compact-panel__title">诉求与顾虑</div>
                              <div class="mt-3 space-y-3">
                                <div>
                                  <label class="form-label form-label--muted">当前诉求</label>
                                  <textarea v-model="person.current_goal" rows="2" class="form-textarea form-textarea--compact" placeholder="例如：先把人稳下来，不想把事情继续闹大"></textarea>
                                </div>
                                <div>
                                  <label class="form-label form-label--muted">最怕后果</label>
                                  <textarea v-model="person.core_concern" rows="2" class="form-textarea form-textarea--compact" placeholder="例如：最怕被认定先动手，最怕家里和单位知道"></textarea>
                                </div>
                              </div>
                            </section>
                            <section class="persona-compact-panel">
                              <div class="persona-compact-panel__title">触发与安抚</div>
                              <div class="mt-3 space-y-3">
                                <div>
                                  <label class="form-label form-label--muted">触发点</label>
                                  <textarea
                                    rows="2"
                                    class="form-textarea form-textarea--compact"
                                    :value="getPersonListText(person.trigger_points)"
                                    @input="updatePersonListField(person, 'trigger_points', ($event.target as HTMLTextAreaElement).value)"
                                    placeholder="每行一条，例如：被质疑在撒谎&#10;提到赔偿金额&#10;被连续打断"
                                  ></textarea>
                                </div>
                                <div>
                                  <label class="form-label form-label--muted">安抚点</label>
                                  <textarea
                                    rows="2"
                                    class="form-textarea form-textarea--compact"
                                    :value="getPersonListText(person.calming_points)"
                                    @input="updatePersonListField(person, 'calming_points', ($event.target as HTMLTextAreaElement).value)"
                                    placeholder="每行一条，例如：先让他说完整&#10;明确下一步怎么处理&#10;减少围观刺激"
                                  ></textarea>
                                </div>
                              </div>
                            </section>
                            <section class="persona-compact-panel">
                              <div class="persona-compact-panel__title">开场状态</div>
                              <div class="mt-3 grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-4">
                                <div>
                                  <label class="form-label form-label--muted">情绪强度</label>
                                  <select v-model="person.emotion_level" class="form-input">
                                    <option v-for="option in stateLevelOptions" :key="option.value" :value="option.value">{{ option.label }}</option>
                                  </select>
                                </div>
                                <div>
                                  <label class="form-label form-label--muted">配合程度</label>
                                  <select v-model="person.cooperation_level" class="form-input">
                                    <option v-for="option in stateLevelOptions" :key="option.value" :value="option.value">{{ option.label }}</option>
                                  </select>
                                </div>
                                <div>
                                  <label class="form-label form-label--muted">失控风险</label>
                                  <select v-model="person.risk_level" class="form-input">
                                    <option v-for="option in stateLevelOptions" :key="option.value" :value="option.value">{{ option.label }}</option>
                                  </select>
                                </div>
                                <div>
                                  <label class="form-label form-label--muted">表达清晰度</label>
                                  <select v-model="person.clarity_level" class="form-input">
                                    <option v-for="option in stateLevelOptions" :key="option.value" :value="option.value">{{ option.label }}</option>
                                  </select>
                                </div>
                              </div>
                            </section>
                            <section class="persona-compact-panel">
                              <div class="persona-compact-panel__title">场景边界</div>
                              <div class="mt-3 space-y-3">
                                <div class="rounded-2xl border border-slate-100 bg-slate-50 px-3 py-2 text-xs leading-5 text-slate-500">
                                  {{ sceneBehaviorModeOptions.find((option) => option.value === person.scene_behavior_mode)?.summary || '先选场景行为模式，再补对应的信息边界。' }}
                                </div>
                                <div v-for="field in getPersonBoundaryFields(person)" :key="field.key">
                                  <label class="form-label form-label--muted">{{ field.label }}</label>
                                  <textarea
                                    rows="2"
                                    class="form-textarea form-textarea--compact"
                                    :value="getPersonBoundaryFieldText(person, field.key)"
                                    @input="updatePersonListField(person, field.key, ($event.target as HTMLTextAreaElement).value)"
                                    :placeholder="field.placeholder"
                                  ></textarea>
                                </div>
                                <div>
                                  <label class="form-label form-label--muted">当前确实不知道的点</label>
                                  <textarea
                                    rows="2"
                                    class="form-textarea form-textarea--compact"
                                    :value="getPersonListText(person.does_not_know)"
                                    @input="updatePersonListField(person, 'does_not_know', ($event.target as HTMLTextAreaElement).value)"
                                    placeholder="每行一条，补充当前角色确实无法回答的问题。"
                                  ></textarea>
                                </div>
                                <div v-if="person.scene_behavior_mode === '管控型'">
                                  <label class="form-label form-label--muted">酒精 / 药物 / 精神状态说明</label>
                                  <textarea v-model="person.impairment_state" rows="2" class="form-textarea form-textarea--compact" placeholder="例如：饮酒明显，语无伦次，步态不稳。"></textarea>
                                </div>
                              </div>
                            </section>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
                <div v-else class="rounded-2xl border border-dashed border-slate-200 bg-slate-50 px-4 py-6 text-center text-sm text-slate-500">
                  当前还没有可用角色。你可以手动新增角色，补齐 AI 漏掉的人物。
                </div>
              </section>
            </section>

            <section class="section-block section-block--violet">
              <div class="section-block__header">
                <div>
                  <div class="section-block__eyebrow">辅助文案</div>
                  <div class="section-block__title">训练入口提示文案</div>
                </div>
              </div>
              <div class="grid grid-cols-1 gap-4 xl:grid-cols-2">
              <div class="rounded-2xl border border-slate-100 bg-white p-5">
                <div class="section-title">接警简报建议</div>
                <div class="preview-body">{{ aiParsedData.dispatch_brief_suggestion || '暂无' }}</div>
              </div>
              <div class="rounded-2xl border border-slate-100 bg-white p-5">
                <div class="section-title">现场第一印象建议</div>
                <div class="preview-body">{{ aiParsedData.first_impression_suggestion || '暂无' }}</div>
              </div>
              </div>
            </section>
          </div>
        </div>

        <div v-else class="space-y-4">
          <div v-if="generating" class="flex justify-center rounded-2xl border border-slate-100 bg-white py-24">
            <van-loading color="#1D3557" vertical>正在生成训练场景...</van-loading>
          </div>
          <div v-else class="space-y-4">
            <div v-if="sceneGenerationWarning(aiParsedData)" class="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-700">
              <div class="font-bold">{{ sceneGenerationLabel(aiParsedData) }}</div>
              <div class="mt-1">{{ sceneGenerationWarning(aiParsedData) }}</div>
            </div>
            <div v-for="(scene, idx) in generatedScenes" :key="idx" class="scene-editor-card">
              <div class="scene-editor-card__top">
                <div class="scene-editor-card__index">场景 {{ Number(idx) + 1 }}</div>
                <van-tag type="primary" plain>{{ scene.difficulty }}</van-tag>
              </div>
              <div class="scene-editor-card__panel scene-editor-card__panel--summary">
                <div class="scene-editor-card__section-head">
                  <div>
                    <h4 class="scene-editor-card__title">{{ scene.scene_name }}</h4>
                  </div>
                </div>
                <p class="mt-2 text-sm leading-7 text-slate-500">{{ scene.scene_description }}</p>
              </div>

              <div class="scene-editor-card__panel scene-editor-card__panel--roles">
                <div class="scene-editor-card__section-head">
                  <div>
                    <div class="scene-editor-card__section-title">参与角色与主对话人</div>
                  </div>
                </div>
                <div class="mt-2 flex flex-wrap gap-2">
                  <span
                    v-for="roleName in scene.roles || []"
                    :key="roleName"
                    class="inline-flex items-center rounded-full bg-[#1D3557] px-3 py-1 text-xs font-bold text-white"
                  >
                    {{ roleName }}
                  </span>
                </div>
                <div v-if="getSceneRoleRecommendation({ persons: aiParsedData.persons || [] }, { role_names: scene.roles || [] })" class="mt-2 rounded-lg border border-sky-200 bg-sky-50 px-3 py-2 text-xs text-sky-700">
                  推荐理由：{{ getSceneRoleRecommendation({ persons: aiParsedData.persons || [] }, { role_names: scene.roles || [] })?.reason }}
                </div>
              </div>

              <div class="scene-editor-card__panel scene-editor-card__panel--copy">
                <div class="scene-editor-card__section-head">
                  <div></div>
                </div>
                <div class="grid grid-cols-1 gap-4 xl:grid-cols-2">
                  <div class="preview-card">
                    <div class="preview-label">接警简报</div>
                    <div class="preview-body">{{ scene.dispatch_brief || '暂无' }}</div>
                  </div>
                  <div class="preview-card">
                    <div class="preview-label">现场第一印象</div>
                    <div class="preview-body">{{ scene.first_impression || '暂无' }}</div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div class="flex h-20 items-center justify-between border-t border-slate-100 bg-white px-8">
        <van-button v-show="currentStep > 0" plain class="!border-slate-200 !text-slate-500 px-8" @click="currentStep -= 1">
          上一步
        </van-button>
        <div v-show="currentStep === 0"></div>
        <van-button type="primary" class="!bg-[#1D3557] !border-none px-12" :loading="parsing || generating || savingCreate" @click="handleNext">
          {{ currentStep === 2 ? '完成并发布' : '下一步' }}
        </van-button>
      </div>
    </van-popup>

    <van-popup v-model:show="showDetail" position="right" :style="{ width: '920px', height: '100%' }" class="flex flex-col">
      <div class="flex h-16 items-center justify-between border-b border-slate-100 bg-white px-6">
        <div>
          <h3 class="font-bold text-slate-800">案件详情与二次编辑</h3>
        </div>
        <div class="flex items-center gap-3">
          <van-button plain size="small" :disabled="!editableCase" @click="resetEditableCase">重置修改</van-button>
          <van-button type="primary" size="small" class="!bg-[#1D3557] !border-none" :loading="savingDetail" :disabled="!editableCase" @click="saveCaseDetail">
            保存修改
          </van-button>
          <van-icon name="cross" class="cursor-pointer text-slate-400" @click="closeDetail" />
        </div>
      </div>

      <div class="cases-compact flex-1 overflow-y-auto bg-[#F8FAFC] p-4">
        <div v-if="editableCase" class="mx-auto max-w-4xl space-y-3 pb-12">
          <nav class="review-module-nav" aria-label="审核模块">
            <button
              v-for="module in reviewModules"
              :key="module.id"
              type="button"
              class="review-module-nav__item"
              :class="{ 'is-active': activeReviewModule === module.id }"
              @click="setReviewModule(module.id)"
            >
              <span class="review-module-nav__step">{{ module.step }}</span>
              <span class="review-module-nav__label">{{ module.label }}</span>
            </button>
          </nav>

          <section v-show="activeReviewModule === 'basic'" class="workspace-panel workspace-panel--indigo">
            <div class="workspace-panel__header">
              <div>
                <div class="workspace-panel__eyebrow">01 基础信息</div>
                <h4 class="workspace-panel__title">案件标题、分类与背景</h4>
              </div>
              <van-button size="small" type="primary" class="!border-none !bg-[#1D3557]" :loading="supplementingAi" :disabled="!canRunAiSupplement" @click="runAiSupplement">
                AI 补全
              </van-button>
            </div>
            <div class="workspace-panel__body">
          <section class="space-y-3 rounded-2xl border border-slate-100 bg-white p-4">
            <div class="supplement-toolbar supplement-toolbar--inline">
              <van-button size="small" plain type="primary" :loading="supplementingAi" :disabled="!canRunAiSupplement" @click="runAiSupplement">
                AI 补全全部
              </van-button>
            </div>
            <div class="flex items-center justify-between gap-4">
              <div class="flex items-center gap-3">
                <van-tag type="primary" round>{{ editableCase.case_type || '未分类' }}</van-tag>
                <span class="text-xs font-bold uppercase tracking-widest text-slate-400">ID: #{{ editableCase.id }}</span>
              </div>
            </div>

            <div class="grid grid-cols-1 gap-4 md:grid-cols-3">
              <div>
                <label class="form-label">案件标题</label>
                <input v-model="editableCase.title" type="text" class="form-input" />
              </div>
              <div>
                <label class="form-label">案件大类</label>
                <select v-model="editableCase.case_type_group" class="form-input">
                  <option value="">请选择案件大类</option>
                  <option v-for="group in caseTypeGroups" :key="group.label" :value="group.label">{{ group.label }}</option>
                </select>
              </div>
              <div>
                <label class="form-label">案件类型</label>
                <select v-model="editableCase.case_type" class="form-input">
                  <option value="">请选择案件类型</option>
                  <option v-for="type in getTypesByGroup(editableCase.case_type_group)" :key="type" :value="type">{{ type }}</option>
                </select>
              </div>
            </div>

            <div v-if="showTypeNormalizationHint(editableCase)" class="rounded-xl border border-sky-200 bg-sky-50 px-4 py-3 text-sm text-sky-700">
              AI 原始识别为“{{ editableCase.ai_case_type_raw || '未识别' }}”，当前标准化类型为“{{ editableCase.case_type || '其他' }}”。
            </div>

            <div v-if="parseWarnings(editableCase).length || sceneGenerationWarning(editableCase)" class="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-700">
              <div class="font-bold">AI 补全复核提醒</div>
              <div class="mt-1">解析来源：{{ parseEngineLabel(editableCase) }}</div>
              <div v-for="warning in parseWarnings(editableCase)" :key="warning" class="mt-1">{{ warning }}</div>
              <div v-if="sceneGenerationWarning(editableCase)" class="mt-1">{{ sceneGenerationWarning(editableCase) }}</div>
            </div>

            <div>
              <label class="form-label">案件背景</label>
              <textarea v-model="editableCase.background" rows="2" class="form-textarea"></textarea>
            </div>

            <div class="source-panel">
              <div class="source-panel__header">
                <label class="block text-sm font-bold text-slate-700">案件原始文本</label>
                <span class="source-panel__meta">
                  {{ String(editableCase.original_content || '').trim() ? `${String(editableCase.original_content || '').trim().length} 字` : '暂无内容' }}
                </span>
                <van-button size="mini" plain type="primary" @click="showOriginalExpanded = !showOriginalExpanded">
                  {{ showOriginalExpanded ? '收起' : '展开全文' }}
                </van-button>
              </div>
              <p v-if="!showOriginalExpanded" class="text-xs leading-5 text-slate-500">原文已保留；需要校对或补全失败时再展开全文。</p>
              <textarea
                v-else
                v-model="editableCase.original_content"
                rows="10"
                class="form-textarea source-panel__textarea"
                placeholder="导入文件提取出的案件原文会保留在这里，支持继续人工整理。"
              ></textarea>
            </div>
            </section>
            </div>
          </section>


            <section v-show="activeReviewModule === 'roles'" class="workspace-panel workspace-panel--cyan">
              <div class="workspace-panel__header">
                <div>
                  <div class="workspace-panel__eyebrow">02 角色审核</div>
                  <h4 class="workspace-panel__title">角色信息复核</h4>
                </div>
                <div class="workspace-panel__badge">人工复核</div>
              </div>
              <div class="workspace-panel__body">
              <section class="space-y-4 rounded-2xl border border-slate-100 bg-white p-4">
              <div class="flex items-center justify-between gap-3">
                <div>
                  <div class="text-sm font-bold text-slate-700">角色模板</div>
                </div>
                <div class="flex items-center gap-2">
                  <van-button
                    v-if="editableCase.persons.length"
                    size="small"
                    class="persona-toolbar-button"
                    :plain="!areAllEditablePersonsExpanded"
                    type="primary"
                    @click="toggleAllEditablePersons"
                  >
                    {{ areAllEditablePersonsExpanded ? '全部收起' : '全部展开' }}
                  </van-button>
                  <van-button size="small" plain type="primary" @click="addEditablePerson">新增角色</van-button>
                </div>
              </div>
              <div v-if="editableCase.persons?.length" class="persona-stack-list">
                  <div
                    v-for="(person, index) in editableCase.persons"
                    :key="person._editor_id || `role-${index}`"
                    class="persona-stack-card"
                    :class="{ 'is-collapsed': person._collapsed, 'is-expanded': !person._collapsed }"
                    :style="getEditablePersonCardStyle(Number(index), person)"
                  >
                    <div class="persona-stack-shell">
                      <div class="persona-stack-layer persona-stack-layer--back"></div>
                      <div class="persona-stack-layer persona-stack-layer--mid"></div>
                      <div
                        class="persona-stack-surface"
                        :class="{ 'persona-stack-surface--clickable': person._collapsed }"
                        @click="person._collapsed && openEditablePersonCard(person)"
                      >
                        <div class="persona-stack-header">
                          <div class="flex min-w-0 items-center gap-3">
                            <div class="text-base font-bold text-slate-800">{{ person.name || '未命名角色' }}</div>
                            <van-tag plain type="primary">{{ person.role_type || person.role || '相关人员' }}</van-tag>
                            <van-tag plain>{{ person.behavior_archetype || '求助配合型' }}</van-tag>
                          </div>
                          <div class="flex items-center gap-2">
                            <span class="persona-stack-toggle" @click.stop="toggleEditablePersonCollapsed(person)">{{ person._collapsed ? '展开详情' : '收起详情' }}</span>
                            <van-button size="small" type="danger" plain @click.stop="removeEditablePerson(Number(index))">删除角色</van-button>
                          </div>
                        </div>
                        <div v-if="person._collapsed" class="persona-stack-summary">
                          <span v-for="item in getCompactPersonaSummary(person)" :key="item">{{ item }}</span>
                        </div>
                        <div v-else class="persona-stack-expanded" @click.stop>
                          <div class="mt-4 grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
                            <div>
                              <label class="form-label form-label--muted">角色姓名</label>
                              <input :value="person.name" type="text" class="form-input" @input="renameEditablePerson(person, ($event.target as HTMLInputElement).value)" />
                            </div>
                            <div>
                              <label class="form-label form-label--muted">人物身份</label>
                              <input v-model="person.role" type="text" class="form-input" placeholder="如报警人、家属、同事" />
                            </div>
                            <div>
                              <label class="form-label form-label--muted">角色类型</label>
                              <select v-model="person.role_type" class="form-input">
                                <option v-for="option in roleTypeOptions" :key="option" :value="option">{{ option }}</option>
                              </select>
                            </div>
                            <div>
                              <label class="form-label form-label--muted">当前状态</label>
                              <select v-model="person.status" class="form-input">
                                <option v-for="option in statusOptions" :key="option" :value="option">{{ option }}</option>
                              </select>
                            </div>
                            <div>
                              <label class="form-label form-label--muted">行为原型</label>
                              <select v-model="person.behavior_archetype" class="form-input">
                                <option v-for="option in behaviorArchetypeOptions" :key="option.value" :value="option.value">{{ option.value }}</option>
                              </select>
                            </div>
                            <div>
                              <label class="form-label form-label--muted">对警方态度</label>
                              <select v-model="person.police_attitude" class="form-input">
                                <option v-for="option in policeAttitudeOptions" :key="option.value" :value="option.value">{{ option.value }}</option>
                              </select>
                            </div>
                            <div>
                              <label class="form-label form-label--muted">场景行为模式</label>
                              <select v-model="person.scene_behavior_mode" class="form-input">
                                <option v-for="option in sceneBehaviorModeOptions" :key="option.value" :value="option.value">{{ option.value }}</option>
                              </select>
                            </div>
                          </div>
                          <div class="persona-role-summary mt-3">
                            <div class="font-bold text-slate-700">{{ getBehaviorArchetypeSummary(person.behavior_archetype) }}</div>
                            <div class="mt-1 text-xs text-slate-500">{{ getPoliceAttitudeSummary(person.police_attitude) }}</div>
                          </div>
                          <div class="persona-compact-grid mt-3">
                            <section class="persona-compact-panel">
                              <div class="persona-compact-panel__title">诉求与顾虑</div>
                              <div class="mt-3 space-y-3">
                                <div>
                                  <label class="form-label form-label--muted">当前诉求</label>
                                  <textarea v-model="person.current_goal" rows="2" class="form-textarea form-textarea--compact" placeholder="例如：先稳住现场，不想让责任全落到自己头上"></textarea>
                                </div>
                                <div>
                                  <label class="form-label form-label--muted">最怕后果</label>
                                  <textarea v-model="person.core_concern" rows="2" class="form-textarea form-textarea--compact" placeholder="例如：最怕被认定先动手，最怕继续刺激后失控"></textarea>
                                </div>
                              </div>
                            </section>
                            <section class="persona-compact-panel">
                              <div class="persona-compact-panel__title">触发与安抚</div>
                              <div class="mt-3 space-y-3">
                                <div>
                                  <label class="form-label form-label--muted">触发点</label>
                                  <textarea
                                    rows="2"
                                    class="form-textarea form-textarea--compact"
                                    :value="getPersonListText(person.trigger_points)"
                                    @input="updatePersonListField(person, 'trigger_points', ($event.target as HTMLTextAreaElement).value)"
                                    placeholder="每行一条，例如：被质疑在撒谎&#10;提到赔偿金额&#10;被连续打断"
                                  ></textarea>
                                </div>
                                <div>
                                  <label class="form-label form-label--muted">安抚点</label>
                                  <textarea
                                    rows="2"
                                    class="form-textarea form-textarea--compact"
                                    :value="getPersonListText(person.calming_points)"
                                    @input="updatePersonListField(person, 'calming_points', ($event.target as HTMLTextAreaElement).value)"
                                    placeholder="每行一条，例如：先让他说完整&#10;明确下一步怎么处理&#10;减少围观刺激"
                                  ></textarea>
                                </div>
                              </div>
                            </section>
                            <section class="persona-compact-panel">
                              <div class="persona-compact-panel__title">开场状态</div>
                              <div class="mt-3 grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-4">
                                <div>
                                  <label class="form-label form-label--muted">情绪强度</label>
                                  <select v-model="person.emotion_level" class="form-input">
                                    <option v-for="option in stateLevelOptions" :key="option.value" :value="option.value">{{ option.label }}</option>
                                  </select>
                                </div>
                                <div>
                                  <label class="form-label form-label--muted">配合程度</label>
                                  <select v-model="person.cooperation_level" class="form-input">
                                    <option v-for="option in stateLevelOptions" :key="option.value" :value="option.value">{{ option.label }}</option>
                                  </select>
                                </div>
                                <div>
                                  <label class="form-label form-label--muted">失控风险</label>
                                  <select v-model="person.risk_level" class="form-input">
                                    <option v-for="option in stateLevelOptions" :key="option.value" :value="option.value">{{ option.label }}</option>
                                  </select>
                                </div>
                                <div>
                                  <label class="form-label form-label--muted">表达清晰度</label>
                                  <select v-model="person.clarity_level" class="form-input">
                                    <option v-for="option in stateLevelOptions" :key="option.value" :value="option.value">{{ option.label }}</option>
                                  </select>
                                </div>
                              </div>
                            </section>
                            <section class="persona-compact-panel">
                              <div class="persona-compact-panel__title">场景边界</div>
                              <div class="mt-3 space-y-3">
                                <div class="rounded-2xl border border-slate-100 bg-slate-50 px-3 py-2 text-xs leading-5 text-slate-500">
                                  {{ sceneBehaviorModeOptions.find((option) => option.value === person.scene_behavior_mode)?.summary || '先选场景行为模式，再补对应的信息边界。' }}
                                </div>
                                <div v-for="field in getPersonBoundaryFields(person)" :key="field.key">
                                  <label class="form-label form-label--muted">{{ field.label }}</label>
                                  <textarea
                                    rows="2"
                                    class="form-textarea form-textarea--compact"
                                    :value="getPersonBoundaryFieldText(person, field.key)"
                                    @input="updatePersonListField(person, field.key, ($event.target as HTMLTextAreaElement).value)"
                                    :placeholder="field.placeholder"
                                  ></textarea>
                                </div>
                                <div>
                                  <label class="form-label form-label--muted">当前确实不知道的点</label>
                                  <textarea
                                    rows="2"
                                    class="form-textarea form-textarea--compact"
                                    :value="getPersonListText(person.does_not_know)"
                                    @input="updatePersonListField(person, 'does_not_know', ($event.target as HTMLTextAreaElement).value)"
                                    placeholder="每行一条，补充当前角色确实无法回答的问题。"
                                  ></textarea>
                                </div>
                                <div v-if="person.scene_behavior_mode === '管控型'">
                                  <label class="form-label form-label--muted">酒精 / 药物 / 精神状态说明</label>
                                  <textarea v-model="person.impairment_state" rows="2" class="form-textarea form-textarea--compact" placeholder="例如：饮酒明显，语无伦次，步态不稳。"></textarea>
                                </div>
                              </div>
                            </section>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              <div v-else class="rounded-2xl border border-dashed border-slate-200 bg-white px-4 py-6 text-center text-sm text-slate-500">
                当前案件还没有角色模板。可以手动新增角色，再继续做场景分配和最终审核。
              </div>
            </section>
            </div>
            </section>

          <section v-show="activeReviewModule === 'scenes'" class="workspace-panel workspace-panel--emerald">
            <div class="workspace-panel__header">
              <div>
                <div class="workspace-panel__eyebrow">03 场景编辑</div>
                <h4 class="workspace-panel__title">训练场景与流程配置</h4>
              </div>
              <van-tag plain type="success">{{ (editableCase.scenes || []).length }} 个场景</van-tag>
            </div>
            <div class="workspace-panel__body">
            <section class="scene-studio rounded-2xl border border-slate-100 bg-white p-4">
            <div v-if="!(editableCase.scenes || []).length" class="scene-studio__empty py-8 text-center text-sm text-slate-500">暂无场景</div>
            <div v-else class="scene-studio__layout">
              <aside class="scene-studio__nav">
                <button
                  v-for="(scene, idx) in editableCase.scenes || []"
                  :key="'nav-' + scene.id"
                  type="button"
                  class="scene-studio__nav-item"
                  :class="{ 'is-active': activeSceneIndex === idx }"
                  @click="setActiveSceneIndex(Number(idx))"
                >
                  <span class="scene-studio__nav-index">场景 {{ Number(idx) + 1 }}</span>
                  <span class="scene-studio__nav-name">{{ scene.name || '未命名' }}</span>
                </button>
              </aside>
              <div class="scene-studio__main">
                <div class="scene-studio__tabs">
                  <button
                    v-for="tab in sceneEditTabs"
                    :key="tab.id"
                    type="button"
                    class="scene-studio__tab"
                    :class="{ 'is-active': activeSceneTab === tab.id }"
                    @click="activeSceneTab = tab.id"
                  >{{ tab.label }}</button>
                </div>
            <div
              v-for="(scene, idx) in editableCase.scenes || []"
              v-show="activeSceneIndex === idx"
              :key="scene.id"
              class="scene-editor-card scene-editor-card--studio"
            >
              <div v-show="activeSceneTab === 'overview'" class="scene-editor-card__panel scene-editor-card__panel--summary">
                <div class="scene-editor-card__section-head">
                  <div>
                    <div class="scene-editor-card__section-title">场景名称、难度与描述</div>
                  </div>
                </div>
                <div class="grid grid-cols-1 gap-4 md:grid-cols-2">
                  <div>
                    <label class="form-label">场景名称</label>
                    <input v-model="scene.name" type="text" class="form-input" />
                  </div>
                  <div>
                    <label class="form-label">难度</label>
                    <select v-model="scene.difficulty" class="form-input">
                      <option value="简单">简单</option>
                      <option value="中等">中等</option>
                      <option value="困难">困难</option>
                    </select>
                  </div>
                </div>
                <div class="mt-4">
                  <label class="form-label">场景描述</label>
                  <textarea v-model="scene.description" rows="2" class="form-textarea"></textarea>
                </div>
              </div>

              <div v-show="activeSceneTab === 'roles_copy'" v-if="editableCase.persons?.length" class="scene-editor-card__panel scene-editor-card__panel--roles">
                <div class="scene-editor-card__section-head">
                  <div>
                    <div class="scene-editor-card__section-title">参与角色与主对话人</div>
                  </div>
                </div>
                <div class="mt-3 flex flex-wrap gap-2">
                  <button
                    v-for="person in editableCase.persons"
                    :key="`${scene.id}-${person.name}`"
                    type="button"
                    class="rounded-full border px-3 py-1.5 text-xs font-bold transition-colors"
                    :class="scene.role_names?.includes(person.name) ? 'border-[#1D3557] bg-[#1D3557] text-white' : 'border-slate-200 bg-white text-slate-600'"
                    @click="toggleSceneRole(scene, person.name)"
                  >
                    {{ person.name }}
                  </button>
                </div>
                <div class="mt-4">
                  <label class="form-label form-label--muted">主对话人</label>
                  <select v-model="scene.primary_role_name" class="form-input">
                    <option value="">请选择主对话人</option>
                    <option v-for="roleName in scene.role_names || []" :key="roleName" :value="roleName">{{ roleName }}</option>
                  </select>
                </div>
                <div v-if="getSceneRoleRecommendation(editableCase, scene)" class="mt-3 rounded-xl border border-sky-200 bg-sky-50 px-3 py-3 text-xs text-sky-700">
                  <div class="font-bold">推荐主对话人：{{ getSceneRoleRecommendation(editableCase, scene)?.name }}</div>
                  <div class="mt-1">{{ getSceneRoleRecommendation(editableCase, scene)?.reason }}</div>
                </div>
                <div v-if="getSceneUnsuitableRoleHints(editableCase, scene).length" class="mt-3 rounded-xl border border-amber-200 bg-amber-50 px-3 py-3 text-xs text-amber-700">
                  <div class="font-bold">不优先建议</div>
                  <div v-for="hint in getSceneUnsuitableRoleHints(editableCase, scene)" :key="hint" class="mt-1">{{ hint }}</div>
                </div>
                <div v-if="scene.primary_role_name" class="mt-3 rounded-xl bg-slate-50 px-3 py-3 text-xs text-slate-500">
                  {{ getScenePrimaryRoleSummary(editableCase, scene) }}
                </div>
              </div>

              <div v-show="activeSceneTab === 'flow'" class="space-y-4">
                <div class="scene-editor-card__panel scene-editor-card__panel--copy">
                  <div class="scene-editor-card__section-head">
                    <div></div>
                  </div>
                  <div class="mt-3 grid grid-cols-1 gap-4">
                    <div>
                      <label class="form-label">接警简报</label>
                      <textarea v-model="scene.dispatch_brief" rows="3" class="form-textarea"></textarea>
                    </div>
                    <div>
                      <label class="form-label">现场第一印象</label>
                      <textarea v-model="scene.first_impression" rows="3" class="form-textarea"></textarea>
                    </div>
                  </div>
                </div>

                <div class="scene-flow-panel">
                  <div class="scene-flow-panel__toolbar">
                    <span class="scene-flow-panel__badge">{{ (scene.assessmentPointsModel || []).length }} 个考察点</span>
                    <div class="scene-flow-panel__actions">
                      <van-button
                        v-if="(scene.assessmentPointsModel || []).length"
                        size="small"
                        class="persona-toolbar-button"
                        :plain="!areAllSceneAssessmentPointsExpanded(scene)"
                        type="primary"
                        @click="toggleAllSceneAssessmentPoints(scene)"
                      >
                        {{ areAllSceneAssessmentPointsExpanded(scene) ? '全部收起' : '全部展开' }}
                      </van-button>
                      <van-button plain size="small" @click="addAssessmentPointToScene(scene)">新增考察点</van-button>
                    </div>
                  </div>

                  <div v-if="!(scene.assessmentPointsModel || []).length" class="scene-flow-panel__empty">
                    暂无考察点。请先在「基础信息」使用 AI 补全，或点击「新增考察点」。
                  </div>

                  <div
                    v-for="(point, pointIndex) in scene.assessmentPointsModel || []"
                    :key="`${scene.id}-ap-${point._editor_id || pointIndex}`"
                    :class="['scene-flow-stage', point._collapsed ? 'scene-flow-stage--collapsed' : '']"
                  >
                    <div class="scene-flow-stage__head">
                      <span class="scene-flow-stage__index">考察点 {{ Number(pointIndex) + 1 }}</span>
                      <div class="flex items-center gap-2">
                        <span class="persona-stack-toggle" @click.stop="toggleAssessmentPointCollapsed(point)">{{ point._collapsed ? '展开详情' : '收起详情' }}</span>
                        <van-button plain size="mini" class="!text-rose-600" @click="removeAssessmentPointFromScene(scene, Number(pointIndex))">删除</van-button>
                      </div>
                    </div>
                    <div v-if="!point._collapsed" class="scene-flow-stage__core">
                      <div class="scene-flow-stage__row">
                        <div class="scene-flow-stage__col">
                          <label class="form-label form-label--muted">考察点名称</label>
                          <input v-model="point.label" type="text" class="form-input" placeholder="如：建立关系与基本信息核实" />
                        </div>
                        <div class="scene-flow-stage__col">
                          <label class="form-label form-label--muted">考察内容</label>
                          <textarea
                            v-model="point.content"
                            rows="1"
                            class="form-textarea"
                            placeholder="写清楚学员需要做到什么，评估时会据此核查对话内容是否满足。"
                          ></textarea>
                        </div>
                      </div>
                    </div>
                    <div v-else class="scene-flow-stage__audit">
                      <span class="scene-flow-stage__stats">
                        {{ String(point.label || '').trim() ? '已配置' : '待补全' }}
                      </span>
                      <div class="mt-1 text-xs text-slate-500">
                        {{ String(point.label || '').trim() || `考察点 ${Number(pointIndex) + 1}` }}
                      </div>
                    </div>
                  </div>
                </div>
              </div>

            </div>
              </div>
            </div>
            </section>
          </div>
          </section>
        </div>
      </div>
    </van-popup>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { showConfirmDialog, showToast } from 'vant'
import {
  behaviorArchetypeOptions,
  buildBehaviorSummary,
  buildLegacyInfoBoundary,
  dedupeStringList,
  getSceneBoundaryFields,
  normalizeBehaviorTemplate,
  PERSON_ALIAS_TO_CANONICAL,
  PERSON_CANONICAL_FIELDS,
  policeAttitudeOptions,
  sceneBehaviorModeOptions,
  stateLevelOptions,
} from '../utils/personaTemplate'
import request from '../utils/request'

const router = useRouter()
const route = useRoute()

const showAdd = ref(false)
const showDetail = ref(false)
const currentStep = ref(0)
const importMode = ref<'plain_case' | 'transcript_file'>('plain_case')
const cases = ref<any[]>([])
const casesLoading = ref(false)
const casesError = ref('')
const parsing = ref(false)
const generating = ref(false)
const savingCreate = ref(false)
const savingDetail = ref(false)
const supplementingAi = ref(false)
type ReviewModule = 'basic' | 'roles' | 'scenes'
type SceneEditTab = 'overview' | 'roles_copy' | 'flow'

const activeReviewModule = ref<ReviewModule>('basic')
const activeSceneIndex = ref(0)
const activeSceneTab = ref<SceneEditTab>('overview')
const showOriginalExpanded = ref(false)

const reviewModules: Array<{ id: ReviewModule; label: string; step: string }> = [
  { id: 'basic', label: '基础信息', step: '01' },
  { id: 'roles', label: '角色审核', step: '02' },
  { id: 'scenes', label: '场景编辑', step: '03' },
]

const sceneEditTabs: Array<{ id: SceneEditTab; label: string }> = [
  { id: 'overview', label: '概览' },
  { id: 'roles_copy', label: '角色与文案' },
  { id: 'flow', label: '流程配置' },
]

const setReviewModule = (moduleId: ReviewModule) => {
  activeReviewModule.value = moduleId
}

const setActiveSceneIndex = (index: number) => {
  activeSceneIndex.value = index
  activeSceneTab.value = 'overview'
}

const activeEditableScene = computed(() => {
  const scenes = editableCase.value?.scenes || []
  if (!scenes.length) return null
  const safeIndex = Math.min(Math.max(activeSceneIndex.value, 0), scenes.length - 1)
  return scenes[safeIndex] || null
})

const getStageFlowStats = (stage: any) => {
  const points = Array.isArray(stage?.assessment_points) ? stage.assessment_points : []
  const actions = Array.isArray(stage?.action_catalog) ? stage.action_catalog : []
  return { pointCount: points.length, actionCount: actions.length, points, actions }
}

let assessmentPointSeed = 1

const normalizeAssessmentPointEditors = (points: any) => {
  if (!Array.isArray(points)) return []
  return points.map((point: any, index: number) => ({
    ...createPointEditor(point, index),
    _editor_id: Number(point?._editor_id) || assessmentPointSeed++,
    _collapsed: typeof point?._collapsed === 'boolean' ? point._collapsed : true,
    content: String(point?.content || point?.requirement || '').trim(),
  }))
}

const normalizeAssessmentPointsFromStages = (stagesModel: any[]) => {
  const points: any[] = []
  for (const stage of stagesModel || []) {
    const stagePoints = Array.isArray(stage?.assessment_points) ? stage.assessment_points : []
    points.push(...stagePoints)
  }
  return normalizeAssessmentPointEditors(points)
}

const ensureSceneAssessmentPointsModel = (scene: any) => {
  if (!scene) return
  if (!Array.isArray(scene.assessmentPointsModel)) {
    scene.assessmentPointsModel = normalizeAssessmentPointsFromStages(scene.stagesModel || [])
  }
}

const addAssessmentPointToScene = (scene: any) => {
  if (!scene) return
  ensureSceneAssessmentPointsModel(scene)
  const nextIndex = (scene.assessmentPointsModel || []).length
  scene.assessmentPointsModel.push({
    ...createPointEditor({ label: `考察点 ${nextIndex + 1}` }, nextIndex),
    _editor_id: assessmentPointSeed++,
    _collapsed: false,
    content: '',
  })
}

const removeAssessmentPointFromScene = (scene: any, index: number) => {
  if (!scene) return
  ensureSceneAssessmentPointsModel(scene)
  scene.assessmentPointsModel = (scene.assessmentPointsModel || []).filter((_: any, i: number) => i !== index)
}

const toggleAssessmentPointCollapsed = (point: any) => {
  if (!point) return
  point._collapsed = !point._collapsed
}

const areAllSceneAssessmentPointsExpanded = (scene: any) => {
  const points = scene?.assessmentPointsModel || []
  return Array.isArray(points) && points.length > 0 && points.every((item: any) => !item?._collapsed)
}

const collapseAllSceneAssessmentPoints = (scene: any) => {
  ensureSceneAssessmentPointsModel(scene)
  for (const item of scene?.assessmentPointsModel || []) {
    item._collapsed = true
  }
}

const expandAllSceneAssessmentPoints = (scene: any) => {
  ensureSceneAssessmentPointsModel(scene)
  for (const item of scene?.assessmentPointsModel || []) {
    item._collapsed = false
  }
}

const toggleAllSceneAssessmentPoints = (scene: any) => {
  if (areAllSceneAssessmentPointsExpanded(scene)) {
    collapseAllSceneAssessmentPoints(scene)
    return
  }
  expandAllSceneAssessmentPoints(scene)
}

const serializeAssessmentPointsForSave = (pointsModel: any[]) => {
  return (Array.isArray(pointsModel) ? pointsModel : []).map((point: any, index: number) => ({
    id: String(point?.id || `ap_${index + 1}`).trim(),
    label: String(point?.label || '').trim(),
    content: String(point?.content || '').trim(),
  }))
}

const resetReviewWorkspace = () => {
  activeReviewModule.value = 'basic'
  activeSceneIndex.value = 0
  activeSceneTab.value = 'overview'
  showOriginalExpanded.value = false
}

const auditLoading = ref(false)
const repairing = ref(false)
const selectedCase = ref<any>(null)
const editableCase = ref<any>(null)
const aiParsedData = ref<any>({})
const generatedScenes = ref<any[]>([])
const auditCases = ref<any[]>([])
const fileInputRef = ref<HTMLInputElement | null>(null)
const uploadedFile = ref<File | null>(null)
const fileParseStatus = ref<'idle' | 'ready' | 'parsed' | 'error'>('idle')
const fileMeta = reactive({ name: '', type: '', size: 0 })

const auditSummary = reactive({
  caseCount: 0,
  issueSceneCount: 0,
  lastRepairCount: 0,
})

const caseTypeGroups = [
  { label: '纠纷求助类', options: ['邻里纠纷', '家庭纠纷', '情感纠纷', '劳资纠纷', '消费纠纷', '噪音扰民', '失踪求助', '自杀干预', '校园警情', '宠物纠纷'] },
  { label: '治安案件类', options: ['打架斗殴', '寻衅滋事', '故意伤害', '损毁财物', '醉酒闹事', '赌博', '卖淫嫖娼', '非法侵入住宅'] },
  { label: '刑事案件类', options: ['故意杀人', '盗窃', '抢夺', '诈骗', '电信网络诈骗', '入室盗窃', '抢劫', '敲诈勒索', '涉毒'] },
  { label: '交通警情类', options: ['交通事故', '酒驾醉驾', '肇事逃逸'] },
  { label: '其他', options: ['其他'] },
]

const form = reactive({
  title: '',
  caseTypeGroup: '',
  caseType: '',
  rawText: '',
})

const uploadedFileExtLabel = computed(() => {
  if (!uploadedFile.value) return ''
  return uploadedFile.value.name.split('.').pop()?.toUpperCase() || 'FILE'
})

const fileParseStatusText = computed(() => {
  if (fileParseStatus.value === 'parsed') return '已解析'
  if (fileParseStatus.value === 'ready') return '待解析'
  if (fileParseStatus.value === 'error') return '解析失败'
  return '未上传'
})

const fileParseStatusClass = computed(() => {
  if (fileParseStatus.value === 'parsed') return 'success'
  if (fileParseStatus.value === 'ready') return 'ready'
  if (fileParseStatus.value === 'error') return 'error'
  return ''
})

const canRunAiSupplement = computed(() => Boolean(String(editableCase.value?.original_content || '').trim()))
const areAllParsedPersonsExpanded = computed(() => {
  const persons = aiParsedData.value?.persons || []
  return persons.length > 0 && persons.every((person: any) => !person._collapsed)
})

const areAllEditablePersonsExpanded = computed(() => {
  const persons = editableCase.value?.persons || []
  return persons.length > 0 && persons.every((person: any) => !person._collapsed)
})

const toggleEditablePersonCollapsed = (target: any) => {
  const persons = editableCase.value?.persons || []
  if (!target) return
  const targetId = Number(target._editor_id)
  if (target._collapsed) {
    for (const person of persons) {
      person._collapsed = Number(person._editor_id) !== targetId
    }
    return
  }
  target._collapsed = true
}

const openEditablePersonCard = (target: any) => {
  const persons = editableCase.value?.persons || []
  const targetId = Number(target?._editor_id)
  for (const person of persons) {
    person._collapsed = Number(person._editor_id) !== targetId
  }
}

const expandAllEditablePersons = () => {
  for (const person of editableCase.value?.persons || []) {
    person._collapsed = false
  }
}

const collapseAllEditablePersons = () => {
  for (const person of editableCase.value?.persons || []) {
    person._collapsed = true
  }
}

const toggleAllEditablePersons = () => {
  if (areAllEditablePersonsExpanded.value) {
    collapseAllEditablePersons()
    return
  }
  expandAllEditablePersons()
}

const getEditablePersonCardStyle = (_index: number, person: any) => {
  return {
    marginTop: '0px',
    zIndex: String(person?._collapsed ? 1 : 2),
  }
}

const parseEngineLabel = (payload: any) => String(payload?.parse_engine || '') === 'ai' ? 'AI 结构化解析' : '规则兜底解析'
const parseEngineIsFallback = (payload: any) => String(payload?.parse_engine || '') !== 'ai'
const sceneGenerationLabel = (payload: any) => String(payload?.scene_generation_mode || '') === 'ai' ? 'AI 场景生成' : '规则兜底场景'
const sceneGenerationIsFallback = (payload: any) => String(payload?.scene_generation_mode || '') === 'fallback'
const parseWarnings = (payload: any) => Array.isArray(payload?.parse_warnings) ? payload.parse_warnings : []
const sceneGenerationWarning = (payload: any) => String(payload?.scene_generation_warning || '').trim()

const roleTypeOptions = ['相关人员', '证人', '嫌疑人', '被害人', '民警']
const statusOptions = ['正常', '受伤可交流', '昏迷', '重伤无法交流', '死亡']
const personBoundaryFieldKeys = [
  'known_key_points',
  'withheld_key_points',
  'conflict_core',
  'acceptable_outcomes',
  'no_go_topics',
  'trigger_sources',
  'concerned_targets',
  'taboo_actions',
  'escalation_actions',
  'deescalation_conditions',
] as const

const getPersonBoundaryFields = (person: any) => getSceneBoundaryFields(person?.scene_behavior_mode || '核查取证型')
const getPersonBoundaryFieldText = (person: any, fieldKey: string) => getPersonListText(person?.[fieldKey])
let personEditorSeed = 1
const getBehaviorArchetypeSummary = (value: string) =>
  behaviorArchetypeOptions.find((item) => item.value === value)?.summary || '用这一类行为原型快速决定角色开场姿态和变化路径。'
const getPoliceAttitudeSummary = (value: string) =>
  policeAttitudeOptions.find((item) => item.value === value)?.summary || '用于决定角色面对警方时是求助、试探还是抵触。'

watch(
  () => form.caseType,
  (value) => {
    if (value) {
      form.caseTypeGroup = getCaseTypeGroup(value) || form.caseTypeGroup
    }
  }
)

const safeJsonParse = (value: any, fallback: any) => {
  if (value == null || value === '') return fallback
  if (typeof value !== 'string') return value
  try {
    return JSON.parse(value)
  } catch {
    return fallback
  }
}

const CASE_SCHEMA_VERSION = '2026.05.canonical-v1'

const normalizePersonEditors = (persons: any, options: { collapsed?: boolean } = {}) => {
  if (!Array.isArray(persons)) return []
  return persons.map((person: any) => {
    const compactFields = normalizeBehaviorTemplate(person)
    return {
      ...person,
      ...compactFields,
      name: String(person?.name || '').trim(),
      role: String(person?.role || '').trim(),
      role_type: String(person?.role_type || person?.role || '相关人员').trim() || '相关人员',
      status: String(person?.status || '正常').trim() || '正常',
      interaction_style: String(compactFields.interaction_style || person?.interaction_style || '配合型').trim() || '配合型',
      weakness: String(person?.weakness || compactFields.core_concern || '').trim(),
      current_need: String(person?.current_need || compactFields.current_goal || '').trim(),
      authority_attitude: String(person?.authority_attitude || compactFields.police_attitude || '').trim(),
      stress_response: String(person?.stress_response || compactFields.pressure_response || '').trim(),
      public_mask: String(person?.public_mask || compactFields.surface_stance || '').trim(),
      private_drive: String(person?.private_drive || compactFields.current_goal || '').trim(),
      knows_facts: dedupeStringList(person?.knows_facts),
      does_not_know: dedupeStringList(person?.does_not_know),
      hidden_truths: dedupeStringList(person?.hidden_truths),
      known_key_points: dedupeStringList(compactFields.known_key_points),
      withheld_key_points: dedupeStringList(compactFields.withheld_key_points),
      conflict_core: dedupeStringList(compactFields.conflict_core),
      acceptable_outcomes: dedupeStringList(compactFields.acceptable_outcomes),
      no_go_topics: dedupeStringList(compactFields.no_go_topics),
      trigger_sources: dedupeStringList(compactFields.trigger_sources),
      concerned_targets: dedupeStringList(compactFields.concerned_targets),
      taboo_actions: dedupeStringList(compactFields.taboo_actions),
      escalation_actions: dedupeStringList(compactFields.escalation_actions),
      deescalation_conditions: dedupeStringList(compactFields.deescalation_conditions),
      protected_targets: dedupeStringList(person?.protected_targets),
      feared_people: dedupeStringList(person?.feared_people),
      conflict_targets: dedupeStringList(person?.conflict_targets),
      feared_consequences: dedupeStringList(person?.feared_consequences),
      trigger_topics: compactFields.trigger_points,
      coping_patterns: dedupeStringList(person?.coping_patterns),
      calming_points: dedupeStringList(compactFields.calming_points),
      behavior_archetype: compactFields.behavior_archetype,
      police_attitude: compactFields.police_attitude,
      scene_behavior_mode: compactFields.scene_behavior_mode,
      emotion_level: compactFields.emotion_level,
      cooperation_level: compactFields.cooperation_level,
      risk_level: compactFields.risk_level,
      clarity_level: compactFields.clarity_level,
      init_risk: Number(compactFields.init_risk ?? 50),
      init_expression_clarity: Number(compactFields.init_expression_clarity ?? 52),
      impairment_state: String(compactFields.impairment_state || '').trim(),
      _original_name: String(person?.name || '').trim(),
      _editor_id: Number(person?._editor_id) || personEditorSeed++,
      _collapsed: typeof person?._collapsed === 'boolean' ? person._collapsed : Boolean(options.collapsed),
    }
  })
}

const buildEmptyPerson = (index: number, options: { collapsed?: boolean } = {}) => normalizePersonEditors([{
  name: `新增角色${index}`,
  role: '相关人员',
  role_type: '相关人员',
  status: '正常',
  behavior_archetype: '求助配合型',
  police_attitude: '主动求助',
  interaction_style: '配合型',
  personality: '',
  speaking_style: '',
  scene_behavior_mode: '核查取证型',
  emotion_level: '中',
  cooperation_level: '中',
  risk_level: '中',
  clarity_level: '中',
  init_emotion: 50,
  init_trust: 30,
  init_risk: 50,
  init_expression_clarity: 52,
  knows_facts: [],
  does_not_know: [],
  hidden_truths: [],
  known_key_points: [],
  withheld_key_points: [],
  conflict_core: [],
  acceptable_outcomes: [],
  no_go_topics: [],
  trigger_sources: [],
  concerned_targets: [],
  taboo_actions: [],
  escalation_actions: [],
  deescalation_conditions: [],
  iq_level: '中等',
  eq_level: '中等',
  lying_ability: '一般',
  weakness: '',
  current_goal: '',
  core_concern: '',
  relationship_pressure: [],
  surface_stance: '',
  pressure_response: '',
  trigger_points: [],
  impairment_state: '',
  calming_points: [],
  self_image: '',
  current_need: '',
  authority_attitude: '',
  stress_response: '',
  protected_targets: [],
  feared_people: [],
  conflict_targets: [],
  feared_consequences: [],
  trigger_topics: [],
  coping_patterns: [],
  public_mask: '',
  private_drive: '',
}], options)[0]

const parsedPersons = (payload: any) => {
  if (!payload) return []
  if (!Array.isArray(payload.persons)) {
    payload.persons = []
  }
  return payload.persons
}
const getPersonListText = (value: any) => (Array.isArray(value) ? value : []).join('\n')
const updatePersonListField = (person: any, field: string, rawValue: string) => {
  person[field] = dedupeStringList(String(rawValue || '')
    .split('\n')
    .map((item) => item.trim())
    .filter(Boolean))
}

const toComparableList = (value: any) => {
  if (Array.isArray(value)) return dedupeStringList(value)
  const text = String(value || '').trim()
  return text ? [text] : []
}

const listEquals = (left: any, right: any) => {
  const leftList = toComparableList(left)
  const rightList = toComparableList(right)
  if (leftList.length !== rightList.length) return false
  return leftList.every((item, idx) => item === rightList[idx])
}

const getPersonDedupInsights = (person: any) => {
  const issues: string[] = []
  for (const [alias, canonical] of Object.entries(PERSON_ALIAS_TO_CANONICAL)) {
    const aliasValue = person?.[alias]
    const canonicalValue = person?.[canonical]
    if (!toComparableList(aliasValue).length || !toComparableList(canonicalValue).length) continue
    if (!listEquals(aliasValue, canonicalValue)) {
      issues.push(`${alias} 与 ${canonical} 不一致，将以 ${canonical} 为准`)
    }
  }

  const merged = normalizeBehaviorTemplate(person || {})
  const mergedPreview = [
    merged.current_goal ? `诉求=${merged.current_goal}` : '',
    merged.core_concern ? `顾虑=${merged.core_concern}` : '',
    merged.trigger_points?.length ? `触发点(${merged.trigger_points.length})` : '',
    merged.calming_points?.length ? `安抚点(${merged.calming_points.length})` : '',
    merged.scene_behavior_mode ? `模式=${merged.scene_behavior_mode}` : '',
  ].filter(Boolean)

  return { issues, mergedPreview }
}

const getCompactPersonaSummary = (person: any) => buildBehaviorSummary(person)

const togglePersonCollapsed = (target: any) => {
  const persons = aiParsedData.value?.persons || []
  if (!target) return
  const targetId = Number(target._editor_id)
  if (target._collapsed) {
    for (const person of persons) {
      person._collapsed = Number(person._editor_id) !== targetId
    }
    return
  }
  target._collapsed = true
}

const openParsedPersonCard = (target: any) => {
  const persons = aiParsedData.value?.persons || []
  const targetId = Number(target?._editor_id)
  for (const person of persons) {
    person._collapsed = Number(person._editor_id) !== targetId
  }
}

const expandAllParsedPersons = () => {
  for (const person of aiParsedData.value?.persons || []) {
    person._collapsed = false
  }
}

const collapseAllParsedPersons = () => {
  for (const person of aiParsedData.value?.persons || []) {
    person._collapsed = true
  }
}

const toggleAllParsedPersons = () => {
  if (areAllParsedPersonsExpanded.value) {
    collapseAllParsedPersons()
    return
  }
  expandAllParsedPersons()
}

const getParsedPersonCardStyle = (_index: number, person: any) => {
  return {
    marginTop: '0px',
    zIndex: String(person?._collapsed ? 1 : 2),
  }
}

const updateSceneNamesForPersonRename = (scenes: any[], oldName: string, nextName: string) => {
  for (const scene of scenes || []) {
    const roleNames = Array.isArray(scene?.role_names) ? scene.role_names : []
    scene.role_names = Array.from(new Set(roleNames.map((item: string) => item === oldName ? nextName : item).filter(Boolean)))
    if (scene.primary_role_name === oldName) {
      scene.primary_role_name = nextName
    }
    if (Array.isArray(scene?.roles)) {
      scene.roles = scene.roles.map((item: string) => item === oldName ? nextName : item).filter(Boolean)
    }
  }
}

const updatePersonName = (container: any, person: any, rawValue: string) => {
  const nextName = String(rawValue || '').trim()
  const oldName = String(person?._original_name || person?.name || '').trim()
  person.name = nextName
  person._original_name = nextName
  if (oldName && nextName && oldName !== nextName) {
    updateSceneNamesForPersonRename(container?.scenes || [], oldName, nextName)
  }
}

const removePersonFromContainer = (container: any, index: number) => {
  const persons = Array.isArray(container?.persons) ? container.persons : []
  const removed = persons[index]
  if (!removed) return
  const removedName = String(removed.name || '').trim()
  persons.splice(index, 1)
  for (const scene of container?.scenes || []) {
    scene.role_names = (Array.isArray(scene?.role_names) ? scene.role_names : []).filter((item: string) => item !== removedName)
    if (scene.primary_role_name === removedName) {
      scene.primary_role_name = scene.role_names?.[0] || ''
    }
    if (Array.isArray(scene?.roles)) {
      scene.roles = scene.roles.filter((item: string) => item !== removedName)
    }
  }
}

const renameParsedPerson = (person: any, rawValue: string) => updatePersonName(aiParsedData.value, person, rawValue)
const renameEditablePerson = (person: any, rawValue: string) => updatePersonName(editableCase.value, person, rawValue)

const removeParsedPerson = async (index: number) => {
  const target = parsedPersons(aiParsedData.value)?.[index]
  if (!target) return
  try {
    await showConfirmDialog({
      title: '删除角色',
      message: `确定删除角色“${target.name || '未命名角色'}”吗？删除后不会进入后续角色模板和训练场景。`,
      confirmButtonColor: '#dc2626',
    })
  } catch {
    return
  }
  removePersonFromContainer(aiParsedData.value, index)
}

const removeEditablePerson = async (index: number) => {
  const target = editableCase.value?.persons?.[index]
  if (!target) return
  try {
    await showConfirmDialog({
      title: '删除角色',
      message: `确定删除角色“${target.name || '未命名角色'}”吗？保存后它会从案件角色模板和场景分配里一并移除。`,
      confirmButtonColor: '#dc2626',
    })
  } catch {
    return
  }
  removePersonFromContainer(editableCase.value, index)
}

const addPersonToContainer = (container: any) => {
  if (!container) return
  if (!Array.isArray(container.persons)) container.persons = []
  const nextIndex = container.persons.length + 1
  container.persons.push(buildEmptyPerson(nextIndex, { collapsed: false }))
}

const addParsedPerson = () => addPersonToContainer(aiParsedData.value)
const addEditablePerson = () => addPersonToContainer(editableCase.value)

const validatePersonsBeforeSave = (persons: any[]) => {
  const seenNames = new Set<string>()
  for (const person of persons || []) {
    for (const fieldKey of personBoundaryFieldKeys) {
      person[fieldKey] = dedupeStringList(person?.[fieldKey])
    }
    const normalizedTemplate = normalizeBehaviorTemplate(person)
    const legacyBoundary = buildLegacyInfoBoundary(person)
    person.name = String(person?.name || '').trim()
    person.role = String(person?.role || '').trim() || '相关人员'
    person.role_type = String(person?.role_type || person?.role || '相关人员').trim() || '相关人员'
    person.status = String(person?.status || '正常').trim() || '正常'
    person.behavior_archetype = normalizedTemplate.behavior_archetype
    person.police_attitude = normalizedTemplate.police_attitude
    person.scene_behavior_mode = normalizedTemplate.scene_behavior_mode
    person.interaction_style = String(normalizedTemplate.interaction_style || person?.interaction_style || '配合型').trim() || '配合型'
    person.current_goal = String(normalizedTemplate.current_goal || '').trim()
    person.core_concern = String(normalizedTemplate.core_concern || '').trim()
    person.surface_stance = String(normalizedTemplate.surface_stance || '').trim()
    person.pressure_response = String(normalizedTemplate.pressure_response || '').trim()
    person.relationship_pressure = dedupeStringList(normalizedTemplate.relationship_pressure)
    person.trigger_points = dedupeStringList(normalizedTemplate.trigger_points)
    person.calming_points = dedupeStringList(normalizedTemplate.calming_points)
    person.emotion_level = normalizedTemplate.emotion_level
    person.cooperation_level = normalizedTemplate.cooperation_level
    person.risk_level = normalizedTemplate.risk_level
    person.clarity_level = normalizedTemplate.clarity_level
    person.init_emotion = normalizedTemplate.init_emotion
    person.init_trust = normalizedTemplate.init_trust
    person.init_risk = normalizedTemplate.init_risk
    person.init_expression_clarity = normalizedTemplate.init_expression_clarity
    person.impairment_state = String(normalizedTemplate.impairment_state || '').trim()
    person.known_key_points = dedupeStringList(normalizedTemplate.known_key_points)
    person.withheld_key_points = dedupeStringList(normalizedTemplate.withheld_key_points)
    person.conflict_core = dedupeStringList(normalizedTemplate.conflict_core)
    person.acceptable_outcomes = dedupeStringList(normalizedTemplate.acceptable_outcomes)
    person.no_go_topics = dedupeStringList(normalizedTemplate.no_go_topics)
    person.trigger_sources = dedupeStringList(normalizedTemplate.trigger_sources)
    person.concerned_targets = dedupeStringList(normalizedTemplate.concerned_targets)
    person.taboo_actions = dedupeStringList(normalizedTemplate.taboo_actions)
    person.escalation_actions = dedupeStringList(normalizedTemplate.escalation_actions)
    person.deescalation_conditions = dedupeStringList(normalizedTemplate.deescalation_conditions)
    person.knows_facts = legacyBoundary.knows_facts
    person.hidden_truths = legacyBoundary.hidden_truths
    person.does_not_know = dedupeStringList(person?.does_not_know)
    person.current_need = person.current_goal || String(person?.current_need || '').trim()
    person.weakness = person.core_concern || String(person?.weakness || '').trim()
    person.public_mask = person.surface_stance || String(person?.public_mask || '').trim()
    person.stress_response = person.pressure_response || String(person?.stress_response || '').trim()
    person.authority_attitude = String(person?.authority_attitude || person.police_attitude || '').trim()
    person.private_drive = String(person?.private_drive || person.current_goal || '').trim()
    person.trigger_topics = [...person.trigger_points]
    person._original_name = person.name

    if (!person.name) {
      showToast('角色姓名不能为空，请先完成人工审核')
      return false
    }
    if (seenNames.has(person.name)) {
      showToast(`角色姓名“${person.name}”重复，请先修正后再保存`)
      return false
    }
    seenNames.add(person.name)
  }
  return true
}

const serializePersonsForSave = (persons: any[]) => {
  return (persons || []).map((person: any) => {
    const cloned = { ...person }
    for (const [alias, canonical] of Object.entries(PERSON_ALIAS_TO_CANONICAL)) {
      if (!cloned[canonical] && cloned[alias]) cloned[canonical] = cloned[alias]
    }
    delete cloned._editor_id
    delete cloned._original_name
    delete cloned._collapsed
    return cloned
  })
}

const splitTextList = (value: any) =>
  String(value || '')
    .split(/[,，\n]/)
    .map((item) => item.trim())
    .filter(Boolean)

const createPointEditor = (point: any = {}, index = 0) => ({
  id: String(point?.id || `ap_${index + 1}`),
  label: String(point?.label || ''),
  category: String(point?.category || 'procedure'),
  required: point?.required !== false,
  weight: Number(point?.weight ?? 10),
  keywordsText: Array.isArray(point?.keywords) ? point.keywords.join(', ') : '',
  knowledgeRefsText: Array.isArray(point?.knowledge_refs) ? point.knowledge_refs.join(', ') : '',
})

const createActionEditor = (action: any = {}, index = 0) => ({
  id: String(action?.id || `act_${index + 1}`),
  label: String(action?.label || ''),
  type: String(action?.type || 'physical'),
  aliasesText: Array.isArray(action?.aliases) ? action.aliases.join(', ') : '',
  countsForText: Array.isArray(action?.counts_for) ? action.counts_for.join(', ') : '',
})

const createStageEditor = (stage: any = {}, index = 0) => ({
  stage_name: String(stage?.stage_name || stage?.name || `阶段 ${index + 1}`),
  stage_goal: String(stage?.stage_goal || stage?.goal || stage?.description || ''),
  recommended_prompts_text: Array.isArray(stage?.recommended_prompts)
    ? stage.recommended_prompts.join('\n')
    : '',
  assessment_points: Array.isArray(stage?.assessment_points) ? stage.assessment_points.map((point: any, pointIndex: number) => createPointEditor(point, pointIndex)) : [],
  action_catalog: Array.isArray(stage?.action_catalog) ? stage.action_catalog.map((action: any, actionIndex: number) => createActionEditor(action, actionIndex)) : [],
  completion_rules: {
    min_user_turns: Number(stage?.completion_rules?.min_user_turns ?? 3),
    required_point_ids_text: Array.isArray(stage?.completion_rules?.required_point_ids) ? stage.completion_rules.required_point_ids.join(', ') : '',
    required_action_ids_text: Array.isArray(stage?.completion_rules?.required_action_ids) ? stage.completion_rules.required_action_ids.join(', ') : '',
  },
  end_conditions: {
    must_complete_current_stage: stage?.end_conditions?.must_complete_current_stage !== false,
    required_point_ids_text: Array.isArray(stage?.end_conditions?.required_point_ids) ? stage.end_conditions.required_point_ids.join(', ') : '',
    required_action_ids_text: Array.isArray(stage?.end_conditions?.required_action_ids) ? stage.end_conditions.required_action_ids.join(', ') : '',
    closure_actions_text: Array.isArray(stage?.end_conditions?.closure_actions) ? stage.end_conditions.closure_actions.join(', ') : '',
    closing_script: String(stage?.end_conditions?.closing_script || ''),
  },
})

const normalizeStageEditors = (value: any) => {
  const stages = safeJsonParse(value, [])
  return Array.isArray(stages) ? stages.map((stage: any, index: number) => createStageEditor(stage, index)) : []
}

const splitPromptLines = (value: string) =>
  String(value || '')
    .split(/\r?\n/)
    .map((item) => item.trim())
    .filter(Boolean)

const serializeStageEditors = (stages: any[]) =>
  (Array.isArray(stages) ? stages : []).map((stage: any) => ({
    stage_name: String(stage?.stage_name || '').trim(),
    stage_goal: String(stage?.stage_goal || '').trim(),
    recommended_prompts: splitPromptLines(stage?.recommended_prompts_text),
    assessment_points: (Array.isArray(stage?.assessment_points) ? stage.assessment_points : []).map((point: any, index: number) => ({
      id: String(point?.id || `ap_${index + 1}`).trim(),
      label: String(point?.label || '').trim(),
      category: String(point?.category || 'procedure').trim(),
      required: point?.required !== false,
      weight: Number(point?.weight ?? 10),
      keywords: splitTextList(point?.keywordsText),
      knowledge_refs: splitTextList(point?.knowledgeRefsText),
    })),
    action_catalog: (Array.isArray(stage?.action_catalog) ? stage.action_catalog : []).map((action: any, index: number) => ({
      id: String(action?.id || `act_${index + 1}`).trim(),
      label: String(action?.label || '').trim(),
      type: String(action?.type || 'physical').trim(),
      aliases: splitTextList(action?.aliasesText),
      counts_for: splitTextList(action?.countsForText),
    })),
    completion_rules: {
      min_user_turns: Number(stage?.completion_rules?.min_user_turns ?? 3),
      required_point_ids: splitTextList(stage?.completion_rules?.required_point_ids_text),
      required_action_ids: splitTextList(stage?.completion_rules?.required_action_ids_text),
    },
    end_conditions: {
      must_complete_current_stage: stage?.end_conditions?.must_complete_current_stage !== false,
      required_point_ids: splitTextList(stage?.end_conditions?.required_point_ids_text),
      required_action_ids: splitTextList(stage?.end_conditions?.required_action_ids_text),
      closure_actions: splitTextList(stage?.end_conditions?.closure_actions_text),
      closing_script: String(stage?.end_conditions?.closing_script || '').trim(),
    },
  }))

const syncSceneStagesText = (scene: any) => {
  scene.stagesText = JSON.stringify(serializeStageEditors(scene?.stagesModel || []), null, 2)
}

const addStageToScene = (scene: any) => {
  scene.stagesModel = [...(scene?.stagesModel || []), createStageEditor({}, (scene?.stagesModel || []).length)]
  syncSceneStagesText(scene)
}

const removeStageFromScene = (scene: any, stageIndex: number) => {
  scene.stagesModel = (scene?.stagesModel || []).filter((_: any, index: number) => index !== stageIndex)
  syncSceneStagesText(scene)
}

const normalizeSceneEditors = (scenes: any, structuredData: any, persons: any[]) => {
  const sceneRoleMap = structuredData?.scene_role_map || {}
  return (scenes || []).map((scene: any) => {
    const sceneName = String(scene?.name || '').trim()
    const mapped = sceneRoleMap?.[sceneName] || {}
    const roleNames = Array.isArray(mapped?.role_names) ? mapped.role_names.filter(Boolean) : []
    const fallbackRoles = Array.isArray(scene?.roles) ? scene.roles.map((item: any) => String(item?.name || item || '').trim()).filter(Boolean) : []
    const normalizedRoleNames: string[] = Array.from(new Set((roleNames.length ? roleNames : fallbackRoles).filter((name: string) => persons.some((person) => person.name === name))))
    const mappedPrimaryRoleName = String(mapped?.primary_role_name || '').trim()
    const recommendedPrimaryRoleName = pickRecommendedPrimaryRoleName(persons, normalizedRoleNames)
    const stagesModel = normalizeStageEditors(scene.stages)
    return {
      ...scene,
      stagesText: stringifyStages(scene.stages),
      stagesModel,
      stagesAdvanced: false,
      assessmentPointsModel: normalizeAssessmentPointsFromStages(stagesModel),
      role_names: normalizedRoleNames,
      primary_role_name: normalizedRoleNames.includes(mappedPrimaryRoleName)
        ? mappedPrimaryRoleName
        : (recommendedPrimaryRoleName || normalizedRoleNames[0] || ''),
    }
  })
}

const pickRecommendedPrimaryRoleName = (persons: any[], roleNames: string[]) => {
  const candidates = (persons || []).filter((person: any) => roleNames.includes(person.name))
  if (!candidates.length) return ''

  const ranked = candidates
    .map((person: any) => {
      let score = 0
      const status = String(person.status || '正常')
      const roleType = String(person.role_type || person.role || '')
      const knowsFactsCount = Array.isArray(person.knows_facts) ? person.knows_facts.length : 0
      const hiddenTruthsCount = Array.isArray(person.hidden_truths) ? person.hidden_truths.length : 0
      const interactionStyle = String(person.interaction_style || '')

      if (!status.includes('无法交流') && !['死亡', '昏迷'].includes(status)) score += 3
      if (['证人', '嫌疑人', '被害人'].includes(roleType)) score += 2
      score += Math.min(knowsFactsCount, 3)
      score += Math.min(hiddenTruthsCount, 2)
      if (interactionStyle.includes('观察') || interactionStyle.includes('情绪') || interactionStyle.includes('对抗')) score += 1

      return { name: person.name, score }
    })
    .sort((a: { score: number }, b: { score: number }) => b.score - a.score)

  return ranked[0]?.name || roleNames[0] || ''
}

const toggleSceneRole = (scene: any, roleName: string) => {
  const current = Array.isArray(scene?.role_names) ? scene.role_names : []
  if (current.includes(roleName)) {
    scene.role_names = current.filter((item: string) => item !== roleName)
  } else {
    scene.role_names = [...current, roleName]
  }
  if (!scene.role_names.length) {
    scene.primary_role_name = ''
  } else if (!scene.role_names.includes(scene.primary_role_name)) {
    scene.primary_role_name = scene.role_names[0]
  }
}

const getSceneRoleCandidates = (caseItem: any, scene: any) => {
  const selectedNames = Array.isArray(scene?.role_names) ? scene.role_names : []
  return (caseItem?.persons || []).filter((person: any) => selectedNames.includes(person.name))
}

const getSceneRoleRecommendation = (caseItem: any, scene: any) => {
  const candidates = getSceneRoleCandidates(caseItem, scene)
  if (!candidates.length) return null

  const scored = candidates.map((person: any) => {
    let score = 0
    const reasons: string[] = []
    const roleType = String(person.role_type || person.role || '')
    const knowsFactsCount = Array.isArray(person.knows_facts) ? person.knows_facts.length : 0
    const hiddenTruthsCount = Array.isArray(person.hidden_truths) ? person.hidden_truths.length : 0
    const status = String(person.status || '正常')

    if (!status.includes('无法交流') && status !== '死亡' && status !== '昏迷') {
      score += 3
      reasons.push('可正常交流')
    }
    if (knowsFactsCount > 0) {
      score += Math.min(knowsFactsCount, 3)
      reasons.push(`掌握 ${knowsFactsCount} 条已知事实`)
    }
    if (hiddenTruthsCount > 0) {
      score += Math.min(hiddenTruthsCount, 2)
      reasons.push(`带有 ${hiddenTruthsCount} 个可压实隐瞒点`)
    }
    if (['证人', '嫌疑人', '被害人'].includes(roleType)) {
      score += 2
      reasons.push(`角色类型是${roleType}`)
    }
    if (String(person.interaction_style || '').includes('观察') || String(person.interaction_style || '').includes('情绪')) {
      score += 1
      reasons.push('有明显问询反应特征')
    }

    return {
      name: person.name,
      score,
      reason: reasons.join('，') || '信息相对完整',
    }
  }).sort((a: { score: number }, b: { score: number }) => b.score - a.score)

  return scored[0] || null
}

const getSceneUnsuitableRoleHints = (caseItem: any, scene: any) => {
  return getSceneRoleCandidates(caseItem, scene)
    .filter((person: any) => {
      const status = String(person.status || '正常')
      return status.includes('无法交流') || status === '死亡' || status === '昏迷' || !(Array.isArray(person.knows_facts) && person.knows_facts.length)
    })
    .map((person: any) => {
      const status = String(person.status || '正常')
      if (status.includes('无法交流') || status === '死亡' || status === '昏迷') {
        return `${person.name} 当前状态为“${status}”，不适合作为主对话人。`
      }
      return `${person.name} 当前可直接输出的已知事实较少，更适合作为辅助角色或补充对象。`
    })
}

const getScenePrimaryRoleSummary = (caseItem: any, scene: any) => {
  const person = (caseItem?.persons || []).find((item: any) => item.name === scene?.primary_role_name)
  if (!person) return '当前未匹配到对应角色模板。'
  const archetype = person.behavior_archetype || '求助配合型'
  const policeAttitude = person.police_attitude || person.authority_attitude || '暂无明确对警方态度'
  const goal = person.current_goal || person.current_need || '暂无当前诉求'
  const concern = person.core_concern || person.weakness || '暂无明确顾虑'
  const triggers = getPersonListText(person.trigger_points).replace(/\n/g, '、') || '暂无明确触发点'
  const calming = getPersonListText(person.calming_points).replace(/\n/g, '、') || '暂无明确安抚点'
  return `主对话人画像：${archetype}；面对警方通常是“${policeAttitude}”；当前最想保住“${goal}”；最怕“${concern}”；触发点常见于“${triggers}”；更容易被“${calming}”稳住。`
}

const stringifyStages = (value: any) => JSON.stringify(safeJsonParse(value, []), null, 2)
const getStructuredData = (caseItem: any) => safeJsonParse(caseItem?.structured_data, {})
const resolveOriginalContent = (payload: any, fallback = '') => {
  const structuredData = getStructuredData(payload)
  return String(
    payload?.original_content
      || structuredData?.rawText
      || structuredData?.original_content
      || structuredData?.extracted_text_full
      || structuredData?.extracted_text_preview
      || fallback
      || ''
  )
}

const getTypesByGroup = (groupLabel: string) => caseTypeGroups.find((item) => item.label === groupLabel)?.options || []
const getCaseTypeGroup = (caseType: string) => caseTypeGroups.find((group) => group.options.includes(caseType))?.label || ''
const showTypeNormalizationHint = (payload: any) => Boolean(payload?.ai_case_type_raw && payload?.case_type && payload.ai_case_type_raw !== payload.case_type)
const shouldWarnOnTitle = (title: string) => /^[\d\W_]+$/u.test(String(title || '').trim())

const formatFileSize = (size: number) => {
  if (!size) return '0 B'
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
  return `${(size / 1024 / 1024).toFixed(1)} MB`
}

const normalizeEditableCase = (caseItem: any) => {
  const structuredData = getStructuredData(caseItem)
  const cloned = JSON.parse(JSON.stringify(caseItem))
  const normalizedPersons = normalizePersonEditors(structuredData.persons || [], { collapsed: true })
  return {
    ...cloned,
    original_content: resolveOriginalContent(cloned),
    ai_case_type_raw: structuredData.ai_case_type_raw || '',
    parse_engine: structuredData.parse_engine || '',
    parse_warnings: Array.isArray(structuredData.parse_warnings) ? structuredData.parse_warnings : [],
    scene_generation_mode: structuredData.scene_generation_mode || '',
    scene_generation_warning: structuredData.scene_generation_warning || '',
    case_type_group: getCaseTypeGroup(cloned.case_type),
    persons: normalizedPersons,
    scenes: normalizeSceneEditors(cloned.scenes || [], structuredData, normalizedPersons),
  }
}

const refreshCasesPage = async () => {
  await Promise.all([fetchCases(), fetchSceneRoleAudit()])
}

const fetchCases = async () => {
  casesLoading.value = true
  casesError.value = ''
  try {
    let res: any = await request.get('/cases/', { _skipErrorToast: true } as any)
    if (typeof res === 'string' && res.toLowerCase().includes('<!doctype html')) {
      res = await request.get('/cases/', { _skipErrorToast: true } as any)
    }
    cases.value = Array.isArray(res) ? [...res] : []
    const focusId = Number(route.query.case_id)
    if (focusId) {
      const target = cases.value.find((item: any) => item.id === focusId)
      if (target) {
        editCase(target)
      }
    }
  } catch (error) {
    console.error('Fetch cases error:', error)
    cases.value = []
    casesError.value = '案件列表加载失败，请稍后重试。'
  } finally {
    casesLoading.value = false
  }
}

const fetchSceneRoleAudit = async () => {
  auditLoading.value = true
  try {
    const res: any = await request.get('/cases/scene-role-audit', { _skipErrorToast: true } as any)
    auditCases.value = res.cases || []
    auditSummary.caseCount = res.case_count || 0
    auditSummary.issueSceneCount = res.issue_scene_count || 0
  } catch {
    showToast('场景人物校验加载失败')
  } finally {
    auditLoading.value = false
  }
}

const repairSceneRoles = async () => {
  repairing.value = true
  try {
    const res: any = await request.post('/cases/scene-role-repair', {}, { _skipErrorToast: true } as any)
    auditSummary.lastRepairCount = res.repaired_scene_count || 0
    if (res.audit) {
      auditCases.value = res.audit.cases || []
      auditSummary.caseCount = res.audit.case_count || 0
      auditSummary.issueSceneCount = res.audit.issue_scene_count || 0
    }
    showToast({ type: 'success', message: `已修复 ${auditSummary.lastRepairCount} 个场景` })
  } catch {
    showToast('场景人物修复失败')
  } finally {
    repairing.value = false
  }
}

const getCaseAudit = (caseId: number) => auditCases.value.find((item: any) => item.case_id === caseId)
const getCaseIssueCount = (caseId: number) => getCaseAudit(caseId)?.issue_scene_count || 0

const resetCreateState = () => {
  currentStep.value = 0
  form.title = ''
  form.caseTypeGroup = ''
  form.caseType = ''
  form.rawText = ''
  importMode.value = 'plain_case'
  aiParsedData.value = {}
  generatedScenes.value = []
  clearUploadedFile()
}

const openAddModal = () => {
  resetCreateState()
  showAdd.value = true
}

const switchImportMode = (mode: 'plain_case' | 'transcript_file') => {
  importMode.value = mode
  aiParsedData.value = {}
  generatedScenes.value = []
  currentStep.value = 0
}

const chooseFile = () => fileInputRef.value?.click()

const clearUploadedFile = () => {
  uploadedFile.value = null
  fileParseStatus.value = 'idle'
  fileMeta.name = ''
  fileMeta.type = ''
  fileMeta.size = 0
  if (fileInputRef.value) fileInputRef.value.value = ''
}

const handleFileChange = (event: Event) => {
  const target = event.target as HTMLInputElement
  const file = target.files?.[0]
  if (!file) return

  const lowerName = file.name.toLowerCase()
  if (!['.pdf', '.docx', '.md'].some((ext) => lowerName.endsWith(ext))) {
    fileParseStatus.value = 'error'
    showToast('仅支持 PDF、DOCX、MD 文件')
    target.value = ''
    return
  }
  if (file.size > 20 * 1024 * 1024) {
    fileParseStatus.value = 'error'
    showToast('文件大小不能超过 20MB')
    target.value = ''
    return
  }

  uploadedFile.value = file
  fileParseStatus.value = 'ready'
  fileMeta.name = file.name
  fileMeta.type = file.name.split('.').pop()?.toUpperCase() || ''
  fileMeta.size = file.size
}

const startParsing = async () => {
  parsing.value = true
  try {
    if (importMode.value === 'transcript_file') {
      if (!uploadedFile.value) {
        showToast('请先上传笔录文件')
        return
      }
      const payload = new FormData()
      payload.append('file', uploadedFile.value)
      payload.append('source_mode', 'transcript_file')
      const res: any = await request.post('/cases/parse-file', payload, { _skipErrorToast: true } as any)
      aiParsedData.value = res || {}
      aiParsedData.value.persons = normalizePersonEditors(aiParsedData.value.persons || [], { collapsed: true })
      if (parseEngineIsFallback(res)) {
        showToast('本次为规则兜底解析，请人工复核后再发布')
      }
      fileParseStatus.value = 'parsed'
      if (!form.title) form.title = res.case_name || ''
      if (!form.caseType) form.caseType = res.case_type || ''
      form.caseTypeGroup = getCaseTypeGroup(form.caseType)
      fileMeta.name = res.file_meta?.name || fileMeta.name
      fileMeta.type = res.file_meta?.type || fileMeta.type
      fileMeta.size = res.file_meta?.size || fileMeta.size
      return
    }

    const res: any = await request.post('/cases/parse', { text: form.rawText, source_mode: 'plain_case' }, { _skipErrorToast: true } as any)
    aiParsedData.value = res || {}
    aiParsedData.value.persons = normalizePersonEditors(aiParsedData.value.persons || [], { collapsed: true })
    if (parseEngineIsFallback(res)) {
      showToast('本次为规则兜底解析，请人工复核后再发布')
    }
    if (!form.caseType) form.caseType = res.case_type || ''
    form.caseTypeGroup = getCaseTypeGroup(form.caseType)
  } catch {
    if (importMode.value === 'transcript_file') fileParseStatus.value = 'error'
    showToast('AI 解析失败')
    throw new Error('parse-failed')
  } finally {
    parsing.value = false
  }
}

const startGenerating = async () => {
  generating.value = true
  try {
    const caseInfo = {
      ...aiParsedData.value,
      case_name: form.title || aiParsedData.value.case_name,
      case_type: form.caseType || aiParsedData.value.case_type,
      case_background: aiParsedData.value.case_background,
    }
    const res: any = await request.post('/cases/generate-scenes', { case_info: caseInfo }, { _skipErrorToast: true } as any)
    generatedScenes.value = (res.scenes || []).map((scene: any) => {
      const roleNames = Array.isArray(scene?.roles) ? scene.roles : []
      return {
        ...scene,
        primary_role_name: pickRecommendedPrimaryRoleName(aiParsedData.value.persons || [], roleNames) || roleNames[0] || '',
      }
    })
    aiParsedData.value = {
      ...aiParsedData.value,
      scene_generation_mode: res.scene_generation_mode || '',
      scene_generation_warning: res.scene_generation_warning || '',
    }
    if (sceneGenerationIsFallback(res)) {
      showToast('本次为规则兜底场景，请人工复核场景与角色分配')
    }
  } catch {
    showToast('场景生成失败')
    throw new Error('generate-failed')
  } finally {
    generating.value = false
  }
}

const submitFinal = async () => {
  if (!validatePersonsBeforeSave(aiParsedData.value?.persons || [])) return
  savingCreate.value = true
  try {
    const personsPayload = serializePersonsForSave(aiParsedData.value.persons || [])
    await request.post('/cases/full-create', {
      case: {
        ...aiParsedData.value,
        persons: personsPayload,
        title: form.title || aiParsedData.value.case_name,
        case_type: form.caseType || aiParsedData.value.case_type,
        background: aiParsedData.value.case_background,
        original_content: importMode.value === 'plain_case'
          ? form.rawText
          : resolveOriginalContent(aiParsedData.value),
        source_mode: importMode.value,
        source_file_name: fileMeta.name || '',
        source_file_type: fileMeta.type || '',
        source_file_size: fileMeta.size || 0,
        extracted_text_preview: aiParsedData.value.extracted_text_preview || '',
      },
      scenes: generatedScenes.value,
    }, { _skipErrorToast: true } as any)
    showToast({ type: 'success', message: '案件发布成功' })
    showAdd.value = false
    await refreshCasesPage()
  } catch {
    showToast('案件发布失败')
  } finally {
    savingCreate.value = false
  }
}

const handleNext = async () => {
  if (currentStep.value === 0) {
    if (importMode.value === 'plain_case') {
      if (!form.title || !form.rawText.trim()) {
        showToast('请填写完整案件标题和原始文本')
        return
      }
      if (shouldWarnOnTitle(form.title)) {
        try {
          await showConfirmDialog({
            title: '标题提示',
            message: '当前案件标题看起来是纯数字或纯符号。系统允许继续保存，但建议确认这就是最终展示标题。',
          })
        } catch {
          return
        }
      }
    } else if (!uploadedFile.value) {
      showToast('请先上传笔录文件')
      return
    }

    currentStep.value = 1
    try {
      await startParsing()
    } catch {
      currentStep.value = 0
    }
    return
  }

  if (currentStep.value === 1) {
    if (!form.title) form.title = aiParsedData.value.case_name || ''
    if (!form.caseType) form.caseType = aiParsedData.value.case_type || ''
    currentStep.value = 2
    try {
      await startGenerating()
    } catch {
      currentStep.value = 1
    }
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
  resetReviewWorkspace()
  if (Array.isArray(editableCase.value?.persons)) {
    editableCase.value.persons.forEach((person: any) => {
      person._collapsed = true
    })
  }
  showDetail.value = true
  router.replace(`/admin/cases?case_id=${caseItem.id}`)
}

const closeDetail = () => {
  showDetail.value = false
  selectedCase.value = null
  editableCase.value = null
  resetReviewWorkspace()
  router.replace('/admin/cases')
}

const resetEditableCase = () => {
  if (!selectedCase.value) return
  editableCase.value = normalizeEditableCase(selectedCase.value)
}

const buildCaseInfoForCompletion = (caseItem: any) => {
  const structured = getStructuredData(caseItem)
  return {
    case_name: caseItem?.title || structured.case_name || '',
    case_type: caseItem?.case_type || structured.case_type || '',
    case_background: caseItem?.background || structured.case_background || '',
    fact_sheet: structured.fact_sheet || {},
    persons: serializePersonsForSave(caseItem?.persons || structured.persons || []),
    conflict_points: structured.conflict_points || [],
    key_facts: structured.key_facts || [],
    hidden_info: structured.hidden_info || [],
    evidence_points: structured.evidence_points || [],
    dispatch_brief_suggestion: structured.dispatch_brief_suggestion || '',
    first_impression_suggestion: structured.first_impression_suggestion || '',
    transcript_summary: structured.transcript_summary || '',
  }
}

const isBlankFormValue = (value: any) => {
  const text = String(value ?? '').trim()
  if (!text) return true
  return ['未明确', '未提取到案件背景', '待核实', '暂无', '解析失败'].includes(text)
}

const pickFilled = (current: any, incoming: any) => (isBlankFormValue(current) ? incoming : current)

const mergePersonEditors = (currentPersons: any[], incomingPersons: any[]) => {
  if (!incomingPersons?.length) return currentPersons
  const byName = new Map((currentPersons || []).map((person: any) => [String(person?.name || '').trim(), person]))
  incomingPersons.forEach((incoming: any) => {
    const name = String(incoming?.name || '').trim()
    if (!name) return
    const existing = byName.get(name)
    if (!existing) {
      byName.set(name, incoming)
      return
    }
    Object.keys(incoming).forEach((key) => {
      const nextValue = incoming[key]
      if (Array.isArray(nextValue)) {
        if (!Array.isArray(existing[key]) || !existing[key].length) existing[key] = nextValue
        return
      }
      if (isBlankFormValue(existing[key]) && !isBlankFormValue(nextValue)) {
        existing[key] = nextValue
      }
    })
  })
  return normalizePersonEditors(Array.from(byName.values()), { collapsed: true })
}

const applyCaseCompletionPayload = (target: any, payload: any, rawText: string) => {
  const parsed = payload?.case_info || {}
  const generatedScenes = Array.isArray(payload?.scenes) ? payload.scenes : []
  const sceneByName = Object.fromEntries(
    generatedScenes
      .map((scene: any) => [String(scene?.scene_name || '').trim(), scene])
      .filter(([name]: [string, any]) => name),
  )

  if (isBlankFormValue(target.title)) target.title = parsed.case_name || target.title
  target.background = pickFilled(target.background, parsed.case_background)
  target.ai_case_type_raw = parsed.ai_case_type_raw || target.ai_case_type_raw
  if (isBlankFormValue(target.case_type) && parsed.case_type) target.case_type = parsed.case_type
  target.case_type_group = getCaseTypeGroup(target.case_type)
  target.persons = mergePersonEditors(target.persons || [], parsed.persons || [])

  target.scenes = (target.scenes || []).map((scene: any, index: number) => {
    const aiScene = sceneByName[String(scene?.name || '').trim()] || generatedScenes[index] || {}
    const nextRoleNames = Array.isArray(aiScene.roles) && aiScene.roles.length
      ? aiScene.roles
      : scene.role_names || []
    const nextStages = Array.isArray(aiScene.stages) && aiScene.stages.length ? aiScene.stages : null
    return {
      ...scene,
      description: pickFilled(scene.description, aiScene.scene_description),
      dispatch_brief: pickFilled(scene.dispatch_brief, aiScene.dispatch_brief),
      first_impression: pickFilled(scene.first_impression, aiScene.first_impression),
      difficulty: pickFilled(scene.difficulty, aiScene.difficulty),
      stagesModel: nextStages ? normalizeStageEditors(nextStages) : scene.stagesModel,
      stagesText: nextStages ? stringifyStages(nextStages) : scene.stagesText,
      role_names: nextRoleNames.length ? nextRoleNames : scene.role_names || [],
      primary_role_name:
        pickFilled(
          scene.primary_role_name,
          pickRecommendedPrimaryRoleName(target.persons || [], nextRoleNames) || nextRoleNames[0] || '',
        ) || scene.primary_role_name,
    }
  })

  const previousStructured = getStructuredData(target)
  const mergedFactSheet = { ...(previousStructured.fact_sheet || {}) }
  const incomingFactSheet = parsed.fact_sheet || {}
  Object.keys(incomingFactSheet).forEach((key) => {
    if (isBlankFormValue(mergedFactSheet[key]) && !isBlankFormValue(incomingFactSheet[key])) {
      mergedFactSheet[key] = incomingFactSheet[key]
    }
  })

  const mergeListField = (key: string) => {
    const current = Array.isArray(previousStructured[key]) ? previousStructured[key] : []
    const incoming = Array.isArray(parsed[key]) ? parsed[key] : []
    return current.length ? current : incoming
  }

  const structuredData = {
    ...previousStructured,
    ...parsed,
    fact_sheet: mergedFactSheet,
    conflict_points: mergeListField('conflict_points'),
    key_facts: mergeListField('key_facts'),
    hidden_info: mergeListField('hidden_info'),
    evidence_points: mergeListField('evidence_points'),
    inconsistencies: mergeListField('inconsistencies'),
    scene_generation_mode: payload.scene_generation_mode || previousStructured.scene_generation_mode || '',
    scene_generation_warning: payload.scene_generation_warning || previousStructured.scene_generation_warning || '',
    completion_engine: payload.completion_engine || '',
    completion_agent: payload.completion_agent || '',
    filled_field_paths: payload.filled_field_paths || [],
    field_evidence: payload.field_evidence || {},
    completion_warnings: payload.completion_warnings || [],
    case_name: target.title,
    case_type: target.case_type,
    case_background: target.background,
    persons: serializePersonsForSave(target.persons || []),
    schema_version: CASE_SCHEMA_VERSION,
    canonical_person_fields: PERSON_CANONICAL_FIELDS,
    canonical_alias_map: PERSON_ALIAS_TO_CANONICAL,
    rawText,
  }
  target.structured_data = JSON.stringify(structuredData, null, 2)
  target.parse_engine = parsed.parse_engine || ''
  target.parse_warnings = Array.isArray(parsed.parse_warnings) ? parsed.parse_warnings : []
  target.scene_generation_mode = payload.scene_generation_mode || ''
  target.scene_generation_warning = payload.scene_generation_warning || ''
}

const runAiSupplement = async () => {
  if (!editableCase.value) return
  const rawText = String(editableCase.value.original_content || '').trim()
  if (!rawText) {
    showToast('请先保留案件原始文本，再执行信息补全')
    return
  }

  supplementingAi.value = true
  try {
    const payload: any = await request.post(
      '/cases/ai-complete',
      {
        source_text: rawText,
        source_mode: 'plain_case',
        mode: 'fill_gaps',
        include_scenes: true,
        target_groups: ['case_basic', 'fact_sheet', 'lists', 'persons', 'scenes'],
        case_info: buildCaseInfoForCompletion(editableCase.value),
      },
      { _skipErrorToast: true } as any,
    )
    applyCaseCompletionPayload(editableCase.value, payload, rawText)

    const hasWarnings = Array.isArray(payload?.completion_warnings) && payload.completion_warnings.length > 0
    const isFallback = String(payload?.completion_engine || '') !== 'deepseek-case-officer'
    showToast({
      type: !isFallback && !hasWarnings ? 'success' : 'fail',
      message: isFallback
        ? '已兜底补全，请人工复核后再保存'
        : hasWarnings
          ? 'AI 已补全空白项，部分字段原文无依据，请复核'
          : 'AI 已根据原文补全案件全部空白信息',
    })
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
  if (!validatePersonsBeforeSave(editableCase.value.persons || [])) return

  const scenesPayload = []
  for (const scene of editableCase.value.scenes || []) {
    ensureSceneAssessmentPointsModel(scene)
    const parsedStages = [
      {
        stage_name: '考察点',
        stage_goal: '',
        recommended_prompts: [],
        assessment_points: serializeAssessmentPointsForSave(scene.assessmentPointsModel || []),
        action_catalog: [],
        completion_rules: {
          min_user_turns: 3,
          required_point_ids: [],
          required_action_ids: [],
        },
        end_conditions: {
          must_complete_current_stage: true,
          required_point_ids: [],
          required_action_ids: [],
          closure_actions: [],
          closing_script: '',
        },
      },
    ]
    scene.stagesText = JSON.stringify(parsedStages, null, 2)

    scenesPayload.push({
      id: scene.id,
      name: scene.name,
      description: scene.description,
      difficulty: scene.difficulty,
      dispatch_brief: scene.dispatch_brief,
      first_impression: scene.first_impression,
      stages: parsedStages,
      role_names: Array.isArray(scene.role_names) ? scene.role_names : [],
      primary_role_name: scene.primary_role_name || '',
    })
  }

  savingDetail.value = true
  try {
    const personsPayload = serializePersonsForSave(editableCase.value.persons || [])
    const structuredData = {
      ...getStructuredData(editableCase.value),
      case_name: editableCase.value.title,
      case_type: editableCase.value.case_type,
      case_background: editableCase.value.background,
      persons: personsPayload,
      schema_version: CASE_SCHEMA_VERSION,
      canonical_person_fields: PERSON_CANONICAL_FIELDS,
      canonical_alias_map: PERSON_ALIAS_TO_CANONICAL,
      rawText: editableCase.value.original_content,
    }

    const res: any = await request.put(`/cases/${editableCase.value.id}`, {
      case: {
        title: editableCase.value.title,
        case_type: editableCase.value.case_type,
        background: editableCase.value.background,
        original_content: editableCase.value.original_content,
        structured_data: structuredData,
      },
      scenes: scenesPayload,
    }, { _skipErrorToast: true } as any)

    showToast({ type: 'success', message: '案件已更新' })
    selectedCase.value = res
    editableCase.value = normalizeEditableCase(res)
    await refreshCasesPage()
  } catch {
    showToast('保存失败')
  } finally {
    savingDetail.value = false
  }
}

const deleteCase = (caseItem: any) => {
  showConfirmDialog({
    title: '确认删除',
    message: `确定要删除《${caseItem.title}》吗？此操作不可撤销。`,
  }).then(async () => {
    try {
      await request.delete(`/cases/${caseItem.id}`, { _skipErrorToast: true } as any)
      showToast({ type: 'success', message: '案件已删除' })
      if (selectedCase.value?.id === caseItem.id) closeDetail()
      await refreshCasesPage()
    } catch {
      showToast('删除失败')
    }
  }).catch(() => {})
}

const getTagType = (type: string) => {
  if (['邻里纠纷', '家庭纠纷', '情感纠纷', '劳资纠纷', '消费纠纷'].includes(type)) return 'success'
  if (['打架斗殴', '寻衅滋事', '故意伤害', '故意杀人'].includes(type)) return 'danger'
  if (['盗窃', '诈骗', '电信网络诈骗', '入室盗窃', '抢劫'].includes(type)) return 'warning'
  return 'primary'
}

onMounted(refreshCasesPage)
</script>

<style scoped>
.line-clamp-3 {
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.stat-label {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.16em;
  font-weight: 900;
  color: #94a3b8;
}

.stat-value {
  margin-top: 10px;
  font-size: 28px;
  line-height: 1;
  font-weight: 900;
}

.form-label {
  display: block;
  margin-bottom: 0.2rem;
  font-size: 12px;
  line-height: 1.3;
  font-weight: 700;
  color: #334155;
}

.form-label--muted {
  color: #64748b;
  font-weight: 600;
}

.form-field-row {
  display: grid;
  grid-template-columns: minmax(6.5rem, 8.5rem) minmax(0, 1fr);
  gap: 0.25rem 0.5rem;
  align-items: center;
}

.form-field-row .form-label {
  margin-bottom: 0;
  text-align: right;
  font-size: 11px;
}

.form-field-row--stack {
  grid-template-columns: 1fr;
  align-items: stretch;
}

.form-field-row--stack .form-label {
  text-align: left;
}

.form-field-stack {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.form-input,
.form-textarea {
  width: 100%;
  padding: 0.35rem 0.6rem;
  font-size: 13px;
  line-height: 1.4;
  background: #fff;
  border: 1px solid rgb(229 231 235);
  border-radius: 0.5rem;
  outline: none;
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}

.form-input:focus,
.form-textarea:focus {
  border-color: #1d3557;
  box-shadow: 0 0 0 3px rgb(29 53 87 / 10%);
}

.form-textarea {
  resize: vertical;
  min-height: 2.75rem;
}

.cases-compact .space-y-6 > :not([hidden]) ~ :not([hidden]) {
  margin-top: 0.875rem;
}

.cases-compact .space-y-5 > :not([hidden]) ~ :not([hidden]) {
  margin-top: 0.75rem;
}

.cases-compact .space-y-4 > :not([hidden]) ~ :not([hidden]) {
  margin-top: 0.625rem;
}

.cases-compact .gap-4 {
  gap: 0.625rem;
}

.cases-compact .gap-3 {
  gap: 0.5rem;
}

.cases-compact .p-6 {
  padding: 0.875rem;
}

.cases-compact .p-5 {
  padding: 0.75rem;
}

.cases-compact .mt-2.text-xs {
  margin-top: 0.25rem;
  font-size: 11px;
  line-height: 1.35;
}

.cases-compact .rounded-xl.border.px-4.py-3 {
  padding: 0.5rem 0.65rem;
  font-size: 12px;
  line-height: 1.45;
}

.section-block {
  border: 1px solid #e5e7eb;
  border-radius: 24px;
  background: #ffffff;
  padding: 18px;
}

.section-block--blue {
  background: #ffffff;
  border-color: #e5e7eb;
}

.section-block--neutral {
  background: #ffffff;
  border-color: #e5e7eb;
}

.section-block--violet {
  background: #ffffff;
  border-color: #e5e7eb;
}

.section-block__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
}

.section-block__eyebrow {
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: #64748b;
}

.section-block__title {
  margin-top: 4px;
  font-size: 20px;
  line-height: 1.2;
  font-weight: 800;
  color: #0f172a;
}

.section-block__hint {
  max-width: 260px;
  border-radius: 999px;
  border: 1px solid #e5e7eb;
  background: #f8fafc;
  padding: 8px 12px;
  font-size: 12px;
  line-height: 1.5;
  color: #475569;
}


.review-module-nav {
  display: flex;
  justify-content: center;
  align-items: stretch;
  gap: 12px;
  margin-bottom: 8px;
}

.review-module-nav__item {
  flex: 1;
  max-width: 200px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4px;
  padding: 14px 16px;
  border-radius: 14px;
  border: 2px solid #e2e8f0;
  background: #fff;
  transition: all 0.2s ease;
  cursor: pointer;
}

.review-module-nav__item.is-active {
  border-color: #1d3557;
  background: #1d3557;
  box-shadow: 0 8px 20px rgba(29, 53, 87, 0.18);
}

.review-module-nav__step {
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.12em;
  color: #94a3b8;
}

.review-module-nav__label {
  font-size: 17px;
  font-weight: 800;
  color: #334155;
}

.review-module-nav__item.is-active .review-module-nav__step,
.review-module-nav__item.is-active .review-module-nav__label {
  color: #fff;
}

.review-module-nav__hint {
  text-align: center;
  font-size: 12px;
  color: #64748b;
  margin-bottom: 12px;
}

.scene-studio__layout {
  display: grid;
  grid-template-columns: 168px 1fr;
  gap: 16px;
  align-items: start;
}

.scene-studio__nav {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.scene-studio__nav-item {
  text-align: left;
  padding: 10px 12px;
  border-radius: 12px;
  border: 1px solid #e2e8f0;
  background: #f8fafc;
  cursor: pointer;
}

.scene-studio__nav-item.is-active {
  border-color: #1d3557;
  background: #eff6ff;
}

.scene-studio__nav-index {
  display: block;
  font-size: 11px;
  font-weight: 700;
  color: #64748b;
}

.scene-studio__nav-name {
  display: block;
  margin-top: 2px;
  font-size: 13px;
  font-weight: 700;
  color: #0f172a;
}

.scene-studio__tabs {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}

.scene-studio__tab {
  padding: 8px 14px;
  border-radius: 999px;
  border: 1px solid #e2e8f0;
  background: #fff;
  font-size: 13px;
  font-weight: 700;
  color: #475569;
  cursor: pointer;
}

.scene-studio__tab.is-active {
  border-color: #1d3557;
  background: #1d3557;
  color: #fff;
}

.scene-editor-card--studio {
  border: none;
  box-shadow: none;
  padding: 0;
}

.scene-flow-panel {
  padding: 4px 0;
}

.scene-flow-panel__toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.scene-flow-panel__badge {
  font-size: 13px;
  font-weight: 700;
  color: #334155;
}

.scene-flow-panel__actions {
  display: flex;
  gap: 8px;
}

.scene-flow-panel__empty {
  padding: 24px 12px;
  text-align: center;
  font-size: 13px;
  color: #64748b;
  border: 1px dashed #e2e8f0;
  border-radius: 12px;
}

.scene-flow-panel__json {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.scene-flow-stage {
  padding: 14px;
  margin-bottom: 10px;
  border: 1px solid #e2e8f0;
  border-radius: 14px;
  background: #f8fafc;
  width: 100%;
  max-width: 100%;
  transition: max-width 0.2s ease, padding 0.2s ease;
}

.scene-flow-stage--collapsed {
  max-width: 100%;
  padding: 8px 12px;
}

.scene-flow-stage__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}

.scene-flow-stage__index {
  font-size: 13px;
  font-weight: 800;
  color: #1d3557;
}

.scene-flow-stage__core {
  display: block;
}

.scene-flow-stage__audit {
  margin-top: 6px;
  padding-top: 0;
  border-top: none;
}

.scene-flow-stage__stats {
  display: block;
  font-size: 12px;
  font-weight: 600;
  color: #64748b;
  margin-bottom: 4px;
}

.scene-flow-stage__row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  align-items: start;
}

.scene-flow-stage__row .form-input,
.scene-flow-stage__row .form-textarea {
  min-height: 44px;
}

.scene-flow-stage__row .form-textarea {
  resize: vertical;
}

.scene-flow-stage__col {
  min-width: 0;
}

.scene-flow-stage__hint {
  font-size: 12px;
  color: #94a3b8;
  line-height: 1.5;
}

.scene-flow-tag-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.scene-flow-tag {
  display: inline-flex;
  align-items: center;
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 600;
  color: #334155;
  background: #fff;
  border: 1px solid #e2e8f0;
}

.scene-flow-tag--required {
  border-color: #f59e0b;
  background: #fffbeb;
  color: #b45309;
}

.scene-flow-stage__advanced {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid #e2e8f0;
}

.scene-flow-advanced-block + .scene-flow-advanced-block {
  margin-top: 14px;
}

.scene-flow-advanced-block__title {
  font-size: 12px;
  font-weight: 800;
  color: #475569;
  margin-bottom: 8px;
}

.scene-flow-advanced-row {
  display: grid;
  grid-template-columns: 1fr auto auto;
  gap: 8px;
  align-items: center;
  margin-bottom: 8px;
}

.scene-flow-advanced-row--single {
  grid-template-columns: 1fr auto;
}

.scene-flow-check {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: #64748b;
  white-space: nowrap;
}

.detail-hero {
  border: 1px solid #e5e7eb;
  border-radius: 16px;
  background: #ffffff;
  padding: 12px 14px;
  box-shadow: none;
}

.detail-hero__eyebrow {
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: #64748b;
}

.detail-hero__title {
  margin-top: 4px;
  font-size: 16px;
  line-height: 1.35;
  font-weight: 800;
  color: #0f172a;
}

.detail-hero__desc {
  margin-top: 4px;
  max-width: 760px;
  font-size: 12px;
  line-height: 1.5;
  color: #475569;
}

.detail-hero__chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 8px;
}

.detail-hero__chip {
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  border: 1px solid #e5e7eb;
  background: #f8fafc;
  color: #475569;
  padding: 4px 8px;
  font-size: 11px;
  font-weight: 700;
}

.detail-hero__chip--blue {
  background: #f8fafc;
  color: #475569;
}

.detail-hero__chip--amber {
  background: #f8fafc;
  color: #475569;
}

.detail-hero__chip--cyan {
  background: #f8fafc;
  color: #475569;
}

.detail-hero__chip--emerald {
  background: #f8fafc;
  color: #475569;
}

.workspace-panel {
  border: 1px solid #e5e7eb;
  border-radius: 16px;
  background: #ffffff;
  padding: 12px;
  box-shadow: none;
}

.workspace-panel--indigo {
  background: #ffffff;
  border-color: #e5e7eb;
}

.workspace-panel--cyan {
  background: #ffffff;
  border-color: #e5e7eb;
}

.workspace-panel--amber {
  background: #ffffff;
  border-color: #e5e7eb;
}

.workspace-panel--emerald {
  background: #ffffff;
  border-color: #e5e7eb;
}

.workspace-panel__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 10px;
}

.workspace-panel__eyebrow {
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: #64748b;
}

.workspace-panel__title {
  margin-top: 2px;
  font-size: 15px;
  line-height: 1.3;
  font-weight: 800;
  color: #0f172a;
}

.supplement-toolbar--inline {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 12px;
  border-radius: 12px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
}

.supplement-toolbar--inline .supplement-toolbar__desc {
  flex: 1;
  font-size: 12px;
  color: #64748b;
  line-height: 1.5;
}

.source-panel--compact .source-panel__header {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.role-compact-table .role-compact-row {
  background: #fff;
}

.workspace-panel__desc {
  margin-top: 4px;
  max-width: 760px;
  font-size: 12px;
  line-height: 1.45;
  color: #64748b;
}

.workspace-panel__badge {
  flex-shrink: 0;
  border-radius: 999px;
  border: 1px solid #e5e7eb;
  background: #f8fafc;
  padding: 4px 8px;
  font-size: 11px;
  font-weight: 700;
  color: #334155;
}

.workspace-panel__body {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.scene-workbench {
  border: 0;
  border-radius: 0;
  background: transparent;
  padding: 0;
}

.scene-workbench__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.scene-workbench__eyebrow {
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: #64748b;
}

.scene-workbench__title {
  margin-top: 6px;
  font-size: 20px;
  line-height: 1.3;
  font-weight: 800;
  color: #0f172a;
}

.scene-workbench__hint {
  max-width: 300px;
  border-radius: 18px;
  border: 1px solid #e5e7eb;
  background: #f8fafc;
  padding: 10px 12px;
  font-size: 12px;
  line-height: 1.6;
  color: #475569;
}

.scene-workbench__legend {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 14px;
}

.scene-workbench__chip {
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  border: 1px solid #e5e7eb;
  background: #f8fafc;
  color: #475569;
  padding: 8px 12px;
  font-size: 12px;
  font-weight: 700;
}

.scene-workbench__chip--slate {
  background: #f8fafc;
  color: #475569;
}

.scene-workbench__chip--blue {
  background: #f8fafc;
  color: #475569;
}

.scene-workbench__chip--violet {
  background: #f8fafc;
  color: #475569;
}

.scene-workbench__chip--amber {
  background: #f8fafc;
  color: #475569;
}

.scene-editor-card {
  border: 1px solid #e5e7eb;
  border-radius: 16px;
  background: #ffffff;
  padding: 12px;
  box-shadow: none;
}

.scene-editor-card__top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
}

.scene-editor-card__index {
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  border: 1px solid #e5e7eb;
  background: #f8fafc;
  color: #475569;
  padding: 8px 12px;
  font-size: 12px;
  font-weight: 800;
}

.scene-editor-card__panel {
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  background: #ffffff;
  padding: 10px;
}

.scene-editor-card__panel + .scene-editor-card__panel {
  margin-top: 8px;
}

.scene-editor-card__panel--summary {
  background: #ffffff;
  border-color: #e5e7eb;
}

.scene-editor-card__panel--roles {
  background: #ffffff;
  border-color: #e5e7eb;
}

.scene-editor-card__panel--copy {
  background: #ffffff;
  border-color: #e5e7eb;
}

.scene-editor-card__panel--json {
  background: #ffffff;
  border-color: #e5e7eb;
}

.scene-editor-card__section-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 12px;
}

.scene-editor-card__eyebrow {
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: #64748b;
}

.scene-editor-card__title {
  margin-top: 2px;
  font-size: 15px;
  line-height: 1.3;
  font-weight: 800;
  color: #0f172a;
}

.scene-editor-card__section-title {
  margin-top: 4px;
  font-size: 16px;
  line-height: 1.35;
  font-weight: 800;
  color: #0f172a;
}

.scene-editor-card__helper {
  max-width: 260px;
  font-size: 12px;
  line-height: 1.6;
  color: #64748b;
}

.scene-stage-toolbar {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 8px;
  padding: 8px 10px;
  border-radius: 10px;
  border: 1px solid #e5e7eb;
  background: #f8fafc;
}

.scene-stage-toolbar__meta {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.scene-stage-toolbar__badge {
  display: inline-flex;
  width: fit-content;
  align-items: center;
  border-radius: 999px;
  border: 1px solid #e5e7eb;
  background: #ffffff;
  color: #475569;
  padding: 6px 10px;
  font-size: 12px;
  font-weight: 800;
}

.scene-stage-toolbar__hint {
  font-size: 12px;
  line-height: 1.6;
  color: #64748b;
}

.scene-stage-toolbar__actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 10px;
}

.scene-stage-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.scene-stage-empty {
  border: 1px dashed #cbd5e1;
  border-radius: 12px;
  background: #ffffff;
  padding: 10px;
  font-size: 12px;
  line-height: 1.5;
  color: #64748b;
}

.scene-stage-card {
  border-radius: 14px;
  border: 1px solid #e5e7eb;
  background: #ffffff;
  padding: 10px;
  box-shadow: none;
}

.scene-stage-card__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 8px;
}

.scene-stage-card__eyebrow {
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: #64748b;
}

.scene-stage-card__title {
  margin-top: 2px;
  font-size: 14px;
  line-height: 1.3;
  font-weight: 800;
  color: #0f172a;
}

.scene-stage-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
  margin-top: 8px;
}

.scene-stage-grid--rules {
  margin-top: 8px;
}

.scene-stage-meta-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}

.scene-stage-block {
  border-radius: 12px;
  border: 1px solid #e5e7eb;
  background: #ffffff;
  padding: 10px;
}

.scene-stage-block--sky {
  background: #ffffff;
  border-color: #e5e7eb;
}

.scene-stage-block--violet {
  background: #ffffff;
  border-color: #e5e7eb;
}

.scene-stage-block--amber {
  background: #ffffff;
  border-color: #e5e7eb;
}

.scene-stage-block--emerald {
  background: #ffffff;
  border-color: #e5e7eb;
}

.scene-stage-block__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 8px;
}

.scene-stage-block__eyebrow {
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: #64748b;
}

.scene-stage-block__title {
  margin-top: 2px;
  font-size: 13px;
  line-height: 1.3;
  font-weight: 800;
  color: #0f172a;
}

.scene-stage-block__empty {
  border: 1px dashed rgba(148, 163, 184, 0.4);
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.66);
  padding: 8px;
  font-size: 11px;
  line-height: 1.45;
  color: #64748b;
}

.scene-stage-item + .scene-stage-item {
  margin-top: 6px;
}

.scene-stage-item {
  border-radius: 10px;
  border: 1px solid rgba(226, 232, 240, 0.9);
  background: rgba(255, 255, 255, 0.88);
  padding: 8px;
}

.scene-stage-item__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 6px;
}

.scene-stage-item__title {
  font-size: 13px;
  font-weight: 800;
  color: #334155;
}

.scene-stage-checkbox {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin: 6px 0;
  font-size: 12px;
  font-weight: 700;
  color: #334155;
}

.scene-stage-checkbox--compact {
  margin: 4px 0 6px;
}

.scene-stage-checkbox input {
  width: 16px;
  height: 16px;
  accent-color: #1d3557;
}

.persona-stack-list {
  position: relative;
  padding-top: 8px;
  padding-bottom: 8px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.persona-stack-card {
  position: relative;
  cursor: default;
  transition: transform 0.24s ease, z-index 0.24s ease;
}

.persona-stack-shell {
  position: relative;
  padding-top: 0;
}

.persona-stack-layer {
  position: absolute;
  left: 18px;
  right: 18px;
  height: 100%;
  border-radius: 26px;
  border: 1px solid rgba(226, 232, 240, 0.9);
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.86) 0%, rgba(241, 245, 249, 0.92) 100%);
  pointer-events: none;
  transition: all 0.24s ease;
  display: none;
}

.persona-stack-layer--back {
  top: 0;
  transform: scale(0.985);
  opacity: 0.6;
}

.persona-stack-layer--mid {
  top: 5px;
  transform: scale(0.992);
  opacity: 0.82;
}

.persona-stack-surface {
  position: relative;
  border-radius: 14px;
  border: 1px solid #e5e7eb;
  background: #ffffff;
  box-shadow: none;
  padding: 10px 12px;
  transition: transform 0.24s ease, box-shadow 0.24s ease, border-color 0.24s ease;
}

.persona-stack-surface--clickable {
  cursor: pointer;
}

.persona-stack-card.is-collapsed:hover .persona-stack-surface,
.persona-stack-card.is-collapsed .persona-stack-surface--clickable:hover {
  transform: translateY(-1px);
  border-color: #cbd5e1;
  box-shadow: none;
}

.persona-stack-card.is-expanded .persona-stack-layer {
  opacity: 0;
  transform: scale(0.98);
}

.persona-stack-card.is-expanded {
  transform: translateY(-2px);
}

.persona-stack-card.is-expanded .persona-stack-surface {
  border-color: #cbd5e1;
  box-shadow: none;
}

.persona-stack-header {
  display: flex;
  width: 100%;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.persona-stack-toggle {
  color: #94a3b8;
  font-size: 13px;
  font-weight: 700;
  white-space: nowrap;
}

.persona-stack-summary {
  margin-top: 8px;
  display: flex;
  flex-wrap: wrap;
  gap: 6px 12px;
  color: #64748b;
  font-size: 12px;
  line-height: 1.45;
}

.persona-stack-expanded {
  padding-bottom: 2px;
}

.persona-role-summary {
  border-radius: 16px;
  border: 1px solid #e5e7eb;
  background: #f8fafc;
  padding: 12px 14px;
  font-size: 13px;
  line-height: 1.6;
  color: #475569;
}

.persona-compact-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 6px;
}

.persona-compact-panel {
  border-radius: 10px;
  border: 1px solid #e5e7eb;
  background: #ffffff;
  padding: 8px 10px;
}

.persona-compact-panel__title {
  font-size: 12px;
  line-height: 1.3;
  font-weight: 800;
  color: #0f172a;
}

.form-textarea--compact {
  min-height: 2.5rem;
}

.persona-toolbar-button {
  white-space: nowrap;
}

.persona-toolbar-button:deep(.van-button__text) {
  white-space: nowrap;
}

.persona-toolbar-button:deep(.van-button) {
  min-width: 96px;
}

@media (max-width: 768px) {
  .persona-toolbar-button {
    min-width: auto;
  }
}

@media (max-width: 768px) {
  .section-block__header,
  .workspace-panel__header,
  .scene-workbench__header,
  .scene-editor-card__section-head {
    flex-direction: column;
  }

  .section-block__hint,
  .workspace-panel__badge,
  .scene-workbench__hint,
  .scene-editor-card__helper {
    max-width: none;
  }

  .detail-hero__title,
  .workspace-panel__title,
  .section-block__title,
  .scene-workbench__title,
  .scene-editor-card__title {
    font-size: 18px;
  }

  .persona-stack-surface {
    padding: 18px;
  }

  .persona-stack-header {
    align-items: flex-start;
    flex-direction: column;
  }

  .persona-compact-grid {
    grid-template-columns: 1fr;
  }

  .scene-stage-toolbar,
  .scene-stage-card__header,
  .scene-stage-block__header {
    flex-direction: column;
  }

  .scene-stage-toolbar__actions {
    width: 100%;
    justify-content: flex-start;
  }

  .scene-stage-grid {
    grid-template-columns: 1fr;
  }

  .scene-stage-meta-grid {
    grid-template-columns: 1fr;
  }

  .scene-flow-stage__core {
    grid-template-columns: 1fr;
  }

  .scene-flow-advanced-row {
    grid-template-columns: 1fr;
  }
}

.mode-card {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 10px 12px;
  border-radius: 12px;
  border: 1px solid #e5e7eb;
  background: #fff;
  text-align: left;
  transition: all 0.2s ease;
}

.mode-card.active {
  border-color: #1d3557;
  box-shadow: 0 0 0 3px rgb(29 53 87 / 8%);
  background: #f8fbff;
}

.mode-card__title {
  font-size: 15px;
  font-weight: 800;
  color: #1f2937;
}

.mode-card__desc {
  font-size: 13px;
  line-height: 1.7;
  color: #64748b;
}

.file-hint {
  border: 1px solid #e5e7eb;
  background: #ffffff;
  border-radius: 16px;
  padding: 14px 16px;
}

.file-dropzone {
  border: 1px dashed #cbd5e1;
  background: #ffffff;
  border-radius: 20px;
  padding: 28px;
}

.status-pill {
  display: inline-flex;
  align-items: center;
  padding: 6px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 800;
  background: #f1f5f9;
  color: #64748b;
}

.status-pill.ready {
  background: #fff7ed;
  color: #c2410c;
}

.status-pill.success {
  background: #ecfdf5;
  color: #047857;
}

.status-pill.error {
  background: #fef2f2;
  color: #dc2626;
}

.preview-card {
  border: 1px solid #eef2f7;
  border-radius: 16px;
  background: #fff;
  padding: 14px 16px;
}

.preview-label,
.section-title {
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: #94a3b8;
}

.preview-value {
  margin-top: 8px;
  color: #1f2937;
  font-weight: 700;
}

.preview-body {
  margin-top: 10px;
  color: #475569;
  line-height: 1.8;
  white-space: pre-wrap;
}

.supplement-toolbar {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: center;
  border: 1px solid #e5e7eb;
  background: #ffffff;
  border-radius: 16px;
  padding: 14px 16px;
}

.supplement-toolbar__title {
  font-weight: 800;
  color: #0f172a;
}

.supplement-toolbar__desc {
  margin-top: 4px;
  font-size: 13px;
  line-height: 1.7;
  color: #64748b;
}

.source-panel {
  border: 1px solid #e5e7eb;
  border-radius: 18px;
  background: #fff;
  padding: 16px;
}

.section-block,
.detail-hero,
.workspace-panel,
.scene-editor-card,
.scene-stage-card,
.scene-stage-block,
.persona-stack-surface,
.file-hint,
.file-dropzone,
.supplement-toolbar,
.source-panel {
  position: relative;
  border-color: #d4dde8;
  background: linear-gradient(180deg, #ffffff 0%, #fcfdff 100%);
  box-shadow: 0 1px 0 rgba(255, 255, 255, 0.96) inset, 0 0 0 1px rgba(212, 221, 232, 0.4), 0 14px 28px rgba(15, 23, 42, 0.035);
}

.section-block::before,
.detail-hero::before,
.workspace-panel::before,
.scene-editor-card::before,
.scene-stage-card::before,
.scene-stage-block::before,
.persona-stack-surface::before,
.file-hint::before,
.file-dropzone::before,
.supplement-toolbar::before,
.source-panel::before {
  content: '';
  position: absolute;
  top: 0;
  left: 16px;
  right: 16px;
  height: 1px;
  background: linear-gradient(90deg, rgba(29, 53, 87, 0.2), rgba(148, 163, 184, 0));
  pointer-events: none;
}

.section-block__hint,
.workspace-panel__badge,
.detail-hero__chip,
.scene-workbench__hint,
.scene-workbench__chip,
.scene-editor-card__index,
.scene-stage-toolbar,
.scene-stage-toolbar__badge,
.scene-stage-empty,
.scene-stage-item,
.persona-role-summary,
.persona-compact-panel,
.preview-card {
  border-color: #d8e0ea;
  box-shadow: 0 1px 0 rgba(255, 255, 255, 0.92) inset, 0 0 0 1px rgba(216, 224, 234, 0.28);
}

.workspace-panel__header,
.section-block__header {
  padding-bottom: 16px;
  border-bottom: 1px solid #edf2f7;
}

.source-panel__header {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: center;
  margin-bottom: 12px;
}

.source-panel__meta {
  font-size: 12px;
  color: #94a3b8;
}

.source-panel__textarea {
  font-family: 'KaiTi', 'STKaiti', 'FangSong', serif;
}

/* 全局精简：隐藏说明性小字，保留核心输入信息 */
.cases-compact .section-block__hint,
.cases-compact .workspace-panel__desc,
.cases-compact .workspace-panel__badge,
.cases-compact .scene-editor-card__helper,
.cases-compact .supplement-toolbar__desc,
.cases-compact .source-panel__meta,
.cases-compact .preview-label,
.cases-compact .mode-card__desc,
.cases-compact .section-block__eyebrow,
.cases-compact .workspace-panel__eyebrow,
.cases-compact .review-module-nav__step,
.cases-compact .scene-editor-card__section-title,
.cases-compact p.mt-1.text-xs,
.cases-compact p.mt-2.text-xs,
.cases-compact p.text-xs,
.cases-compact .text-xs.text-slate-400 {
  display: none !important;
}

/* 视觉收敛：统一更简约的大卡片风格 */
.cases-compact .section-block,
.cases-compact .workspace-panel,
.cases-compact .scene-editor-card {
  border-color: #e2e8f0;
  border-radius: 18px;
  background: #ffffff;
  box-shadow: none;
}

@media (max-width: 960px) {
  .supplement-toolbar {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>
