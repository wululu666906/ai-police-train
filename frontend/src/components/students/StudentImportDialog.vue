<template>
  <van-popup :show="dialogVisible" teleport="body" :close-on-click-overlay="false" class="student-import-popup">
    <section class="import-workspace">
      <header class="import-header">
        <div>
          <h2>批量导入学员档案</h2>
          <p>预检名单、人脸照片、班级及账号匹配结果</p>
        </div>
        <button type="button" class="icon-button" title="关闭" @click="closeImportDialog">
          <van-icon name="cross" />
        </button>
      </header>

      <template v-if="!batch">
        <div class="upload-body">
          <div class="mode-tabs" role="tablist">
            <button type="button" :class="{ active: mode === 'zip' }" @click="mode = 'zip'">ZIP压缩包</button>
            <button type="button" :class="{ active: mode === 'files' }" @click="mode = 'files'">多文件上传</button>
          </div>

          <section class="upload-zone">
            <template v-if="mode === 'zip'">
              <van-icon name="description" size="34" />
              <strong>{{ archiveFile?.name || '选择标准ZIP压缩包' }}</strong>
              <span>根目录放置“学员名单.xlsx”，人脸照片放入photos文件夹</span>
              <button type="button" class="command-button" @click="archiveInput?.click()">选择ZIP</button>
              <input ref="archiveInput" type="file" accept=".zip" hidden @change="onArchiveChange" />
            </template>
            <template v-else>
              <div class="file-pickers">
                <button type="button" class="file-picker" @click="rosterInput?.click()">
                  <van-icon name="description" />
                  <span>{{ rosterFile?.name || '选择学员名单.xlsx' }}</span>
                </button>
                <button type="button" class="file-picker" @click="photoInput?.click()">
                  <van-icon name="photograph" />
                  <span>{{ photoFiles.length ? `已选择 ${photoFiles.length} 张人脸照片` : '选择以学号命名的人脸照片' }}</span>
                </button>
              </div>
              <input ref="rosterInput" type="file" accept=".xlsx" hidden @change="onRosterChange" />
              <input ref="photoInput" type="file" accept=".jpg,.jpeg,.png,.webp" multiple hidden @change="onPhotosChange" />
            </template>
          </section>

          <div class="template-row">
            <span>标准字段：学号、姓名、性别、单位、院系、班级</span>
            <button type="button" @click="downloadTemplate"><van-icon name="down" /> 下载模板</button>
          </div>
        </div>
        <footer class="import-footer">
          <span>新建账号初始密码统一为 123456</span>
          <button type="button" class="primary-button" :disabled="!canPreview || busy" @click="previewImport">
            <van-loading v-if="busy" size="16" />
            <van-icon v-else name="scan" />
            上传并预检
          </button>
        </footer>
      </template>

      <template v-else>
        <div class="preview-body">
          <div class="summary-strip">
            <div class="summary-new"><span>新建账号</span><strong>{{ batch.summary.new_students }}</strong></div>
            <div><span>匹配成功</span><strong>{{ batch.summary.matched }}</strong></div>
            <div><span>新增班级</span><strong>{{ batch.summary.new_classes }}</strong></div>
            <div><span>已跳过</span><strong>{{ batch.summary.skipped }}</strong></div>
            <div class="summary-error"><span>错误</span><strong>{{ batch.summary.errors }}</strong></div>
            <div class="summary-ready"><span>待同步</span><strong>{{ batch.summary.ready }}</strong></div>
          </div>

          <div class="preview-toolbar">
            <div>
              <strong>{{ batch.source_name }}</strong>
              <span>错误条目和新建账号已优先排列</span>
            </div>
            <button type="button" :disabled="busy" @click="resetBatch"><van-icon name="replay" /> 重新选择</button>
          </div>

          <div class="item-list">
            <article v-for="item in batch.items" :key="item.id" class="import-item" :class="{ 'has-error': item.errors.length, 'is-new': item.is_new }">
              <div class="item-state">
                <van-icon v-if="item.errors.length" name="warning-o" />
                <van-icon v-else-if="item.status === 'synced'" name="passed" />
                <van-icon v-else name="user-o" />
              </div>
              <div class="item-main">
                <div class="item-title">
                  <strong>{{ item.student_no || `第 ${item.row_number} 行` }}</strong>
                  <span v-if="item.source_kind === 'orphan_photo'" class="status-tag error">孤立图片</span>
                  <span v-else-if="item.errors.length" class="status-tag error">异常</span>
                  <span v-else-if="item.is_new" class="status-tag new">新建账号</span>
                  <span v-else class="status-tag matched">存量匹配</span>
                  <span v-if="item.status === 'synced'" class="status-tag synced">已同步</span>
                </div>
                <div class="item-fields">
                  <span>{{ item.data.real_name || '未填写姓名' }}</span>
                  <span>{{ item.data.class_name || '未填写班级' }}</span>
                  <span>{{ item.has_photo ? '已匹配照片' : '无新照片' }}</span>
                </div>
                <p v-if="item.errors.length" class="item-error">{{ item.errors.join('；') }}</p>
                <p v-else-if="item.warnings.length" class="item-warning">{{ item.warnings.join('；') }}</p>
              </div>
              <div class="item-options" v-if="item.status !== 'synced'">
                <label><input v-model="item.replace_face" type="checkbox" :disabled="!item.has_photo" @change="saveOptions(item)" /> 替换人脸</label>
                <label><input v-model="item.replace_class" type="checkbox" :disabled="!item.data.class_name" @change="saveOptions(item)" /> 替换班级</label>
              </div>
              <div class="item-actions">
                <button type="button" title="查看或编辑" @click="openDetail(item)"><van-icon name="edit" /></button>
                <button type="button" title="移除" :disabled="busy || item.status === 'synced'" class="delete" @click="removeItem(item)"><van-icon name="delete-o" /></button>
              </div>
            </article>
          </div>
        </div>
        <footer class="import-footer">
          <span>异常条目不会同步，可修改后重新校验或手动移除</span>
          <button type="button" class="primary-button" :disabled="!batch.summary.ready || busy || batch.status !== 'preview'" @click="commitImport">
            <van-loading v-if="busy" size="16" />
            <van-icon v-else name="passed" />
            确认同步 {{ batch.summary.ready }} 条
          </button>
        </footer>
      </template>
    </section>
  </van-popup>

  <van-popup v-if="detailVisible" v-model:show="detailVisible" teleport="body" :close-on-click-overlay="false" class="student-detail-popup">
    <section v-if="activeItem" class="detail-dialog">
      <header>
        <div><h3>学员导入详情</h3><span>名单第 {{ activeItem.row_number }} 行</span></div>
        <button type="button" class="icon-button" title="关闭" @click="closeDetail"><van-icon name="cross" /></button>
      </header>
      <div class="detail-grid">
        <div class="detail-form">
          <label><span>学号</span><input v-model.trim="editForm.student_no" /></label>
          <label><span>姓名</span><input v-model.trim="editForm.real_name" /></label>
          <label><span>性别</span><select v-model="editForm.gender"><option value="">未填写</option><option>男</option><option>女</option><option>其他</option></select></label>
          <label><span>单位</span><input v-model.trim="editForm.unit" /></label>
          <label><span>院系</span><input v-model.trim="editForm.department" /></label>
          <label><span>班级</span><input v-model.trim="editForm.class_name" /></label>
          <label class="check-line"><input v-model="editForm.replace_face" type="checkbox" :disabled="!activeItem.has_photo" /><span>使用新照片替换人脸档案</span></label>
          <label class="check-line"><input v-model="editForm.replace_class" type="checkbox" :disabled="!editForm.class_name" /><span>使用名单班级替换当前班级</span></label>
          <div v-if="activeItem.errors.length" class="detail-errors">{{ activeItem.errors.join('；') }}</div>
        </div>
        <div class="face-preview">
          <img v-if="activePhotoUrl" :src="activePhotoUrl" alt="学员人脸照片" />
          <div v-else><van-icon name="photograph" size="42" /><span>未匹配人脸照片</span></div>
        </div>
        <div class="face-replace">
          <input ref="detailPhotoInput" type="file" accept=".jpg,.jpeg,.png,.webp" hidden @change="replaceDetailPhoto" />
          <button type="button" :disabled="busy || !editForm.student_no" @click="detailPhotoInput?.click()">
            <van-icon name="photograph" /> 选择{{ editForm.student_no || '学号' }}图片
          </button>
        </div>
      </div>
      <footer>
        <button type="button" @click="closeDetail">取消</button>
        <button type="button" class="primary-button" :disabled="busy" @click="saveDetail">保存并重新校验</button>
      </footer>
    </section>
  </van-popup>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, reactive, ref } from 'vue'
