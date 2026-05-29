<template>
  <el-dialog
    :model-value="visible"
    @update:model-value="handleVisibleChange"
    :title="isRelogin ? '重新登录采集账号' : '登录新增采集账号'"
    width="640px"
    destroy-on-close
  >
    <el-alert
      title="验证码和二步验证密码只用于本次登录，不会保存到数据库，也不会写入日志。"
      type="info"
      show-icon
      :closable="false"
    />

    <el-steps :active="activeStep" finish-status="success" class="login-steps">
      <el-step title="基础信息" />
      <el-step title="验证码" />
      <el-step title="完成" />
    </el-steps>

    <el-form
      v-if="activeStep === 0"
      label-width="130px"
      :model="form"
      class="login-form"
    >
      <el-form-item label="账号名称" required>
        <el-input v-model="form.name" placeholder="例如 主采集账号" />
      </el-form-item>

      <el-form-item label="手机号" required>
        <el-input v-model="form.phone" placeholder="例如 +86138xxxx 或 86138xxxx" />
      </el-form-item>

      <el-form-item label="Session路径" required>
        <el-input v-model="form.session_path" placeholder="例如 data/sessions/collector_1" />
      </el-form-item>

      <el-form-item label="代理">
        <el-input v-model="form.proxy" placeholder="可留空，例如 socks5://host:port" />
      </el-form-item>

      <el-form-item label="备注">
        <el-input v-model="form.remark" type="textarea" :rows="3" />
      </el-form-item>
    </el-form>

    <div v-else-if="activeStep === 1" class="verify-panel">
      <el-alert
        :title="verifyHint"
        type="success"
        show-icon
        :closable="false"
      />

      <el-form label-width="130px" class="login-form">
        <el-form-item label="验证码" required>
          <el-input v-model="verifyForm.code" placeholder="请输入 Telegram 验证码" />
        </el-form-item>

        <el-form-item v-if="needPassword" label="二步密码" required>
          <el-input
            v-model="verifyForm.password"
            type="password"
            show-password
            placeholder="请输入 Telegram 二步验证密码"
          />
        </el-form-item>
      </el-form>
    </div>

    <div v-else class="success-panel">
      <el-result
        icon="success"
        title="账号登录成功"
        :sub-title="successText"
      />
    </div>

    <template #footer>
      <el-button @click="closeDialog">关闭</el-button>

      <el-button
        v-if="activeStep === 0"
        type="primary"
        :loading="loading"
        @click="sendCode"
      >
        发送验证码
      </el-button>

      <el-button
        v-if="activeStep === 1"
        type="primary"
        :loading="loading"
        @click="verifyCode"
      >
        {{ needPassword ? "提交二步验证" : "登录" }}
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed, reactive, ref, watch } from "vue"
import { ElMessage, ElMessageBox } from "element-plus"
import { startAccountLogin, verifyAccountLogin } from "../api/accounts"

const props = defineProps({
  visible: Boolean,
  account: {
    type: Object,
    default: null,
  },
})

const emit = defineEmits(["update:visible", "success"])

const loading = ref(false)
const activeStep = ref(0)
const loginId = ref("")
const needPassword = ref(false)
const savedAccount = ref(null)

const form = reactive({
  account_id: null,
  name: "",
  phone: "",
  session_path: "",
  proxy: "",
  remark: "",
  update_existing: false,
})

const verifyForm = reactive({
  code: "",
  password: "",
})

const isRelogin = computed(() => Boolean(form.account_id))

const verifyHint = computed(() => (
  needPassword.value
    ? "该账号开启了二步验证，请继续输入二步验证密码。"
    : "验证码已发送到 Telegram，请输入收到的验证码。"
))

const successText = computed(() => {
  const account = savedAccount.value || {}
  const username = account.username ? `@${account.username}` : "-"
  return `ID：${account.id || "-"}，用户名：${username}，Session：${account.session_path || "-"}`
})

watch(
  () => props.visible,
  (visible) => {
    if (!visible) return
    resetState()
  },
)

function nextSessionPath() {
  return "data/sessions/collector_new"
}

function resetState() {
  const account = props.account || {}
  activeStep.value = 0
  loading.value = false
  loginId.value = ""
  needPassword.value = false
  savedAccount.value = null
  verifyForm.code = ""
  verifyForm.password = ""

  form.account_id = account.id || null
  form.name = account.name || ""
  form.phone = account.phone || ""
  form.session_path = account.session_path || nextSessionPath()
  form.proxy = account.proxy || ""
  form.remark = account.remark || ""
  form.update_existing = Boolean(account.id)
}

function closeDialog() {
  emit("update:visible", false)
}

function handleVisibleChange(value) {
  emit("update:visible", value)
}

function validateBaseForm() {
  if (!form.name) {
    ElMessage.error("账号名称不能为空")
    return false
  }

  if (!form.phone) {
    ElMessage.error("手机号不能为空")
    return false
  }

  if (!form.session_path) {
    ElMessage.error("Session 路径不能为空")
    return false
  }

  return true
}

async function sendCode() {
  if (!validateBaseForm()) {
    return
  }

  loading.value = true

  try {
    const payload = {
      account_id: form.account_id || null,
      name: form.name,
      phone: form.phone,
      session_path: form.session_path,
      proxy: form.proxy,
      remark: form.remark,
      update_existing: form.update_existing,
    }

    const res = await startAccountLogin(payload)
    const data = res.data || {}

    if (data.ok && data.already_authorized) {
      savedAccount.value = data.account
      activeStep.value = 2
      emit("success", data.account)
      ElMessage.success(data.message || "账号已授权")
      return
    }

    if (data.ok) {
      loginId.value = data.login_id
      activeStep.value = 1
      ElMessage.success(data.message || "验证码已发送")
      return
    }

    if (data.code === "session_path_exists" && data.existing_account) {
      await ElMessageBox.confirm(
        `该 Session 路径已属于账号 #${data.existing_account.id}：${data.existing_account.name}。是否改为更新这个已有账号？`,
        "Session 路径已存在",
        { type: "warning" },
      )

      form.account_id = data.existing_account.id
      form.name = data.existing_account.name || form.name
      form.update_existing = true
      await sendCode()
      return
    }

    ElMessage.error(data.message || "发送验证码失败")
  } catch (error) {
    ElMessage.error(error?.response?.data?.message || error.message || "发送验证码失败")
  } finally {
    loading.value = false
  }
}

async function verifyCode() {
  if (!verifyForm.code) {
    ElMessage.error("验证码不能为空")
    return
  }

  loading.value = true

  try {
    const res = await verifyAccountLogin({
      login_id: loginId.value,
      code: verifyForm.code,
      password: verifyForm.password,
    })
    const data = res.data || {}

    if (data.ok) {
      savedAccount.value = data.account
      activeStep.value = 2
      emit("success", data.account)
      ElMessage.success("账号登录成功")
      return
    }

    if (data.need_password) {
      needPassword.value = true
      ElMessage.warning(data.message || "请输入二步验证密码")
      return
    }

    ElMessage.error(data.message || "登录验证失败")
  } catch (error) {
    ElMessage.error(error?.response?.data?.message || error.message || "登录验证失败")
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-steps {
  margin: 18px 0;
}

.login-form {
  margin-top: 12px;
}

.verify-panel,
.success-panel {
  margin-top: 12px;
}
</style>
