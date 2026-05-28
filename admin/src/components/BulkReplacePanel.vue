<template>
  <div class="page">
    <div class="page-header">
      <div>
        <h2>批量替换</h2>
        <p>基于系统已保存的发送记录，批量编辑频道历史消息里的文本或媒体 caption。</p>
      </div>
    </div>

    <el-card class="panel-card">
      <el-form label-position="top" class="filter-form">
        <el-form-item label="选择频道">
          <ChannelSelect
            v-model="form.channel_ids"
            multiple
            value-key="id"
            placeholder="请选择一个或多个我的频道"
          />
        </el-form-item>

        <div class="form-grid">
          <el-form-item label="旧内容">
            <el-input
              v-model="form.old_text"
              clearable
              placeholder="例如 123455"
            />
          </el-form-item>

          <el-form-item label="新内容">
            <el-input
              v-model="form.new_text"
              clearable
              placeholder="例如 111111，留空表示删除"
            />
          </el-form-item>

          <el-form-item label="消息类型">
            <el-select v-model="form.message_type">
              <el-option label="全部" value="all" />
              <el-option label="文本" value="text" />
              <el-option label="媒体 caption" value="caption" />
            </el-select>
          </el-form-item>

          <el-form-item label="任务来源">
            <el-select v-model="form.source_type">
              <el-option label="全部" value="all" />
              <el-option label="克隆发送" value="clone" />
              <el-option label="监听发送" value="listener" />
            </el-select>
          </el-form-item>

          <el-form-item label="时间范围">
            <el-date-picker
              v-model="form.date_range"
              type="datetimerange"
              start-placeholder="开始时间"
              end-placeholder="结束时间"
              value-format="YYYY-MM-DDTHH:mm:ss"
              clearable
            />
          </el-form-item>

          <el-form-item label="最大扫描数量">
            <el-input-number
              v-model="form.limit"
              :min="1"
              :max="5000"
              :step="100"
            />
          </el-form-item>
        </div>

        <div class="actions">
          <el-button
            type="primary"
            :loading="previewLoading"
            @click="handlePreview"
          >
            扫描预览
          </el-button>
          <el-button @click="resetForm">重置</el-button>
          <el-button
            type="success"
            :disabled="!editableItems.length"
            :loading="executeLoading"
            @click="handleExecute(false)"
          >
            确认执行
          </el-button>
          <el-button
            :disabled="!editableItems.length"
            :loading="executeLoading"
            @click="handleExecute(true)"
          >
            Dry Run
          </el-button>
        </div>
      </el-form>
    </el-card>

    <el-card class="panel-card">
      <template #header>
        <div class="result-header">
          <span>预览结果</span>
          <div class="result-stats">
            <el-tag type="success">可编辑 {{ editableItems.length }}</el-tag>
            <el-tag type="info">命中 {{ previewItems.length }}</el-tag>
            <el-tag v-if="unavailableCount" type="warning">
              缺少正文 {{ unavailableCount }}
            </el-tag>
          </div>
        </div>
      </template>

      <el-alert
        v-if="unavailableCount"
        type="warning"
        show-icon
        :closable="false"
        class="hint"
        title="部分旧发送记录没有保存 text/caption，Bot API 也不能反查频道历史内容，因此无法安全替换。新发送记录会从本次改造后开始保存可编辑信息。"
      />

      <el-table
        :data="previewItems"
        v-loading="previewLoading"
        border
        stripe
        empty-text="暂无命中记录，请选择频道并输入旧内容后扫描。"
      >
        <el-table-column prop="source_type" label="来源" width="90" />
        <el-table-column prop="channel_title" label="频道" min-width="150" show-overflow-tooltip />
        <el-table-column prop="target_message_id" label="消息ID" width="100" />
        <el-table-column prop="message_type" label="类型" width="110" />
        <el-table-column label="替换前" min-width="260" show-overflow-tooltip>
          <template #default="{ row }">
            <span class="text-cell">{{ row.original_text }}</span>
          </template>
        </el-table-column>
        <el-table-column label="替换后" min-width="260" show-overflow-tooltip>
          <template #default="{ row }">
            <span class="text-cell">{{ row.replaced_text }}</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="150">
          <template #default="{ row }">
            <el-tag :type="row.can_edit ? 'success' : 'warning'">
              {{ row.can_edit ? "可编辑" : "不可编辑" }}
            </el-tag>
            <div v-if="row.reason" class="reason">{{ row.reason }}</div>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card v-if="jobResult" class="panel-card">
      <template #header>
        <div class="result-header">
          <span>执行结果 #{{ jobResult.id }}</span>
          <div class="result-stats">
            <el-tag type="success">成功 {{ jobResult.success_count }}</el-tag>
            <el-tag type="danger">失败 {{ jobResult.failed_count }}</el-tag>
            <el-tag type="warning">跳过 {{ jobResult.skipped_count }}</el-tag>
          </div>
        </div>
      </template>

      <el-table :data="jobResult.items || []" border stripe>
        <el-table-column prop="source_type" label="来源" width="90" />
        <el-table-column prop="target_message_id" label="消息ID" width="100" />
        <el-table-column prop="message_type" label="类型" width="110" />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="resultTagType(row.status)">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="error_message" label="错误原因" min-width="240" show-overflow-tooltip />
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { computed, reactive, ref } from "vue"
import { ElMessage, ElMessageBox } from "element-plus"
import ChannelSelect from "./ChannelSelect.vue"
import { executeBulkReplace, previewBulkReplace } from "../api/bulkReplace"