import * as XLSX from 'xlsx'
import { showConfirmDialog, showToast } from 'vant'
import request from '../../utils/request'
import type { StudentImportBatch, StudentImportItem } from '../../types/studentImport'

const emit = defineEmits<{ close: []; synced: [batch: StudentImportBatch] }>()
const mode = ref<'zip' | 'files'>('zip')
const archiveInput = ref<HTMLInputElement | null>(null)
const rosterInput = ref<HTMLInputElement | null>(null)
const photoInput = ref<HTMLInputElement | null>(null)
const archiveFile = ref<File | null>(null)
const rosterFile = ref<File | null>(null)
const photoFiles = ref<File[]>([])
const batch = ref<StudentImportBatch | null>(null)
const busy = ref(false)
const dialogVisible = ref(true)
const detailVisible = ref(false)
const activeItem = ref<StudentImportItem | null>(null)
const activePhotoUrl = ref('')
const detailPhotoInput = ref<HTMLInputElement | null>(null)
let activeController: AbortController | null = null
let requestVersion = 0

const editForm = reactive({
  student_no: '', real_name: '', gender: '', unit: '', department: '', class_name: '',
  replace_face: true, replace_class: true,
})

const canPreview = computed(() => mode.value === 'zip' ? Boolean(archiveFile.value) : Boolean(rosterFile.value))
const apiPhotoUrl = (item: StudentImportItem) => item.photo_url?.replace('/student-imports/', `/student-imports/`) || ''

