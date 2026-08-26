<template>
  <el-dialog
    :model-value="visible"
    @update:model-value="$emit('update:visible', $event)"
    :title="isEdit ? '编辑账号' : '新增账号'"
    width="min(720px, calc(100vw - 24px))"
    destroy-on-close
  >
    <el-form ref="formRef" :model="localForm" :rules="rules" label-position="top">
      <div class="form-grid">
        <el-form-item label="账号名称" prop="name">
          <el-input v-model="localForm.name" placeholder="例如 主账号" />
        </el-form-item>
        <el-form-item label="Telegram 用户名">
          <el-input v-model="localForm.username" placeholder="例如 review 或 @review" />
        </el-form-item>
        <el-form-item label="Session 路径" prop="session_path">
          <el-input v-model="localForm.session_path" placeholder="例如 data/sessions/main_1" />
        </el-form-item>
        <el-form-item label="代理">
          <el-input v-model="localForm.proxy" placeholder="留空则使用系统代理" />
        </el-form-item>
      </div>

      <el-form-item label="账号状态">
        <el-switch v-model="localForm.enabled" active-text="启用" inactive-text="停用" />
      </el-form-item>

      <el-divider content-position="left">私聊自动回复</el-divider>
      <el-alert
        title="仅回复其他用户发给该账号的私聊消息；群组、频道和机器人消息不会触发。"
        type="info"
        :closable="false"
        show-icon
        class="section-tip"
      />

      <section class="reply-section">
        <div class="section-heading">
          <div>
            <div class="section-title">问候消息</div>
            <div class="section-description">每位联系人首次给此账号发私聊时自动发送一次。</div>
          </div>
          <el-switch v-model="localForm.greeting_enabled" aria-label="启用问候消息" />
        </div>
        <el-form-item v-if="localForm.greeting_enabled" label="问候内容" prop="greeting_message">
          <el-input
            v-model="localForm.greeting_message"
            type="textarea"
            :rows="3"
            maxlength="4096"
            show-word-limit
            placeholder="例如：您好，感谢您的联系，我们会尽快回复。"
          />
        </el-form-item>
      </section>

      <section class="reply-section">
        <div class="section-heading">
          <div>
            <div class="section-title">离线消息</div>
            <div class="section-description">每天营业时间之外收到私聊时自动发送，并按间隔限制重复回复。</div>
          </div>
          <el-switch v-model="localForm.away_enabled" aria-label="启用离线消息" />
        </div>
        <template v-if="localForm.away_enabled">
          <el-form-item label="离线内容" prop="away_message">
            <el-input
              v-model="localForm.away_message"
              type="textarea"
              :rows="3"
              maxlength="4096"
              show-word-limit
              placeholder="例如：当前为非营业时间，我们将在上班后尽快回复。"
            />
          </el-form-item>
          <div class="schedule-grid">
            <el-form-item label="营业开始" prop="business_start_time">
              <el-time-select v-model="localForm.business_start_time" start="00:00" step="00:30" end="23:30" placeholder="选择开始时间" />
            </el-form-item>
            <el-form-item label="营业结束" prop="business_end_time">
              <el-time-select v-model="localForm.business_end_time" start="00:00" step="00:30" end="23:30" placeholder="选择结束时间" />
            </el-form-item>
            <el-form-item label="重复回复间隔" prop="away_repeat_hours">
              <el-input-number v-model="localForm.away_repeat_hours" :min="1" :max="168" />
              <span class="field-suffix">小时</span>
            </el-form-item>
          </div>
          <div class="schedule-note">按服务器本地时间判断；开始时间晚于结束时间时视为跨夜营业。</div>
        </template>
      </section>

      <el-form-item label="备注">
        <el-input v-model="localForm.remark" type="textarea" :rows="2" />
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button :disabled="saving" @click="$emit('update:visible', false)">取消</el-button>
      <el-button type="primary" :loading="saving" @click="submit">保存</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { reactive, ref, watch } from "vue"

const props = defineProps({ visible: Boolean, form: Object, isEdit: Boolean, saving: Boolean })
const emit = defineEmits(["update:visible", "submit"])
const formRef = ref(null)

const localForm = reactive({
  id: null, name: "", username: "", session_path: "", proxy: "", enabled: true, remark: "",
  greeting_enabled: false, greeting_message: "", away_enabled: false, away_message: "",
  business_start_time: "09:00", business_end_time: "18:00", away_repeat_hours: 12,
})

const requiredWhen = (enabledField, message) => (_rule, value, callback) => {
  if (localForm[enabledField] && !String(value || "").trim()) callback(new Error(message))
  else callback()
}

const rules = {
  name: [{ required: true, message: "请输入账号名称", trigger: "blur" }],
  session_path: [{ required: true, message: "请输入 Session 路径", trigger: "blur" }],
  greeting_message: [{ validator: requiredWhen("greeting_enabled", "请输入问候内容"), trigger: "blur" }],
  away_message: [{ validator: requiredWhen("away_enabled", "请输入离线内容"), trigger: "blur" }],
  business_start_time: [{ required: true, message: "请选择营业开始时间", trigger: "change" }],
  business_end_time: [{ required: true, message: "请选择营业结束时间", trigger: "change" }],
}

watch(() => props.form, (val) => {
  if (!val) return
  Object.assign(localForm, {
    id: val.id ?? null, name: val.name || "", username: val.username || "",
    session_path: val.session_path || "", proxy: val.proxy || "", enabled: val.enabled !== false,
    remark: val.remark || "", greeting_enabled: Boolean(val.greeting_enabled),
    greeting_message: val.greeting_message || "", away_enabled: Boolean(val.away_enabled),
    away_message: val.away_message || "", business_start_time: val.business_start_time || "09:00",
    business_end_time: val.business_end_time || "18:00", away_repeat_hours: Number(val.away_repeat_hours || 12),
  })
}, { immediate: true, deep: true })

async function submit() {
  if (!formRef.value || !(await formRef.value.validate().catch(() => false))) return
  emit("submit", { ...localForm, username: String(localForm.username || "").trim().replace(/^@+/, "") })
}
</script>

<style scoped>
.form-grid, .schedule-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0 16px; }
.schedule-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); }
.section-tip { margin-bottom: 12px; }
.reply-section { padding: 14px 0; border-bottom: 1px solid var(--el-border-color-lighter); }
.reply-section + .reply-section { margin-bottom: 16px; }
.section-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; margin-bottom: 12px; }
.section-title { color: var(--el-text-color-primary); font-weight: 600; }
.section-description, .schedule-note { margin-top: 4px; color: var(--el-text-color-secondary); font-size: 13px; line-height: 1.5; }
.field-suffix { margin-left: 8px; color: var(--el-text-color-secondary); }
@media (max-width: 600px) { .form-grid, .schedule-grid { grid-template-columns: 1fr; } .section-heading { gap: 12px; } }
</style>
