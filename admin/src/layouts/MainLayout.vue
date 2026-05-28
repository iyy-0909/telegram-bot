<template>
  <el-container class="layout">
    <el-aside width="220px" class="aside">
      <div class="logo">校长克隆机器人</div>
      <AppMenu :active-menu="activeMenu" @select="handleSelect" />
    </el-aside>

    <el-container class="content-shell">
      <el-header class="header">
        <div class="header-title">Telegram Clone System</div>

        <el-tag :type="status === 'running' ? 'success' : 'danger'" size="small">
          {{ status || "unknown" }}
        </el-tag>
      </el-header>

      <el-main class="main">
        <slot />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { defineComponent, h, resolveComponent } from "vue"

defineProps({
  status: {
    type: String,
    default: "unknown",
  },
  activeMenu: {
    type: String,
    default: "rules",
  },
})

const emit = defineEmits(["change-menu"])

const menuItems = [
  ["rules", "监听任务"],
  ["clone", "克隆任务"],
  ["bots", "Bot 管理"],
  ["my-channels", "我的频道"],
  ["support", "客服机器人"],
  ["templates", "内容模板规则"],
  ["accounts", "账号管理"],
  ["logs", "运行日志"],
  ["settings", "系统设置"],
  ["guide", "使用教程"],
]

const handleSelect = (menu) => {
  emit("change-menu", menu)
}

const AppMenu = defineComponent({
  props: {
    activeMenu: {
      type: String,
      default: "rules",
    },
  },
  emits: ["select"],
  setup(props, { emit: componentEmit }) {
    return () => h(resolveComponent("el-menu"), {
      defaultActive: props.activeMenu,
      class: "menu",
      backgroundColor: "#111827",
      textColor: "#cbd5e1",
      activeTextColor: "#ffffff",
      onSelect: (menu) => componentEmit("select", menu),
    }, () => menuItems.map(([index, label]) => h(resolveComponent("el-menu-item"), {
      index,
      key: index,
    }, () => h("span", label))))
  },
})
</script>

<style scoped>
.layout {
  min-height: 100vh;
}

.aside {
  background: #111827;
  color: #cbd5e1;
}

.logo {
  height: 60px;
  display: flex;
  align-items: center;
  padding-left: 22px;
  font-size: 18px;
  font-weight: 700;
  color: #ffffff;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.menu {
  border-right: none;
}

.content-shell {
  min-width: 0;
}

.header {
  height: 60px;
  background: #ffffff;
  border-bottom: 1px solid #e5e7eb;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 0 24px;
}

.header-title {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 16px;
  font-weight: 600;
  color: #303133;
}

.main {
  min-width: 0;
  background: #f3f4f6;
  padding: 20px;
}
</style>
