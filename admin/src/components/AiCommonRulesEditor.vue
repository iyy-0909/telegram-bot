<template>
  <section class="common-rules" aria-labelledby="common-rules-title" :aria-busy="loading">
    <div class="common-rules-header">
      <div>
        <h2 id="common-rules-title">通用改写规则</h2>
        <p>联系方式、链接、事实和排版要求只维护一处，统一用于当前账号的固定改写、自动改写和文案试写。</p>
      </div>
      <el-button :loading="loading" :disabled="!loaded || forbidden" @click="openEditor">编辑通用规则</el-button>
    </div>
    <el-skeleton v-if="loading && !loaded" :rows="2" animated />
    <div v-else-if="loadError" class="common-rules-feedback" role="status">
      <el-alert :title="loadError" type="error" :closable="false" show-icon />
      <el-button :loading="loading" @click="loadRules">重新加载规则</el-button>
    </div>
    <template v-else-if="loaded">
      <p class="common-rules-preview">{{ savedContent || "尚未设置通用规则，请先编辑并保存。" }}</p>
      <el-alert v-if="saved" title="通用规则已保存，下次改写时生效。" type="success" :closable="false" show-icon />
    </template>

    <el-dialog
      v-model="visible"
      title="编辑通用改写规则"
      width="min(760px, calc(100vw - 24px))"
      class="ai-common-rules-dialog"
      destroy-on-close
      :close-on-click-modal="!saving"
      :close-on-press-escape="!saving"
      :show-close="!saving"
    >
      <p class="common-rules-help">保存后应用于当前账号的所有 AI 改写。每套提示词只需填写对应文案的风格和分类要求。</p>
      <el-form ref="formRef" :model="form" :rules="rules" label-position="top" :disabled="saving" @submit.prevent="saveRules">
        <el-form-item label="通用规则内容" prop="content">
          <el-input v-model="form.content" type="textarea" :rows="14" maxlength="20000" show-word-limit placeholder="填写所有改写共用的保留、事实和排版规则" />
        </el-form-item>
        <el-alert v-if="saveError" :title="saveError" type="error" :closable="false" show-icon />
      </el-form>
      <template #footer>
        <el-button :disabled="saving" @click="visible = false">取消</el-button>
        <el-button type="primary" :loading="saving" :disabled="forbidden" @click="saveRules">保存通用规则</el-button>
      </template>
    </el-dialog>
  </section>
</template>

<script setup>
import { onBeforeUnmount, onMounted, reactive, ref, watch } from "vue"
import { getAiCommonRules, updateAiCommonRules } from "../api/aiPrompts"
import { getAuthGeneration, isAuthGenerationCurrent, isCanceledAuthRequest } from "../authSession"

const props = defineProps({ refreshing: Boolean })
const loading = ref(false)
const loaded = ref(false)
const saving = ref(false)
const saved = ref(false)
const forbidden = ref(false)
const visible = ref(false)
const savedContent = ref("")
const loadError = ref("")
const saveError = ref("")
const formRef = ref(null)
const form = reactive({ content: "" })
let active = true
const rules = {
  content: [
    { required: true, whitespace: true, message: "请输入通用规则，不能只填写空格。", trigger: "blur" },
    { max: 20000, message: "通用规则不能超过 20000 个字符。", trigger: "blur" },
  ],
}

function errorMessage(error, fallback) {
  if (error.response?.status === 403) return "当前账号没有 AI 配置权限，请联系管理员。"
  if (error.response?.status === 404 || error.response?.status >= 500) return fallback
  const detail = error.response?.data?.detail
  return typeof detail === "string" ? detail : fallback
}

async function loadRules() {
  if (loading.value || saving.value) return
  const generation = getAuthGeneration()
  loading.value = true
  saved.value = false
  loadError.value = ""
  try {
    const response = await getAiCommonRules()
    if (!active || !isAuthGenerationCurrent(generation)) return
    savedContent.value = response.data?.content || ""
    loaded.value = true
    forbidden.value = false
  } catch (error) {
    if (!active || isCanceledAuthRequest(error) || !isAuthGenerationCurrent(generation)) return
    loaded.value = false
    forbidden.value = error.response?.status === 403
    loadError.value = errorMessage(error, "通用规则加载失败，请重新加载。")
  } finally {
    if (active && isAuthGenerationCurrent(generation)) loading.value = false
  }
}

function openEditor() {
  saved.value = false
  form.content = savedContent.value
  saveError.value = ""
  visible.value = true
}

async function saveRules() {
  if (saving.value || forbidden.value) return
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  const generation = getAuthGeneration()
  saving.value = true
  saveError.value = ""
  try {
    const response = await updateAiCommonRules({ content: form.content.trim() })
    if (!active || !isAuthGenerationCurrent(generation)) return
    savedContent.value = response.data.content
    saved.value = true
    visible.value = false
  } catch (error) {
    if (!active || isCanceledAuthRequest(error) || !isAuthGenerationCurrent(generation)) return
    forbidden.value = error.response?.status === 403
    saveError.value = errorMessage(error, "通用规则保存失败，内容已保留，请重试。")
  } finally {
    if (active && isAuthGenerationCurrent(generation)) saving.value = false
  }
}

onMounted(loadRules)
onBeforeUnmount(() => { active = false })
watch(() => props.refreshing, (value, previous) => {
  if (previous && !value && !visible.value) loadRules()
})
</script>

<style scoped>
.common-rules { min-width: 0; margin-bottom: 16px; padding-bottom: 16px; border-bottom: 1px solid var(--el-border-color-lighter); }
.common-rules-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; margin-bottom: 12px; }
.common-rules-header h2 { margin: 0; font-size: var(--el-font-size-base); color: var(--el-text-color-primary); }
.common-rules-header p, .common-rules-help { margin: 6px 0 0; font-size: var(--el-font-size-small); color: var(--el-text-color-regular); line-height: 1.6; }
.common-rules-header .el-button { flex-shrink: 0; }
.common-rules-preview { display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; overflow-wrap: anywhere; white-space: pre-wrap; margin: 0 0 12px; font-size: var(--el-font-size-small); color: var(--el-text-color-secondary); line-height: 1.6; }
.common-rules-feedback { display: grid; justify-items: start; gap: 12px; }
.common-rules-help { margin-bottom: 16px; }
@media (max-width: 600px) {
  .common-rules-header { flex-direction: column; align-items: stretch; gap: 12px; }
  :global(.ai-common-rules-dialog) { width: calc(100vw - 24px) !important; margin: 12px auto !important; }
  :global(.ai-common-rules-dialog .el-dialog__body) { max-height: 65vh; overflow-y: auto; }
}
</style>
