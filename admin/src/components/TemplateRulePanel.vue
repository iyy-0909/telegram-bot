<template>
  <div class="template-panel">
    <div class="template-panel-header">
      <div>
        <div class="template-panel-title">内容模板规则</div>
        <div class="template-panel-desc">
          AI 改写完成后，再按 head、body、footer 追加内容。只选择规则时随机取一条；选择指定内容时固定使用该内容。
        </div>
      </div>
    </div>

    <div class="template-grid">
      <div
        v-for="section in sections"
        :key="section.type"
        class="template-card"
        :class="{ active: values[section.enabledKey] }"
      >
        <div class="template-card-top">
          <div>
            <div class="template-type">{{ section.title }}</div>
            <div class="template-desc">{{ section.desc }}</div>
          </div>
          <el-switch
            :model-value="values[section.enabledKey]"
            @update:model-value="value => update(section.enabledKey, value)"
          />
        </div>

        <el-select
          :model-value="values[section.groupKey]"
          :disabled="!values[section.enabledKey]"
          clearable
          filterable
          class="template-select"
          placeholder="选择规则"
          @update:model-value="value => updateGroup(section, value)"
        >
          <el-option
            v-for="group in groupsByType(section.type)"
            :key="group.id"
            :label="groupLabel(group)"
            :value="group.id"
          />
        </el-select>

        <el-select
          :model-value="values[section.itemKey]"
          :disabled="!values[section.enabledKey] || !values[section.groupKey]"
          clearable
          filterable
          class="template-select"
          placeholder="规则内随机"
          @update:model-value="value => update(section.itemKey, value)"
        >
          <el-option label="规则内随机" value="" />
          <el-option
            v-for="item in itemsByGroup(section.type, values[section.groupKey])"
            :key="item.id"
            :label="itemLabel(item)"
            :value="item.id"
          />
        </el-select>

        <div class="template-hint">
          {{ hintText(section) }}
        </div>

        <div
          v-if="section.type === 'footer'"
          class="footer-spacing-option"
          :class="{ disabled: !values[section.enabledKey] }"
        >
          <div>
            <div class="footer-spacing-label">Footer 前保留空行</div>
            <div class="footer-spacing-help">关闭后，Footer 将紧接上一段的下一行。</div>
          </div>
          <el-switch
            :model-value="values.footer_leading_blank_line !== false"
            :disabled="!values[section.enabledKey]"
            @update:model-value="value => update('footer_leading_blank_line', value)"
          />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
const props = defineProps({
  values: {
    type: Object,
    required: true,
  },
  templates: {
    type: Array,
    default: () => [],
  },
})

const emit = defineEmits([
  "update",
])

const sections = [
  {
    type: "head",
    title: "Head 头部",
    desc: "插入到原文最前面",
    enabledKey: "use_random_head",
    groupKey: "selected_head_template_group_id",
    itemKey: "selected_head_template_id",
  },
  {
    type: "body",
    title: "Body 正文补充",
    desc: "插入到原文后、footer 前",
    enabledKey: "use_random_body",
    groupKey: "selected_body_template_group_id",
    itemKey: "selected_body_template_id",
  },
  {
    type: "footer",
    title: "Footer 底部",
    desc: "插入到内容最后",
    enabledKey: "use_random_footer",
    groupKey: "selected_footer_template_group_id",
    itemKey: "selected_footer_template_id",
  },
]

function update(key, value) {
  emit("update", { key, value: normalizeTemplateValue(value) })
}

function updateGroup(section, value) {
  emit("update", { key: section.groupKey, value: normalizeTemplateValue(value) })
  emit("update", { key: section.itemKey, value: null })
}

function groupsByType(type) {
  return props.templates.filter(
    (template) => template.type === type && template.enabled && !template.parent_id,
  )
}

function itemsByGroup(type, groupId) {
  if (!groupId) return []

  return props.templates.filter(
    (template) => (
      template.type === type
      && template.enabled
      && Number(template.parent_id) === Number(groupId)
      && String(template.content || "").trim()
    ),
  )
}

function groupLabel(group) {
  const count = props.templates.filter((item) => Number(item.parent_id) === Number(group.id)).length
  return `${group.name || `规则 ${group.id}`} - ${count} 条内容`
}

function itemLabel(item) {
  const name = item.name || `内容 ${item.id}`
  const preview = String(item.content || "").trim().replace(/\s+/g, " ").slice(0, 24)
  return preview ? `${name} - ${preview}` : name
}

function hintText(section) {
  if (!props.values[section.enabledKey]) {
    return "未启用，不会添加该段模板。"
  }

  if (!props.values[section.groupKey]) {
    return "已启用但未选择规则，发送时会跳过该段。"
  }

  if (!props.values[section.itemKey]) {
    return "已选择规则，发送时会在该规则内容中随机取一条。"
  }

  return "已指定内容，发送时固定使用这一条。"
}

function normalizeTemplateValue(value) {
  if (value === "" || value === undefined) {
    return null
  }

  return value
}
</script>

<style scoped>
.template-panel {
  padding: 12px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #f9fafb;
}

.template-panel-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.template-panel-title {
  font-size: 14px;
  font-weight: 600;
  color: #303133;
}

.template-panel-desc {
  margin-top: 3px;
  font-size: 12px;
  color: #6b7280;
  line-height: 1.5;
}

.template-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.template-card {
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-width: 0;
  padding: 12px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #ffffff;
}

.template-card.active {
  border-color: #b3d8ff;
  background: #fbfdff;
}

.template-card-top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
}

.template-type {
  font-size: 13px;
  font-weight: 600;
  color: #303133;
}

.template-desc,
.template-hint {
  font-size: 12px;
  color: #909399;
  line-height: 1.45;
}

.template-select {
  width: 100%;
}

.footer-spacing-option {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding-top: 10px;
  border-top: 1px solid #ebeef5;
}

.footer-spacing-option.disabled {
  opacity: 0.6;
}

.footer-spacing-label {
  font-size: 12px;
  font-weight: 600;
  color: #606266;
}

.footer-spacing-help {
  margin-top: 2px;
  font-size: 11px;
  line-height: 1.4;
  color: #909399;
}

@media (max-width: 900px) {
  .template-grid {
    grid-template-columns: 1fr;
  }
}
</style>
