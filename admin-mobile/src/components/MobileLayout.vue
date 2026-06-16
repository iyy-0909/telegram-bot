<template>
  <div class="mobile-shell">
    <header class="top-bar">
      <div class="top-title">
        <strong>{{ currentTitle }}</strong>
        <span>{{ currentSubtitle }}</span>
      </div>
      <el-button circle plain @click="$emit('refresh')">
        <el-icon><Refresh /></el-icon>
      </el-button>
    </header>

    <main>
      <slot />
    </main>

    <nav class="bottom-nav">
      <button
        v-for="item in navItems"
        :key="item.key"
        type="button"
        class="nav-item"
        :class="{ active: active === item.key }"
        @click="$emit('change', item.key)"
      >
        <el-icon><component :is="item.icon" /></el-icon>
        <span>{{ item.label }}</span>
      </button>
    </nav>
  </div>
</template>

<script setup>
import { computed } from "vue"
import {
  Collection,
  Grid,
  House,
  MoreFilled,
  Refresh,
  Switch,
} from "@element-plus/icons-vue"

const props = defineProps({
  active: {
    type: String,
    required: true,
  },
})

defineEmits(["change", "refresh"])

const navItems = [
  { key: "home", label: "首页", title: "移动运营台", subtitle: "排队、告警和系统状态", icon: House },
  { key: "listeners", label: "监听", title: "监听任务", subtitle: "实时监听、补齐和漏发处理", icon: Switch },
  { key: "clones", label: "克隆", title: "克隆任务", subtitle: "克隆进度和任务控制", icon: Collection },
  { key: "channels", label: "频道", title: "我的频道", subtitle: "频道检测、投放和收录状态", icon: Grid },
  { key: "more", label: "更多", title: "更多功能", subtitle: "Bot、客服、模板和账号", icon: MoreFilled },
]

const activeItem = computed(() => navItems.find((item) => item.key === props.active) || navItems[0])
const currentTitle = computed(() => activeItem.value.title)
const currentSubtitle = computed(() => activeItem.value.subtitle)
</script>
