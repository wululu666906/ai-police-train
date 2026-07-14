<template>
  <div
    class="role-speaking-avatar"
    :class="{
      'role-speaking-avatar--live': speaking || thinking,
      'role-speaking-avatar--speaking': speaking && !thinking,
      'role-speaking-avatar--thinking': thinking,
      'role-speaking-avatar--primary': primary,
      'role-speaking-avatar--risk': risk,
    }"
    :style="{ '--avatar-size': `${size}px`, '--avatar-bg': avatarBgColor }"
  >
    <span v-if="speaking || thinking" class="role-speaking-avatar__halo" aria-hidden="true">
      <span class="role-speaking-avatar__halo-core"></span>
      <span class="role-speaking-avatar__halo-ring role-speaking-avatar__halo-ring--a"></span>
      <span class="role-speaking-avatar__halo-ring role-speaking-avatar__halo-ring--b"></span>
    </span>
    <div class="role-speaking-avatar__circle">
      <img
        v-if="!showFallback"
        :src="resolvedAvatarUrl"
        :alt="name"
        class="role-speaking-avatar__img"
        @error="onImageError"
      />
      <span v-else class="role-speaking-avatar__initial">{{ initial }}</span>
    </div>

    <span v-if="risk && !speaking && !thinking" class="role-speaking-avatar__risk-dot" title="失控风险偏高" />
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { resolveMediaUrl } from '../utils/media'

const AVATAR_PALETTE = [
  '#4F46E5', '#0891B2', '#059669', '#D97706', '#DC2626',
  '#7C3AED', '#0E7490', '#047857', '#B45309', '#BE123C',
  '#6366F1', '#0284C7', '#16A34A', '#D97706', '#E11D48',
  '#8B5CF6', '#0EA5E9', '#22C55E', '#F59E0B', '#EF4444',
]

const props = withDefaults(
  defineProps<{
    name: string
    avatarUrl?: string
    avatarId?: number
    speaking?: boolean
    thinking?: boolean
    primary?: boolean
    risk?: boolean
    size?: number
  }>(),
  {
    speaking: false,
    thinking: false,
    primary: false,
    risk: false,
    size: 44,
  }
)

const imageLoadFailed = ref(false)

const initial = computed(() => {
  const text = String(props.name || '').trim()
  return text ? text.slice(0, 1) : '?'
})

const avatarBgColor = computed(() => {
  if (props.avatarId != null && props.avatarId >= 1 && props.avatarId <= AVATAR_PALETTE.length) {
    return AVATAR_PALETTE[props.avatarId - 1]
  }
  const hash = props.name.split('').reduce((acc, c) => acc + c.charCodeAt(0), 0)
  return AVATAR_PALETTE[hash % AVATAR_PALETTE.length]
})

const resolvedAvatarUrl = computed(() => resolveMediaUrl(props.avatarUrl))

const showFallback = computed(() => {
  return !resolvedAvatarUrl.value || imageLoadFailed.value
})

function onImageError() {
  imageLoadFailed.value = true
}
</script>

<style scoped>
.role-speaking-avatar {
  position: relative;
  width: var(--avatar-size);
  height: var(--avatar-size);
  flex-shrink: 0;
}

.role-speaking-avatar__halo {
  position: absolute;
  inset: -6px;
  z-index: 0;
  pointer-events: none;
}

.role-speaking-avatar__halo-core,
.role-speaking-avatar__halo-ring {
  position: absolute;
  inset: 0;
  border-radius: 50%;
}

.role-speaking-avatar__halo-core {
  border: 2px solid rgba(83, 130, 201, 0.45);
  background: radial-gradient(circle, rgba(83, 130, 201, 0.18) 0%, rgba(83, 130, 201, 0.02) 62%, rgba(83, 130, 201, 0) 74%);
}

.role-speaking-avatar__halo-ring {
  inset: -2px;
  border: 1px solid rgba(83, 130, 201, 0.34);
  opacity: 0;
  transform: scale(0.9);
}

