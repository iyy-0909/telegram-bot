<template>
  <el-card shadow="never" class="preview-card">
    <template #header><strong>文案试写</strong></template>
    <p class="help">保留原文大致内容，用表情区分信息板块，适当加粗标题和重点，重新安排整篇版式，可少量润色措辞。试写后可直接查看排版效果。会调用已配置的 AI；结果不符合要求时自动重新试写一次，不会发送到频道。</p>
    <el-form label-position="top" :disabled="loading" @submit.prevent="runPreview">
      <el-form-item label="源文案" :error="inputError">
        <el-input v-model="text" type="textarea" :rows="5" maxlength="16000" show-word-limit placeholder="粘贴需要分析和改写的源正文" />
      </el-form-item>
      <div class="preview-options">
        <el-form-item label="模型供应商">
          <el-select v-model="provider" aria-label="试写模型供应商">
            <el-option label="Grok（xAI）" value="grok" />
            <el-option label="DeepSeek" value="deepseek" />
          </el-select>
        </el-form-item>
        <el-form-item label="最大输出字数"><el-input-number v-model="maxChars" :min="100" :max="4000" /></el-form-item>
      </div>
      <el-form-item label="改写比例">
        <AiRewriteRatioField v-model="rewriteRatio" />
      </el-form-item>
      <request-button type="primary" :loading="loading" native-type="submit">{{ loading ? "正在分析并改写…" : "分析并试写" }}</request-button>
    </el-form>
    <el-alert v-if="error" class="feedback" type="error" :title="error" :closable="false" show-icon />
    <div v-if="result" class="preview-result" aria-live="polite">
      <el-alert v-if="result.analysis_fallback" title="分析未完成，已按“混合或未知”分类试写。" :description="result.analysis_error || '无法确定分类，已使用兜底提示词；通用保护规则仍生效。'" type="warning" :closable="false" show-icon />
      <el-alert v-if="!error && result.rewrite_status === 'preserved'" title="本次按规则保留原文" :description="result.rewrite_reason" type="info" :closable="false" show-icon />
      <el-alert v-else-if="!error && result.text" title="改写完成，可检查下方结果。" :description="result.rewrite_retried ? '已自动调整后重新试写一次。' : ''" type="success" :closable="false" show-icon />
      <section v-if="result.text && !error" class="formatted-result">
        <div class="result-heading">
          <strong>{{ result.rewrite_status === 'preserved' ? '原文预览' : '排版效果' }}</strong>
          <span class="result-hint">可检查表情、加粗和分段</span>
        </div>
        <TelegramTextPreview :text="result.text" />
      </section>
      <el-form v-if="result.text && !error" label-position="top">
        <el-form-item :label="result.rewrite_status === 'preserved' ? '保留原文（本次未改写）' : '改写结果（Telegram HTML）'">
          <el-input :model-value="result.text" readonly type="textarea" :rows="7" />
        </el-form-item>
      </el-form>
      <el-collapse>
        <el-collapse-item v-if="result.matches?.length" title="查看各段使用的提示词" name="matches">
          <div v-for="(match, index) in result.matches" :key="match.segment_id" class="match-row">
            <span class="segment-label">第 {{ index + 1 }} 段</span>
            <el-tag type="info">{{ contentTypeLabel(match.content_type) }}</el-tag>
            <span>{{ match.action === 'preserve' ? '原样保留' : match.name + (match.builtin ? '（内置）' : '') }}</span>
          </div>
        </el-collapse-item>
        <el-collapse-item v-if="result.analysis" title="查看分析结果与改写范围" name="analysis"><pre>{{ JSON.stringify(result.analysis, null, 2) }}</pre></el-collapse-item>
        <el-collapse-item v-if="result.rewrite_prompt" title="查看本次使用的完整提示词" name="prompt"><pre>{{ result.rewrite_prompt }}</pre></el-collapse-item>
      </el-collapse>
    </div>
  </el-card>
</template>

