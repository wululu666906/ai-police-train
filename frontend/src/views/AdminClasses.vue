<template>
  <div class="classroom-page">
    <header class="admin-list-header">
      <div>
        <h1>班级训练</h1>
        <p>以班级为边界发布训练作业、收集评估报告，并处理未交与补交流程。</p>
      </div>
      <div class="header-actions">
        <van-button plain class="!rounded-[6px] !border-slate-200 !text-slate-600" :loading="loadingClasses" @click="fetchClasses">
          刷新
        </van-button>
        <van-button type="primary" icon="plus" class="!rounded-[6px] !border-none !bg-[#1D3557]" @click="showClassPopup = true">
          创建班级
        </van-button>
      </div>
    </header>

    <section class="classroom-grid">
      <button
        v-for="item in classes"
        :key="item.id"
        type="button"
        class="class-card"
        :class="{ 'class-card--active': selectedClassId === item.id }"
        @click="selectClass(item.id)"
      >
        <div class="class-card__head">
          <strong>{{ item.name }}</strong>
          <span>邀请码 {{ item.invite_code }}</span>
        </div>
        <p>{{ item.description || '暂无班级说明' }}</p>
        <div class="class-card__stats">
          <span>{{ item.student_count || 0 }} 名学员</span>
          <span>{{ item.assignment_count || 0 }} 个作业</span>
          <span>全员禁言</span>
        </div>
      </button>
      <button v-if="!classes.length && !loadingClasses" type="button" class="class-card class-card--empty" @click="showClassPopup = true">
        <strong>创建第一个班级</strong>
        <p>班级创建后会自动生成邀请码，学员可通过邀请码加入。</p>
      </button>
    </section>

    <div v-if="loadingDetail" class="state-card">
      <el-skeleton :rows="7" animated />
    </div>

    <section v-else-if="classDetail" class="class-workspace">
      <div class="workspace-header">
        <div>
          <span class="workspace-kicker">班级空间</span>
          <h2>{{ classDetail.classroom.name }}</h2>
          <p>{{ classDetail.classroom.description || '该班级暂未填写说明。' }}</p>
        </div>
        <div class="invite-panel">
          <span>学员加入邀请码</span>
          <strong>{{ classDetail.classroom.invite_code }}</strong>
          <van-button plain size="small" class="!rounded-[6px] !border-slate-200 !text-slate-600" @click="copyInviteCode">
            复制
          </van-button>
        </div>
      </div>

      <div class="workspace-actions">
        <van-button plain icon="friends-o" class="!rounded-[6px] !border-slate-200 !text-slate-600" @click="showStudentPopup = true">
          添加学员
        </van-button>
        <van-button plain icon="volume-o" class="!rounded-[6px] !border-slate-200 !text-slate-600" @click="showAnnouncementPopup = true">
          发布通知
        </van-button>
        <van-button type="primary" icon="description" class="!rounded-[6px] !border-none !bg-[#1D3557]" @click="showAssignmentPopup = true">
          发布作业
        </van-button>
      </div>

      <el-tabs v-model="activeTab" class="workspace-tabs">
        <el-tab-pane label="学员名单" name="students" />
        <el-tab-pane label="作业任务" name="assignments" />
        <el-tab-pane label="作业评审区" name="review" />
        <el-tab-pane label="班级通知" name="announcements" />
      </el-tabs>

      <div v-if="activeTab === 'students'" class="panel-table-wrap">
        <table class="ops-table">
          <thead>
            <tr>
              <th>学员账号</th>
              <th>加入时间</th>
              <th>身份</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="student in classDetail.students" :key="student.id">
              <td><strong>{{ student.username }}</strong></td>
              <td>{{ formatDateTime(student.joined_at) }}</td>
              <td><van-tag type="primary" plain>学员</van-tag></td>
            </tr>
          </tbody>
        </table>
        <el-empty v-if="!classDetail.students.length" description="班级内暂无学员" />
      </div>

      <div v-if="activeTab === 'assignments'">
        <div class="assignment-filter-bar">
          <button
            v-for="item in assignmentFilterOptions"
            :key="item.key"
            type="button"
            :class="{ 'assignment-filter--active': assignmentFilter === item.key }"
            @click="assignmentFilter = item.key"
          >
            <span>{{ item.label }}</span>
            <strong>{{ item.count }}</strong>
          </button>
        </div>
        <div class="panel-table-wrap">
          <table class="ops-table">
            <thead>
              <tr>
                <th>作业名称</th>
                <th>指定训练内容</th>
                <th>状态</th>
                <th>截止时间</th>
                <th>补交</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="assignment in displayedAssignments" :key="assignment.id">
                <td>
                  <strong>{{ assignment.title }}</strong>
                  <p>{{ assignment.instructions || '暂无训练要求说明' }}</p>
                </td>
                <td>
                  <div class="tag-list">
                    <span v-for="scene in assignment.scenes || []" :key="scene.id">{{ scene.case_title }} / {{ scene.name }}</span>
                    <span v-if="!(assignment.scenes || []).length" v-for="caseItem in assignment.cases" :key="caseItem.id">{{ caseItem.title }}</span>
                  </div>
                </td>
                <td>
                  <van-tag :type="assignmentStatusType(assignment)" plain>
                    {{ assignmentStatusLabel(assignment) }}
                  </van-tag>
                </td>
                <td>{{ formatDateTime(assignment.due_at) }}</td>
                <td>
                  <van-tag :type="assignment.allow_late ? 'success' : 'default'" plain>
                    {{ assignment.allow_late ? '允许补交' : '按时截止' }}
                  </van-tag>
                </td>
                <td>
                  <div class="row-actions">
                    <button type="button" @click="openReview(assignment)">评审</button>
                    <button type="button" @click="draftAssignmentNotice(assignment)">通知</button>
                    <button type="button" @click="toggleAssignmentLate(assignment)">
                      {{ assignment.allow_late ? '关闭补交' : '允许补交' }}
                    </button>
                    <button type="button" @click="extendAssignmentDue(assignment)">延期</button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
          <el-empty v-if="!displayedAssignments.length" :description="assignmentEmptyDescription" />
        </div>
      </div>

      <div v-if="activeTab === 'review'" class="review-panel">
        <div class="review-toolbar">
          <label>
            <span>评审作业</span>
            <select v-model.number="selectedReviewAssignmentId" @change="fetchReview">
              <option :value="0">请选择作业</option>
              <option v-for="assignment in classDetail.assignments" :key="assignment.id" :value="assignment.id">
                {{ assignment.title }}
              </option>
            </select>
          </label>
          <div v-if="reviewData" class="review-summary">
            <span>已交 {{ reviewData.summary.submitted_count }}</span>
            <span>进行中 {{ reviewData.summary.in_progress_count }}</span>
            <span>未提交 {{ reviewData.summary.unsubmitted_count }}</span>
          </div>
          <div v-if="reviewData" class="review-notice-actions">
            <button type="button" :disabled="!pendingRows.length" @click="draftReviewNotice('start')">提醒开始</button>
            <button type="button" :disabled="!overdueRows.length" @click="draftReviewNotice('overdue')">催交/补交</button>
            <button type="button" :disabled="!lowScoreRows.length" @click="draftReviewNotice('remedial')">复训通知</button>
          </div>
        </div>

        <section v-if="reviewData" class="review-insights">
          <article v-for="item in reviewInsightCards" :key="item.label" class="review-insight-card" :class="item.tone">
            <span>{{ item.label }}</span>
            <strong>{{ item.value }}</strong>
            <p>{{ item.note }}</p>
          </article>
        </section>

        <section v-if="attentionRows.length" class="attention-panel">
          <div>
            <strong>需要优先处理</strong>
            <span>按逾期、未开始、低分和训练中断自动聚合</span>
          </div>
          <div class="attention-list">
            <button v-for="row in attentionRows" :key="row.student.id" type="button" @click="openSubmission(row)">
              <strong>{{ row.student.username }}</strong>
              <span>{{ attentionReason(row) }}</span>
            </button>
          </div>
        </section>

        <div v-if="reviewData" class="review-filter-bar">
          <button
            v-for="item in reviewFilterOptions"
            :key="item.key"
            type="button"
            :class="{ 'review-filter--active': reviewFilter === item.key }"
            @click="reviewFilter = item.key"
          >
            <span>{{ item.label }}</span>
            <strong>{{ item.count }}</strong>
          </button>
        </div>

        <div v-if="reviewData" class="bulk-action-bar">
          <span>当前筛选 {{ displayedReviewRows.length }} 人</span>
          <button type="button" :disabled="!displayedReviewRows.length || bulkUpdating" @click="bulkSetLate(true)">
            批量允许补交
          </button>
          <button type="button" :disabled="!displayedReviewRows.length || bulkUpdating" @click="bulkSetLate(false)">
            批量关闭补交
          </button>
          <button type="button" :disabled="!displayedReviewRows.length || bulkUpdating" @click="bulkExtendDue">
            批量延期
          </button>
          <button type="button" :disabled="!displayedReviewRows.length" @click="exportReviewCsv">
            导出 CSV
          </button>
          <button type="button" :disabled="!displayedReviewRows.length" @click="copyReviewSummary">
            复制摘要
          </button>
        </div>

        <div v-if="loadingReview" class="state-card state-card--flat">
          <el-skeleton :rows="6" animated />
        </div>
        <div v-else-if="reviewData" class="panel-table-wrap">
          <table class="ops-table review-table">
            <thead>
              <tr>
                <th>学员</th>
                <th>状态</th>
                <th>完成进度</th>
                <th>平均分</th>
                <th>最近提交</th>
                <th>补交策略</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in displayedReviewRows" :key="row.student.id">
                <td><strong>{{ row.student.username }}</strong></td>
                <td><van-tag :type="reviewStatusType(row.status)" plain>{{ reviewStatusLabel(row.status) }}</van-tag></td>
                <td>{{ row.completed_count }}/{{ row.required_count }}</td>
                <td class="score-cell">{{ row.score_avg ?? '--' }}</td>
                <td>{{ formatDateTime(row.last_submitted_at) }}</td>
                <td>
                  <span>{{ row.allow_late ? '可补交' : '不可补交' }}</span>
                  <small>截止 {{ formatDateTime(row.effective_due_at) }}</small>
                </td>
                <td>
                  <div class="row-actions">
                    <button type="button" :disabled="!firstSubmission(row)" @click="openSubmission(row)">查看</button>
                    <button type="button" @click="setStudentLate(row, true)">允许补交</button>
                    <button type="button" @click="setStudentLate(row, false)">拒绝补交</button>
                    <button type="button" @click="extendStudentDue(row)">延期</button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
          <el-empty v-if="!displayedReviewRows.length" :description="reviewEmptyDescription" />
        </div>
        <el-empty v-else description="请选择一个作业进入评审区" />
      </div>

      <div v-if="activeTab === 'announcements'" class="announcement-list">
        <article v-for="item in classDetail.announcements" :key="item.id" class="notice-item">
          <div>
            <strong>{{ item.title }}</strong>
            <span>{{ formatDateTime(item.created_at) }}</span>
          </div>
          <p>{{ item.content || '无正文' }}</p>
        </article>
        <el-empty v-if="!classDetail.announcements.length" description="暂无班级通知" />
      </div>
    </section>

    <van-popup v-model:show="showClassPopup" teleport="body" :style="popupStyle">
      <div class="popup-panel">
        <header>
          <h3>创建班级</h3>
          <van-icon name="cross" @click="showClassPopup = false" />
        </header>
        <label class="field-block">
          <span>班级名称</span>
          <input v-model.trim="classForm.name" type="text" placeholder="例如 2026 春季接警训练班" />
        </label>
        <label class="field-block">
          <span>班级说明</span>
          <textarea v-model.trim="classForm.description" rows="4" placeholder="说明训练对象、周期或教学安排" />
        </label>
        <van-button block type="primary" :loading="savingClass" class="!rounded-[6px] !border-none !bg-[#1D3557]" @click="createClass">
          创建
        </van-button>
      </div>
    </van-popup>

    <van-popup v-model:show="showStudentPopup" teleport="body" :style="{ ...popupStyle, width: 'min(680px, 96vw)' }">
      <div class="popup-panel popup-panel--student-import">
        <header>
          <h3>添加学员</h3>
          <van-icon name="cross" @click="showStudentPopup = false" />
        </header>
        <section class="student-import-section student-import-section--text">
          <label class="field-block">
            <span>学员账号</span>
            <textarea v-model.trim="studentForm.usernames" rows="4" placeholder="每行一个学员账号，例如 student001" />
          </label>
        </section>
        <section class="student-import-section student-import-section--file">
          <div class="student-import-head">
            <div>
              <strong>名单文件导入</strong>
              <span>支持 xlsx / csv，识别学号、username、账号、account 列；无表头时读取第一列。</span>
            </div>
            <button type="button" @click="downloadStudentImportTemplate">下载模板</button>
          </div>
          <input ref="studentFileInputRef" type="file" accept=".xlsx,.csv" class="hidden" @change="handleStudentFileChange" />
          <div
            class="student-file-dropzone"
            :class="{ 'student-file-dropzone--dragging': studentFileDragging, 'student-file-dropzone--ready': importedStudentUsernames.length }"
            tabindex="0"
            @click="chooseStudentFile"
            @dragover.prevent="studentFileDragging = true"
            @dragleave.prevent="studentFileDragging = false"
            @drop.prevent="handleStudentFileDrop"
            @paste="handleStudentFilePaste"
          >
            <van-icon name="description" size="34" />
            <strong>{{ studentImportFileName || '拖入名单文件，或点击上传' }}</strong>
            <span>也可以复制文件后在此区域粘贴上传</span>
            <small v-if="studentImportError">{{ studentImportError }}</small>
            <small v-else-if="importedStudentUsernames.length">
              已识别 {{ importedStudentUsernames.length }} 个账号，去重 {{ studentImportSummary.duplicateCount }} 个
            </small>
          </div>
          <div v-if="studentImportPreviewVisibleList.length" class="student-import-preview">
            <span v-for="item in studentImportPreviewVisibleList" :key="item">{{ item }}</span>
            <em v-if="studentImportPreviewHiddenCount">另有 {{ studentImportPreviewHiddenCount }} 个</em>
          </div>
          <label class="field-block">
            <span>导入初始密码</span>
            <input v-model.trim="studentImportForm.password" type="text" placeholder="新开通账号统一初始密码" />
          </label>
        </section>
        <van-button block type="primary" :loading="savingStudents" class="!rounded-[6px] !border-none !bg-[#1D3557]" @click="addStudents">
          添加到班级
        </van-button>
      </div>
    </van-popup>

    <van-popup v-model:show="showAnnouncementPopup" teleport="body" :style="popupStyle">
      <div class="popup-panel">
        <header>
          <h3>发布通知</h3>
          <van-icon name="cross" @click="showAnnouncementPopup = false" />
        </header>
        <label class="field-block">
          <span>标题</span>
          <input v-model.trim="announcementForm.title" type="text" placeholder="例如 第二次作业补交提醒" />
        </label>
        <label class="field-block">
          <span>内容</span>
          <textarea v-model.trim="announcementForm.content" rows="5" placeholder="通知内容仅管理员可发布，学员端只读展示。" />
        </label>
        <van-button block type="primary" :loading="savingAnnouncement" class="!rounded-[6px] !border-none !bg-[#1D3557]" @click="createAnnouncement">
          发布
        </van-button>
      </div>
    </van-popup>

    <van-popup v-model:show="showAssignmentPopup" teleport="body" :style="{ ...popupStyle, width: 'min(760px, 96vw)' }">
      <div class="popup-panel">
        <header>
          <h3>发布训练作业</h3>
          <van-icon name="cross" @click="showAssignmentPopup = false" />
        </header>
        <div class="form-grid">
          <label class="field-block">
            <span>作业名称</span>
            <input v-model.trim="assignmentForm.title" type="text" placeholder="例如 第三周接警专项训练" />
          </label>
          <label class="field-block">
            <span>截止时间</span>
            <input v-model="assignmentForm.dueAt" type="datetime-local" />
          </label>
        </div>
        <label class="checkline">
          <input v-model="assignmentForm.allowLate" type="checkbox" />
          允许截止后补交
        </label>
        <div class="field-block">
          <span>教学模板</span>
          <div class="template-picker">
            <button
              v-for="template in assignmentTemplates"
              :key="template.key"
              type="button"
              :class="{ 'template-option--active': assignmentForm.templateKey === template.key }"
              @click="applyAssignmentTemplate(template)"
            >
              <strong>{{ template.name }}</strong>
              <small>{{ template.goal }}</small>
            </button>
          </div>
        </div>
        <div class="form-grid form-grid--three">
          <label class="field-block">
            <span>训练目标</span>
            <input v-model.trim="assignmentForm.trainingGoal" type="text" placeholder="例如 主动问清关键信息并完成处置闭环" />
          </label>
          <label class="field-block">
            <span>通过分</span>
            <input v-model.number="assignmentForm.passScore" type="number" min="0" max="100" />
          </label>
          <label class="field-block">
            <span>必考命中率</span>
            <input v-model.number="assignmentForm.requiredRate" type="number" min="0" max="100" />
          </label>
        </div>
        <label class="field-block">
          <span>多次训练计分口径</span>
          <select v-model="assignmentForm.scoreStrategy">
            <option value="best">多次训练取最高分</option>
            <option value="latest">多次训练取最近一次</option>
            <option value="average">多次训练取平均分</option>
          </select>
        </label>
        <label class="field-block">
          <span>训练要求说明</span>
          <textarea v-model.trim="assignmentForm.instructions" rows="3" placeholder="写明训练重点、提交要求或复盘方向" />
        </label>
        <label class="field-block">
          <span>评分规则</span>
          <textarea v-model.trim="assignmentForm.scoringRule" rows="3" placeholder="默认使用系统 Adaptive V1 评估，也可补充自定义规则。" />
        </label>
        <div class="field-block">
          <span>选择训练内容</span>
          <div class="case-picker">
            <div v-for="caseItem in cases" :key="caseItem.id" class="case-option case-option--stack">
              <label class="case-option__head">
                <input
                  type="checkbox"
                  :checked="isCaseFullySelected(caseItem)"
                  :indeterminate.prop="isCasePartiallySelected(caseItem)"
                  @change="toggleCaseScenes(caseItem, isInputChecked($event))"
                />
                <strong>{{ caseItem.title }}</strong>
                <small>{{ caseItem.case_type || '未分类' }}</small>
              </label>
              <div class="scene-option-list">
                <label v-for="scene in caseScenes(caseItem)" :key="scene.id" class="scene-option">
                  <input v-model="assignmentForm.sceneIds" type="checkbox" :value="scene.id" @change="syncCaseSelectionFromScenes" />
                  <span>{{ scene.name }}</span>
                  <small>{{ scene.difficulty || '中等' }}</small>
                </label>
                <span v-if="!caseScenes(caseItem).length" class="scene-option-empty">该案件暂无可训练场景</span>
              </div>
            </div>
          </div>
        </div>
        <van-button block type="primary" :loading="savingAssignment" class="!rounded-[6px] !border-none !bg-[#1D3557]" @click="createAssignment">
          发布作业
        </van-button>
      </div>
    </van-popup>

    <van-popup v-model:show="showSubmissionPopup" teleport="body" :style="{ width: 'min(920px, 96vw)', maxHeight: '92vh', borderRadius: '12px', overflow: 'hidden' }">
      <div class="submission-panel">
        <header class="submission-panel__header">
          <div>
            <h3>提交详情</h3>
            <p v-if="submissionDetail">{{ submissionMetaText }}</p>
          </div>
          <div class="submission-panel__header-actions">
            <van-button
              v-if="hasEvaluationReport"
              plain
              size="small"
              class="!rounded-[6px] !border-slate-200 !text-slate-600"
              @click="showEvaluationPopup = true"
            >
              查看完整版
            </van-button>
            <van-icon name="cross" @click="closeSubmissionPopup" />
          </div>
        </header>
        <div v-if="loadingSubmission" class="state-card state-card--flat">
          <el-skeleton :rows="8" animated />
        </div>
        <div v-else-if="submissionDetail" class="submission-body">
          <aside class="submission-summary">
            <section class="submission-card submission-card--score">
              <div class="submission-card__head">
                <span>综合得分</span>
                <strong>{{ submissionSummary.totalScore }}</strong>
              </div>
              <div class="submission-score-meta">
                <span class="submission-score-meta__grade" :class="`grade-${submissionSummary.gradeClass}`">
                  {{ submissionSummary.gradeText }}
                </span>
                <span class="submission-score-meta__desc">{{ submissionSummary.scoreDesc }}</span>
              </div>
              <div class="submission-score-stats">
                <div>
                  <span>提交时间</span>
                  <strong>{{ formatDateTime(submissionDetail.submission.submitted_at) }}</strong>
                </div>
                <div>
                  <span>完成率</span>
                  <strong>{{ submissionSummary.assessmentRateText }}</strong>
                </div>
                <div>
                  <span>状态</span>
                  <strong>{{ reviewStatusLabel(submissionDetail.submission.status) }}</strong>
                </div>
              </div>
              <div class="submission-score-dimensions">
                <div v-for="item in displayedCommonReviewItems" :key="item.dimension" class="dimension-row">
                  <span>{{ item.dimension }}</span>
                  <strong>{{ item.score }}/{{ item.full_score }}</strong>
                </div>
              </div>
            </section>

            <section class="submission-card submission-card--points">
              <div class="submission-card__head">
                <span>考察点完成情况</span>
                <strong>{{ assessmentPointItems.length }} 项</strong>
              </div>
              <div class="assessment-list">
                <article v-for="item in assessmentPointItems" :key="assessmentPointKey(item)" class="assessment-list__item">
                  <div class="assessment-list__head">
                    <strong>{{ item.label || item.content || '未命名考察点' }}</strong>
                    <span class="status-pill" :class="`status-pill--${item.status}`">
                      {{ assessmentPointStatusLabel(item.status) }}
                    </span>
                  </div>
                  <div class="assessment-list__meta">
                    <span>{{ item.stage_name || '通用' }}</span>
                    <span>{{ assessmentCompletionLabel(item) }}</span>
                  </div>
                </article>
                <div v-if="!assessmentPointItems.length" class="submission-empty-inline">暂无考察点结果</div>
              </div>
            </section>

            <section class="submission-card submission-card--comment">
              <div class="submission-card__head">
                <span>综合点评</span>
                <van-button
                  v-if="commentHasMore"
                  plain
                  size="small"
                  class="!rounded-[6px] !border-slate-200 !text-slate-600"
                  @click="showEvaluationPopup = true"
                >
                  查看完整版
                </van-button>
              </div>
              <div class="comment-preview">
                <p v-for="(line, index) in commentPreviewLines" :key="`comment-${index}`">{{ line }}</p>
                <p v-if="!commentPreviewLines.length" class="submission-empty-inline">暂无综合点评</p>
                <button v-if="commentHasMore" type="button" class="link-button" @click="showEvaluationPopup = true">
                  展开查看完整内容
                </button>
              </div>
            </section>
          </aside>

          <main class="submission-dialogue">
            <div class="submission-dialogue__head">
              <div>
                <h4>对话记录</h4>
                <p>学员与 AI 角色完整对话记录，可滚动浏览全部训练过程。</p>
              </div>
              <div class="submission-dialogue__meta">
                <span>共 {{ submissionMessages.length }} 条</span>
                <span>{{ formatDateTime(submissionDetail.session.created_at) }}</span>
              </div>
            </div>

            <div class="dialogue-timeline">
              <div v-if="!submissionMessages.length" class="submission-empty-state">
                <van-icon name="chat-o" size="42" color="#cbd5e1" />
                <strong>暂无对话记录</strong>
                <span>当前提交没有可展示的聊天内容。</span>
              </div>

              <template v-for="(message, index) in submissionMessages" :key="message.key">
                <div v-if="shouldShowDateDivider(index)" class="timeline-divider">
                  <span>{{ formatDateDivider(message.createdAt) }}</span>
                </div>

                <article class="timeline-message" :class="`timeline-message--${message.displayRole}`">
                  <div class="timeline-message__avatar" :class="`timeline-message__avatar--${message.displayRole}`">
                    {{ getMessageAvatarText(message) }}
                  </div>
                  <div class="timeline-message__body">
                    <div class="timeline-message__head">
                      <strong>{{ message.speakerName }}</strong>
                      <time>{{ formatMessageClock(message.createdAt) }}</time>
                    </div>
                    <div class="timeline-message__label">{{ roleLabel(message.originalRole) }}</div>
                    <div class="timeline-message__bubble">{{ message.content }}</div>
                  </div>
                </article>
              </template>
            </div>
          </main>
        </div>
      </div>
    </van-popup>

    <van-popup v-model:show="showEvaluationPopup" teleport="body" :style="evaluationPopupStyle">
      <div class="evaluation-panel">
        <header class="evaluation-panel__header">
          <div>
            <h3>综合点评完整版</h3>
            <p v-if="submissionDetail">{{ submissionMetaText }}</p>
          </div>
          <van-icon name="cross" @click="showEvaluationPopup = false" />
        </header>

        <div class="evaluation-panel__summary">
          <div>
            <span>总分</span>
            <strong>{{ submissionSummary.totalScore }}</strong>
          </div>
          <div>
            <span>等级</span>
            <strong>{{ submissionSummary.gradeText }}</strong>
          </div>
          <div>
            <span>考察点</span>
            <strong>{{ assessmentPointItems.length }}</strong>
          </div>
          <div>
            <span>完成率</span>
            <strong>{{ submissionSummary.assessmentRateText }}</strong>
          </div>
        </div>

        <div class="evaluation-panel__body">
          <section class="evaluation-panel__block">
            <h4>完整点评</h4>
            <p v-for="(line, index) in commentLines" :key="`full-comment-${index}`">{{ line }}</p>
            <p v-if="!commentLines.length">暂无点评内容</p>
          </section>
          <section class="evaluation-panel__block">
            <h4>亮点与不足</h4>
            <div class="evaluation-panel__columns">
              <div>
                <span>亮点</span>
                <p v-if="strengthItems.length">{{ strengthItems.join('；') }}</p>
                <p v-else>暂无亮点摘要</p>
              </div>
              <div>
                <span>不足</span>
                <p v-if="improvementItems.length">{{ improvementItems.join('；') }}</p>
                <p v-else>暂无不足摘要</p>
              </div>
              <div>
                <span>建议</span>
                <p>{{ suggestionText || '暂无复训建议' }}</p>
              </div>
            </div>
          </section>
        </div>
      </div>
    </van-popup>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { showToast } from 'vant'
