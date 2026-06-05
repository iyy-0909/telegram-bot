<template>
  <el-card class="template-card">
    <template #header>
      <div class="card-header">
        <div>
          <div class="card-title">内容模板规则</div>
          <div class="card-subtitle">
            一条规则包含类型、名称和多条内容；任务选择规则后可随机或指定内容。
          </div>
        </div>

        <el-button type="primary" @click="emit('add')">
          添加规则
        </el-button>
      </div>
    </template>

    <el-table
      :data="rules"
      v-loading="loading"
      border
      stripe
      row-key="id"
      height="492"
      class="template-table"
      empty-text="暂无内容模板规则，请点击“添加规则”创建 head/body/footer/过滤关键词规则。"
    >
      <el-table-column prop="id" label="ID" width="70" align="center" />

      <el-table-column label="类型" width="110" align="center">
        <template #default="{ row }">
          <el-tag :type="getTypeTag(row.type)" size="small">
            {{ typeLabel(row.type) }}
          </el-tag>
        </template>
      </el-table-column>

      <el-table-column prop="name" label="规则名称" min-width="180" show-overflow-tooltip />

      <el-table-column label="内容数量" width="100" align="center">
        <template #default="{ row }">
          {{ row.items.length }}
        </template>
      </el-table-column>

      <el-table-column label="内容预览" min-width="320" show-overflow-tooltip>
        <template #default="{ row }">
          {{ previewItems(row.items) }}
        </template>
      </el-table-column>

      <el-table-column label="启用" width="90" align="center">
        <template #default="{ row }">
          <el-switch
            :model-value="row.enabled"
            @change="value => emit('toggle', row, value)"
          />
        </template>
      </el-table-column>

      <el-table-column label="操作" width="160" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="emit('edit', row)">
            编辑
          </el-button>
          <el-button
            size="small"
            type="danger"
            @click="emit('delete', row.id)"
          >
            删除
          </el-button>
        </template>
      </el-table-column>
    </el-table>
  </el-card>
</template>

<script setup>
import { computed } from "vue"

const props = defineProps({
  templates: {
    type: Array,
    required: true,
  },
  loading: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits(["add", "edit", "delete", "toggle"])

const rules = computed(() => {
  const groups = props.templates
    .filter((template) => !template.parent_id)
    .map((group) => ({
      ...group,
      items: props.templates
        .filter((template) => template.parent_id === group.id)
        .sort((a, b) => a.id - b.id),
    }))

  return groups.sort((a, b) => b.id - a.id)
})

function getTypeTag(type) {
  const map = {
    head: "success",
    body: "warning",
    footer: "info",
    filter: "danger",
  }

  return map[type] || "info"
}

function typeLabel(type) {
  const map = {
    head: "头部",
    body: "正文",
    footer: "底部",
    filter: "过滤",
  }

  return map[type] || type || "-"
}

function previewItems(items) {
  return (items || [])
    .map((item) => (item.content || "").trim())
    .filter(Boolean)
    .slice(0, 3)
    .join(" / ")
}
</script>

<style scoped>
.template-card {
  border-radius: 8px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
}

.card-title {
  font-size: 16px;
  font-weight: 600;
  color: #303133;
}

.card-subtitle {
  margin-top: 4px;
  font-size: 12px;
  color: #909399;
}

.template-table {
  width: 100%;
}
</style>
