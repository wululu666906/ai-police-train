<template>
  <section class="scene-opening-config">
    <div class="scene-opening-config__header">
      <div>
        <h4>场景开场对话</h4>
        <p>进入场景后按顺序生成角色气泡，最多配置 3 名角色。</p>
      </div>
      <van-switch :model-value="model.enabled" size="20" @update:model-value="patch({ enabled: $event })" />
    </div>
    <template v-if="model.enabled">
      <div class="scene-opening-config__row">
        <label>生成模式</label>
        <van-radio-group :model-value="model.mode" direction="horizontal" @update:model-value="patch({ mode: $event })">
          <van-radio name="dynamic">动态生成</van-radio>
          <van-radio name="preset">预设台词</van-radio>
        </van-radio-group>
      </div>
      <label class="scene-opening-config__field"><span>发言角色（按选择顺序）</span>
        <select v-model="selectedId" @change="addSpeaker">
          <option value="">选择角色</option>
          <option v-for="role in availableRoles" :key="roleKey(role)" :value="roleKey(role)">{{ role.name }}</option>
        </select>
      </label>
      <ol class="scene-opening-config__speakers">
        <li v-for="(speaker, index) in selectedSpeakers" :key="speaker.key">
          <span>{{ index + 1 }}. {{ speaker.name }}</span>
          <van-button icon="cross" plain hairline size="mini" @click="removeSpeaker(index)" />
        </li>
      </ol>
      <label class="scene-opening-config__field"><span>导演约束</span><textarea :value="model.director_note" rows="2" placeholder="例如：先安抚情绪，再交代最紧急事实" @input="patch({ director_note: ($event.target as HTMLTextAreaElement).value })" /></label>
      <div v-if="model.mode === 'preset'" class="scene-opening-config__presets">
        <label v-for="speaker in selectedSpeakers" :key="speaker.key" class="scene-opening-config__field"><span>{{ speaker.name }}的预设台词</span><textarea :value="presetText(speaker)" rows="2" @input="setPreset(speaker, ($event.target as HTMLTextAreaElement).value)" /></label>
      </div>
    </template>
  </section>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
const props = defineProps<{ modelValue?: any; roles?: any[] }>()
const emit = defineEmits<{ (event: 'update:modelValue', value: any): void }>()
const selectedId = ref('')
const model = computed({
  get: () => ({ enabled: true, mode: 'dynamic', speaker_role_ids: [], speaker_names: [], director_note: '', preset_turns: [], ...(props.modelValue || {}) }),
  set: (value) => emit('update:modelValue', value),
})
const patch = (changes: Record<string, any>) => { model.value = { ...model.value, ...changes } }
const roleKey = (role: any) => role?.id ? `id:${role.id}` : `name:${String(role?.name || '')}`
const selectedSpeakers = computed(() => [
  ...(model.value.speaker_role_ids || []).map((id: any) => ({ key: `id:${id}`, id, name: props.roles?.find((role) => String(role.id) === String(id))?.name || '相关人员' })),
  ...(model.value.speaker_names || []).map((name: string) => ({ key: `name:${name}`, name })),
].slice(0, 3))
const availableRoles = computed(() => (props.roles || []).filter((role) => role?.name && !selectedSpeakers.value.some((speaker) => speaker.key === roleKey(role))))
const addSpeaker = () => {
  if (!selectedId.value || selectedSpeakers.value.length >= 3) return
  if (selectedId.value.startsWith('id:')) patch({ speaker_role_ids: [...model.value.speaker_role_ids, Number(selectedId.value.slice(3))] })
  else patch({ speaker_names: [...model.value.speaker_names, selectedId.value.slice(5)] })
  selectedId.value = ''
}
const removeSpeaker = (index: number) => {
  const speaker = selectedSpeakers.value[index]
  if (speaker?.id) patch({ speaker_role_ids: model.value.speaker_role_ids.filter((id: any) => String(id) !== String(speaker.id)) })
  else patch({ speaker_names: model.value.speaker_names.filter((name: string) => name !== speaker?.name) })
}
const presetText = (speaker: any) => model.value.preset_turns?.find((item: any) => speaker.id ? String(item.speaker_role_id) === String(speaker.id) : item.speaker_name === speaker.name)?.content || ''
const setPreset = (speaker: any, content: string) => { const turns = [...(model.value.preset_turns || [])]; const found = turns.find((item: any) => speaker.id ? String(item.speaker_role_id) === String(speaker.id) : item.speaker_name === speaker.name); if (found) found.content = content; else turns.push(speaker.id ? { speaker_role_id: speaker.id, content } : { speaker_name: speaker.name, content }); patch({ preset_turns: turns }) }
</script>

<style scoped>
.scene-opening-config { margin-top: 16px; padding: 14px; border: 1px solid #e5e7eb; border-radius: 8px; background: #fff; }
.scene-opening-config__header, .scene-opening-config__row { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.scene-opening-config h4 { margin: 0; font-size: 15px; }.scene-opening-config p { margin: 4px 0 12px; color: #6b7280; font-size: 12px; }
.scene-opening-config__field { display: grid; gap: 6px; margin-top: 12px; font-size: 13px; }.scene-opening-config select, textarea { width: 100%; border: 1px solid #d1d5db; border-radius: 4px; padding: 7px; font: inherit; }.scene-opening-config__speakers { margin: 8px 0 0; padding-left: 20px; }.scene-opening-config__speakers li { display: flex; justify-content: space-between; align-items: center; margin: 4px 0; }
</style>