import * as XLSX from 'xlsx'
import request from '../utils/request'
import { isInternalPromptMessage } from '../utils/dialogueMessage'

const classes = ref<any[]>([])
const cases = ref<any[]>([])
const classDetail = ref<any>(null)
const reviewData = ref<any>(null)
const submissionDetail = ref<any>(null)
const selectedClassId = ref<number | null>(null)
const selectedReviewAssignmentId = ref(0)
const activeTab = ref<'students' | 'assignments' | 'review' | 'announcements'>('students')
const assignmentFilter = ref<'all' | 'active' | 'overdue' | 'late_allowed' | 'closed'>('all')
const reviewFilter = ref<'all' | 'attention' | 'pending' | 'in_progress' | 'unsubmitted' | 'low_score' | 'submitted'>('all')

const loadingClasses = ref(false)
const loadingDetail = ref(false)
const loadingReview = ref(false)
const loadingSubmission = ref(false)
const bulkUpdating = ref(false)
const savingClass = ref(false)
const savingStudents = ref(false)
const savingAnnouncement = ref(false)
const savingAssignment = ref(false)
const studentFileInputRef = ref<HTMLInputElement | null>(null)
const studentFileDragging = ref(false)
const studentImportFileName = ref('')
const importedStudentUsernames = ref<string[]>([])
const studentImportError = ref('')
const studentImportPreviewLimit = 12

