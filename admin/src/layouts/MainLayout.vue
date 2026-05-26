<template>
  <el-container class="layout">
    <el-aside width="220px" class="aside">
      <div class="logo">
        校长克隆机器人
      </div>

      <el-menu
        :default-active="activeMenu"
        class="menu"
        background-color="#111827"
        text-color="#cbd5e1"
        active-text-color="#ffffff"
        @select="handleSelect"
      >
        <el-menu-item index="rules">
          <span>监听任务</span>
        </el-menu-item>

        <el-menu-item index="clone">
          <span>克隆任务</span>
        </el-menu-item>

        <el-menu-item index="bots">
          <span>Bot 管理</span>
        </el-menu-item>

        <el-menu-item index="my-channels">
          <span>我的频道</span>
        </el-menu-item>

        <el-menu-item index="support">
          <span>客服机器人</span>
        </el-menu-item>

        <el-menu-item index="templates">
          <span>内容模板规则</span>
        </el-menu-item>

        <el-menu-item index="accounts">
          <span>账号管理</span>
        </el-menu-item>

        <el-menu-item index="logs">
          <span>运行日志</span>
        </el-menu-item>

        <el-menu-item index="settings">
          <span>系统设置</span>
        </el-menu-item>

        <el-menu-item index="guide">
          <span>使用教程</span>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <el-container>
      <el-header class="header">
        <div class="header-title">
          Telegram Clone System
        </div>

        <el-tag
          :type="status === 'running' ? 'success' : 'danger'"
          size="small"
        >
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

const emit = defineEmits([
  "change-menu",
])

const handleSelect = (menu) => {
  emit("change-menu", menu)
}
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

.header {
  height: 60px;
  background: #ffffff;
  border-bottom: 1px solid #e5e7eb;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
}

.header-title {
  font-size: 16px;
  font-weight: 600;
  color: #303133;
}

.main {
  background: #f3f4f6;
  padding: 20px;
}
</style>
