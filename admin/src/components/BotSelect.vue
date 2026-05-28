<template>
  <el-select
    :model-value="modelValue"
    :placeholder="placeholder"
    clearable
    filterable
    class="bot-select"
    @update:model-value="$emit('update:modelValue', $event)"
  >
    <el-option
      v-for="bot in options"
      :key="bot.id"
      :label="botLabel(bot)"
      :value="bot.id"
      :disabled="onlyEnabled && !bot.enabled"
    >
      <div class="option-row">
        <span>{{ botLabel(bot) }}</span>
        <StatusTag :status="bot.enabled ? 'enabled' : 'disabled'" />
      </div>
    </el-option>
  </el-select>
</template>

<script setup>
import { computed } from "vue"
import StatusTag from "./StatusTag.vue"

const props = defineProps({
  modelValue: {
    type: [Number, String],
    default: null,
  },
  bots: {
    type: Array,
    default: () => [],
  },
  placeholder: {
    type: String,
    default: "璇烽€夋嫨 Bot",
  },
  onlyEnabled: {
    type: Boolean,
    default: true,
  },
})

defineEmits(["update:modelValue"])

const options = computed(() => (
  props.onlyEnabled ? props.bots.filter((bot) => bot.enabled) : props.bots
))

function botLabel(bot) {
  const username = bot.username ? ` @${String(bot.username).replace(/^@/, "")}` : ""
  return `${bot.name || "Bot"}${username} (#${bot.id})`
}
</script>

<style scoped>
.bot-select {
  width: 100%;
}

.option-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  min-width: 0;
}

.option-row span {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