const onArchiveChange = (event: Event) => {
  archiveFile.value = (event.target as HTMLInputElement).files?.[0] || null
}
const onRosterChange = (event: Event) => {
  rosterFile.value = (event.target as HTMLInputElement).files?.[0] || null
}
const onPhotosChange = (event: Event) => {
  photoFiles.value = Array.from((event.target as HTMLInputElement).files || [])
}

const beginRequest = () => {
  activeController?.abort()
  activeController = new AbortController()
  requestVersion += 1
  return { controller: activeController, version: requestVersion }
}

const resetImportState = () => {
  closeDetail()
  batch.value = null
  archiveFile.value = null
  rosterFile.value = null
  photoFiles.value = []
  busy.value = false
}

const closeImportDialog = () => {
  requestVersion += 1
  activeController?.abort()
  activeController = null
  dialogVisible.value = false
  resetImportState()
  emit('close')
}

const downloadTemplate = () => {
  const sheet = XLSX.utils.aoa_to_sheet([
    ['学号', '姓名', '性别', '单位', '院系', '班级'],
    ['25104080101', '张三', '男', '某警察学院', '治安系', '治安一班'],
  ])
  const workbook = XLSX.utils.book_new()
  XLSX.utils.book_append_sheet(workbook, sheet, '学员名单')
  XLSX.writeFile(workbook, '学员名单.xlsx')
}

const previewImport = async () => {
  if (!canPreview.value) return
  const form = new FormData()
  if (mode.value === 'zip' && archiveFile.value) form.append('archive', archiveFile.value)
  if (mode.value === 'files' && rosterFile.value) {
    form.append('roster', rosterFile.value)
    photoFiles.value.forEach((file) => form.append('photos', file))
  }
  const { controller, version } = beginRequest()
  busy.value = true
  try {
    const result = await request.post('/student-imports/preview', form, { signal: controller.signal } as any) as StudentImportBatch
    if (version !== requestVersion) return
    batch.value = result
    showToast({ type: 'success', message: '预检完成' })
  } catch (error: any) {
    if (error?.code !== 'ERR_CANCELED') return
  } finally {
    if (version === requestVersion) busy.value = false
  }
}

const resetBatch = async () => {
  if (batch.value?.items.length) {
    try {
      await showConfirmDialog({ title: '重新选择文件', message: '当前预检修改不会保留，确定重新选择吗？' })
    } catch { return }
  }
  resetImportState()
}

const updateBatch = (value: StudentImportBatch) => { batch.value = value }
const saveOptions = async (item: StudentImportItem) => {
  if (!batch.value) return
  const { controller, version } = beginRequest()
  try {
    const result = await request.patch(`/student-imports/${batch.value.batch_id}/items/${item.id}`, {
      ...item.data,
      student_no: item.student_no,
      replace_face: item.replace_face,
      replace_class: item.replace_class,
    }, { signal: controller.signal } as any) as StudentImportBatch
    if (version === requestVersion) updateBatch(result)
  } catch { /* global interceptor reports the error */ }
}