const showClassPopup = ref(false)
const showStudentPopup = ref(false)
const showAnnouncementPopup = ref(false)
const showAssignmentPopup = ref(false)
const showSubmissionPopup = ref(false)
const showEvaluationPopup = ref(false)

const classForm = reactive({ name: '', description: '' })
const studentForm = reactive({ usernames: '' })
const studentImportForm = reactive({ password: '123456' })
const studentImportSummary = reactive({
  totalRows: 0,
  validCount: 0,
  duplicateCount: 0,
})
const announcementForm = reactive({ title: '', content: '' })
const assignmentForm = reactive({
  title: '',
  caseIds: [] as number[],
  sceneIds: [] as number[],
  dueAt: '',
  templateKey: '',
  trainingGoal: '',
  passScore: 60,
  requiredRate: 70,
  scoreStrategy: 'best',
  instructions: '',
  scoringRule: '系统默认评分；系统完成对话记录归档与 Adaptive V1 评估。',
  allowLate: false,
})

const assignmentTemplates = [
  {
    key: 'inquiry',
    name: '信息采集专项',
    goal: '问清时间、地点、人物、经过和风险',
    instructions: '训练重点：主动核实报警人身份、事件发生时间地点、涉事人员关系、现场风险和当前诉求。提交要求：完成全部关联案件训练并生成评估报告。',
    scoringRule: '重点关注主动询问与逻辑推进、关键信息获取、必考点命中情况。',
  },
  {
    key: 'deescalation',
    name: '情绪安抚专项',
    goal: '先稳住情绪，再推进事实核查',
    instructions: '训练重点：面对情绪激动或抵触对象时，先降低对抗感，再逐步核实事实、风险和诉求。提交要求：完成全部关联案件训练并生成评估报告。',
    scoringRule: '重点关注沟通表达与执法语言、情绪安抚、冲突降温和处置推进。',
  },
  {
    key: 'closure',
    name: '处置闭环专项',
    goal: '补齐取证、告知、收尾和后续安排',
    instructions: '训练重点：在掌握基本事实后，体现证据意识、风险判断、处置告知和收尾确认。提交要求：完成全部关联案件训练并生成评估报告。',
    scoringRule: '重点关注证据固定、现场动作、后续处置安排和闭环表达。',
  },
]

const popupStyle = {
  width: 'min(560px, 96vw)',
  borderRadius: '12px',
  overflow: 'hidden',
}

const evaluationPopupStyle = {
  width: 'min(760px, 96vw)',
  maxHeight: '88vh',
  borderRadius: '12px',
  overflow: 'hidden',
}

const selectedClass = computed(() => classes.value.find((item) => item.id === selectedClassId.value))
const studentImportPreviewVisibleList = computed(() => importedStudentUsernames.value.slice(0, studentImportPreviewLimit))
const studentImportPreviewHiddenCount = computed(() =>
  Math.max(importedStudentUsernames.value.length - studentImportPreviewVisibleList.value.length, 0),
)

const assignmentRows = computed(() => Array.isArray(classDetail.value?.assignments) ? classDetail.value.assignments : [])

const caseScenes = (caseItem: any) => Array.isArray(caseItem?.scenes) ? caseItem.scenes : []

const selectedSceneIdSet = computed(() => new Set(assignmentForm.sceneIds.map((id) => Number(id))))

const isInputChecked = (event: Event) => Boolean((event.target as HTMLInputElement | null)?.checked)

const isCaseFullySelected = (caseItem: any) => {
  const scenes = caseScenes(caseItem)
  return scenes.length > 0 && scenes.every((scene: any) => selectedSceneIdSet.value.has(Number(scene.id)))
}

const isCasePartiallySelected = (caseItem: any) => {
  const scenes = caseScenes(caseItem)
  if (!scenes.length) return false
  const selectedCount = scenes.filter((scene: any) => selectedSceneIdSet.value.has(Number(scene.id))).length
  return selectedCount > 0 && selectedCount < scenes.length
}

const syncCaseSelectionFromScenes = () => {
  const selectedCaseIds = new Set<number>()
  for (const caseItem of cases.value) {
    if (caseScenes(caseItem).some((scene: any) => selectedSceneIdSet.value.has(Number(scene.id)))) {
      selectedCaseIds.add(Number(caseItem.id))
    }
  }
  assignmentForm.caseIds = Array.from(selectedCaseIds)
}

const toggleCaseScenes = (caseItem: any, checked: boolean) => {
  const next = new Set(assignmentForm.sceneIds.map((id) => Number(id)))
  for (const scene of caseScenes(caseItem)) {
    const sceneId = Number(scene.id)
    if (!sceneId) continue
    if (checked) next.add(sceneId)
    else next.delete(sceneId)
  }
  assignmentForm.sceneIds = Array.from(next)
  syncCaseSelectionFromScenes()
}

const assignmentDueState = (assignment: any) => {
  if (!assignment?.due_at) return 'active'
  const due = new Date(assignment.due_at).getTime()
  if (Number.isNaN(due)) return 'active'
  return due < Date.now() ? 'overdue' : 'active'
}

const assignmentStatusLabel = (assignment: any) => {
  if (assignment.allow_late && assignmentDueState(assignment) === 'overdue') return '补交中'
  if (assignmentDueState(assignment) === 'overdue') return '已截止'
  if (assignment.status && assignment.status !== 'published') return String(assignment.status)
  return '进行中'
}

const assignmentStatusType = (assignment: any) => {
  if (assignment.allow_late && assignmentDueState(assignment) === 'overdue') return 'warning'
  if (assignmentDueState(assignment) === 'overdue') return 'danger'
  return 'primary'
}

const displayedAssignments = computed(() => {
  if (assignmentFilter.value === 'active') return assignmentRows.value.filter((item: any) => assignmentDueState(item) === 'active')
  if (assignmentFilter.value === 'overdue') return assignmentRows.value.filter((item: any) => assignmentDueState(item) === 'overdue')
  if (assignmentFilter.value === 'late_allowed') return assignmentRows.value.filter((item: any) => item.allow_late)
  if (assignmentFilter.value === 'closed') return assignmentRows.value.filter((item: any) => assignmentDueState(item) === 'overdue' && !item.allow_late)
  return assignmentRows.value
})

const assignmentFilterOptions = computed(() => [
  { key: 'all' as const, label: '全部', count: assignmentRows.value.length },
  { key: 'active' as const, label: '进行中', count: assignmentRows.value.filter((item: any) => assignmentDueState(item) === 'active').length },
  { key: 'overdue' as const, label: '已截止', count: assignmentRows.value.filter((item: any) => assignmentDueState(item) === 'overdue').length },
  { key: 'late_allowed' as const, label: '允许补交', count: assignmentRows.value.filter((item: any) => item.allow_late).length },
  { key: 'closed' as const, label: '不可补交', count: assignmentRows.value.filter((item: any) => assignmentDueState(item) === 'overdue' && !item.allow_late).length },
])

const assignmentEmptyDescription = computed(() => {
  const option = assignmentFilterOptions.value.find((item) => item.key === assignmentFilter.value)
  return option ? `当前没有“${option.label}”作业` : '暂无作业任务'
})

const reviewRows = computed(() => Array.isArray(reviewData.value?.rows) ? reviewData.value.rows : [])

const reviewScoreRows = computed(() =>
  reviewRows.value.filter((row: any) => Number.isFinite(Number(row.score_avg))),
)

