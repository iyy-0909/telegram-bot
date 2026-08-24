<template>
  <div class="rewrite-ratio-field">
    <div class="rewrite-ratio-field__top">
      <div>
        <div class="rewrite-ratio-field__value">{{ ratioValue }}% · {{ ratioLabel }}</div>
        <div class="rewrite-ratio-field__summary">
          约保留 {{ 100 - ratioValue }}% 原有措辞与结构
        </div>
      </div>
      <el-input-number
        v-model="ratioValue"
        :min="0"
        :max="100"
        :step="5"
        controls-position="right"
        aria-label="AI 改写比例"
      />
    </div>

    <el-slider
      v-model="ratioValue"
      :min="0"
      :max="100"
      :step="5"
      :format-tooltip="formatTooltip"
      aria-label="AI 改写比例滑块"
    />

    <div class="rewrite-ratio-field__scale" aria-hidden="true">
      <span>0% 仅排版</span>
      <span>50% 中度</span>
      <span>100% 重写</span>
    </div>
    <div class="rewrite-ratio-field__help">
      比例越高，句式和排版变化越明显；事实、数字及受保护链接始终保留。该值表示模型改写强度，不是机械字数占比。
    </div>
  </div>
</template>

<script setup>
import { computed } from "vue"

const props = defineProps({
  modelValue: {
    type: Number,
    default: 70,
  },
})

const emit = defineEmits(["update:modelValue"])

const ratioValue = computed({
  get() {
    return clampRatio(props.modelValue)
  },
  set(value) {
    emit("update:modelValue", clampRatio(value))
  },
})

const ratioLabel = computed(() => {
  if (ratioValue.value === 0) return "只整理排版"
  if (ratioValue.value <= 25) return "轻度润色"
  if (ratioValue.value <= 50) return "中度改写"
  if (ratioValue.value <= 75) return "明显改写"
  return "高强度重写"
})

function clampRatio(value) {
  const numberValue = Number(value)
  if (!Number.isFinite(numberValue)) return 70
  return Math.max(0, Math.min(100, Math.round(numberValue)))
}

function formatTooltip(value) {
  return `${value}% 改写强度`
}
</script>

<style scoped>
.rewrite-ratio-field {
  width: 100%;
  min-width: 0;
}

.rewrite-ratio-field__top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.rewrite-ratio-field__value {
  color: var(--el-text-color-primary);
  font-weight: 600;
  line-height: 1.5;
}

.rewrite-ratio-field__summary,
.rewrite-ratio-field__help,
.rewrite-ratio-field__scale {
  color: var(--el-text-color-secondary);
  font-size: 12px;
  line-height: 1.5;
}

.rewrite-ratio-field__top :deep(.el-input-number) {
  flex: 0 0 120px;
  width: 120px;
}

.rewrite-ratio-field :deep(.el-slider) {
  margin: 8px 6px 0;
}

.rewrite-ratio-field__scale {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin-top: -4px;
}

.rewrite-ratio-field__help {
  margin-top: 8px;
}

@media (max-width: 600px) {
  .rewrite-ratio-field__top {
    align-items: flex-start;
    flex-direction: column;
    gap: 8px;
  }

  .rewrite-ratio-field__top :deep(.el-input-number) {
    flex: 0 0 auto;
    width: 100%;
  }
}
</style>
