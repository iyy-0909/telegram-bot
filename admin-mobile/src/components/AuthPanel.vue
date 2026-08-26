<template>
  <main class="mobile-auth-page">
    <section class="mobile-auth-panel" aria-labelledby="mobile-auth-title">
      <header class="mobile-auth-header">
        <div class="mobile-product-mark">TG</div>
        <div>
          <h1 id="mobile-auth-title">移动运营台</h1>
          <p>{{ mode === "login" ? "正常登录请输入用户名和密码" : "首次使用请在服务器本机创建首个账号" }}</p>
        </div>
      </header>

      <el-radio-group v-model="mode" class="mobile-auth-mode" size="large" :disabled="submitting">
        <el-radio-button value="login">登录</el-radio-button>
        <el-radio-button value="register">注册</el-radio-button>
      </el-radio-group>

      <el-alert
        v-show="requestError"
        :title="requestError"
        type="error"
        show-icon
        :closable="false"
        class="mobile-auth-error"
      />

      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        :validate-on-rule-change="false"
        label-position="top"
        @submit.prevent="submit"
      >
        <el-form-item v-if="mode === 'register'" label="用户名" prop="username">
          <el-input
            v-model="form.username"
            size="large"
            maxlength="24"
            autocomplete="username"
            placeholder="4-24 位，以字母开头"
            clearable
          />
          <p class="mobile-field-help">支持字母、数字和下划线。首个账号成为管理员，后续注册由系统配置决定。</p>
        </el-form-item>

        <el-form-item v-else label="用户名" prop="loginUsername">
          <el-input
            v-model="form.loginUsername"
            size="large"
            maxlength="24"
            autocomplete="username"
            placeholder="请输入用户名"
            clearable
          />
          <p class="mobile-field-help">正常登录需要填写已注册的用户名。首次使用可在服务器本机切换到注册。</p>
        </el-form-item>

        <el-form-item label="密码" prop="password">
          <el-input
            v-model="form.password"
            type="password"
            size="large"
            maxlength="128"
            show-password
            :autocomplete="mode === 'register' ? 'new-password' : 'current-password'"
            :placeholder="mode === 'register' ? '至少 8 位，包含字母和数字' : '请输入密码'"
            @keyup.enter="mode === 'login' && submit()"
          />
        </el-form-item>

        <el-form-item v-if="mode === 'register'" label="确认密码" prop="confirmPassword">
          <el-input
            v-model="form.confirmPassword"
            type="password"
            size="large"
            maxlength="128"
            show-password
            autocomplete="new-password"
            placeholder="再次输入密码"
          />
        </el-form-item>

        <el-form-item v-if="mode === 'register'" label="图形验证码" prop="captchaCode">
          <div class="mobile-captcha-field">
            <el-input
              v-model="form.captchaCode"
              size="large"
              maxlength="5"
              autocomplete="off"
              placeholder="输入图中字符"
              @keyup.enter="submit"
            />
            <button
              type="button"
              class="mobile-captcha-image"
              :disabled="captchaLoading || submitting"
              aria-label="刷新图形验证码"
              title="点击刷新验证码"
              @click="loadCaptcha"
            >
              <img v-if="captchaImage" :src="captchaImage" alt="图形验证码" />
              <el-icon v-else :class="{ rotating: captchaLoading }"><Refresh /></el-icon>
            </button>
          </div>
          <p class="mobile-field-help">点击图片可刷新，5 分钟内有效。</p>
        </el-form-item>

        <el-button
          type="primary"
          size="large"
          native-type="submit"
          class="mobile-auth-submit"
          :loading="submitting"
          :disabled="mode === 'register' && captchaLoading"
        >
          {{ mode === "login" ? "登录" : "注册并登录" }}
        </el-button>
      </el-form>
    </section>
  </main>
</template>

<script setup>
import { computed, nextTick, reactive, ref, watch } from "vue"
import { Refresh } from "@element-plus/icons-vue"
import { getCaptcha, loginAdmin, registerUser } from "../api"

const emit = defineEmits(["authenticated"])
const mode = ref("login")
const formRef = ref(null)
const submitting = ref(false)
const captchaLoading = ref(false)
const captchaId = ref("")
const captchaImage = ref("")
const requestError = ref("")
const form = reactive({
  username: "",
  loginUsername: "",
  password: "",
  confirmPassword: "",
  captchaCode: "",
})

function validateUsername(_rule, value, callback) {
  if (!/^[A-Za-z][A-Za-z0-9_]{3,23}$/.test((value || "").trim())) {
    callback(new Error("请输入 4-24 位用户名，并以字母开头"))
    return
  }
  callback()
}

function validatePassword(_rule, value, callback) {
  if (mode.value === "register") {
    if ((value || "").length < 8 || !/[A-Za-z]/.test(value) || !/\d/.test(value)) {
      callback(new Error("密码至少 8 位，并同时包含字母和数字"))
      return
    }
  } else if (!value) {
    callback(new Error("请输入密码"))
    return
  }
  callback()
}

