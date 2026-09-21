<template>
  <el-card class="prompt-card" shadow="never">
    <template #header>
      <div class="card-header">
        <div>
          <div class="card-title">提示词库</div>
          <div class="card-subtitle">
            固定模式按任务选择；自动模式按适用类型匹配最近保存且启用的提示词，未配置时使用内置规则。
          </div>
        </div>
        <request-button type="primary" @click="emit('add')">新增提示词</request-button>
      </div>
    </template>

    <AiCommonRulesEditor :refreshing="loading" />

    <el-alert
      v-if="defaultPrompt"
      type="success"
      :closable="false"
      show-icon
      :title="`当前系统默认：${defaultPrompt.name}`"
      class="default-alert"
    />

    <p v-if="compact" class="card-subtitle">左右滑动表格查看适用类型和操作。</p>
    <el-table
      :data="prompts"
      v-loading="loading"
      height="520"
      empty-text="暂无提示词，请点击“新增提示词”创建。"
    >
      <el-table-column label="提示词名称" min-width="190">
        <template #default="{ row }">
          <div class="name-cell">
            <span class="prompt-name">{{ row.name }}</span>
            <el-tag v-if="row.is_default" type="success" size="small">系统默认</el-tag>
            <el-tag v-else :type="row.enabled ? 'success' : 'info'" size="small">
              {{ row.enabled ? "已启用" : "已停用" }}
            </el-tag>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="适用类型" width="130">
        <template #default="{ row }"><el-tag type="info">{{ contentTypeLabel(row.content_type) }}</el-tag></template>
      </el-table-column>
      <el-table-column label="内容预览" min-width="260" show-overflow-tooltip>
        <template #default="{ row }">
          <span class="content-preview">{{ compactContent(row.content) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="固定引用" width="110" align="center">
        <template #default="{ row }">{{ row.usage_count || 0 }} 个</template>
      </el-table-column>
      <el-table-column label="更新时间" width="170">
        <template #default="{ row }">{{ formatTime(row.updated_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="250" :fixed="compact ? false : 'right'">
        <template #default="{ row }">
          <request-button link type="primary" @click="emit('edit', row)">编辑</request-button>
          <request-button
            v-if="!row.is_default"
            link
            type="primary"
            :loading="defaultingId === row.id"
            :disabled="!row.enabled"
            @click="emit('set-default', row)"
          >
            设为默认
          </request-button>
          <el-popconfirm
            v-if="!row.is_default"
            :title="row.usage_count ? `该提示词正被 ${row.usage_count} 个任务使用，暂时不能删除。` : '确定删除这个提示词吗？删除后无法恢复。'"
            :disabled="Boolean(row.usage_count)"
            @confirm="emit('delete', row)"
          >
            <template #reference>
              <request-button
                link
                type="danger"
                :loading="deletingId === row.id"
                :disabled="Boolean(row.usage_count)"
              >
                删除
              </request-button>
            </template>
          </el-popconfirm>
        </template>
      </el-table-column>
    </el-table>
  </el-card>
</template>

<script setup>
import { useRequestEmit } from '../../../frontend-shared/requestActions.mjs'

import { computed, onBeforeUnmount, onMounted, ref } from "vue"
import { contentTypeLabel } from "../config/aiContentTypes"
import AiCommonRulesEditor from "./AiCommonRulesEditor.vue"

const props = defineProps({
  requestActions: { type: Object, default: () => ({}) },
  prompts: { type: Array, default: () => [] },
  loading: Boolean,
  deletingId: { type: Number, default: null },
  defaultingId: { type: Number, default: null },
})

const rawEmit = defineEmits(["add", "edit", "delete", "set-default"])
const emit = useRequestEmit(rawEmit, props)
const defaultPrompt = computed(() => props.prompts.find((item) => item.is_default))
const compact = ref(false)
const mediaQuery = window.matchMedia("(max-width: 900px)")
const updateCompact = () => { compact.value = mediaQuery.matches }
onMounted(() => { updateCompact(); mediaQuery.addEventListener("change", updateCompact) })
onBeforeUnmount(() => mediaQuery.removeEventListener("change", updateCompact))

function compactContent(value) {
  return String(value || "").replace(/\s+/g, " ").trim()
}

function formatTime(value) {
  if (!value) return "—"
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return String(value)
  const pad = (number) => String(number).padStart(2, "0")
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`
}
</script>

<style scoped>
.prompt-card {
  border-radius: 8px;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.card-title {
  color: var(--el-text-color-primary);
  font-size: 16px;
  font-weight: 600;
}

.card-subtitle {
  margin-top: 4px;
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

.default-alert {
  margin-bottom: 12px;
}

.name-cell {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.prompt-name,
.content-preview {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.prompt-name {
  color: var(--el-text-color-primary);
  font-weight: 600;
}

@media (max-width: 900px) {
  .card-header {
    align-items: stretch;
    flex-direction: column;
  }

  .prompt-card :deep(.el-card__body) {
    overflow-x: auto;
  }
}
</style>
