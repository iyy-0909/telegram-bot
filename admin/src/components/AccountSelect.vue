<template>
  <el-select
    :model-value="modelValue"
    :placeholder="placeholder"
    clearable
    filterable
    class="account-select"
    @update:model-value="$emit('update:modelValue', $event)"
  >
    <el-option
      v-for="account in options"
      :key="account.id"
      :label="accountLabel(account)"
      :value="account.id"
      :disabled="onlyEnabled && !account.enabled"
    >
      <div class="option-row">
        <span>{{ accountLabel(account) }}</span>
        <StatusTag :status="account.enabled ? 'enabled' : 'disabled'" />
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
  accounts: {
    type: Array,
    default: () => [],
  },
  placeholder: {
    type: String,
    default: "请选择采集账号",
  },
  onlyEnabled: {
    type: Boolean,
    default: true,
  },
})

defineEmits(["update:modelValue"])

const options = computed(() => (
  props.onlyEnabled ? props.accounts.filter((account) => account.enabled) : props.accounts
))

function accountLabel(account) {
  const username = account.username ? ` @${String(account.username).replace(/^@/, "")}` : ""
  const phone = account.phone ? ` ${account.phone}` : ""
  return `${account.name || "账号"}${username}${phone} (#${account.id})`
}
</script>

<style scoped>
.account-select {
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
