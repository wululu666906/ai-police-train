<template>
  <svg
    class="ops-icon"
    :width="size"
    :height="size"
    viewBox="0 0 24 24"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
    aria-hidden="true"
  >
    <g v-if="name === 'shield'">
      <path d="M12 3.2 5.4 5.7v5.2c0 4.2 2.7 8.1 6.6 9.4 3.9-1.3 6.6-5.2 6.6-9.4V5.7L12 3.2Z" />
      <path d="m9.2 12 1.8 1.8 3.9-4.1" />
    </g>
    <g v-else-if="name === 'bookmark-plus'">
      <path d="M14.5 10.6504H9.5" />
      <path d="M12 8.21094V13.2109" />
      <path d="M16.8199 2H7.17995C5.04995 2 3.31995 3.74 3.31995 5.86V19.95C3.31995 21.75 4.60995 22.51 6.18995 21.64L11.0699 18.93C11.5899 18.64 12.4299 18.64 12.9399 18.93L17.8199 21.64C19.3999 22.52 20.6899 21.76 20.6899 19.95V5.86C20.6799 3.74 18.9499 2 16.8199 2Z" />
    </g>
    <g v-else-if="name === 'user'">
      <path d="M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8Z" />
      <path d="M4.8 20c.8-3.2 3.4-5 7.2-5s6.4 1.8 7.2 5" />
    </g>
    <g v-else-if="name === 'lock'">
      <path d="M7.2 10V8a4.8 4.8 0 0 1 9.6 0v2" />
      <path d="M6.5 10h11c1 0 1.8.8 1.8 1.8v6.1c0 1-.8 1.8-1.8 1.8h-11c-1 0-1.8-.8-1.8-1.8v-6.1c0-1 .8-1.8 1.8-1.8Z" />
      <path d="M12 14.2v2.2" />
    </g>
    <g v-else-if="name === 'users'">
      <path d="M9.2 11.4a3.4 3.4 0 1 0 0-6.8 3.4 3.4 0 0 0 0 6.8Z" />
      <path d="M3.8 19.4c.5-2.8 2.5-4.5 5.4-4.5 2.8 0 4.9 1.7 5.4 4.5" />
      <path d="M16.1 10.9a2.8 2.8 0 1 0-.8-5.4" />
      <path d="M16.7 14.3c2 .4 3.2 1.8 3.5 4" />
    </g>
    <g v-else-if="name === 'search'">
      <path d="M11 18a7 7 0 1 0 0-14 7 7 0 0 0 0 14Z" />
      <path d="m16.2 16.2 3.5 3.5" />
    </g>
    <g v-else-if="name === 'refresh'">
      <path d="M19.2 8.2A7.8 7.8 0 0 0 5.1 7.1L4 9.4" />
      <path d="M4 4.8v4.6h4.6" />
      <path d="M4.8 15.8a7.8 7.8 0 0 0 14.1 1.1l1.1-2.3" />
      <path d="M20 19.2v-4.6h-4.6" />
    </g>
    <g v-else-if="name === 'add'">
      <path d="M12 5v14" />
      <path d="M5 12h14" />
    </g>
    <g v-else-if="name === 'batch'">
      <path d="M5.8 7.5h8.4c1 0 1.8.8 1.8 1.8v8.4c0 1-.8 1.8-1.8 1.8H5.8c-1 0-1.8-.8-1.8-1.8V9.3c0-1 .8-1.8 1.8-1.8Z" />
      <path d="M8 4.5h8.2c2.1 0 3.3 1.2 3.3 3.3V16" />
      <path d="M10 11.3v4.4" />
      <path d="M7.8 13.5h4.4" />
    </g>
    <g v-else-if="name === 'edit'">
      <path d="M13.2 5.2H7.1c-1.5 0-2.6 1.1-2.6 2.6v9.1c0 1.5 1.1 2.6 2.6 2.6h9.1c1.5 0 2.6-1.1 2.6-2.6v-6.1" />
      <path d="m14.7 4.7 4.6 4.6" />
      <path d="M19.8 4.2c-.8-.8-2.1-.8-2.9 0l-7 7-.8 3.8 3.8-.8 7-7c.7-.8.7-2.1-.1-3Z" />
    </g>
    <g v-else-if="name === 'key'">
      <path d="M14.1 10.8a4.4 4.4 0 1 0-2.7 4.1" />
      <path d="M14.2 10.8h5.3v3" />
      <path d="M17.2 10.8v2.2" />
      <path d="M7.9 12h.1" />
    </g>
    <g v-else-if="name === 'trash'">
      <path d="M5 7h14" />
      <path d="M9.5 7V5.8c0-.7.5-1.2 1.2-1.2h2.6c.7 0 1.2.5 1.2 1.2V7" />
      <path d="m7 7 .7 11.1c.1 1 1 1.8 2 1.8h4.6c1 0 1.9-.8 2-1.8L17 7" />
      <path d="M10.4 11v5" />
      <path d="M13.6 11v5" />
    </g>
    <g v-else-if="name === 'logout'">
      <path d="M10.2 4.8H7.5c-1.5 0-2.6 1.1-2.6 2.6v9.2c0 1.5 1.1 2.6 2.6 2.6h2.7" />
      <path d="M14.2 8.2 18 12l-3.8 3.8" />
      <path d="M18 12H9.6" />
    </g>
  </svg>
</template>

<script setup lang="ts">
withDefaults(defineProps<{ name: string; size?: number | string }>(), { size: 20 })
</script>

<style scoped>
.ops-icon {
  display: inline-block;
  flex: none;
  stroke: currentColor;
  stroke-width: 1.7;
  stroke-linecap: round;
  stroke-linejoin: round;
}
</style>
