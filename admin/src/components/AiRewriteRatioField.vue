<template>
  <div class="rewrite-ratio-field">
    <div class="rewrite-ratio-field__top">
      <div>
        <div class="rewrite-ratio-field__value">{{ ratioValue }}% · {{ ratioLabel }}</div>
        <div class="rewrite-ratio-field__summary">
          保留原文大意，用表情分区、适当加粗，整理整篇版式
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
      <span>50% 适度整理</span>
      <span>100% 加强排版</span>
    </div>
    <div class="rewrite-ratio-field__help">
      0% 只调整版式、表情和加粗；比例越高，整篇布局调整越明显，可少量润色措辞。大致内容、价格、地址、联系方式和链接保持不变，不按比例替换原文字数。
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
  if (ratioValue.value <= 25) return "轻度整理"
  if (ratioValue.value <= 50) return "适度整理"
  if (ratioValue.value <= 75) return "明显排版调整"
  return "加强排版"
})

function clampRatio(value) {
  const numberValue = Number(value)
  if (!Number.isFinite(numberValue)) return 70
  return Math.max(0, Math.min(100, Math.round(numberValue)))
}

function formatTooltip(value) {
  return `${value}% 排版与润色强度`
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