function validateConfirmPassword(_rule, value, callback) {
  if (value !== form.password) {
    callback(new Error("两次输入的密码不一致"))
    return
  }
  callback()
}

const rules = computed(() => ({
  username: mode.value === "register" ? [{ validator: validateUsername, trigger: "blur" }] : [],
  password: [{ validator: validatePassword, trigger: "blur" }],
  confirmPassword: mode.value === "register" ? [{ validator: validateConfirmPassword, trigger: "blur" }] : [],
  captchaCode: mode.value === "register" ? [{ required: true, message: "请输入图形验证码", trigger: "blur" }] : [],
}))

async function loadCaptcha() {
  captchaLoading.value = true
  requestError.value = ""
  try {
    const response = await getCaptcha()
    captchaId.value = response.data?.captcha_id || ""
    captchaImage.value = response.data?.image || ""
    form.captchaCode = ""
    if (!captchaId.value || !captchaImage.value) throw new Error("验证码加载失败")
  } catch (error) {
    captchaId.value = ""
    captchaImage.value = ""
    requestError.value = error.response?.data?.detail || error.message || "验证码加载失败，请重试"
  } finally {
    captchaLoading.value = false
  }
}

async function submit() {
  requestError.value = ""
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  submitting.value = true
  try {
    const response = mode.value === "register"
      ? await registerUser({
          username: form.username.trim(),
          password: form.password,
          captcha_id: captchaId.value,
          captcha_code: form.captchaCode.trim(),
        })
      : await loginAdmin(form.password, form.loginUsername.trim())
    const token = response.data?.token
    if (!token) throw new Error("登录成功但未返回访问凭证")
    emit("authenticated", token, mode.value)
  } catch (error) {
    const operationError = error.response?.data?.detail || error.message || "操作失败，请稍后重试"
    if (mode.value === "register") await loadCaptcha()
    requestError.value = operationError
  } finally {
    submitting.value = false
  }
}

watch(mode, async (nextMode) => {
  requestError.value = ""
  form.password = ""
  form.confirmPassword = ""
  form.captchaCode = ""
  await nextTick()
  formRef.value?.clearValidate()
  if (nextMode === "register" && !captchaImage.value) await loadCaptcha()
})
</script>

<style scoped>
.mobile-auth-page {
  min-height: 100vh;
  display: grid;
  place-items: center;
  padding: 16px;
  background: var(--bg, #f5f7fb);
}

.mobile-auth-panel {
  width: min(420px, 100%);
  padding: 22px 18px;
  background: var(--panel, #fff);
  border: 1px solid var(--border, #e5e7eb);
  border-radius: 8px;
  box-shadow: var(--shadow, 0 4px 14px rgba(15, 23, 42, 0.05));
}

.mobile-auth-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 20px;
}

.mobile-product-mark {
  display: grid;
  place-items: center;
  flex: 0 0 42px;
  width: 42px;
  height: 42px;
  border-radius: 8px;
  color: #fff;
  background: var(--primary, #2563eb);
  font-size: 14px;
  font-weight: 800;
}

.mobile-auth-header h1 {
  margin: 0;
  font-size: 20px;
  letter-spacing: 0;
}

.mobile-auth-header p {
  margin: 3px 0 0;
  color: var(--muted, #6b7280);
  font-size: 12px;
}

.mobile-auth-mode {
  display: flex;
  margin-bottom: 18px;
}

.mobile-auth-mode :deep(.el-radio-button) {
  flex: 1;
}

.mobile-auth-mode :deep(.el-radio-button__inner) {
  width: 100%;
}

.mobile-auth-error {
  margin-bottom: 16px;
}

.mobile-field-help {
  margin: 4px 0 0;
  color: var(--muted, #6b7280);
  font-size: 12px;
  line-height: 1.5;
}

.mobile-captcha-field {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 136px;
  gap: 8px;
  width: 100%;
}

.mobile-captcha-image {
  display: grid;
  place-items: center;
  width: 136px;
  height: 42px;
  padding: 0;
  overflow: hidden;
  border: 1px solid var(--border, #dcdfe6);
  border-radius: 4px;
  background: #f4f7fb;
  color: var(--primary, #2563eb);
  cursor: pointer;
}

.mobile-captcha-image:focus-visible {
  outline: 2px solid var(--primary, #2563eb);
  outline-offset: 2px;
}

.mobile-captcha-image:disabled {
  cursor: not-allowed;
  opacity: 0.65;
}

.mobile-captcha-image img {
  display: block;
  width: 136px;
  height: 52px;
}

.mobile-auth-submit {
  width: 100%;
}

.rotating {
  animation: rotate 0.8s linear infinite;
}

@keyframes rotate {
  to { transform: rotate(360deg); }
}

@media (max-width: 360px) {
  .mobile-captcha-field {
    grid-template-columns: 1fr;
  }

  .mobile-captcha-image,
  .mobile-captcha-image img {
    width: 100%;
  }
}
</style>