const loadPhoto = async (item: StudentImportItem) => {
  if (activePhotoUrl.value) URL.revokeObjectURL(activePhotoUrl.value)
  activePhotoUrl.value = ''
  if (!item.photo_url) return
  const { controller, version } = beginRequest()
  try {
    const blob = await request.get(apiPhotoUrl(item), { responseType: 'blob', _skipErrorToast: true, signal: controller.signal } as any) as Blob
    if (version === requestVersion) activePhotoUrl.value = URL.createObjectURL(blob)
  } catch { activePhotoUrl.value = '' }
}

const openDetail = (item: StudentImportItem) => {
  activeItem.value = item
  Object.assign(editForm, {
    student_no: item.student_no,
    real_name: item.data.real_name || '',
    gender: item.data.gender || '',
    unit: item.data.unit || '',
    department: item.data.department || '',
    class_name: item.data.class_name || '',
    replace_face: item.replace_face,
    replace_class: item.replace_class,
  })
  detailVisible.value = true
  void loadPhoto(item)
}

const closeDetail = () => {
  detailVisible.value = false
  activeItem.value = null
  if (activePhotoUrl.value) URL.revokeObjectURL(activePhotoUrl.value)
  activePhotoUrl.value = ''
}

const saveDetail = async () => {
  if (!batch.value || !activeItem.value) return
  const { controller, version } = beginRequest()
  busy.value = true
  try {
    const result = await request.patch(`/student-imports/${batch.value.batch_id}/items/${activeItem.value.id}`, editForm, { signal: controller.signal } as any) as StudentImportBatch
    if (version !== requestVersion) return
    updateBatch(result)
    closeDetail()
    showToast({ type: 'success', message: '已保存并重新校验' })
  } finally { if (version === requestVersion) busy.value = false }
}

const replaceDetailPhoto = async (event: Event) => {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file || !batch.value || !activeItem.value) return
  const filePath = file.name.toLowerCase()
  const allowedNames = ['jpg', 'jpeg', 'png', 'webp'].map((suffix) => `${editForm.student_no}.${suffix}`.toLowerCase())
  if (!allowedNames.includes(filePath)) {
    showToast(`照片必须以学号命名，支持 JPG、PNG 或 WebP`)
    return
  }
  const form = new FormData()
  form.append('photo', file)
  const { controller, version } = beginRequest()
  busy.value = true
  try {
    const updated = await request.post(`/student-imports/${batch.value.batch_id}/items/${activeItem.value.id}/photo`, form, { signal: controller.signal } as any) as StudentImportBatch
    if (version !== requestVersion) return
    batch.value = updated
    const refreshed = updated.items.find((item) => item.id === activeItem.value?.id)
    if (refreshed) {
      activeItem.value = refreshed
      editForm.replace_face = refreshed.replace_face
      await loadPhoto(refreshed)
    }
    showToast({ type: 'success', message: '照片已替换并重新校验' })
  } finally { if (version === requestVersion) busy.value = false }
}

const removeItem = async (item: StudentImportItem) => {
  if (!batch.value) return
  try {
    await showConfirmDialog({ title: '移除导入条目', message: `确定从本次导入中移除 ${item.student_no || `第${item.row_number}行`} 吗？`, confirmButtonColor: '#dc2626' })
  } catch { return }
  const { controller, version } = beginRequest()
  busy.value = true
  try {
    const result = await request.delete(`/student-imports/${batch.value.batch_id}/items/${item.id}`, { signal: controller.signal } as any) as StudentImportBatch
    if (version === requestVersion) updateBatch(result)
  } finally { if (version === requestVersion) busy.value = false }
}

const commitImport = async () => {
  if (!batch.value) return
  try {
    await showConfirmDialog({ title: '确认批量同步', message: `将同步 ${batch.value.summary.ready} 条合规数据，异常条目会保留但不执行。` })
  } catch { return }
  const { controller, version } = beginRequest()
  busy.value = true
  try {
    const result = await request.post(`/student-imports/${batch.value.batch_id}/commit`, undefined, { signal: controller.signal } as any) as StudentImportBatch
    if (version !== requestVersion) return
    showToast({ type: 'success', message: `同步完成，共成功 ${result.summary.synced} 条` })
    emit('synced', result)
    closeImportDialog()
  } catch (error: any) {
    if (error?.code !== 'ERR_CANCELED') return
  } finally {
    if (version === requestVersion) busy.value = false
  }
}