const reviewAverageScore = computed(() => {
  if (!reviewScoreRows.value.length) return null
  const total = reviewScoreRows.value.reduce((sum: number, row: any) => sum + Number(row.score_avg), 0)
  return Math.round((total / reviewScoreRows.value.length) * 10) / 10
})

const reviewCompletionRate = computed(() => {
  const total = Number(reviewData.value?.summary?.student_count || reviewRows.value.length || 0)
  if (!total) return 0
  const submitted = Number(reviewData.value?.summary?.submitted_count || 0)
  return Math.round((submitted / total) * 100)
})

const lowScoreRows = computed(() =>
  reviewScoreRows.value.filter((row: any) => Number(row.score_avg) < 60),
)

const pendingRows = computed(() =>
  reviewRows.value.filter((row: any) => row.status === 'pending'),
)

const overdueRows = computed(() =>
  reviewRows.value.filter((row: any) => row.status === 'unsubmitted' || row.status === 'in_progress'),
)

const submittedRows = computed(() =>
  reviewRows.value.filter((row: any) => row.status === 'submitted' || row.status === 'late'),
)

const attentionRows = computed(() =>
  reviewRows.value
    .filter((row: any) =>
      row.status === 'unsubmitted' ||
      row.status === 'pending' ||
      row.status === 'in_progress' ||
      Number(row.score_avg) < 60,
    )
    .sort((left: any, right: any) => attentionWeight(right) - attentionWeight(left))
    .slice(0, 6),
)

const attentionWeight = (row: any) => {
  if (row.status === 'unsubmitted') return 4
  if (Number(row.score_avg) < 60) return 3
  if (row.status === 'in_progress') return 2
  if (row.status === 'pending') return 1
  return 0
}

const attentionReason = (row: any) => {
  if (row.status === 'unsubmitted') return row.allow_late ? '已逾期，可考虑单独催交或延长期限' : '已逾期且不可补交，需确认是否开放补交'
  if (Number(row.score_avg) < 60) return `平均分 ${row.score_avg}，建议安排补练或点评`
  if (row.status === 'in_progress') return '已有训练记录但未完成提交，可提醒继续训练'
  if (row.status === 'pending') return '尚未开始，可发送开始训练提醒'
  return '建议关注'
}

const reviewInsightCards = computed(() => {
  const summary = reviewData.value?.summary || {}
  const studentCount = Number(summary.student_count || reviewRows.value.length || 0)
  const pendingTotal = Number(summary.pending_count || 0) + Number(summary.in_progress_count || 0)
  return [
    {
      label: '提交完成率',
      value: `${reviewCompletionRate.value}%`,
      note: `${summary.submitted_count || 0}/${studentCount || 0} 名学员已完成`,
      tone: reviewCompletionRate.value >= 80 ? 'is-good' : reviewCompletionRate.value >= 50 ? 'is-warn' : 'is-danger',
    },
    {
      label: '班级平均分',
      value: reviewAverageScore.value === null ? '--' : `${reviewAverageScore.value}`,
      note: reviewAverageScore.value === null ? '暂无可统计成绩' : `${reviewScoreRows.value.length} 名学员已有成绩`,
      tone: reviewAverageScore.value === null || reviewAverageScore.value >= 75 ? 'is-good' : reviewAverageScore.value >= 60 ? 'is-warn' : 'is-danger',
    },
    {
      label: '低于通过线',
      value: `${lowScoreRows.value.length}`,
      note: '建议优先查看报告并布置补练',
      tone: lowScoreRows.value.length ? 'is-danger' : 'is-good',
    },
    {
      label: '待推进人数',
      value: `${pendingTotal}`,
      note: '包含待开始与训练中未提交',
      tone: pendingTotal ? 'is-warn' : 'is-good',
    },
  ]
})

const selectedReviewAssignment = computed(() => reviewData.value?.assignment || classDetail.value?.assignments?.find((item: any) => item.id === selectedReviewAssignmentId.value))

const isAttentionRow = (row: any) =>
  row.status === 'unsubmitted' ||
  row.status === 'pending' ||
  row.status === 'in_progress' ||
  Number(row.score_avg) < 60

const displayedReviewRows = computed(() => {
  if (reviewFilter.value === 'attention') return reviewRows.value.filter(isAttentionRow)
  if (reviewFilter.value === 'pending') return pendingRows.value
  if (reviewFilter.value === 'in_progress') return reviewRows.value.filter((row: any) => row.status === 'in_progress')
  if (reviewFilter.value === 'unsubmitted') return reviewRows.value.filter((row: any) => row.status === 'unsubmitted')
  if (reviewFilter.value === 'low_score') return lowScoreRows.value
  if (reviewFilter.value === 'submitted') return submittedRows.value
  return reviewRows.value
})

const reviewFilterOptions = computed(() => [
  { key: 'all' as const, label: '全部', count: reviewRows.value.length },
  { key: 'attention' as const, label: '需处理', count: reviewRows.value.filter(isAttentionRow).length },
  { key: 'pending' as const, label: '未开始', count: pendingRows.value.length },
  { key: 'in_progress' as const, label: '训练中', count: reviewRows.value.filter((row: any) => row.status === 'in_progress').length },
  { key: 'unsubmitted' as const, label: '未提交', count: reviewRows.value.filter((row: any) => row.status === 'unsubmitted').length },
  { key: 'low_score' as const, label: '低分', count: lowScoreRows.value.length },
  { key: 'submitted' as const, label: '已提交', count: submittedRows.value.length },
])

const reviewEmptyDescription = computed(() => {
  const option = reviewFilterOptions.value.find((item) => item.key === reviewFilter.value)
  return option ? `当前没有“${option.label}”学员` : '当前作业暂无可评审学员'
})

const studentNamesText = (rows: any[]) => {
  const names = rows.map((row: any) => row?.student?.username).filter(Boolean)
  if (!names.length) return '相关学员'
  if (names.length <= 8) return names.join('、')
  return `${names.slice(0, 8).join('、')} 等 ${names.length} 名学员`
}

const draftReviewNotice = (kind: 'start' | 'overdue' | 'remedial') => {
  const assignment = selectedReviewAssignment.value || {}
  const title = assignment.title || '班级训练作业'
  const dueText = formatDateTime(assignment.due_at)
  if (kind === 'start') {
    announcementForm.title = `${title} 开始训练提醒`
    announcementForm.content = [
      `${studentNamesText(pendingRows.value)}：请尽快进入“班级作业”完成《${title}》。`,
      `本次作业截止时间：${dueText}。请按作业卡片中的完成标准完成全部关联案件训练，并确认已生成评估报告。`,
    ].join('\n')
  } else if (kind === 'overdue') {
    announcementForm.title = `${title} 提交进度提醒`
    announcementForm.content = [
      `${studentNamesText(overdueRows.value)}：系统显示你们仍有《${title}》未完成提交或仍处于训练中。`,
      `请在截止时间 ${dueText} 前完成；如已逾期，请关注教官是否开放补交，并尽快补齐训练报告。`,
    ].join('\n')
  } else {
    announcementForm.title = `${title} 复训提醒`
    announcementForm.content = [
      `${studentNamesText(lowScoreRows.value)}：你们在《${title}》中的成绩低于通过线，建议查看评估报告中的薄弱项后重新训练。`,
      '复训重点：优先补齐未命中考察点，训练结束前完成事实复述、风险判断和后续处置安排。',
    ].join('\n')
  }
  showAnnouncementPopup.value = true
}

const fetchClasses = async () => {
  loadingClasses.value = true
  try {
    const res: any = await request.get('/classes')
    classes.value = Array.isArray(res) ? res : []
    if (!selectedClassId.value && classes.value.length) {
      selectedClassId.value = classes.value[0].id
      await fetchClassDetail()
    } else if (selectedClassId.value) {
      await fetchClassDetail()
    }
  } finally {
    loadingClasses.value = false
  }
}

const fetchCases = async () => {
  try {
    const res: any = await request.get('/cases/', { _skipErrorToast: true } as any)
    cases.value = Array.isArray(res) ? res : []
  } catch (bulkError) {
    // Assignment creation needs titles and scene ids only. The compact endpoint
    // avoids reverse proxies truncating large case bodies during page startup.
    console.warn('Bulk case list failed, retrying with summaries:', bulkError)
    const summaries: any = await request.get('/cases/role-case-options', { _skipErrorToast: true } as any)
    cases.value = Array.isArray(summaries) ? summaries : []
  }
}

const selectClass = async (classId: number) => {
  selectedClassId.value = classId
  reviewData.value = null
  selectedReviewAssignmentId.value = 0
  await fetchClassDetail()
}

const fetchClassDetail = async () => {
  if (!selectedClassId.value) return
  loadingDetail.value = true
  try {
    classDetail.value = await request.get(`/classes/${selectedClassId.value}`)
  } finally {
    loadingDetail.value = false
  }
}

const createClass = async () => {
  if (!classForm.name.trim()) {
    showToast('请输入班级名称')
    return
  }
  savingClass.value = true
  try {
    const res: any = await request.post('/classes', {
      name: classForm.name.trim(),
      description: classForm.description.trim(),
    })
    showToast({ type: 'success', message: '班级已创建' })
    classForm.name = ''
    classForm.description = ''
    showClassPopup.value = false
    await fetchClasses()
    selectedClassId.value = res.id
    await fetchClassDetail()
  } finally {
    savingClass.value = false
  }
}

const parseStudentTextUsernames = () =>
  studentForm.usernames
    .split(/[\r\n,，]+/)
    .map((item) => item.trim())
    .filter(Boolean)

const resetStudentImportSummary = () => {
  studentImportSummary.totalRows = 0
  studentImportSummary.validCount = 0
  studentImportSummary.duplicateCount = 0
}

const normalizeImportedStudentUsernames = (rows: any[][]) => {
  if (!rows.length) {
    resetStudentImportSummary()
    return []
  }
  const firstRow = rows[0].map((cell) => String(cell ?? '').trim())
  const normalizedHeaderRow = firstRow.map((item) => item.toLowerCase())
  const headerIndex = normalizedHeaderRow.findIndex((item) => ['学号', '学生', 'username', '账号', 'account'].includes(item))
  const dataRows = headerIndex >= 0 ? rows.slice(1) : rows
  const targetIndex = headerIndex >= 0 ? headerIndex : 0
  const usernames = dataRows.map((row) => String(row?.[targetIndex] ?? '').trim()).filter(Boolean)
  const uniqueUsernames = Array.from(new Set(usernames))
  studentImportSummary.totalRows = dataRows.length
  studentImportSummary.validCount = usernames.length
  studentImportSummary.duplicateCount = usernames.length - uniqueUsernames.length
  return uniqueUsernames
}

const parseStudentImportFile = async (file: File) => {
  const lowerName = file.name.toLowerCase()
  if (!lowerName.endsWith('.xlsx') && !lowerName.endsWith('.csv')) {
    studentImportError.value = '仅支持 xlsx 或 csv 名单文件'
    importedStudentUsernames.value = []
    resetStudentImportSummary()
    return
  }
  studentImportFileName.value = file.name
  studentImportError.value = ''
  try {
    const buffer = await file.arrayBuffer()
    const workbook = XLSX.read(buffer, { type: 'array' })
    const firstSheetName = workbook.SheetNames[0]
    const firstSheet = workbook.Sheets[firstSheetName]
    const rows = XLSX.utils.sheet_to_json(firstSheet, { header: 1, raw: false }) as any[][]
    const usernames = normalizeImportedStudentUsernames(rows)
    if (!usernames.length) {
      studentImportError.value = '未从文件中识别到有效账号，请检查表头或第一列内容'
      importedStudentUsernames.value = []
      return
    }
    importedStudentUsernames.value = usernames
  } catch {
    studentImportError.value = '文件解析失败，请使用 xlsx 或 csv 格式'
    importedStudentUsernames.value = []
    resetStudentImportSummary()
  }
}

const chooseStudentFile = () => studentFileInputRef.value?.click()

const handleStudentFileChange = async (event: Event) => {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (file) await parseStudentImportFile(file)
  input.value = ''
}

