<template>
  <div class="login-page">
    <div class="login-box">
      <div class="login-title">Telegram 后台</div>
      <div class="login-subtitle">请输入访问密码</div>

      <el-form @submit.prevent="submit">
        <el-form-item>
          <el-input
            v-model="password"
            type="password"
            show-password
            autocomplete="current-password"
            placeholder="访问密码"
            size="large"
            @keyup.enter="submit"
          />
        </el-form-item>

        <el-button
          type="primary"
          size="large"
          class="login-button"
          :loading="loading"
          @click="submit"
        >
          进入后台
        </el-button>
      </el-form>
    </div>
  </div>
</template>

<script setup>
import { ref } from "vue"
import { ElMessage } from "element-plus"
import { loginAdmin } from "../api/auth"

const emit = defineEmits(["login"])

const password = ref("")
const loading = ref(false)

async function submit() {
  const value = password.value.trim()

  if (!value) {
    ElMessage.warning("请输入访问密码")
    return
  }

  loading.value = true

  try {
    const res = await loginAdmin(value)
    const token = res.data?.token

    if (!token) {
      ElMessage.error("登录失败，未返回访问凭证")
      return
    }

    emit("login", token)
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || "密码错误")
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #eef2f7;
  padding: 24px;
}

.login-box {
  width: min(380px, 100%);
  padding: 32px;
  border-radius: 14px;
  background: #ffffff;
  box-shadow: 0 18px 50px rgba(15, 23, 42, 0.12);
}

.login-title {
  font-size: 24px;
  font-weight: 700;
  color: #111827;
}

.login-subtitle {
  margin: 8px 0 24px;
  color: #6b7280;
  font-size: 14px;
}

.login-button {
  width: 100%;
}
</style>