onBeforeUnmount(() => {
  requestVersion += 1
  activeController?.abort()
  activeController = null
  closeDetail()
})
</script>

<style scoped>
.student-import-popup { width: min(1080px, 96vw); height: min(820px, 92vh); border-radius: 8px; overflow: hidden; }
.import-workspace { height: 100%; display: flex; flex-direction: column; background: #f7f9fc; color: #24324a; }
.import-header { height: 72px; flex: 0 0 72px; display: flex; align-items: center; justify-content: space-between; padding: 0 24px; background: #fff; border-bottom: 1px solid #e6eaf0; }
.import-header h2, .detail-dialog h3 { margin: 0; font-size: 19px; color: #18243a; }
.import-header p { margin: 5px 0 0; font-size: 12px; color: #78859a; }
.icon-button, .item-actions button { width: 34px; height: 34px; border: 0; background: transparent; color: #66758c; cursor: pointer; font-size: 18px; }
.upload-body { flex: 1; padding: 32px; overflow: auto; }
.mode-tabs { display: grid; grid-template-columns: 1fr 1fr; width: 360px; margin: 0 auto 24px; padding: 3px; background: #e9edf3; border-radius: 6px; }
.mode-tabs button { height: 36px; border: 0; background: transparent; color: #65738a; cursor: pointer; border-radius: 4px; }
.mode-tabs button.active { background: #fff; color: #17345b; font-weight: 700; box-shadow: 0 1px 3px #b9c1cc80; }
.upload-zone { min-height: 330px; border: 1px dashed #aeb9c8; background: #fff; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 12px; border-radius: 8px; color: #6f7d90; }
.upload-zone strong { color: #263650; font-size: 16px; }
.upload-zone span { font-size: 13px; }
.command-button, .primary-button { border: 0; background: #1d3557; color: #fff; height: 38px; padding: 0 18px; border-radius: 6px; cursor: pointer; display: inline-flex; align-items: center; justify-content: center; gap: 7px; }
.file-pickers { width: min(680px, 90%); display: grid; grid-template-columns: 1fr 1fr; gap: 18px; }
.file-picker { height: 130px; border: 1px solid #d7dde6; background: #f9fafc; border-radius: 6px; display: flex; flex-direction: column; justify-content: center; align-items: center; gap: 12px; cursor: pointer; color: #33445e; }
.file-picker .van-icon { font-size: 28px; color: #315a8c; }
.template-row, .preview-toolbar { display: flex; justify-content: space-between; align-items: center; margin-top: 14px; font-size: 12px; color: #77849a; }
.template-row button, .preview-toolbar button { border: 0; background: transparent; color: #24578f; cursor: pointer; }
.import-footer { height: 68px; flex: 0 0 68px; display: flex; align-items: center; justify-content: space-between; padding: 0 24px; background: #fff; border-top: 1px solid #e2e7ee; font-size: 12px; color: #78859a; }
button:disabled { opacity: .45; cursor: not-allowed; }
.preview-body { flex: 1; min-height: 0; padding: 18px 24px; display: flex; flex-direction: column; }
.summary-strip { display: grid; grid-template-columns: repeat(6, 1fr); background: #fff; border: 1px solid #e2e7ee; border-radius: 6px; }
.summary-strip div { height: 66px; padding: 12px 16px; border-right: 1px solid #edf0f4; }
.summary-strip div:last-child { border-right: 0; }
.summary-strip span { display: block; font-size: 11px; color: #7b8799; }
.summary-strip strong { display: block; margin-top: 5px; font-size: 20px; color: #243650; }
.summary-strip .summary-new strong { color: #2264a7; }.summary-strip .summary-error strong { color: #c2413b; }.summary-strip .summary-ready strong { color: #19865d; }
.preview-toolbar { margin: 14px 2px 10px; }.preview-toolbar div { display: flex; gap: 14px; align-items: baseline; }.preview-toolbar strong { color: #34445d; }
.item-list { flex: 1; min-height: 0; overflow: auto; display: flex; flex-direction: column; gap: 8px; padding-right: 3px; }
.import-item { display: grid; grid-template-columns: 38px minmax(0, 1fr) auto 76px; align-items: center; min-height: 86px; padding: 12px 14px; background: #fff; border: 1px solid #e2e7ed; border-radius: 6px; }
.import-item.has-error { border-left: 3px solid #d24b45; }.import-item.is-new:not(.has-error) { border-left: 3px solid #2873b5; }
.item-state { font-size: 22px; color: #60728a; }.has-error .item-state { color: #cf433c; }
.item-title { display: flex; align-items: center; gap: 8px; }.item-title strong { color: #21324d; }
.status-tag { padding: 2px 6px; border-radius: 4px; font-size: 10px; }.status-tag.error { color: #b7322d; background: #fff0ef; }.status-tag.new { color: #1f5f9d; background: #edf6ff; }.status-tag.matched { color: #42715d; background: #edf8f2; }.status-tag.synced { color: #fff; background: #25875f; }
.item-fields { display: flex; gap: 18px; margin-top: 7px; font-size: 12px; color: #748197; }.item-error, .item-warning { margin: 6px 0 0; font-size: 11px; }.item-error { color: #bf3d37; }.item-warning { color: #a66b15; }
.item-options { display: flex; flex-direction: column; gap: 8px; margin-right: 20px; font-size: 11px; color: #617087; }.item-options label { display: flex; align-items: center; gap: 6px; }
.item-actions { display: flex; border-left: 1px solid #edf0f4; padding-left: 8px; }.item-actions .delete { color: #c24943; }
.student-detail-popup { width: min(860px, 94vw); height: 600px; border-radius: 8px; overflow: hidden; }
.detail-dialog { height: 100%; display: flex; flex-direction: column; background: #fff; }
.detail-dialog > header { height: 64px; flex: 0 0 64px; display: flex; justify-content: space-between; align-items: center; padding: 0 20px; border-bottom: 1px solid #e5e9ef; }.detail-dialog header span { font-size: 11px; color: #8994a5; }
.detail-grid { flex: 1; min-height: 0; display: grid; grid-template-columns: 1fr 1fr; grid-template-rows: 1fr auto; gap: 12px 24px; padding: 22px; }
.detail-form { overflow: auto; padding-right: 6px; display: grid; grid-template-columns: 1fr 1fr; gap: 14px; align-content: start; }.detail-form label:not(.check-line) { display: flex; flex-direction: column; gap: 6px; }.detail-form label span { font-size: 12px; color: #647188; }.detail-form input:not([type=checkbox]), .detail-form select { width: 100%; height: 36px; border: 1px solid #d7dde6; border-radius: 5px; padding: 0 10px; box-sizing: border-box; color: #273750; background: #fff; }
.check-line { grid-column: 1 / -1; display: flex; gap: 8px; align-items: center; }.detail-errors { grid-column: 1 / -1; padding: 9px 10px; background: #fff3f2; color: #b73a35; font-size: 11px; border-radius: 5px; }
.face-preview { min-width: 0; background: #f0f3f7; border: 1px solid #dfe4eb; display: flex; align-items: center; justify-content: center; overflow: hidden; border-radius: 6px; }.face-preview img { width: 100%; height: 100%; object-fit: contain; }.face-preview > div { display: flex; flex-direction: column; gap: 12px; align-items: center; color: #8995a7; font-size: 12px; }
.face-replace { grid-column: 2; display: flex; justify-content: center; }.face-replace button { height: 34px; border: 1px solid #cbd4df; background: #fff; color: #31577f; border-radius: 5px; padding: 0 12px; cursor: pointer; }
.detail-dialog > footer { height: 64px; flex: 0 0 64px; display: flex; justify-content: flex-end; align-items: center; gap: 10px; padding: 0 20px; border-top: 1px solid #e5e9ef; }.detail-dialog > footer > button:not(.primary-button) { height: 38px; padding: 0 18px; border: 1px solid #d6dce5; background: #fff; color: #526178; border-radius: 6px; cursor: pointer; }
@media (max-width: 720px) { .student-import-popup { width: 98vw; height: 94vh; }.summary-strip { grid-template-columns: repeat(3, 1fr); }.summary-strip div { border-bottom: 1px solid #edf0f4; }.import-item { grid-template-columns: 32px minmax(0,1fr) 70px; }.item-options { grid-column: 2 / -1; flex-direction: row; margin-top: 10px; }.detail-grid { grid-template-columns: 1fr; overflow: auto; }.face-preview { min-height: 220px; }.face-replace { grid-column: 1; }.student-detail-popup { height: 88vh; }.file-pickers { grid-template-columns: 1fr; }.upload-body { padding: 18px; } }
</style>