const handleStudentFileDrop = async (event: DragEvent) => {
  studentFileDragging.value = false
  const file = event.dataTransfer?.files?.[0]
  if (file) await parseStudentImportFile(file)
}

const handleStudentFilePaste = async (event: ClipboardEvent) => {
  const files = Array.from(event.clipboardData?.files || [])
  const file = files[0]
  if (!file) return
  event.preventDefault()
  await parseStudentImportFile(file)
}

const downloadStudentImportTemplate = () => {
  const rows = [
    ['学号'],
    ['student001'],
    ['student002'],
  ]
  const csv = rows.map((row) => row.map((cell) => `"${String(cell).replace(/"/g, '""')}"`).join(',')).join('\n')
  const blob = new Blob(['\ufeff' + csv], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = 'class-student-import-template.csv'
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}

const addStudents = async () => {
  if (!selectedClassId.value) return
  const textUsernames = parseStudentTextUsernames()
  const fileUsernames = importedStudentUsernames.value
  const usernames = Array.from(new Set([...textUsernames, ...fileUsernames]))
  if (!usernames.length) {
    showToast('请输入学员账号')
    return
  }
  if (fileUsernames.length && !studentImportForm.password.trim()) {
    showToast('请输入导入初始密码')
    return
  }
  savingStudents.value = true
  try {
    if (fileUsernames.length) {
      await request.post('/auth/students/import', {
        usernames: fileUsernames,
        password: studentImportForm.password.trim(),
      })
    }
    const res: any = await request.post(`/classes/${selectedClassId.value}/students`, { usernames })
    const createdHint = fileUsernames.length ? `，名单 ${fileUsernames.length} 个已开户或跳过已有账号` : ''
    showToast({ type: 'success', message: `已匹配 ${res.matched_count || 0} 名学员${createdHint}` })
    studentForm.usernames = ''
    studentImportFileName.value = ''
    importedStudentUsernames.value = []
    studentImportError.value = ''
    resetStudentImportSummary()
    showStudentPopup.value = false
    await fetchClassDetail()
  } finally {
    savingStudents.value = false
  }
}

const createAnnouncement = async () => {
  if (!selectedClassId.value) return
  if (!announcementForm.title.trim()) {
    showToast('请输入通知标题')
    return
  }
  savingAnnouncement.value = true
  try {
    await request.post(`/classes/${selectedClassId.value}/announcements`, {
      title: announcementForm.title.trim(),
      content: announcementForm.content.trim(),
      category: 'notice',
    })
    showToast({ type: 'success', message: '通知已发布' })
    announcementForm.title = ''
    announcementForm.content = ''
    showAnnouncementPopup.value = false
    await fetchClassDetail()
  } finally {
    savingAnnouncement.value = false
  }
}

const draftAssignmentNotice = (assignment: any) => {
  const title = assignment?.title || '班级训练作业'
  const dueText = formatDateTime(assignment?.due_at)
  const status = assignmentStatusLabel(assignment)
  announcementForm.title = `${title} ${status === '进行中' ? '训练提醒' : status === '补交中' ? '补交提醒' : '复盘安排'}`
  if (status === '进行中') {
    announcementForm.content = [
      `请各位学员按时完成《${title}》。`,
      `截止时间：${dueText}。请进入“班级作业”查看完成标准，完成全部关联案件训练并生成评估报告。`,
    ].join('\n')
  } else if (status === '补交中') {
    announcementForm.content = [
      `《${title}》已过原截止时间，目前仍开放补交。`,
      '尚未完成或报告未生成的学员，请尽快补齐训练记录；已完成的学员请查看评估报告，准备后续复盘。',
    ].join('\n')
  } else {
    announcementForm.content = [
      `《${title}》已截止。`,
      '请已完成的学员查看评估报告，重点复盘未命中考察点、低分能力项和后续改进建议；未完成学员请等待教官后续安排。',
    ].join('\n')
  }
  showAnnouncementPopup.value = true
}

const scoreStrategyLabel = (value: string) => {
  const map: Record<string, string> = {
    best: '多次训练取最高分',
    latest: '多次训练取最近一次',
    average: '多次训练取平均分',
  }
  return map[value] || '多次训练取最高分'
}

const applyAssignmentTemplate = (template: any) => {
  assignmentForm.templateKey = template.key
  assignmentForm.trainingGoal = template.goal
  assignmentForm.instructions = template.instructions
  assignmentForm.scoringRule = template.scoringRule
}

const buildAssignmentInstructions = () => {
  const parts = [
    assignmentForm.trainingGoal ? `训练目标：${assignmentForm.trainingGoal}` : '',
    assignmentForm.instructions.trim(),
  ].filter(Boolean)
  return parts.join('\n')
}

const buildAssignmentScoringRule = () => {
  const ruleLines = [
    `达标规则：总分不低于 ${Number(assignmentForm.passScore || 0)} 分，必考点命中率不低于 ${Number(assignmentForm.requiredRate || 0)}%。`,
    `计分口径：${scoreStrategyLabel(assignmentForm.scoreStrategy)}。`,
    assignmentForm.scoringRule.trim(),
  ].filter(Boolean)
  return ruleLines.join('\n')
}

const resetAssignmentForm = () => {
  assignmentForm.title = ''
  assignmentForm.caseIds = []
  assignmentForm.sceneIds = []
  assignmentForm.dueAt = ''
  assignmentForm.templateKey = ''
  assignmentForm.trainingGoal = ''
  assignmentForm.passScore = 60
  assignmentForm.requiredRate = 70
  assignmentForm.scoreStrategy = 'best'
  assignmentForm.instructions = ''
  assignmentForm.scoringRule = '系统默认评分；系统完成对话记录归档与 Adaptive V1 评估。'
  assignmentForm.allowLate = false
}

const createAssignment = async () => {
  if (!selectedClassId.value) return
  if (!assignmentForm.title.trim()) {
    showToast('请输入作业名称')
    return
  }
  if (!assignmentForm.sceneIds.length) {
    showToast('请选择训练场景')
    return
  }
  savingAssignment.value = true
  try {
    const res: any = await request.post(`/classes/${selectedClassId.value}/assignments`, {
      title: assignmentForm.title.trim(),
      case_ids: assignmentForm.caseIds,
      scene_ids: assignmentForm.sceneIds,
      due_at: assignmentForm.dueAt || null,
      instructions: buildAssignmentInstructions(),
      scoring_rule: buildAssignmentScoringRule(),
      allow_late: assignmentForm.allowLate,
    })
    showToast({ type: 'success', message: '作业已发布' })
    resetAssignmentForm()
    showAssignmentPopup.value = false
    await fetchClassDetail()
    openReview(res)
  } finally {
    savingAssignment.value = false
  }
}

const openReview = async (assignment: any) => {
  activeTab.value = 'review'
  selectedReviewAssignmentId.value = Number(assignment.id)
  await fetchReview()
}

const fetchReview = async () => {
  if (!selectedClassId.value || !selectedReviewAssignmentId.value) {
    reviewData.value = null
    return
  }
  reviewFilter.value = 'all'
  loadingReview.value = true
  try {
    reviewData.value = await request.get(`/classes/${selectedClassId.value}/assignments/${selectedReviewAssignmentId.value}/review`)
  } finally {
    loadingReview.value = false
  }
}

const updateAssignmentPolicy = async (assignment: any, payload: Record<string, unknown>) => {
  if (!selectedClassId.value) return
  await request.post(`/classes/${selectedClassId.value}/assignments/${assignment.id}/late-policy`, payload)
  showToast({ type: 'success', message: '作业策略已更新' })
  await fetchClassDetail()
  if (selectedReviewAssignmentId.value === assignment.id) await fetchReview()
}

const toggleAssignmentLate = async (assignment: any) => {
  await updateAssignmentPolicy(assignment, { allow_late: !assignment.allow_late })
}

const extendAssignmentDue = async (assignment: any) => {
  const value = window.prompt('请输入新的全班截止时间（格式：2026-06-30T18:00）', toDatetimeInput(assignment.due_at))
  if (value === null) return
  await updateAssignmentPolicy(assignment, { due_at: value || null })
}

const setStudentLate = async (row: any, allowLate: boolean) => {
  if (!selectedClassId.value || !selectedReviewAssignmentId.value) return
  await request.post(`/classes/${selectedClassId.value}/assignments/${selectedReviewAssignmentId.value}/students/${row.student.id}/override`, {
    allow_late: allowLate,
  })
  showToast({ type: 'success', message: allowLate ? '已允许该学员补交' : '已拒绝该学员补交' })
  await fetchReview()
}

const extendStudentDue = async (row: any) => {
  if (!selectedClassId.value || !selectedReviewAssignmentId.value) return
  const value = window.prompt('请输入该学员新的截止时间（格式：2026-06-30T18:00）', toDatetimeInput(row.effective_due_at))
  if (value === null) return
  await request.post(`/classes/${selectedClassId.value}/assignments/${selectedReviewAssignmentId.value}/students/${row.student.id}/override`, {
    due_at: value || null,
    allow_late: true,
  })
  showToast({ type: 'success', message: '已更新该学员截止时间' })
  await fetchReview()
}

const bulkSetLate = async (allowLate: boolean) => {
  if (!selectedClassId.value || !selectedReviewAssignmentId.value || !displayedReviewRows.value.length) return
  const label = allowLate ? '允许补交' : '关闭补交'
  const ok = window.confirm(`确定对当前筛选的 ${displayedReviewRows.value.length} 名学员批量${label}吗？`)
  if (!ok) return
  bulkUpdating.value = true
  try {
    await Promise.all(displayedReviewRows.value.map((row: any) =>
      request.post(`/classes/${selectedClassId.value}/assignments/${selectedReviewAssignmentId.value}/students/${row.student.id}/override`, {
        allow_late: allowLate,
      }),
    ))
    showToast({ type: 'success', message: `已批量${label}` })
    await fetchReview()
  } finally {
    bulkUpdating.value = false
  }
}

const bulkExtendDue = async () => {
  if (!selectedClassId.value || !selectedReviewAssignmentId.value || !displayedReviewRows.value.length) return
  const value = window.prompt('请输入当前筛选学员的新截止时间（格式：2026-06-30T18:00）')
  if (value === null) return
  bulkUpdating.value = true
  try {
    await Promise.all(displayedReviewRows.value.map((row: any) =>
      request.post(`/classes/${selectedClassId.value}/assignments/${selectedReviewAssignmentId.value}/students/${row.student.id}/override`, {
        due_at: value || null,
        allow_late: true,
      }),
    ))
    showToast({ type: 'success', message: '已批量更新截止时间' })
    await fetchReview()
  } finally {
    bulkUpdating.value = false
  }
}

const csvCell = (value: any) => {
  const text = String(value ?? '').replace(/\r?\n/g, ' ').trim()
  return `"${text.replace(/"/g, '""')}"`
}

const reviewFilterLabel = computed(() =>
  reviewFilterOptions.value.find((item) => item.key === reviewFilter.value)?.label || '全部',
)

const reviewExportRows = computed(() =>
  displayedReviewRows.value.map((row: any) => ({
    student: row.student?.username || '',
    status: reviewStatusLabel(row.status),
    progress: `${row.completed_count || 0}/${row.required_count || 0}`,
    score: row.score_avg ?? '',
    lastSubmittedAt: formatDateTime(row.last_submitted_at),
    allowLate: row.allow_late ? '可补交' : '不可补交',
    dueAt: formatDateTime(row.effective_due_at),
    attention: attentionReason(row),
  })),
)

const exportReviewCsv = () => {
  const assignment = selectedReviewAssignment.value || {}
  const headers = ['学员', '状态', '完成进度', '平均分', '最近提交', '补交策略', '截止时间', '处理建议']
  const lines = [
    headers.map(csvCell).join(','),
    ...reviewExportRows.value.map((row) => [
      row.student,
      row.status,
      row.progress,
      row.score,
      row.lastSubmittedAt,
      row.allowLate,
      row.dueAt,
      row.attention,
    ].map(csvCell).join(',')),
  ]
  const blob = new Blob([`\uFEFF${lines.join('\n')}`], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  const safeTitle = String(assignment.title || '作业评审').replace(/[\\/:*?"<>|]/g, '_')
  link.href = url
  link.download = `${safeTitle}-${reviewFilterLabel.value}-评审数据.csv`
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}

const copyReviewSummary = async () => {
  const assignment = selectedReviewAssignment.value || {}
  const lines = [
    `作业：${assignment.title || '未命名作业'}`,
    `筛选：${reviewFilterLabel.value}，共 ${displayedReviewRows.value.length} 人`,
    `提交完成率：${reviewCompletionRate.value}%`,
    `班级平均分：${reviewAverageScore.value === null ? '暂无' : reviewAverageScore.value}`,
    `低于通过线：${lowScoreRows.value.length} 人`,
    '',
    ...reviewExportRows.value.slice(0, 20).map((row) =>
      `${row.student}｜${row.status}｜进度 ${row.progress}｜平均分 ${row.score || '--'}｜${row.attention}`,
    ),
  ]
  if (reviewExportRows.value.length > 20) {
    lines.push(`……另有 ${reviewExportRows.value.length - 20} 人未展开`)
  }
  const text = lines.join('\n')
  try {
    await navigator.clipboard.writeText(text)
    showToast({ type: 'success', message: '评审摘要已复制' })
  } catch {
    window.prompt('复制以下评审摘要', text)
  }
}

const firstSubmission = (row: any) => {
  for (const caseRow of row?.cases || []) {
    if (caseRow?.submission?.id) return caseRow.submission
  }
  return null
}

const openSubmission = async (row: any) => {
  if (!selectedClassId.value || !selectedReviewAssignmentId.value) return
  const submission = firstSubmission(row)
  if (!submission) {
    showToast('该学员暂无可查看提交')
    return
  }
  showSubmissionPopup.value = true
  loadingSubmission.value = true
  submissionDetail.value = null
  try {
    submissionDetail.value = await request.get(
      `/classes/${selectedClassId.value}/assignments/${selectedReviewAssignmentId.value}/submissions/${submission.id}`,
    )
  } finally {
    loadingSubmission.value = false
  }
}

const closeSubmissionPopup = () => {
  showSubmissionPopup.value = false
  showEvaluationPopup.value = false
}

const safeParseJson = <T>(value: any, fallback: T): T => {
  if (value === null || value === undefined || value === '') return fallback
  if (typeof value !== 'string') return value as T
  try {
    return JSON.parse(value) as T
  } catch {
    return fallback
  }
}

const evaluationReport = computed<Record<string, any> | null>(() => {
  const raw = submissionDetail.value?.submission?.evaluation_result ?? submissionDetail.value?.session?.evaluation_result
  const parsed = safeParseJson(raw, null)
  return parsed && typeof parsed === 'object' && !Array.isArray(parsed) ? parsed as Record<string, any> : null
})

const hasEvaluationReport = computed(() => !!evaluationReport.value)

const submissionMetaText = computed(() => {
  if (!submissionDetail.value) return ''
  return [
    submissionDetail.value?.student?.username || '未知学员',
    submissionDetail.value?.case?.title || '未命名案件',
    submissionDetail.value?.scene?.name || '训练场景',
  ].join(' · ')
})

const getLevel = (score: number) => {
  if (score >= 90) return '卓越'
  if (score >= 80) return '优秀'
  if (score >= 70) return '良好'
  if (score >= 60) return '合格'
  return '需改进'
}

const getGradeClass = (score: number) => {
  if (score >= 80) return 'pass'
  if (score >= 60) return 'ok'
  return 'fail'
}

const getScoreDesc = (score: number) => {
  if (score >= 90) return '表现稳定，关键能力覆盖充分'
  if (score >= 75) return '基本达标，仍需巩固薄弱环节'
  if (score >= 60) return '达到基础要求，关键点仍需补齐'
  return '未达预期，需要优先复训'
}

const percentText = (value: any) => {
  const number = Number(value)
  if (!Number.isFinite(number)) return '暂无'
  return `${Math.round(number * 100)}%`
}

const submissionSummary = computed(() => {
  const report = evaluationReport.value || {}
  const score = Number(
    report.total_score ??
    report.evaluation_meta?.report_header?.total_score ??
    submissionDetail.value?.submission?.score ??
    0,
  )
  const safeScore = Number.isFinite(score) ? Math.max(0, Math.min(100, Math.round(score))) : 0
  const completion = report.evaluation_meta?.assessment_completion || {}
  return {
    totalScore: hasEvaluationReport.value ? safeScore : (submissionDetail.value?.submission?.score ?? '--'),
    gradeText: report.grade_level || report.evaluation_meta?.report_header?.grade_level || getLevel(safeScore),
    gradeClass: getGradeClass(safeScore),
    scoreDesc: getScoreDesc(safeScore),
    assessmentRateText: percentText(completion.weight_rate ?? completion.overall_rate ?? completion.required_rate),
  }
})

const displayedCommonReviewItems = computed(() => {
  const scores = Array.isArray(evaluationReport.value?.scores) ? evaluationReport.value?.scores : []
  return scores
    .filter((item: any) => item?.group !== 'assessment')
    .map((item: any) => ({
      ...item,
      dimension: String(item?.dimension || '能力维度').replace(/^考察点[:：]/, ''),
      score: Math.round(Number(item?.score || 0)),
      full_score: Math.round(Number(item?.full_score || 100)),
    }))
    .slice(0, 4)
})

const assessmentPointItems = computed(() => {
  const points = Array.isArray(evaluationReport.value?.assessment_point_results)
    ? evaluationReport.value?.assessment_point_results
    : []
  return points.map((item: any, index: number) => ({
    ...item,
    id: item?.id || `point-${index}`,
    label: String(item?.label || item?.content || `考察点 ${index + 1}`).trim(),
    status: normalizeAssessmentStatus(item?.status),
  }))
})

const assessmentPointKey = (item: any) => `${item?.id || ''}-${item?.label || ''}-${item?.status || ''}`

const normalizeAssessmentStatus = (status: any) => {
  const value = String(status || '').trim()
  if (value === 'hit') return 'hit'
  if (value === 'partial') return 'partial'
  return 'missed'
}

const assessmentPointStatusLabel = (status: string) => {
  if (status === 'hit') return '已命中'
  if (status === 'partial') return '部分命中'
  return '未命中'
}

const assessmentCompletionLabel = (item: any) => {
  const score = Number(item?.weighted_score ?? item?.score)
  const fullScore = Number(item?.full_score ?? item?.weight)
  if (Number.isFinite(score) && Number.isFinite(fullScore) && fullScore > 0) {
    return `${Math.round(score)}/${Math.round(fullScore)}`
  }
  return assessmentPointStatusLabel(item?.status)
}

const strengthItems = computed(() =>
  Array.isArray(evaluationReport.value?.strengths)
    ? evaluationReport.value.strengths.map((item: any) => String(item || '').trim()).filter(Boolean)
    : [],
)

const improvementItems = computed(() =>
  Array.isArray(evaluationReport.value?.improvements)
    ? evaluationReport.value.improvements.map((item: any) => String(item || '').trim()).filter(Boolean)
    : [],
)

const suggestionText = computed(() => String(evaluationReport.value?.suggestions || '').trim())

const commentText = computed(() => {
  const report = evaluationReport.value || {}
  const sections = [
    strengthItems.value.length ? `亮点：${strengthItems.value.join('；')}` : '',
    improvementItems.value.length ? `不足：${improvementItems.value.join('；')}` : '',
    suggestionText.value ? `建议：${suggestionText.value}` : '',
  ].filter(Boolean)
  if (sections.length) return sections.join('\n')
  if (report.error) return `评估生成异常：${report.error}`
  return ''
})

const commentLines = computed(() =>
  commentText.value
    .split(/\n+/)
    .map((line) => line.trim())
    .filter(Boolean),
)

const commentPreviewLines = computed(() => {
  if (!commentText.value) return []
  const lines = commentLines.value
  if (lines.length >= 3) return lines.slice(0, 3)
  const singleText = lines.join('')
  if (singleText.length > 150) return [`${singleText.slice(0, 150)}...`]
  return lines
})

const commentHasMore = computed(() => {
  const lines = commentLines.value
  return lines.length > 3 || commentText.value.length > 150
})

const submissionMessages = computed(() => {
  const messages = Array.isArray(submissionDetail.value?.messages) ? submissionDetail.value.messages : []
  return messages
    .filter((message: any) => !isInternalPromptMessage(message))
    .map((message: any, index: number) => {
      const content = String(message?.content || '').trim()
      if (!content) return null
      const originalRole = String(message?.role || '')
      const displayRole = originalRole === 'user' || originalRole === 'human'
        ? 'human'
        : originalRole === 'system'
          ? 'system'
          : 'assistant'
      return {
        key: `${message?.id || index}-${displayRole}`,
        id: Number(message?.id || index),
        originalRole,
        displayRole,
        content,
        speakerName: String(message?.speaker_name || roleLabel(originalRole)).trim(),
        createdAt: message?.created_at,
      }
    })
    .filter(Boolean) as Array<{
      key: string
      id: number
      originalRole: string
      displayRole: 'human' | 'assistant' | 'system'
      content: string
      speakerName: string
      createdAt?: string
    }>
})

const parseDate = (value?: string) => {
  if (!value) return null
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? null : date
}

const pad = (value: number) => String(value).padStart(2, '0')

const formatDateKey = (value?: string) => {
  const date = parseDate(value)
  if (!date) return ''
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
}

const shouldShowDateDivider = (index: number) => {
  const current = submissionMessages.value[index]
  if (!current?.createdAt) return index === 0
  if (index === 0) return true
  return formatDateKey(current.createdAt) !== formatDateKey(submissionMessages.value[index - 1]?.createdAt)
}

const formatDateDivider = (value?: string) => {
  const date = parseDate(value)
  if (!date) return '训练过程'
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
}

const formatMessageClock = (value?: string) => {
  const date = parseDate(value)
  if (!date) return '--:--'
  return `${pad(date.getHours())}:${pad(date.getMinutes())}`
}

const getMessageAvatarText = (message: any) => {
  if (message.displayRole === 'human') return '学'
  if (message.displayRole === 'system') return '系'
  return String(message.speakerName || 'AI').slice(0, 1)
}

const copyInviteCode = async () => {
  const code = selectedClass.value?.invite_code || classDetail.value?.classroom?.invite_code
  if (!code) return
  try {
    await navigator.clipboard.writeText(code)
    showToast({ type: 'success', message: '邀请码已复制' })
  } catch {
    showToast(`邀请码：${code}`)
  }
}

const reviewStatusLabel = (status: string) => {
  const map: Record<string, string> = {
    submitted: '已提交',
    completed: '已完成',
    late: '迟交',
    in_progress: '训练中',
    evaluating: '评估中',
    pending: '待完成',
    unsubmitted: '未提交',
    missing: '未提交',
  }
  return map[status] || status || '--'
}

const reviewStatusType = (status: string) => {
  if (status === 'submitted' || status === 'completed') return 'success'
  if (status === 'late' || status === 'in_progress' || status === 'evaluating') return 'warning'
  if (status === 'unsubmitted' || status === 'missing') return 'danger'
  return 'default'
}

const roleLabel = (role: string) => {
  if (role === 'user') return '学员'
  if (role === 'assistant' || role === 'ai') return 'AI角色'
  if (role === 'action') return '训练动作'
  return role || '系统'
}

const toDatetimeInput = (value: any) => {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return String(value)
  const pad = (num: number) => String(num).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`
}

const formatDateTime = (value: any) => {
  if (!value) return '未设置'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return String(value)
  const pad = (num: number) => String(num).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`
}

onMounted(async () => {
  await Promise.all([fetchCases(), fetchClasses()])
})
</script>

<style scoped>
.classroom-page {
  display: grid;
  gap: 16px;
  padding-bottom: 28px;
}

.admin-list-header,
.workspace-header,
.workspace-actions,
.review-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.admin-list-header {
  padding: 18px 20px;
  border: 1px solid var(--police-border);
  border-radius: var(--police-radius-lg);
  background: #fff;
}

.admin-list-header h1,
.workspace-header h2 {
  margin: 0;
  color: var(--police-text-primary);
  font-weight: 900;
}

.admin-list-header h1 {
  font-size: 22px;
}

.admin-list-header p,
.workspace-header p {
  margin: 5px 0 0;
  color: var(--police-text-muted);
  font-size: 13px;
}

.header-actions,
.workspace-actions,
.row-actions,
.review-summary,
.review-notice-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.classroom-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 12px;
}

.class-card {
  min-height: 132px;
  border: 1px solid var(--police-border);
  border-radius: 8px;
  background: #fff;
  padding: 16px;
  text-align: left;
  cursor: pointer;
  transition: border-color 0.16s, box-shadow 0.16s;
}

.class-card:hover,
.class-card--active {
  border-color: #1d4ed8;
  box-shadow: 0 6px 20px rgba(29, 78, 216, 0.12);
}

.class-card__head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}

.class-card strong {
  color: #0f172a;
  font-size: 16px;
}

.class-card__head span {
  color: #1d4ed8;
  font-size: 12px;
  font-weight: 800;
  white-space: nowrap;
}

.class-card p {
  min-height: 40px;
  margin: 10px 0 12px;
  color: #64748b;
  font-size: 13px;
  line-height: 1.6;
}

.class-card__stats {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.class-card__stats span,
.tag-list span {
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  background: #f1f5f9;
  padding: 4px 9px;
  color: #475569;
  font-size: 12px;
  font-weight: 800;
}

.class-card--empty {
  border-style: dashed;
}

.class-workspace,
.state-card {
  border: 1px solid var(--police-border);
  border-radius: 8px;
  background: #fff;
  padding: 18px;
}

.workspace-header {
  align-items: flex-start;
  padding-bottom: 16px;
  border-bottom: 1px solid #eef2f7;
}

.workspace-kicker {
  color: #1d4ed8;
  font-size: 12px;
  font-weight: 900;
}

.invite-panel {
  display: grid;
  grid-template-columns: auto auto auto;
  align-items: center;
  gap: 10px;
  border: 1px solid #dbeafe;
  border-radius: 8px;
  background: #f8fbff;
  padding: 10px 12px;
}

.invite-panel span {
  color: #64748b;
  font-size: 12px;
  font-weight: 800;
}

.invite-panel strong {
  color: #1d4ed8;
  letter-spacing: 0.08em;
}

.workspace-actions {
  justify-content: flex-start;
  margin: 14px 0;
}

.workspace-tabs {
  border-top: 1px solid #eef2f7;
  padding-top: 4px;
}

.assignment-filter-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 12px;
}

.assignment-filter-bar button {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 32px;
  border: 1px solid #dbe3ee;
  border-radius: 999px;
  background: #fff;
  padding: 0 12px;
  color: #475569;
  cursor: pointer;
}

.assignment-filter-bar span {
  font-size: 12px;
  font-weight: 900;
}

.assignment-filter-bar strong {
  min-width: 20px;
  border-radius: 999px;
  background: #f1f5f9;
  padding: 2px 6px;
  color: #0f172a;
  font-size: 12px;
  line-height: 1.2;
  text-align: center;
}

.assignment-filter-bar button:hover,
.assignment-filter-bar .assignment-filter--active {
  border-color: #165dff;
  background: #eff6ff;
  color: #1d4ed8;
}

.assignment-filter-bar .assignment-filter--active strong {
  background: #165dff;
  color: #fff;
}

.panel-table-wrap {
  overflow-x: auto;
}

.ops-table {
  width: 100%;
  min-width: 860px;
  border-collapse: collapse;
}

.ops-table th,
.ops-table td {
  border-bottom: 1px solid #eef2f7;
  padding: 12px 14px;
  text-align: left;
  vertical-align: top;
  font-size: 13px;
}

.ops-table th {
  background: #f8fafc;
  color: #475569;
  font-weight: 900;
}

.ops-table td strong {
  color: #0f172a;
}

.ops-table td p,
.ops-table td small {
  display: block;
  margin: 4px 0 0;
  color: #64748b;
  line-height: 1.6;
}

.tag-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.row-actions button {
  height: 28px;
  border: 1px solid #cbd5e1;
  border-radius: 6px;
  background: #fff;
  color: #1d3557;
  font-size: 12px;
  font-weight: 800;
  cursor: pointer;
}

.row-actions button:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.review-toolbar {
  margin: 4px 0 12px;
}

.review-toolbar label {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #334155;
  font-size: 13px;
  font-weight: 900;
}

.review-toolbar select {
  height: 34px;
  min-width: 260px;
  border: 1px solid #cbd5e1;
  border-radius: 6px;
  padding: 0 10px;
}

.review-summary span {
  border-radius: 999px;
  background: #f1f5f9;
  padding: 5px 10px;
  color: #475569;
  font-size: 12px;
  font-weight: 900;
}

.review-notice-actions button {
  height: 28px;
  border: 1px solid #bfdbfe;
  border-radius: 6px;
  background: #eff6ff;
  padding: 0 9px;
  color: #1d4ed8;
  font-size: 12px;
  font-weight: 900;
  cursor: pointer;
}

.review-notice-actions button:disabled {
  border-color: #e5e7eb;
  background: #f8fafc;
  color: #94a3b8;
  cursor: not-allowed;
}

.review-insights {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
  margin: 14px 0;
}

.review-insight-card {
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #fff;
  padding: 14px;
}

.review-insight-card span {
  color: #64748b;
  font-size: 12px;
  font-weight: 900;
}

.review-insight-card strong {
  display: block;
  margin-top: 6px;
  color: #0f172a;
  font-size: 26px;
  line-height: 1;
  font-weight: 900;
}

.review-insight-card p {
  margin: 8px 0 0;
  color: #64748b;
  font-size: 12px;
  line-height: 1.5;
}

.review-insight-card.is-good {
  border-color: #bbf7d0;
  background: #f0fdf4;
}

.review-insight-card.is-warn {
  border-color: #fed7aa;
  background: #fff7ed;
}

.review-insight-card.is-danger {
  border-color: #fecaca;
  background: #fef2f2;
}

.attention-panel {
  display: grid;
  gap: 10px;
  margin-bottom: 14px;
  border: 1px solid #dbeafe;
  border-radius: 8px;
  background: #f8fbff;
  padding: 12px;
}

.attention-panel > div:first-child {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
}

.attention-panel strong {
  color: #0f172a;
  font-size: 14px;
  font-weight: 900;
}

.attention-panel span {
  color: #64748b;
  font-size: 12px;
}

.attention-list {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
}

.attention-list button {
  display: grid;
  gap: 4px;
  min-height: 62px;
  border: 1px solid #dbeafe;
  border-radius: 8px;
  background: #fff;
  padding: 10px;
  text-align: left;
  cursor: pointer;
}

.attention-list button:hover {
  border-color: #165dff;
}

.review-filter-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 12px;
}

.review-filter-bar button {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 32px;
  border: 1px solid #dbe3ee;
  border-radius: 999px;
  background: #fff;
  padding: 0 12px;
  color: #475569;
  cursor: pointer;
}

.review-filter-bar span {
  font-size: 12px;
  font-weight: 900;
}

.review-filter-bar strong {
  min-width: 20px;
  border-radius: 999px;
  background: #f1f5f9;
  padding: 2px 6px;
  color: #0f172a;
  font-size: 12px;
  line-height: 1.2;
  text-align: center;
}

.review-filter-bar button:hover,
.review-filter-bar .review-filter--active {
  border-color: #165dff;
  background: #eff6ff;
  color: #1d4ed8;
}

.review-filter-bar .review-filter--active strong {
  background: #165dff;
  color: #fff;
}

.bulk-action-bar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin: -4px 0 12px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #f8fafc;
  padding: 10px;
}