<script setup>
import { onBeforeUnmount, ref, watch } from "vue"
import { previewAiRewrite } from "../api/aiPrompts"
import { contentTypeLabel } from "../config/aiContentTypes"
import AiRewriteRatioField from "./AiRewriteRatioField.vue"
import TelegramTextPreview from "./TelegramTextPreview.js"

const props = defineProps({
  defaultProvider: { type: String, default: "grok" },
})

const text = ref("")
const provider = ref("grok")
const maxChars = ref(800)
const rewriteRatio = ref(70)
const loading = ref(false)
const inputError = ref("")
const error = ref("")
const result = ref(null)
let active = true
let inputVersion = 0
onBeforeUnmount(() => { active = false })

watch(
  () => props.defaultProvider,
  (value) => { provider.value = value === "deepseek" ? "deepseek" : "grok" },
  { immediate: true },
)

watch([text, provider, maxChars, rewriteRatio], () => {
  inputVersion += 1
  result.value = null
  error.value = ""
  inputError.value = ""
}, { flush: "sync" })

async function runPreview() {
  if (loading.value) return
  inputError.value = text.value.trim() ? "" : "请输入需要试写的源文案"
  if (inputError.value) return
  loading.value = true
  error.value = ""
  result.value = null
  const requestVersion = inputVersion
  try {
    const response = await previewAiRewrite({ text: text.value, provider: provider.value, max_chars: maxChars.value || 800, rewrite_ratio: rewriteRatio.value })
    if (!active || requestVersion !== inputVersion) return
    result.value = response.data
    error.value = response.data.error || ""
  } catch (err) {
    if (!active || requestVersion !== inputVersion) return
    const detail = err.response?.data?.detail
    error.value = err.response?.status === 403 ? "当前账号没有 AI 配置权限，请联系管理员。"
      : typeof detail === "string" ? detail : "试写请求失败，请检查 AI 配置后重试。源文案已保留。"
  } finally {
    if (active) loading.value = false
  }
}
</script>

<style scoped>
.preview-card { min-width: 0; }
.help { margin: 0 0 16px; color: var(--el-text-color-secondary); line-height: 1.6; }
.preview-options { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; }
.preview-options :deep(.el-select), .preview-options :deep(.el-input-number) { width: 100%; }
.feedback, .preview-result { margin-top: 16px; }
.preview-result > .el-alert + .el-alert { margin-top: 12px; }
.formatted-result { margin: 16px 0; min-width: 0; }
.result-heading { display: flex; flex-wrap: wrap; align-items: baseline; gap: 8px 12px; margin-bottom: 8px; }
.result-hint { color: var(--el-text-color-secondary); font-size: var(--el-font-size-small); }
.formatted-result :deep(.telegram-text-preview) { padding: 16px; border: 1px solid var(--el-border-color); border-radius: var(--el-border-radius-base); background: var(--el-fill-color-blank); color: var(--el-text-color-primary); white-space: pre-wrap; overflow-wrap: anywhere; line-height: 1.75; max-height: 640px; overflow-y: auto; }
.formatted-result :deep(.telegram-text-preview:focus-visible) { outline: 2px solid var(--el-color-primary); outline-offset: 2px; }
.formatted-result :deep(strong) { font-weight: 700; }
.formatted-result :deep(blockquote) { margin: 8px 0; padding-left: 12px; border-left: 3px solid var(--el-border-color); color: var(--el-text-color-regular); }
.formatted-result :deep(code) { font-family: var(--mono); background: var(--el-fill-color-light); }
.formatted-result :deep(pre) { white-space: pre-wrap; overflow-wrap: anywhere; margin: 8px 0; }
.match-row { display: flex; align-items: center; gap: 8px; margin: 12px 0; overflow-wrap: anywhere; }
.segment-label { color: var(--el-text-color-secondary); flex-shrink: 0; }
.match-row .el-tag { flex-shrink: 0; }
pre { white-space: pre-wrap; overflow-wrap: anywhere; max-height: 360px; overflow-y: auto; margin: 0; }
@media (max-width: 600px) { .preview-options { grid-template-columns: 1fr; gap: 0; } .match-row { flex-wrap: wrap; } }
</style>
