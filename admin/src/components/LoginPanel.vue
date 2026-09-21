<template>
  <main class="auth-page">
    <section class="auth-panel" aria-labelledby="auth-title">
      <header class="auth-header">
        <div class="product-mark">TG</div>
        <div>
          <h1 id="auth-title">Telegram 运营后台</h1>
          <p>{{ mode === "login" ? "正常登录请输入用户名和密码" : "注册后由管理员分配功能和使用期限" }}</p>
        </div>
      </header>

      <el-radio-group v-model="mode" class="auth-mode" size="large" :disabled="submitting">
        <el-radio-button value="login">登录</el-radio-button>
        <el-radio-button value="register">注册</el-radio-button>
      </el-radio-group>

      <el-alert
        v-show="requestError || initialError"
        :title="requestError || initialError"
        type="error"
        show-icon
        :closable="false"
        class="auth-error"
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
            autocomplete="username"
            maxlength="24"
            placeholder="4-24 位，以字母开头"
            clearable
          />
          <div class="field-help">支持字母、数字和下划线，注册后不可修改。注册后由管理员分配功能和使用期限。</div>
        </el-form-item>

        <el-form-item v-else label="用户名" prop="loginUsername">
          <el-input
            v-model="form.loginUsername"
            size="large"
            autocomplete="username"
            maxlength="24"
            placeholder="请输入用户名"
            clearable
          />
          <div class="field-help">正常登录需要填写已注册的用户名。没有账号时可切换到注册。</div>
        </el-form-item>

        <el-form-item label="密码" prop="password">
          <el-input
            v-model="form.password"
            type="password"
            show-password
            :autocomplete="mode === 'register' ? 'new-password' : 'current-password'"
            maxlength="128"
            :placeholder="mode === 'register' ? '至少 8 位，包含字母和数字' : '请输入密码'"
            size="large"
            @keyup.enter="mode === 'login' && submit()"
          />
        </el-form-item>

        <el-form-item v-if="mode === 'register'" label="确认密码" prop="confirmPassword">
          <el-input
            v-model="form.confirmPassword"
            type="password"
            show-password
            autocomplete="new-password"
            maxlength="128"
            placeholder="再次输入密码"
            size="large"
          />
        </el-form-item>

        <el-form-item v-if="mode === 'register'" label="图形验证码" prop="captchaCode">
          <div class="captcha-field">
            <el-input
              v-model="form.captchaCode"
              size="large"
              maxlength="5"
              autocomplete="off"
              placeholder="输入图中字符"
              @keyup.enter="submit"
            />
            <request-button native
              type="button"
              class="captcha-image"
              :loading="captchaLoading"
              :disabled="submitting"
              aria-label="刷新图形验证码"
              title="点击刷新验证码"
              @click="loadCaptcha"
            >
              <img v-if="captchaImage" :src="captchaImage" alt="图形验证码" />
              <el-icon v-else :class="{ rotating: captchaLoading }"><Refresh /></el-icon>
            </request-button>
          </div>
          <div class="field-help">看不清可点击图片刷新，验证码 5 分钟内有效。</div>
        </el-form-item>

        <request-button
          type="primary"
          size="large"
          class="auth-submit"
          native-type="submit"
          :loading="submitting"
          :disabled="mode === 'register' && captchaLoading"
        >
          {{ mode === "login" ? "登录" : "注册并登录" }}
        </request-button>
      </el-form>
    </section>
  </main>
</template>

<script setup>
import { useRequestEmit } from '../../../frontend-shared/requestActions.mjs'

import { computed, nextTick, reactive, ref, watch } from "vue"
import { Refresh } from "@element-plus/icons-vue"
import { getCaptcha, loginAdmin, registerUser } from "../api/auth"

const requestProps = defineProps({
  requestActions: { type: Object, default: () => ({}) },
  initialError: {
    type: String,
    default: "",
  },
})

