<template>
  <el-dialog
    :model-value="visible"
    :title="isEdit ? '编辑提示词' : '新增提示词'"
    width="760px"
    class="ai-prompt-dialog"
    destroy-on-close
    @update:model-value="emit('update:visible', $event)"
  >
    <el-form ref="formRef" :model="localForm" :rules="rules" label-position="top">
      <el-form-item label="提示词名称" prop="name">
        <el-input
          v-model="localForm.name"
          maxlength="100"
          show-word-limit
          placeholder="例如：商务活动改写"
        />
      </el-form-item>

      <el-form-item label="提示词内容" prop="content">
        <el-input
          v-model="localForm.content"
          type="textarea"
          :rows="16"
          maxlength="20000"
          show-word-limit
          placeholder="填写模型需要执行的改写规则"
        />
        <div class="field-help">
          支持 {{ contentToken }}、{{ maxCharsToken }} 和 {{ rewriteRatioToken }} 占位符；未写 {{ contentToken }} 时系统会自动附加待处理内容。
        </div>
      </el-form-item>

      <div class="form-switches">
        <el-form-item label="启用">
          <el-switch v-model="localForm.enabled" :disabled="localForm.is_default" />
        </el-form-item>
        <el-form-item label="设为系统默认">
          <el-switch v-model="localForm.is_default" @change="handleDefaultChange" />
        </el-form-item>
      </div>
    </el-form>

    <template #footer>
      <el-button :disabled="saving" @click="emit('update:visible', false)">取消</el-button>
      <el-button type="primary" :loading="saving" @click="submit">保存提示词</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { reactive, ref, watch } from "vue"

const props = defineProps({
  visible: Boolean,
  prompt: { type: Object, default: () => ({}) },
  isEdit: Boolean,
  saving: Boolean,
})

const emit = defineEmits(["update:visible", "submit"])
const formRef = ref(null)
const contentToken = "{{content}}"
const maxCharsToken = "{{max_chars}}"
const rewriteRatioToken = "{{rewrite_ratio}}"

const localForm = reactive({
  id: null,
  name: "",
  content: "",
  enabled: true,
  is_default: false,
})

const rules = {
  name: [
    { required: true, message: "请输入提示词名称", trigger: "blur" },
    { max: 100, message: "名称不能超过 100 个字符", trigger: "blur" },
  ],
  content: [
    { required: true, message: "请输入提示词内容", trigger: "blur" },
    { max: 20000, message: "提示词内容不能超过 20000 个字符", trigger: "blur" },
  ],
}

watch(
  () => [props.visible, props.prompt],
  ([visible, prompt]) => {
    if (!visible) return
    Object.assign(localForm, {
      id: prompt?.id || null,
      name: prompt?.name || "",
      content: prompt?.content || "",
      enabled: prompt?.enabled ?? true,
      is_default: prompt?.is_default ?? false,
    })
  },
  { immediate: true, deep: true },
)

function handleDefaultChange(value) {
  if (value) localForm.enabled = true
}

async function submit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  emit("submit", {
    id: localForm.id,
    name: localForm.name.trim(),
    content: localForm.content.trim(),
    enabled: localForm.is_default ? true : localForm.enabled,
    is_default: localForm.is_default,
  })
}
</script>

<style scoped>
.field-help {
  margin-top: 6px;
  color: var(--el-text-color-secondary);
  font-size: 12px;
  line-height: 1.5;
}

.form-switches {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

@media (max-width: 600px) {
  :global(.ai-prompt-dialog) {
    width: calc(100vw - 24px) !important;
    margin: 12px auto !important;
  }

  :global(.ai-prompt-dialog .el-dialog__body) {
    max-height: 70vh;
    overflow-y: auto;
  }

  .form-switches {
    grid-template-columns: 1fr;
    gap: 0;
  }
}
</style>
