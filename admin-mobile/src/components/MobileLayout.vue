<template>
  <div class="mobile-shell">
    <header class="top-bar">
      <div class="top-title">
        <strong>{{ currentTitle }}</strong>
        <span>{{ currentSubtitle }}<template v-if="user?.username"> · {{ user.username }}</template></span>
      </div>
      <div class="top-actions">
        <request-button
          circle
          plain
          :disabled="refreshDisabled"
          :aria-label="refreshDisabled ? '当前页面无需刷新' : '刷新当前页面'"
          :title="refreshDisabled ? '当前页面无需刷新' : '刷新当前页面'"
          @click="emit('refresh')"
        >
          <el-icon><Refresh /></el-icon>
        </request-button>
        <request-button circle plain aria-label="退出登录" title="退出登录" @click="emit('logout')">
          <el-icon><SwitchButton /></el-icon>
        </request-button>
      </div>
    </header>

    <main>
      <slot />
    </main>

    <nav
      class="bottom-nav"
      aria-label="主要导航"
      :style="{ gridTemplateColumns: `repeat(${Math.max(navItems.length, 1)}, minmax(0, 1fr))` }"
    >
      <request-button native
        v-for="item in navItems"
        :key="item.key"
        type="button"
        class="nav-item"
        :class="{ active: active === item.key }"
        :aria-current="active === item.key ? 'page' : undefined"
        @click="emit('change', item.key)"
      >
        <el-icon><component :is="item.icon" /></el-icon>
        <span>{{ item.label }}</span>
      </request-button>
    </nav>
  </div>
</template>

<script setup>
import { useRequestEmit } from '../../../frontend-shared/requestActions.mjs'

import { computed } from "vue"
import {
  Collection,
  Grid,
  House,
  MoreFilled,
  Refresh,
  Switch,
  SwitchButton,
} from "@element-plus/icons-vue"

const props = defineProps({
  requestActions: { type: Object, default: () => ({}) },
  active: {
    type: String,
    required: true,
  },
  navKeys: {
    type: Array,
    default: () => ["home", "listeners", "clones", "channels", "more"],
  },
  user: {
    type: Object,
    default: null,
  },
  refreshDisabled: {
    type: Boolean,
    default: false,
  },
})

const rawEmit = defineEmits(["change", "refresh", "logout"])
const emit = useRequestEmit(rawEmit, props)

const allNavItems = [
  { key: "home", label: "首页", title: "移动运营台", subtitle: "排队、告警和系统状态", icon: House },
  { key: "listeners", label: "监听", title: "监听任务", subtitle: "实时监听、补齐和漏发处理", icon: Switch },
  { key: "clones", label: "克隆", title: "克隆任务", subtitle: "克隆进度和任务控制", icon: Collection },
  { key: "channels", label: "频道", title: "我的频道", subtitle: "频道检测、投放和收录状态", icon: Grid },
  { key: "more", label: "更多", title: "更多功能", subtitle: "Bot、客服、模板和账号", icon: MoreFilled },
]

const navItems = computed(() => {
  const allowed = new Set(props.navKeys)
  return allNavItems.filter((item) => allowed.has(item.key))
})

const activeItem = computed(() => navItems.value.find((item) => item.key === props.active) || navItems.value[0] || allNavItems[4])
const currentTitle = computed(() => activeItem.value.title)
const currentSubtitle = computed(() => activeItem.value.subtitle)
</script>

<style scoped>
.top-actions {
  display: flex;
  flex: 0 0 auto;
  gap: 6px;
}

.top-actions :deep(.el-button) {
  width: 44px;
  height: 44px;
  margin-left: 0;
}
</style>