.bulk-action-bar span {
  margin-right: auto;
  color: #64748b;
  font-size: 12px;
  font-weight: 900;
}

.bulk-action-bar button {
  height: 30px;
  border: 1px solid #cbd5e1;
  border-radius: 6px;
  background: #fff;
  padding: 0 10px;
  color: #334155;
  font-size: 12px;
  font-weight: 900;
  cursor: pointer;
}

.bulk-action-bar button:hover {
  border-color: #165dff;
  color: #165dff;
}

.bulk-action-bar button:disabled {
  border-color: #e5e7eb;
  background: #f8fafc;
  color: #94a3b8;
  cursor: not-allowed;
}

.score-cell {
  color: #1d4ed8;
  font-weight: 900;
}

.announcement-list {
  display: grid;
  gap: 10px;
}

.notice-item {
  border: 1px solid #eef2f7;
  border-radius: 8px;
  padding: 12px 14px;
  background: #fbfdff;
}

.notice-item div {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}

.notice-item strong {
  color: #0f172a;
}

.notice-item span,
.notice-item p {
  margin: 0;
  color: #64748b;
  font-size: 13px;
}

.popup-panel {
  display: grid;
  gap: 14px;
  padding: 18px;
  max-height: 88vh;
  overflow: auto;
  background: #fff;
}