.role-speaking-avatar__circle {
  position: relative;
  z-index: 1;
  width: 100%;
  height: 100%;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--avatar-bg, linear-gradient(160deg, #f4f7fb 0%, #e6edf5 100%));
  border: 2px solid color-mix(in srgb, var(--avatar-bg, #c9d4e3) 60%, transparent);
  box-sizing: border-box;
  overflow: hidden;
  transition:
    border-color 0.25s ease,
    box-shadow 0.25s ease;
}

.role-speaking-avatar--primary .role-speaking-avatar__circle {
  border-color: rgba(255, 200, 50, 0.6);
  box-shadow: 0 0 0 1px rgba(255, 200, 50, 0.15);
}

.role-speaking-avatar--risk:not(.role-speaking-avatar--live) .role-speaking-avatar__circle {
  border-color: #e8b4b0;
}

.role-speaking-avatar--speaking .role-speaking-avatar__circle {
  border-color: #4b78c2;
  box-shadow: 0 0 0 2px rgba(22, 93, 255, 0.12);
}

.role-speaking-avatar--thinking .role-speaking-avatar__circle {
  border-color: #9cb6dc;
  box-shadow: 0 0 0 1px rgba(134, 173, 225, 0.2);
}

.role-speaking-avatar__img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.role-speaking-avatar__initial {
  font-size: calc(var(--avatar-size) * 0.4);
  font-weight: 700;
  color: #fff;
  line-height: 1;
  letter-spacing: 0.02em;
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.15);
}

.role-speaking-avatar--speaking .role-speaking-avatar__halo {
  filter: drop-shadow(0 0 10px rgba(71, 120, 196, 0.26));
}

.role-speaking-avatar--speaking .role-speaking-avatar__halo-core {
  animation: halo-core-breathe 1.9s cubic-bezier(0.25, 0.1, 0.25, 1) infinite;
}

.role-speaking-avatar--speaking .role-speaking-avatar__halo-ring--a {
  animation: halo-wave 2.2s ease-out infinite;
}

.role-speaking-avatar--speaking .role-speaking-avatar__halo-ring--b {
  animation: halo-wave 2.2s ease-out infinite 1.1s;
}

.role-speaking-avatar--thinking .role-speaking-avatar__halo {
  filter: none;
}

.role-speaking-avatar--thinking .role-speaking-avatar__halo-core {
  border-color: rgba(134, 173, 225, 0.3);
  background: radial-gradient(circle, rgba(134, 173, 225, 0.13) 0%, rgba(134, 173, 225, 0) 70%);
  animation: halo-thinking 1.6s ease-in-out infinite;
}

.role-speaking-avatar--thinking .role-speaking-avatar__halo-ring {
  border-color: rgba(134, 173, 225, 0.23);
  animation: none;
  opacity: 0;
}

.role-speaking-avatar__risk-dot {
  position: absolute;
  right: -1px;
  bottom: -1px;
  z-index: 3;
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: #f53f3f;
  border: 2px solid #fff;
}

@keyframes halo-core-breathe {
  0%,
  100% {
    transform: scale(0.94);
    opacity: 0.58;
  }
  50% {
    transform: scale(1.04);
    opacity: 1;
  }
}

@keyframes halo-wave {
  0% {
    transform: scale(0.9);
    opacity: 0;
  }
  20% {
    opacity: 0.56;
  }
  100% {
    transform: scale(1.28);
    opacity: 0;
  }
}

@keyframes halo-thinking {
  0%,
  100% {
    transform: scale(0.96);
    opacity: 0.48;
  }
  50% {
    transform: scale(1.01);
    opacity: 1;
  }
}

@media (prefers-reduced-motion: reduce) {
  .role-speaking-avatar--speaking .role-speaking-avatar__halo-core,
  .role-speaking-avatar--speaking .role-speaking-avatar__halo-ring--a,
  .role-speaking-avatar--speaking .role-speaking-avatar__halo-ring--b,
  .role-speaking-avatar--thinking .role-speaking-avatar__halo-core {
    animation: none;
  }
}
</style>
