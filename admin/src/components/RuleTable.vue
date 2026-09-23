<template>
  <el-card>
    <template #header>
      <div class="card-header">
        <span>监听任务</span>
        <request-button type="primary" @click="emit('add')">新增任务</request-button>
      </div>
    </template>

    <TableSearch v-model="keyword" label="搜索监听规则" placeholder="搜索 ID / 源频道 / 目标频道 / 状态" :count="filteredRules.length" :total="rules.length" />
    <el-table :data="filteredRules" border height="492" style="width: 100%" :empty-text="keyword.trim() ? '没有匹配的规则，请调整或清空搜索。' : '暂无监听规则'">
      <el-table-column prop="id" label="ID" width="80" />
      <el-table-column prop="source" label="源频道" />
      <el-table-column prop="target" label="目标频道" />

      <el-table-column label="启用" width="100">
        <template #default="{ row }">
          <request-switch
            v-model="row.enabled"
            @change="emit('toggle', row)"
          />
        </template>
      </el-table-column>

      <el-table-column prop="last_message_id" label="最后消息ID" width="130" />

      <el-table-column label="操作" width="180">
        <template #default="{ row }">
          <request-button size="small" @click="emit('edit', row)">编辑</request-button>
          <request-button size="small" type="danger" @click="emit('delete', row.id)">
            删除
          </request-button>
        </template>
      </el-table-column>
    </el-table>
  </el-card>
</template>

<script setup>
import { useRequestEmit } from '../../../frontend-shared/requestActions.mjs'
import { computed, ref } from "vue"
import { searchRows } from "../utils/search"

const requestProps = defineProps({
  requestActions: { type: Object, default: () => ({}) },
  rules: {
    type: Array,
    required: true
  }
})

const rawEmit = defineEmits(["add", "edit", "delete", "toggle","clone"])
const emit = useRequestEmit(rawEmit, requestProps)
const keyword = ref("")
const filteredRules = computed(() => searchRows(requestProps.rules, keyword.value, "rules"))
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

@media (max-width: 900px) {
  .card-header {
    align-items: stretch;
    flex-direction: column;
    gap: 10px;
  }
}
</style>