const rawEmit = defineEmits(["login"])
const emit = useRequestEmit(rawEmit, requestProps)

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
  if (captchaLoading.value) return
  captchaLoading.value = true
  requestError.value = ""
  try {
    const response = await getCaptcha()
    captchaId.value = response.data?.captcha_id || ""
    captchaImage.value = response.data?.image || ""
    form.captchaCode = ""
    if (!captchaId.value || !captchaImage.value) {
      throw new Error("验证码加载失败")
    }
  } catch (error) {
    captchaId.value = ""
    captchaImage.value = ""
    requestError.value = error.response?.data?.detail || error.message || "验证码加载失败，请重试"
  } finally {
    captchaLoading.value = false
  }
}

async function submit() {
  if (submitting.value) return
  submitting.value = true
  requestError.value = ""
  try {
    const valid = await formRef.value?.validate().catch(() => false)
    if (!valid) return
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
    await emit("login", token, mode.value)
  } catch (error) {
    const operationError = error.response?.data?.detail || error.message || "操作失败，请稍后重试"
    if (mode.value === "register") {
      await loadCaptcha()
    }
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
  if (nextMode === "register" && !captchaImage.value) {
    await loadCaptcha()
  }
})
</script>

<style scoped>
.auth-page {
  min-height: 100vh;
  display: grid;
  place-items: center;
  padding: 24px;
  background: var(--app-bg, #f3f4f6);
}

.auth-panel {
  width: min(440px, 100%);
  padding: 30px;
  background: #fff;
  border: 1px solid var(--border-color, #e5e7eb);
  border-radius: 8px;
  box-shadow: 0 12px 30px rgba(15, 23, 42, 0.08);
}

.auth-header {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-bottom: 22px;
}

.product-mark {
  display: grid;
  place-items: center;
  flex: 0 0 44px;
  width: 44px;
  height: 44px;
  border-radius: 8px;
  color: #fff;
  background: var(--primary, #409eff);
  font-size: 15px;
  font-weight: 800;
}

.auth-header h1 {
  margin: 0;
  font-size: 21px;
  letter-spacing: 0;
}

.auth-header p {
  margin: 3px 0 0;
  color: var(--text-muted, #6b7280);
  font-size: 13px;
}

.auth-mode {
  display: flex;
  margin-bottom: 20px;
}

.auth-mode :deep(.el-radio-button) {
  flex: 1;
}

.auth-mode :deep(.el-radio-button__inner) {
  width: 100%;
}

.auth-error {
  margin-bottom: 18px;
}

.field-help {
  margin-top: 5px;
  color: var(--text-muted, #6b7280);
  font-size: 12px;
  line-height: 1.5;
}

.captcha-field {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 160px;
  gap: 10px;
  width: 100%;
}

.captcha-image {
  display: grid;
  place-items: center;
  width: 160px;
  height: 42px;
  padding: 0;
  overflow: hidden;
  border: 1px solid var(--border-color, #dcdfe6);
  border-radius: 4px;
  background: #f4f7fb;
  color: var(--primary, #409eff);
  cursor: pointer;
}

.captcha-image:focus-visible {
  outline: 2px solid var(--primary, #409eff);
  outline-offset: 2px;
}

.captcha-image:disabled {
  cursor: not-allowed;
  opacity: 0.65;
}

.captcha-image img {
  display: block;
  width: 160px;
  height: 52px;
}

.auth-submit {
  width: 100%;
  margin-top: 2px;
}

.rotating {
  animation: rotate 0.8s linear infinite;
}

@keyframes rotate {
  to { transform: rotate(360deg); }
}

@media (max-width: 480px) {
  .auth-page {
    padding: 16px;
  }

  .auth-panel {
    padding: 22px 18px;
  }

  .captcha-field {
    grid-template-columns: minmax(0, 1fr) 136px;
  }

  .captcha-image,
  .captcha-image img {
    width: 136px;
  }
}
</style>
