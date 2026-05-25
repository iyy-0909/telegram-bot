<template>
  <el-card>
    <template #header>
      <div class="card-header">
        <span>账号管理</span>

        <el-button type="primary" @click="$emit('add')">
          新增账号
        </el-button>
      </div>
    </template>

    <el-table :data="accounts" border>

      <el-table-column prop="id" label="ID" width="80" />

      <el-table-column prop="name" label="账号名称" />

      <el-table-column
        prop="session_path"
        label="Session"
      />

      <el-table-column label="启用" width="100">

        <template #default="{ row }">

          <el-switch
            v-model="row.enabled"
            @change="$emit('toggle', row)"
          />

        </template>

      </el-table-column>

      <el-table-column prop="remark" label="备注" />

      <el-table-column label="操作" width="180">

        <template #default="{ row }">

          <el-button
            size="small"
            @click="$emit('edit', row)"
          >
            编辑
          </el-button>

          <el-button
            size="small"
            type="danger"
            @click="$emit('delete', row.id)"
          >
            删除
          </el-button>

        </template>

      </el-table-column>

    </el-table>
  </el-card>
</template>

<script setup>

defineProps({
  accounts: Array
})

defineEmits([
  "add",
  "edit",
  "delete",
  "toggle"
])

</script>

<style scoped>

.card-header{
  display:flex;
  justify-content:space-between;
  align-items:center;
}

</style>