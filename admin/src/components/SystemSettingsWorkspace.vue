<template>
  <div ref="gridRef" class="settings-workspace">
    <div class="workspace-item workspace-item--compact">
      <SendSettingsPanel
        :settings="settings"
        :saving="settingsSaving"
        @submit="emit('save-settings', $event)"
      />
    </div>

    <div
      v-for="section in allSections"
      :key="section.key"
      class="workspace-item"
      :class="section.compact ? 'workspace-item--compact' : 'workspace-item--table'"
    >
      <RuleSectionPanel
        v-bind="section"
        :rules="groupRules"
        :loading="loading"
        :toggling-id="togglingId"
        @add="emit('add', $event)"
        @edit="emit('edit', $event)"
        @delete="emit('delete', $event)"
        @toggle="(row, value) => emit('toggle', row, value)"
      />
    </div>

    <div v-if="otherTypes.length" class="workspace-item workspace-item--table">
      <RuleSectionPanel
        title="其他配置"
        subtitle="尚未归类的新配置会自动显示在这里，现有数据不会被隐藏。"
        :types="otherTypes"
        :rules="groupRules"
        :loading="loading"
        :toggling-id="togglingId"
        @add="emit('add', $event)"
        @edit="emit('edit', $event)"
        @delete="emit('delete', $event)"
        @toggle="(row, value) => emit('toggle', row, value)"
      />
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue"
import SendSettingsPanel from "./SendSettingsPanel.vue"
import RuleSectionPanel from "./RuleSectionPanel.vue"
import { CONTENT_RULE_SECTIONS, knownContentRuleTypes } from "../config/contentRuleSections"

const props = defineProps({
  settings: { type: Object, required: true },
  templates: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
  settingsSaving: { type: Boolean, default: false },
  togglingId: { type: Number, default: null },
})

const emit = defineEmits(["save-settings", "add", "edit", "delete", "toggle"])
const allSections = CONTENT_RULE_SECTIONS
const gridRef = ref(null)
const observedItems = new Set()
const GRID_ROW_HEIGHT = 8
const GRID_GAP = 12
let resizeObserver = null

const groupRules = computed(() => props.templates
  .filter((template) => !template.parent_id)
  .map((group) => ({
    ...group,
    items: props.templates
      .filter((template) => template.parent_id === group.id)
      .sort((a, b) => a.id - b.id),
  }))
  .sort((a, b) => b.id - a.id))

const otherTypes = computed(() => {
  const knownTypes = knownContentRuleTypes()
  return Array.from(new Set(groupRules.value.map((rule) => rule.type).filter((type) => type && !knownTypes.has(type))))
})

function updateItemSpan(element) {
  const height = element.getBoundingClientRect().height
  const span = Math.max(1, Math.ceil((height + GRID_GAP) / (GRID_ROW_HEIGHT + GRID_GAP)))
  element.style.gridRowEnd = `span ${span}`
}

function syncObservedItems() {
  if (!resizeObserver || !gridRef.value) return

  const currentItems = new Set(gridRef.value.querySelectorAll(".workspace-item"))
  observedItems.forEach((element) => {
    if (!currentItems.has(element)) {
      resizeObserver.unobserve(element)
      observedItems.delete(element)
    }
  })

  currentItems.forEach((element) => {
    if (!observedItems.has(element)) {
      observedItems.add(element)
      resizeObserver.observe(element)
    }
    updateItemSpan(element)
  })
}

onMounted(() => {
  resizeObserver = new ResizeObserver((entries) => {
    entries.forEach((entry) => updateItemSpan(entry.target))
  })
  syncObservedItems()
})

watch(
  [groupRules, otherTypes],
  async () => {
    await nextTick()
    syncObservedItems()
  },
  { deep: true },
)

onBeforeUnmount(() => {
  resizeObserver?.disconnect()
  observedItems.clear()
})
</script>

<style scoped>
.settings-workspace {
  display: grid;
  grid-template-columns: repeat(12, minmax(0, 1fr));
  grid-auto-flow: dense;
  grid-auto-rows: 8px;
  column-gap: 12px;
  row-gap: 12px;
  container-type: inline-size;
}
.workspace-item {
  min-width: 0;
  align-self: start;
}
.workspace-item--compact { grid-column: span 4; }
.workspace-item--table { grid-column: span 6; }

@container (max-width: 1139px) {
  .workspace-item:first-child { grid-column: span 12; }
  .workspace-item--compact { grid-column: span 6; }
  .workspace-item--table { grid-column: span 12; }
}

@container (max-width: 680px) {
  .workspace-item--compact,
  .workspace-item--table {
    grid-column: span 12;
  }
}
</style>
