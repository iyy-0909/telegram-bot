<template>
  <div class="settings-workspace">
    <div class="primary-grid">
      <SendSettingsPanel
        :settings="settings"
        :saving="settingsSaving"
        @submit="emit('save-settings', $event)"
      />
      <RuleSectionPanel
        v-for="section in primarySections"
        :key="section.key"
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

    <div class="rules-grid">
      <RuleSectionPanel
        v-for="section in ruleSections"
        :key="section.key"
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

    <RuleSectionPanel
      v-if="otherTypes.length"
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
</template>

<script setup>
import { computed } from "vue"
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
const primarySections = CONTENT_RULE_SECTIONS.filter((section) => section.placement === "primary")
const ruleSections = CONTENT_RULE_SECTIONS.filter((section) => section.placement === "rules")

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
</script>

<style scoped>
.settings-workspace { display: flex; flex-direction: column; gap: 12px; }
.primary-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; align-items: stretch; }
.rules-grid { display: grid; grid-template-columns: minmax(0, 3fr) minmax(360px, 2fr); gap: 12px; align-items: start; }
.primary-grid > *, .rules-grid > * { min-width: 0; height: 100%; }

@media (max-width: 1180px) {
  .primary-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .primary-grid > :first-child { grid-column: 1 / -1; }
  .rules-grid { grid-template-columns: 1fr; }
}

@media (max-width: 720px) {
  .primary-grid { grid-template-columns: 1fr; }
  .primary-grid > :first-child { grid-column: auto; }
}
</style>
