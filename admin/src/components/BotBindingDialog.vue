<template>
  <el-dialog
    :model-value="visible"
    :title="isEdit ? '编辑绑定' : '新增绑定'"
    width="560px"
    @close="handleClose"
  >
    <el-form
      :model="localForm"
      label-width="100px"
    >
      <el-form-item label="目标频道">
        <el-input
          v-model="localForm.target_channel"
          placeholder="例如：@target_channel"
        />
      </el-form-item>

      <el-form-item label="选择 Bot">
        <el-select
          v-model="localForm.bot_id"
          placeholder="请选择 Bot"
          style="width: 100%"
        >
          <el-option
            v-for="bot in bots"
            :key="bot.id"
            :label="`${bot.name} (#${bot.id})`"
            :value="bot.id"
          />
        </el-select>
      </el-form-item>

      <el-form-item label="启用">
        <el-switch
          v-model="localForm.enabled"
          active-text="开启"
          inactive-text="关闭"
        />
      </el-form-item>

      <el-form-item label="备注">
        <el-input
          v-model="localForm.remark"
          type="textarea"
          :rows="3"
          placeholder="可选"
        />
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="handleClose">
        取消
      </el-button>

      <el-button
        type="primary"
        @click="handleSubmit"
      >
        保存
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { reactive, watch } from "vue"

const props = defineProps({
  visible: {
    type: Boolean,
    default: false,
  },
  form: {
    type: Object,
    required: true,
  },
  bots: {
    type: Array,
    default: () => [],
  },
  isEdit: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits([
  "update:visible",
  "submit",
])

const localForm = reactive({
  id: null,
  target_channel: "",
  bot_id: null,
  enabled: true,
  remark: "",
})

watch(
  () => props.visible,
  (visible) => {
    if (visible) {
      Object.assign(localForm, {
        id: props.form.id ?? null,
        target_channel: props.form.target_channel || "",
        bot_id: props.form.bot_id || null,
        enabled: props.form.enabled ?? true,
        remark: props.form.remark || "",
      })
    }
  },
  {
    immediate: true,
  },
)

const handleClose = () => {
  emit("update:visible", false)
}

const handleSubmit = () => {
  emit("submit", {
    id: localForm.id,
    target_channel: localForm.target_channel,
    bot_id: localForm.bot_id,
    enabled: localForm.enabled,
    remark: localForm.remark,
  })
}
</script>