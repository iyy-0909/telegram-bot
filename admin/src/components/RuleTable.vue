<template>
  <el-card>
    <template #header>
      <div class="card-header">
        <span>监听任务</span>
        <el-button type="primary" @click="$emit('add')">新增任务</el-button>
      </div>
    </template>

    <el-table :data="rules" border height="492" style="width: 100%">
      <el-table-column prop="id" label="ID" width="80" />
      <el-table-column prop="source" label="源频道" />
      <el-table-column prop="target" label="目标频道" />

      <el-table-column label="启用" width="100">
        <template #default="{ row }">
          <el-switch
            v-model="row.enabled"
            @change="$emit('toggle', row)"
          />
        </template>
      </el-table-column>

      <el-table-column prop="last_message_id" label="最后消息ID" width="130" />

      <el-table-column label="操作" width="180">
        <template #default="{ row }">
          <el-button size="small" @click="$emit('edit', row)">编辑</el-button>
          <el-button size="small" type="danger" @click="$emit('delete', row.id)">
            删除
          </el-button>
        </template>
      </el-table-column>
    </el-table>
  </el-card>
</template>

<script setup>
defineProps({
  rules: {
    type: Array,
    required: true
  }
})

defineEmits(["add", "edit", "delete", "toggle","clone"])
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