.popup-panel--student-import {
  grid-template-rows: auto auto minmax(280px, 1fr) auto;
}

.student-import-section {
  display: grid;
  gap: 12px;
  border: 1px solid #e5ebf3;
  border-radius: 10px;
  background: #fbfdff;
  padding: 12px;
}

.student-import-section--text {
  min-height: 138px;
}

.student-import-section--file {
  min-height: 300px;
}

.student-import-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.student-import-head strong {
  display: block;
  color: #0f172a;
  font-size: 14px;
  font-weight: 900;
}

.student-import-head span {
  display: block;
  margin-top: 4px;
  color: #64748b;
  font-size: 12px;
  line-height: 1.6;
}

.student-import-head button {
  border: 1px solid #dbe3ee;
  border-radius: 6px;
  background: #fff;
  padding: 7px 10px;
  color: #1d3557;
  font-size: 12px;
  font-weight: 800;
}

.student-file-dropzone {
  display: grid;
  place-items: center;
  min-height: 158px;
  border: 1px dashed #b9c7d8;
  border-radius: 10px;
  background: #fff;
  padding: 18px;
  color: #64748b;
  text-align: center;
  cursor: pointer;
  outline: none;
}

.student-file-dropzone:hover,
.student-file-dropzone:focus,
.student-file-dropzone--dragging {
  border-color: #1d3557;
  background: #f6f9fd;
}

.student-file-dropzone--ready {
  border-color: #16a34a;
  background: #f7fef9;
}

.student-file-dropzone strong {
  margin-top: 10px;
  color: #0f172a;
  font-size: 15px;
  font-weight: 900;
}

.student-file-dropzone span,
.student-file-dropzone small {
  color: #64748b;
  font-size: 12px;
  line-height: 1.6;
}

.student-file-dropzone small {
  color: #1d3557;
  font-weight: 800;
}

.student-import-preview {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.student-import-preview span,
.student-import-preview em {
  border: 1px solid #dbe3ee;
  border-radius: 999px;
  background: #fff;
  padding: 4px 9px;
  color: #334155;
  font-size: 12px;
  font-style: normal;
  font-weight: 800;
}

.popup-panel header,
.submission-panel header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  border-bottom: 1px solid #eef2f7;
  padding-bottom: 12px;
}

.popup-panel h3,
.submission-panel h3 {
  margin: 0;
  color: #0f172a;
  font-size: 18px;
  font-weight: 900;
}