const defaultForm = () => ({
  channel_ids: [],
  old_text: "",
  new_text: "",
  message_type: "all",
  source_type: "all",
  date_range: [],
  limit: 500,
})

const form = reactive(defaultForm())
const previewItems = ref([])
const unavailableCount = ref(0)
const previewLoading = ref(false)
const executeLoading = ref(false)
const jobResult = ref(null)

const editableItems = computed(() => previewItems.value.filter((item) => item.can_edit))

function resetForm() {
  Object.assign(form, defaultForm())
  previewItems.value = []
  unavailableCount.value = 0
  jobResult.value = null
}

function validateForm() {
  if (!form.channel_ids.length) {
    ElMessage.error("请选择至少一个频道")
    return false
  }

  if (!form.old_text.trim()) {
    ElMessage.error("旧内容不能为空")
    return false
  }

  return true
}

async function handlePreview(clearJob = true) {
  if (!validateForm()) {
    return
  }

  previewLoading.value = true
  if (clearJob) {
    jobResult.value = null
  }

  try {
    const res = await previewBulkReplace({
      ...form,
      old_text: form.old_text,
      new_text: form.new_text,
    })
    previewItems.value = res.data.items || []
    unavailableCount.value = res.data.unavailable_count || 0
    ElMessage.success(`扫描完成，命中 ${previewItems.value.length} 条`)
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || "扫描失败")
  } finally {
    previewLoading.value = false
  }
}

async function handleExecute(dryRun) {
  if (!editableItems.value.length) {
    ElMessage.warning("没有可执行的记录")
    return
  }

  try {
    if (!form.new_text) {
      await ElMessageBox.confirm(
        "新内容为空，这会删除命中的旧内容。是否继续？",
        "确认删除内容",
        { type: "warning" },
      )
    }

    await ElMessageBox.confirm(
      `将把 ${editableItems.value.length} 条消息中的「${form.old_text}」替换为「${form.new_text}」，是否继续？`,
      dryRun ? "确认 Dry Run" : "确认执行",
      { type: dryRun ? "info" : "warning" },
    )
  } catch {
    return
  }

  executeLoading.value = true

  try {
    const res = await executeBulkReplace({
      records: editableItems.value.map((item) => ({
        source_type: item.source_type,
        record_id: item.record_id,
        channel_id: item.channel_id,
      })),
      old_text: form.old_text,
      new_text: form.new_text,
      channel_ids: form.channel_ids,
      message_type: form.message_type,
      source_type: form.source_type,
      dry_run: dryRun,
    })
    jobResult.value = res.data
    ElMessage.success(dryRun ? "Dry Run 完成" : "批量替换完成")
    await handlePreview(false)
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || "执行失败")
  } finally {
    executeLoading.value = false
  }
}

function resultTagType(status) {
  if (status === "success") return "success"
  if (status === "failed") return "danger"
  if (status === "skipped") return "warning"
  return "info"
}
</script>

<style scoped>
.page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.page-header h2 {
  margin: 0 0 6px;
  font-size: 22px;
  color: #111827;
}

.page-header p {
  margin: 0;
  color: #6b7280;
}

.panel-card {
  border-radius: 8px;
}

.filter-form {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(220px, 1fr));
  gap: 12px 16px;
}

.actions,
.result-header,
.result-stats {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.result-header {
  justify-content: space-between;
}

.hint {
  margin-bottom: 12px;
}

.text-cell {
  white-space: pre-wrap;
  word-break: break-word;
}

.reason {
  margin-top: 4px;
  font-size: 12px;
  color: #9ca3af;
}
</style>
