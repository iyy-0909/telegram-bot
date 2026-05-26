<template>
  <el-dialog
    :model-value="visible"
    :title="isEdit ? '编辑 Bot' : '新增 Bot'"
    width="560px"
    @close="handleClose"
  >
    <el-form
      :model="localForm"
      label-width="100px"
    >
      <el-form-item label="Bot 名称">
        <el-input
          v-model="localForm.name"
          placeholder="例如：主分发 Bot"
        />
      </el-form-item>

      <el-form-item label="Bot Token">
        <el-input
          v-model="localForm.token"
          type="password"
          show-password
          autocomplete="new-password"
          :placeholder="isEdit ? '留空表示不修改 Token' : '从 BotFather 获取的 Token'"
        />
        <div class="field-tip">
          {{ isEdit ? "为避免泄露，已保存的 Token 不会回显。需要更换时再填写新 Token。" : "Token 只会提交给后端保存，列表不会展示明文。" }}
        </div>
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
  name: "",
  token: "",
  enabled: true,
  remark: "",
})

watch(
  () => props.visible,
  (visible) => {
    if (visible) {
      Object.assign(localForm, {
        id: props.form.id ?? null,
        name: props.form.name || "",
        token: "",
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
    name: localForm.name,
    token: localForm.token,
    enabled: localForm.enabled,
    remark: localForm.remark,
  })
}
</script>

<style scoped>
.field-tip {
  margin-top: 6px;
  color: #909399;
  font-size: 12px;
  line-height: 1.4;
}
</style>
