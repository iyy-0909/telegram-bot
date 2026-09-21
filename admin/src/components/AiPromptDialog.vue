<template>
  <el-dialog
    :model-value="visible"
    :title="isEdit ? '编辑提示词' : '新增提示词'"
    width="760px"
    class="ai-prompt-dialog"
    destroy-on-close
    @update:model-value="emit('update:visible', $event)"
  >
    <el-form ref="formRef" :model="localForm" :rules="rules" label-position="top" :disabled="saving">
      <el-form-item label="提示词名称" prop="name">
        <el-input
          v-model="localForm.name"
          maxlength="100"
          show-word-limit
          placeholder="例如：商务活动改写"
        />
      </el-form-item>

      <el-form-item label="适用类型" prop="content_type">
        <el-select v-model="localForm.content_type" aria-label="适用类型" placeholder="仅固定选择（不参与自动匹配）" style="width: 100%">
          <el-option label="仅固定选择（不参与自动匹配）" value="" />
          <el-option v-for="item in aiContentTypes" :key="item.value" :label="item.label" :value="item.value" />
        </el-select>
        <div class="field-help">自动模式采用同类型最近保存且启用的提示词。未配置分类时使用内置规则。</div>
      </el-form-item>
      <el-form-item v-if="localForm.content_type">
        <request-button :loading="presetsLoading" :disabled="!selectedPreset || Boolean(localForm.content.trim())" @click="usePreset">填入内置提示词</request-button>
        <div class="field-help">内容为空时可填入内置规则，再按需要编辑；已有内容将保留。</div>
        <el-alert v-if="presetsError" :title="presetsError" type="error" :closable="false" show-icon />
        <request-button v-if="presetsError" link type="primary" @click="loadPresets">重新加载内置规则</request-button>
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
          通用规则会自动应用，此处只需填写本套提示词的风格和分类要求。
          支持 {{ contentToken }}、{{ maxCharsToken }} 和 {{ rewriteRatioToken }}；自动模式另支持 {{ analysisToken }}，系统会自动附加分析结果和原文。
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
      <request-button :disabled="saving" @click="emit('update:visible', false)">取消</request-button>
      <request-button type="primary" :loading="saving" @click="submit">保存提示词</request-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { useRequestEmit } from '../../../frontend-shared/requestActions.mjs'

import { computed, reactive, ref, watch } from "vue"
import { aiContentTypes } from "../config/aiContentTypes"
import { getAiPromptPresets } from "../api/aiPrompts"

const props = defineProps({
  requestActions: { type: Object, default: () => ({}) },
  visible: Boolean,
  prompt: { type: Object, default: () => ({}) },
  isEdit: Boolean,
  saving: Boolean,
})

const rawEmit = defineEmits(["update:visible", "submit"])
const emit = useRequestEmit(rawEmit, props)
const formRef = ref(null)
const contentToken = "{{content}}"
const maxCharsToken = "{{max_chars}}"
const rewriteRatioToken = "{{rewrite_ratio}}"
const analysisToken = "{{analysis}}"
const presets = ref([])
const presetsLoading = ref(false)
const presetsError = ref("")
const selectedPreset = computed(() => presets.value.find((item) => item.content_type === localForm.content_type))

async function loadPresets() {
  if (presetsLoading.value) return
  presetsLoading.value = true
  presetsError.value = ""
  try {
    presets.value = (await getAiPromptPresets()).data || []
  } catch {
    presetsError.value = "内置规则加载失败，请重试。也可以直接填写提示词。"
  } finally {
    presetsLoading.value = false
  }
}

function usePreset() {
  if (!selectedPreset.value || localForm.content.trim()) return
  localForm.content = selectedPreset.value.content
  if (!localForm.name.trim()) localForm.name = `${selectedPreset.value.name}改写`
}

const localForm = reactive({
  id: null,
  name: "",
  content: "",
  content_type: "",
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
    if (!presets.value.length) loadPresets()
    Object.assign(localForm, {
      id: prompt?.id || null,
      name: prompt?.name || "",
      content: prompt?.content || "",
      content_type: prompt?.content_type || "",
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
  await emit("submit", {
    id: localForm.id,
    name: localForm.name.trim(),
    content: localForm.content.trim(),
    content_type: localForm.content_type,
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
