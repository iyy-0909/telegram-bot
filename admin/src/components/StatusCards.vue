<template>
  <el-row :gutter="16" class="stats">
    <el-col :span="8">
      <el-card>
        <div class="stat-title">运行状态</div>
        <div class="stat-value">{{ status.status || "-" }}</div>
      </el-card>
    </el-col>

    <el-col :span="8">
      <el-card>
        <div class="stat-title">规则数量</div>
        <div class="stat-value">{{ status.rules_count || 0 }}</div>
      </el-card>
    </el-col>
  </el-row>
</template>

<script setup>
defineProps({
  status: {
    type: Object,
    required: true
  }
})
</script>

<style scoped>
.stats {
  margin-bottom: 20px;
}

.stat-title {
  color: #6b7280;
  font-size: 14px;
}

.stat-value {
  font-size: 28px;
  font-weight: bold;
  margin-top: 8px;
}
</style>