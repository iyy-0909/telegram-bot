<template>
  <el-container class="layout">
    <el-aside width="220px" class="aside">
      <div class="logo">校长克隆机器人</div>
      <AppMenu :active-menu="activeMenu" :items="visibleMenuItems" @select="handleSelect" />
    </el-aside>

    <el-container class="content-shell">
      <el-header class="header">
        <div class="header-title">
          <span>Telegram Clone System</span>
          <small>运营管理后台</small>
        </div>

        <div class="header-actions">
          <el-tag v-if="allowedMenus.includes('home')" :type="status === 'running' ? 'success' : 'danger'" size="small">
            {{ status || "unknown" }}
          </el-tag>
          <div class="current-user">
            <div class="current-user__identity">
              <strong>{{ currentUser?.username || "后台用户" }}</strong>
              <span>{{ roleLabel }} · {{ accessValidityLabel }}</span>
            </div>
            <el-tag :type="roleTagType" size="small" effect="plain">{{ roleLabel }}</el-tag>
            <el-button size="small" plain :loading="loggingOut" @click="$emit('logout')">退出</el-button>
          </div>
        </div>
      </el-header>

      <div class="mobile-menu">
        <AppMenu :active-menu="activeMenu" :items="visibleMenuItems" @select="handleSelect" />
      </div>

      <el-main class="main">
        <slot />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { computed, defineComponent, h, resolveComponent } from "vue"
import {
  Bell,
  ChatDotRound,
  Collection,
  Connection,
  Grid,
  Guide,
  House,
  MagicStick,
  Operation,
  Warning,
  Setting,
  Switch,
  User,
  UserFilled,
} from "@element-plus/icons-vue"

const props = defineProps({
  status: {
    type: String,
    default: "unknown",
  },
  activeMenu: {
    type: String,
    default: "rules",
  },
  allowedMenus: {
    type: Array,
    default: () => [],
  },
  currentUser: {
    type: Object,
    default: null,
  },
  loggingOut: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits(["change-menu", "logout"])

const menuItems = [
  ["home", "首页", House],
  ["rules", "监听任务", Switch],
  ["clone", "克隆任务", Collection],
  ["bots", "Bot 管理", Connection],
  ["my-channels", "频道管理", Grid],
  ["bulk-replace", "批量替换", Operation],
  ["support", "客服机器人", ChatDotRound],
  ["accounts", "账号管理", User],
  ["notifications", "消息通知", Bell],
  ["alerts", "系统告警", Warning],
  ["ai-settings", "AI 配置", MagicStick],
  ["settings", "系统设置", Setting],
  ["guide", "使用教程", Guide],
  ["user-access", "后台管理", UserFilled],
]
const visibleMenuItems = computed(() => menuItems.filter(([key]) => props.allowedMenus.includes(key)))
const roleLabel = computed(() => props.currentUser?.role === "admin" ? "管理员" : "普通用户")
const roleTagType = computed(() => props.currentUser?.role === "admin" ? "warning" : "info")
const accessValidityLabel = computed(() => {
  if (props.currentUser?.role === "admin") return "全部权限"
  if (props.currentUser?.access_state === "disabled") return "账号已停用"
  if (props.currentUser?.access_state === "expired") return "使用期已结束"
  if (["pending", "waiting"].includes(props.currentUser?.access_state)) return "待管理员授权"
  if (!props.currentUser?.access_expires_at) return "永久有效"
  const expiresAt = new Date(props.currentUser.access_expires_at)
  if (Number.isNaN(expiresAt.getTime())) return "期限未知"
  const remaining = expiresAt.getTime() - Date.now()
  if (remaining <= 0) return "使用期已结束"
  const days = Math.ceil(remaining / (24 * 60 * 60 * 1000))
  return days <= 1 ? "不足 1 天" : `剩余 ${days} 天`
})
const handleSelect = (menu) => {
  emit("change-menu", menu)
}

const AppMenu = defineComponent({
  props: {
    activeMenu: {
      type: String,
      default: "rules",
    },
    items: {
      type: Array,
      default: () => [],
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
    }, () => props.items.map(([index, label, icon]) => h(resolveComponent("el-menu-item"), {
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
  position: fixed;
  inset: 0 auto 0 0;
  z-index: 100;
  height: 100vh;
  background: #111827;
  color: #cbd5e1;
  overflow-y: auto;
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
  width: calc(100% - 220px);
  margin-left: 220px;
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

.header-actions,
.current-user {
  display: flex;
  align-items: center;
  gap: 10px;
}

.current-user {
  padding-left: 10px;
  border-left: 1px solid var(--el-border-color, #e5e7eb);
}

.current-user__identity {
  min-width: 0;
  text-align: right;
}

.current-user__identity strong,
.current-user__identity span {
  display: block;
  max-width: 180px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.current-user__identity strong {
  color: var(--el-text-color-primary, #303133);
  font-size: 13px;
}

.current-user__identity span {
  margin-top: 1px;
  color: var(--el-text-color-secondary, #909399);
  font-size: 11px;
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
  scrollbar-width: none;
}

.mobile-menu::-webkit-scrollbar {
  display: none;
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

  .content-shell {
    width: 100%;
    margin-left: 0;
  }

  .header {
    height: 56px;
    padding: 0 14px;
  }

  .header-actions {
    gap: 6px;
  }

  .current-user {
    gap: 6px;
    padding-left: 6px;
  }

  .current-user__identity,
  .current-user > .el-tag {
    display: none;
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

