<template>
  <el-container class="layout">
    <el-aside width="220px" class="aside">
      <div class="logo">校长克隆机器人</div>
      <AppMenu :active-menu="activeMenu" @select="handleSelect" />
    </el-aside>

    <el-container class="content-shell">
      <el-header class="header">
        <div class="header-title">
          <span>Telegram Clone System</span>
          <small>运营管理后台</small>
        </div>

        <el-tag :type="status === 'running' ? 'success' : 'danger'" size="small">
          {{ status || "unknown" }}
        </el-tag>
      </el-header>

      <div class="mobile-menu">
        <AppMenu :active-menu="activeMenu" @select="handleSelect" />
      </div>

      <el-main class="main">
        <slot />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { defineComponent, h, resolveComponent } from "vue"
import {
  ChatDotRound,
  Collection,
  Connection,
  Grid,
  Guide,
  House,
  Operation,
  Setting,
  Switch,
  User,
} from "@element-plus/icons-vue"

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
  ["home", "首页", House],
  ["rules", "监听任务", Switch],
  ["clone", "克隆任务", Collection],
  ["bots", "Bot 管理", Connection],
  ["my-channels", "我的频道", Grid],
  ["bulk-replace", "批量替换", Operation],
  ["support", "客服机器人", ChatDotRound],
  ["accounts", "账号管理", User],
  ["settings", "系统设置", Setting],
  ["guide", "使用教程", Guide],
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
    }, () => menuItems.map(([index, label, icon]) => h(resolveComponent("el-menu-item"), {
      index,
      key: index,
    }, () => [
      h(resolveComponent("el-icon"), null, () => h(icon)),
      h("span", label),
    ])))
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
  font-size: 16px;
  font-weight: 600;
  color: #303133;
}

.header-title span,
.header-title small {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.header-title small {
  margin-top: 2px;
  font-size: 12px;
  font-weight: 400;
  color: #909399;
}

.mobile-menu {
  display: none;
  background: #111827;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  overflow-x: auto;
}

.main {
  min-width: 0;
  background: #f3f4f6;
  padding: 20px;
}

@media (max-width: 900px) {
  .layout {
    display: block;
  }

  .aside {
    display: none;
  }

  .header {
    height: 56px;
    padding: 0 14px;
  }

  .mobile-menu {
    display: block;
  }

  .mobile-menu :deep(.el-menu) {
    display: flex;
    width: max-content;
    min-width: 100%;
  }

  .mobile-menu :deep(.el-menu-item) {
    flex: 0 0 auto;
    height: 46px;
    padding: 0 14px;
  }

  .main {
    padding: 12px;
  }
}
</style>

