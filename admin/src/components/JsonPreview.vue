<template>
  <pre class="json-preview">{{ formatted }}</pre>
</template>

<script setup>
import { computed } from "vue"

const props = defineProps({
  value: {
    type: [Object, Array, String, Number, Boolean],
    default: null,
  },
})

const formatted = computed(() => {
  try {
    if (typeof props.value === "string") {
      return JSON.stringify(JSON.parse(props.value), null, 2)
    }
    return JSON.stringify(props.value, null, 2)
  } catch {
    return String(props.value ?? "")
  }
})
</script>

<style scoped>
.json-preview {
  max-height: 260px;
  margin: 0;
  padding: 10px 12px;
  overflow: auto;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  background: #f9fafb;
  color: #374151;
  font-family: var(--mono, ui-monospace, Consolas, monospace);
  font-size: 12px;
  line-height: 1.5;
  white-space: pre-wrap;
}
</style>
