<template>
  <el-select
    :model-value="modelValue"
    :multiple="multiple"
    :placeholder="placeholder"
    filterable
    clearable
    collapse-tags
    collapse-tags-tooltip
    :allow-create="allowCreate"
    :default-first-option="allowCreate"
    class="channel-select"
    @update:model-value="$emit('update:modelValue', $event)"
  >
    <el-option-group
      v-for="group in groupedChannels"
      :key="group.name"
      :label="group.name"
    >
      <el-option
        v-for="channel in group.items"
        :key="channel.id"
        :label="channelLabel(channel)"
        :value="channelValue(channel)"
        :disabled="channel.status !== 'enabled' && !includeDisabled"
      >
        <div class="option-row">
          <span>{{ channelLabel(channel) }}</span>
          <el-tag size="small" :type="channel.status === 'enabled' ? 'success' : 'warning'">
            {{ channel.status }}
          </el-tag>
        </div>
      </el-option>
    </el-option-group>
  </el-select>
</template>

<script setup>
import { computed, onMounted, ref, watch } from "vue"
import { getMyChannels } from "../api/myChannels"

const props = defineProps({
  modelValue: {
    type: [String, Array],
    default: "",
  },
  multiple: {
    type: Boolean,
    default: false,
  },
  placeholder: {
    type: String,
    default: "请选择频道",
  },
  includeDisabled: {
    type: Boolean,
    default: false,
  },
  botId: {
    type: [Number, String, null],
    default: null,
  },
  allowCreate: {
    type: Boolean,
    default: false,
  },
})

defineEmits(["update:modelValue"])

const channels = ref([])

const groupedChannels = computed(() => {
  const groups = new Map()
  const filtered = channels.value.filter((channel) => {
    if (!props.includeDisabled && channel.status !== "enabled") {
      return false
    }

    if (props.botId && channel.bot_id && Number(channel.bot_id) !== Number(props.botId)) {
      return false
    }

    return true
  })

  for (const channel of filtered) {
    const groupName = channel.group_name || "默认分组"

    if (!groups.has(groupName)) {
      groups.set(groupName, [])
    }

    groups.get(groupName).push(channel)
  }

  return Array.from(groups.entries()).map(([name, items]) => ({ name, items }))
})

watch(
  () => props.botId,
  () => loadChannels(),
)

onMounted(loadChannels)

async function loadChannels() {
  const res = await getMyChannels({
    bot_id: props.botId || undefined,
  })
  channels.value = res.data.items || []
}

function channelValue(channel) {
  return channel.username || channel.chat_id || channel.target_value || ""
}

function channelLabel(channel) {
  const name = channel.title || channel.username || channel.chat_id || `频道 ${channel.id}`
  const value = channel.username || channel.chat_id || ""
  return value && value !== name ? `${name} (${value})` : name
}
</script>

<style scoped>
.channel-select {
  width: 100%;
}

.option-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
</style>