.field-block {
  display: grid;
  gap: 7px;
}

.field-block span {
  color: #334155;
  font-size: 13px;
  font-weight: 900;
}

.field-block input,
.field-block textarea,
.field-block select,
.review-toolbar select {
  width: 100%;
  border: 1px solid #dbe3ee;
  border-radius: 6px;
  background: #fff;
  padding: 9px 10px;
  color: #0f172a;
  font-size: 13px;
  outline: none;
}

.form-grid {
  display: grid;
  grid-template-columns: 1fr 220px;
  gap: 12px;
}

.form-grid--three {
  grid-template-columns: minmax(0, 1.6fr) minmax(96px, 0.7fr) minmax(110px, 0.7fr);
}

.template-picker {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
}

.template-picker button {
  display: grid;
  gap: 4px;
  min-height: 72px;
  border: 1px solid #dbe3ee;
  border-radius: 8px;
  background: #fff;
  padding: 10px;
  text-align: left;
  cursor: pointer;
}

.template-picker button:hover,
.template-picker .template-option--active {
  border-color: #165dff;
  background: #eff6ff;
}

.template-picker strong {
  color: #0f172a;
  font-size: 13px;
  font-weight: 900;
}

.template-picker small {
  color: #64748b;
  font-size: 12px;
  line-height: 1.45;
}

.checkline {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #334155;
  font-size: 13px;
  font-weight: 800;
}

.case-picker {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}

.case-option {
  display: grid;
  grid-template-columns: 18px minmax(0, 1fr) auto;
  align-items: center;
  gap: 8px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 10px;
  color: #334155;
}

.case-option--stack {
  grid-template-columns: 1fr;
  align-items: stretch;
  gap: 9px;
}

.case-option__head {
  display: grid;
  grid-template-columns: 18px minmax(0, 1fr) auto;
  align-items: center;
  gap: 8px;
}

.case-option strong {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 13px;
}

.case-option small {
  color: #64748b;
  font-size: 12px;
}

.scene-option-list {
  display: grid;
  gap: 6px;
  padding-left: 26px;
}

.scene-option {
  display: grid;
  grid-template-columns: 18px minmax(0, 1fr) auto;
  align-items: center;
  gap: 7px;
  border-radius: 6px;
  background: #f8fafc;
  padding: 7px 8px;
}

.scene-option span {
  min-width: 0;
  overflow: hidden;
  color: #334155;
  font-size: 12px;
  font-weight: 800;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.scene-option-empty {
  color: #94a3b8;
  font-size: 12px;
}

.submission-panel {
  display: grid;
  grid-template-rows: auto minmax(0, 1fr);
  max-height: 92vh;
  background: #fff;
}

.submission-panel__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 16px 18px;
  border-bottom: 1px solid #eef2f7;
}

.submission-panel__header p {
  margin: 4px 0 0;
  color: #64748b;
  font-size: 13px;
}

.submission-panel__header-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.submission-body {
  display: grid;
  grid-template-columns: 296px minmax(0, 1fr);
  gap: 18px;
  min-height: 0;
  height: min(740px, calc(92vh - 68px));
  overflow: hidden;
  padding: 18px;
  background: #f8fafc;
}

.submission-summary {
  display: grid;
  grid-template-rows: repeat(3, 1fr);
  gap: 12px;
  min-height: 0;
}

.submission-card {
  border: 1px solid #eef2f7;
  border-radius: 8px;
  padding: 14px;
  overflow: hidden;
  background: #fff;
  box-shadow: 0 6px 18px rgba(15, 23, 42, 0.04);
}

.submission-card__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 10px;
}

.submission-card__head span {
  color: #64748b;
  font-size: 13px;
  font-weight: 900;
}

.submission-card__head strong {
  color: #0f172a;
  font-size: 15px;
  font-weight: 900;
}

.submission-card--score .submission-card__head strong {
  color: #dc2626;
  font-size: 48px;
  line-height: 1;
  font-variant-numeric: tabular-nums;
}

.submission-score-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.submission-score-meta__grade {
  display: inline-flex;
  align-items: center;
  height: 24px;
  border-radius: 999px;
  padding: 0 10px;
  background: #fee2e2;
  color: #dc2626;
  font-size: 12px;
  font-weight: 900;
  white-space: nowrap;
}

.submission-score-meta__grade.grade-pass {
  background: #dcfce7;
  color: #047857;
}

.submission-score-meta__grade.grade-ok {
  background: #fef3c7;
  color: #b45309;
}

.submission-score-meta__desc {
  min-width: 0;
  overflow: hidden;
  color: #64748b;
  font-size: 12px;
  font-weight: 700;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.submission-score-stats {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
  margin: 12px 0;
}

.submission-score-stats div {
  display: grid;
  gap: 4px;
  min-width: 0;
  border-radius: 6px;
  background: #f8fafc;
  padding: 8px;
}

.submission-score-stats span,
.assessment-list__meta,
.timeline-message__label {
  color: #64748b;
  font-size: 12px;
}

.submission-score-stats strong {
  overflow: hidden;
  color: #0f172a;
  font-size: 12px;
  font-weight: 900;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.submission-score-dimensions {
  display: grid;
  gap: 7px;
}

.dimension-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  min-width: 0;
}

.dimension-row span {
  min-width: 0;
  overflow: hidden;
  color: #334155;
  font-size: 12px;
  font-weight: 800;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.dimension-row strong {
  color: #1d4ed8;
  font-size: 12px;
  font-weight: 900;
  white-space: nowrap;
}

.assessment-list {
  display: grid;
  gap: 8px;
  height: calc(100% - 32px);
  overflow-y: auto;
  padding-right: 4px;
}

.assessment-list__item {
  display: grid;
  gap: 6px;
  border: 1px solid #eef2f7;
  border-radius: 7px;
  padding: 9px 10px;
  background: #fbfdff;
}

.assessment-list__head,
.assessment-list__meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.assessment-list__head strong {
  min-width: 0;
  overflow: hidden;
  color: #0f172a;
  font-size: 13px;
  font-weight: 900;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.status-pill {
  border-radius: 999px;
  padding: 2px 7px;
  background: #fee2e2;
  color: #dc2626;
  font-size: 11px;
  font-weight: 900;
  white-space: nowrap;
}

.status-pill--hit {
  background: #dcfce7;
  color: #047857;
}

.status-pill--partial {
  background: #fef3c7;
  color: #b45309;
}

.comment-preview {
  height: calc(100% - 32px);
  overflow: hidden;
}

.comment-preview p {
  display: -webkit-box;
  margin: 0 0 10px;
  overflow: hidden;
  color: #0f172a;
  font-size: 13px;
  line-height: 1.7;
  text-overflow: ellipsis;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}

.link-button {
  border: none;
  background: transparent;
  color: #1d4ed8;
  font-size: 12px;
  font-weight: 900;
  cursor: pointer;
}

.submission-dialogue {
  display: grid;
  grid-template-rows: auto minmax(0, 1fr);
  min-width: 0;
  border: 1px solid #eef2f7;
  border-radius: 8px;
  overflow: hidden;
  background: #fff;
  box-shadow: 0 6px 18px rgba(15, 23, 42, 0.04);
}

.submission-dialogue__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  padding: 16px 18px;
  border-bottom: 1px solid #eef2f7;
}

.submission-dialogue__head h4 {
  margin: 0 0 4px;
  color: #0f172a;
  font-size: 17px;
  font-weight: 900;
}

.submission-dialogue__head p {
  margin: 0;
  color: #64748b;
  font-size: 13px;
}

.submission-dialogue__meta {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.submission-dialogue__meta span {
  border-radius: 999px;
  background: #f1f5f9;
  padding: 4px 9px;
  color: #475569;
  font-size: 12px;
  font-weight: 900;
}

.dialogue-timeline {
  display: grid;
  align-content: start;
  gap: 12px;
  min-height: 0;
  overflow-y: auto;
  padding: 18px;
}

.timeline-divider {
  display: flex;
  justify-content: center;
}

.timeline-divider span {
  border-radius: 999px;
  background: #e2e8f0;
  padding: 4px 10px;
  color: #475569;
  font-size: 12px;
  font-weight: 900;
}

.timeline-message {
  display: grid;
  grid-template-columns: 34px minmax(0, 1fr);
  gap: 10px;
  align-items: flex-start;
}

.timeline-message__avatar {
  display: grid;
  place-items: center;
  width: 34px;
  height: 34px;
  border-radius: 50%;
  background: #475569;
  color: #fff;
  font-size: 13px;
  font-weight: 900;
}

.timeline-message__avatar--human {
  background: #1d4ed8;
}

.timeline-message__avatar--system {
  background: #64748b;
}

.timeline-message__body {
  min-width: 0;
}

.timeline-message__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.timeline-message__head strong {
  min-width: 0;
  overflow: hidden;
  color: #0f172a;
  font-size: 13px;
  font-weight: 900;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.timeline-message__head time {
  color: #94a3b8;
  font-size: 12px;
  white-space: nowrap;
}

.timeline-message__bubble {
  margin-top: 6px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 11px 12px;
  background: #fff;
  color: #0f172a;
  font-size: 14px;
  line-height: 1.7;
  white-space: pre-wrap;
}

.timeline-message--human .timeline-message__bubble {
  border-color: #bfdbfe;
  background: #eff6ff;
}

.timeline-message--system .timeline-message__bubble {
  background: #f8fafc;
  color: #475569;
}

.submission-empty-inline {
  color: #94a3b8;
  font-size: 13px;
}

.submission-empty-state {
  display: grid;
  place-items: center;
  gap: 8px;
  min-height: 260px;
  color: #94a3b8;
  text-align: center;
}

.submission-empty-state strong {
  color: #475569;
}

.evaluation-panel {
  display: grid;
  grid-template-rows: auto auto minmax(0, 1fr);
  max-height: 88vh;
  background: #fff;
}

.evaluation-panel__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 16px 18px;
  border-bottom: 1px solid #eef2f7;
}

.evaluation-panel__header h3 {
  margin: 0;
  color: #0f172a;
  font-size: 18px;
  font-weight: 900;
}

.evaluation-panel__header p {
  margin: 4px 0 0;
  color: #64748b;
  font-size: 13px;
}

.evaluation-panel__summary {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
  padding: 14px 18px;
  background: #f8fafc;
}

.evaluation-panel__summary div {
  display: grid;
  gap: 4px;
  border: 1px solid #eef2f7;
  border-radius: 7px;
  background: #fff;
  padding: 10px;
}

.evaluation-panel__summary span {
  color: #64748b;
  font-size: 12px;
  font-weight: 800;
}

.evaluation-panel__summary strong {
  color: #0f172a;
  font-size: 18px;
  font-weight: 900;
}

.evaluation-panel__body {
  display: grid;
  gap: 14px;
  min-height: 0;
  overflow-y: auto;
  padding: 18px;
}

.evaluation-panel__block {
  border: 1px solid #eef2f7;
  border-radius: 8px;
  padding: 14px 16px;
  background: #fff;
}

.evaluation-panel__block h4 {
  margin: 0 0 10px;
  color: #0f172a;
  font-size: 15px;
  font-weight: 900;
}

.evaluation-panel__block p {
  margin: 0 0 8px;
  color: #334155;
  font-size: 14px;
  line-height: 1.8;
}

.evaluation-panel__columns {
  display: grid;
  gap: 10px;
}

.evaluation-panel__columns div {
  display: grid;
  gap: 4px;
}

.evaluation-panel__columns span {
  color: #1d4ed8;
  font-size: 12px;
  font-weight: 900;
}

.state-card--flat {
  border: none;
  padding: 12px;
}

@media (max-width: 900px) {
  .admin-list-header,
  .workspace-header,
  .review-toolbar,
  .submission-body {
    grid-template-columns: 1fr;
    display: grid;
  }

  .invite-panel,
  .form-grid,
  .case-picker {
    grid-template-columns: 1fr;
  }
}
</style>
