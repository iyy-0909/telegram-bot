<template>
  <div class="settings-workspace">
    <SendSettingsPanel
      :settings="settings"
      :saving="settingsSaving"
      @submit="emit('save-settings', $event)"
    />

    <section class="rules-workspace">
      <el-tabs v-model="activeSection" class="section-tabs">
        <el-tab-pane
          v-for="section in displaySections"
          :key="section.key"
          :name="section.key"
        >
          <template #label>
            <span class="tab-label">
              <span>{{ section.title }}</span>
              <span class="tab-count">{{ sectionCount(section) }}</span>
            </span>
          </template>

          <RuleSectionPanel
            :title="section.title"
            :subtitle="section.subtitle"
            :types="section.types"
            :rules="groupRules"
            :loading="loading"
            :toggling-id="togglingId"
            @add="emit('add', $event)"
            @edit="emit('edit', $event)"
            @delete="emit('delete', $event)"
            @toggle="(row, value) => emit('toggle', row, value)"
          />
        </el-tab-pane>
      </el-tabs>
    </section>
  </div>
</template>

<script setup>
import { computed, ref, watch } from "vue"
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
const activeSection = ref(CONTENT_RULE_SECTIONS[0]?.key || "")

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
  return Array.from(
    new Set(
      groupRules.value
        .map((rule) => rule.type)
        .filter((type) => type && !knownTypes.has(type)),
    ),
  )
})

const displaySections = computed(() => {
  const sections = CONTENT_RULE_SECTIONS.map((section) => ({
    ...section,
    compact: false,
  }))

  if (otherTypes.value.length) {
    sections.push({
      key: "other",
      title: "其他配置",
      subtitle: "尚未归类的配置会统一显示在这里。",
      types: otherTypes.value,
      compact: false,
    })
  }
  return sections
})

watch(
  displaySections,
  (sections) => {
    if (!sections.some((section) => section.key === activeSection.value)) {
      activeSection.value = sections[0]?.key || ""
    }
  },
  { immediate: true },
)

function sectionCount(section) {
  return groupRules.value.filter((rule) => section.types.includes(rule.type)).length
}
</script>

<style scoped>
.settings-workspace {
  display: grid;
  min-width: 0;
  gap: 16px;
}

.rules-workspace {
  min-width: 0;
}

.section-tabs {
  min-width: 0;
}

.tab-label {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.tab-count {
  display: inline-flex;
  min-width: 22px;
  height: 20px;
  align-items: center;
  justify-content: center;
  padding: 0 6px;
  border-radius: 10px;
  background: var(--el-fill-color-light);
  color: var(--el-text-color-secondary);
  font-size: 12px;
  line-height: 20px;
}

:deep(.el-tabs__header) {
  margin-bottom: 12px;
}

:deep(.el-tabs__nav-wrap::after) {
  height: 1px;
}

@media (max-width: 900px) {
  .settings-workspace {
    gap: 12px;
  }

  :deep(.el-tabs__nav-wrap) {
    overflow-x: auto;
    scrollbar-width: none;
  }

  :deep(.el-tabs__nav-wrap::-webkit-scrollbar) {
    display: none;
  }

  :deep(.el-tabs__nav-scroll) {
    min-width: max-content;
  }
}
</style>
