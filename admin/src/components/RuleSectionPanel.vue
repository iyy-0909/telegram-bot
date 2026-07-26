<template>
  <el-card class="rule-section" :class="{ 'rule-section--compact': compact }">
    <template #header>
      <div class="section-header">
        <div>
          <div class="section-title">{{ title }}</div>
          <div class="section-subtitle">{{ subtitle }}</div>
        </div>
        <el-button type="primary" :icon="Plus" @click="emit('add', activeType)">
          新增
        </el-button>
      </div>
    </template>

    <el-tabs v-if="types.length > 1" v-model="activeType" class="type-tabs">
      <el-tab-pane
        v-for="type in types"
        :key="type"
        :label="typeMeta(type).label"
        :name="type"
      />
    </el-tabs>

    <div v-if="compact" v-loading="loading" class="compact-rule-list">
      <div v-if="visibleRules.length">
        <article v-for="row in visibleRules" :key="row.id" class="compact-rule-item">
          <div class="compact-rule-head">
            <div>
              <strong>{{ row.name || `${typeMeta(row.type).label}配置` }}</strong>
              <span>{{ ruleSummary(row) }}</span>
            </div>
            <el-switch
              :model-value="row.enabled"
              :loading="togglingId === row.id"
              @change="value => emit('toggle', row, value)"
            />
          </div>
          <div class="compact-rule-actions">
            <el-button text type="primary" @click="emit('edit', row)">编辑</el-button>
            <el-button text type="danger" @click="emit('delete', row.id)">删除</el-button>
          </div>
        </article>
      </div>
      <el-empty v-else :image-size="58" :description="`暂无${typeMeta(activeType).label}配置，请点击新增创建。`" />
    </div>

    <el-table
      v-else
      :data="visibleRules"
      v-loading="loading"
      border
      stripe
      row-key="id"
      height="420"
      :empty-text="`暂无${typeMeta(activeType).label}配置，请点击新增创建。`"
    >
      <el-table-column prop="name" label="配置名称" min-width="145" show-overflow-tooltip />
      <el-table-column v-if="types.length > 1" label="类型" width="82" align="center">
        <template #default="{ row }">
          <el-tag :type="typeMeta(row.type).tagType" size="small">{{ typeMeta(row.type).label }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="内容" min-width="180" show-overflow-tooltip>
        <template #default="{ row }">{{ ruleSummary(row) }}</template>
      </el-table-column>
      <el-table-column label="启用" width="72" align="center">
        <template #default="{ row }">
          <el-switch
            :model-value="row.enabled"
            :loading="togglingId === row.id"
            @change="value => emit('toggle', row, value)"
          />
        </template>
      </el-table-column>
      <el-table-column label="操作" width="116" fixed="right">
        <template #default="{ row }">
          <div class="row-actions">
            <el-button text type="primary" @click="emit('edit', row)">编辑</el-button>
            <el-button text type="danger" @click="emit('delete', row.id)">删除</el-button>
          </div>
        </template>
      </el-table-column>
    </el-table>
  </el-card>
</template>

<script setup>
import { computed, ref, watch } from "vue"
import { Plus } from "@element-plus/icons-vue"
import { CONTENT_RULE_TYPE_META } from "../config/contentRuleSections"

const props = defineProps({
  title: { type: String, required: true },
  subtitle: { type: String, default: "" },
  rules: { type: Array, default: () => [] },
  types: { type: Array, required: true },
  compact: { type: Boolean, default: false },
  loading: { type: Boolean, default: false },
  togglingId: { type: Number, default: null },
})

const emit = defineEmits(["add", "edit", "delete", "toggle"])
const activeType = ref(props.types[0] || "")

watch(
  () => props.types,
  (types) => {
    if (!types.includes(activeType.value)) activeType.value = types[0] || ""
  },
  { deep: true },
)

const visibleRules = computed(() => props.rules.filter((rule) => rule.type === activeType.value))

function typeMeta(type) {
  return CONTENT_RULE_TYPE_META[type] || { label: type || "其他", tagType: "info" }
}

function ruleSummary(rule) {
  const contents = (rule.items || []).map((item) => String(item.content || "").trim()).filter(Boolean)
  if (!contents.length) return "-"

  if (rule.type === "contact") {
    const config = parseJson(contents[0])
    const actions = [
      config.remove_phone && "手机号",
      config.remove_links && "链接",
      config.remove_usernames && "@用户名",
      config.remove_keywords && "关键词行",
    ].filter(Boolean)
    const count = Array.isArray(config.keywords) ? config.keywords.length : 0
    return `删除：${actions.join("、") || "未选择"}；关键词 ${count} 个`
  }

  if (rule.type === "link") {
    const config = parseJson(contents[0])
    const labels = { target_link: "目标链接", downgrade: "降级文本", keep: "保留", delete: "删除", replace: "替换" }
    const values = Object.entries(config)
      .filter(([key]) => !key.endsWith("_replacement"))
      .map(([, value]) => labels[value] || value)
      .filter(Boolean)
    return `已配置 ${values.length} 类链接：${Array.from(new Set(values)).join("、") || "未设置"}`
  }

  if (rule.type === "filter") {
    const keywords = contents.flatMap((content) => content.split(/\r?\n/).map((item) => item.trim()).filter(Boolean))
    return `${keywords.length} 个关键词：${keywords.slice(0, 4).join("、")}`
  }

  return `${contents.length} 条内容：${stripHtml(contents.slice(0, 2).join(" / "))}`
}

function parseJson(value) {
  try {
    const parsed = JSON.parse(value || "{}")
    return parsed && typeof parsed === "object" ? parsed : {}
  } catch {
    return {}
  }
}

function stripHtml(value) {
  return String(value || "").replace(/<[^>]+>/g, "").trim()
}
</script>

<style scoped>
.rule-section { min-width: 0; border-radius: 8px; }
.section-header { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.section-title { color: var(--el-text-color-primary); font-size: 16px; font-weight: 600; }
.section-subtitle { margin-top: 4px; color: var(--el-text-color-secondary); font-size: 12px; line-height: 1.45; }
.type-tabs { margin-top: -8px; }
.row-actions { display: flex; align-items: center; white-space: nowrap; }
.row-actions .el-button { margin-left: 0; }
.compact-rule-list {
  min-width: 0;
  min-height: 238px;
  max-height: 238px;
  overflow-x: hidden;
  overflow-y: auto;
}
.compact-rule-item { padding: 12px 0; border-bottom: 1px solid var(--el-border-color-lighter); }
.compact-rule-item:last-child { border-bottom: 0; }
.compact-rule-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; }
.compact-rule-head > div { min-width: 0; }
.compact-rule-head strong, .compact-rule-head span { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.compact-rule-head span { margin-top: 5px; color: var(--el-text-color-secondary); font-size: 12px; }
.compact-rule-actions { display: flex; justify-content: flex-end; margin-top: 8px; }
.compact-rule-actions .el-button { margin-left: 0; }
:deep(.el-table .cell) { white-space: nowrap; }

@media (max-width: 900px) {
  .section-header { align-items: stretch; flex-direction: column; }
}
</style>
