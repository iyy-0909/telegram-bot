<template>
  <div class="mobile-profile-editor">
    <el-skeleton v-if="loading" :rows="10" animated />
    <el-result v-else-if="loadError" icon="error" title="公开资料加载失败" :sub-title="loadError">
      <template #extra><el-button type="primary" @click="loadProfile">重新加载</el-button></template>
    </el-result>

    <el-form v-else ref="formRef" :model="form" :rules="rules" label-position="top">
      <el-alert
        title="修改后会直接展示给 Telegram 用户"
        description="描述图片和隐私政策需要机器人拥有者账号支持；不可用的配置会显示具体原因。"
        type="info" :closable="false" show-icon class="profile-tip"
      />

      <section class="profile-section">
        <div class="section-heading">
          <div><h3>基础资料</h3><p>Name、About 和 Description</p></div>
          <el-tag v-if="!capabilities.profile.write" type="warning" effect="plain">只读</el-tag>
        </div>
        <CapabilityAlert :capability="capabilities.profile" fallback="当前 Bot Token 无法修改基础资料。" />
        <el-form-item label="显示名称（Name）" prop="name">
          <el-input v-model="form.name" maxlength="64" show-word-limit placeholder="Telegram 显示名称" :disabled="busy || !capabilities.profile.write" />
        </el-form-item>
        <el-form-item label="关于（About）" prop="short_description">
          <el-input v-model="form.short_description" type="textarea" :rows="2" maxlength="120" show-word-limit placeholder="资料页中的简短说明" :disabled="busy || !capabilities.profile.write" />
        </el-form-item>
        <el-form-item label="详细描述（Description）" prop="description">
          <el-input v-model="form.description" type="textarea" :rows="4" maxlength="512" show-word-limit placeholder="空聊天页中的详细说明" :disabled="busy || !capabilities.profile.write" />
        </el-form-item>
      </section>

      <section class="profile-section">
        <div class="section-heading"><div><h3>图片资料</h3><p>两种图片需要分别上传</p></div></div>
        <article class="media-card">
          <div class="media-summary">
            <div class="avatar-preview"><el-avatar :size="76" :src="botPhotoUrl">BOT</el-avatar></div>
            <div class="media-copy">
              <div class="media-title"><strong>机器人头像（Botpic）</strong></div>
              <p>JPG、PNG 或 WebP，最大 10 MB</p>
              <el-tag v-if="!capabilities.photo.write" type="warning" size="small" effect="plain">不可配置</el-tag>
            </div>
          </div>
          <CapabilityAlert :capability="capabilities.photo" fallback="当前 Bot Token 无法修改机器人头像。" compact />
          <div class="media-actions">
            <el-upload :auto-upload="false" :show-file-list="false" accept="image/jpeg,image/png,image/webp" :disabled="busy || !capabilities.photo.write" :on-change="selectBotPhoto">
              <el-button :disabled="busy || !capabilities.photo.write">选择图片</el-button>
            </el-upload>
            <el-button v-if="selectedBotPhoto" :disabled="busy" @click="cancelBotPhoto">取消选择</el-button>
            <el-button v-else-if="hasBotPhoto" type="danger" plain :loading="removingBotPhoto" :disabled="busy || !capabilities.photo.remove" @click="removeBotPhoto">移除</el-button>
          </div>
          <p v-if="selectedBotPhoto" class="selected-file" :title="selectedBotPhoto.name">待上传：{{ selectedBotPhoto.name }}</p>
          <p v-if="mediaErrors.botPhoto" class="media-error">{{ mediaErrors.botPhoto }}</p>
        </article>

        <article class="media-card">
          <div class="description-preview">
            <span v-if="descriptionMediaNotice" class="description-media-notice">{{ descriptionMediaNotice }}</span>
            <img v-else-if="descriptionPhotoUrl" :src="descriptionPhotoUrl" alt="机器人描述图片预览" />
            <span v-else>暂无描述图片</span>
          </div>
          <div class="media-copy description-copy">
            <div class="media-title"><strong>描述图片（Description Picture）</strong></div>
            <p>展示在机器人详细介绍区域</p>
            <el-tag v-if="!capabilities.descriptionPhoto.write" type="warning" size="small" effect="plain">需拥有者账号</el-tag>
          </div>
          <CapabilityAlert :capability="capabilities.descriptionPhoto" fallback="需要登录该机器人的拥有者账号；当前只能在 BotFather 中配置。" compact />
          <div class="media-actions">
            <el-upload :auto-upload="false" :show-file-list="false" accept="image/jpeg,image/png,image/webp" :disabled="busy || !capabilities.descriptionPhoto.write" :on-change="selectDescriptionPhoto">
              <el-button :disabled="busy || !capabilities.descriptionPhoto.write">选择图片</el-button>
            </el-upload>
            <el-button v-if="selectedDescriptionPhoto" :disabled="busy" @click="cancelDescriptionPhoto">取消选择</el-button>
            <el-button v-else-if="hasDescriptionPhoto" type="danger" plain :loading="removingDescriptionPhoto" :disabled="busy || !capabilities.descriptionPhoto.remove" @click="removeDescriptionPhoto">移除</el-button>
          </div>
          <p v-if="selectedDescriptionPhoto" class="selected-file" :title="selectedDescriptionPhoto.name">待上传：{{ selectedDescriptionPhoto.name }}</p>
          <p v-if="mediaErrors.descriptionPhoto" class="media-error">{{ mediaErrors.descriptionPhoto }}</p>
        </article>
      </section>

      <el-collapse v-model="expandedSections" class="advanced-sections">
        <el-collapse-item name="commands">
          <template #title>
            <div class="collapse-title">
              <span>命令菜单（Commands）</span>
              <el-tag size="small" effect="plain">{{ form.commands.length }}/100</el-tag>
              <el-tag v-if="!capabilities.commands.write" size="small" type="warning" effect="plain">只读</el-tag>
            </div>
          </template>
          <CapabilityAlert :capability="capabilities.commands" fallback="当前 Bot API 无法修改命令菜单。" />
          <p class="section-help">命令无需输入 /，仅限小写字母、数字和下划线，最多 32 个字符。</p>
          <el-empty v-if="form.commands.length === 0" :image-size="64" description="暂无命令，可添加常用操作入口。" />
          <div v-else class="command-list">
            <article v-for="(item, index) in form.commands" :key="item._key" class="command-card">
              <div class="command-card-heading">
                <strong>命令 {{ index + 1 }}</strong>
                <div class="command-actions">
                  <el-button text circle :icon="ArrowUp" :aria-label="`上移第 ${index + 1} 条命令`" :disabled="busy || !capabilities.commands.write || index === 0" @click="moveCommand(index, -1)" />
                  <el-button text circle :icon="ArrowDown" :aria-label="`下移第 ${index + 1} 条命令`" :disabled="busy || !capabilities.commands.write || index === form.commands.length - 1" @click="moveCommand(index, 1)" />
                  <el-button text circle type="danger" :icon="Delete" :aria-label="`删除第 ${index + 1} 条命令`" :disabled="busy || !capabilities.commands.write" @click="removeCommand(index)" />
                </div>
              </div>
              <el-form-item :prop="`commands.${index}.command`" :rules="commandFieldRules(index, 'command')">
                <el-input v-model="item.command" maxlength="32" placeholder="start" :disabled="busy || !capabilities.commands.write"><template #prepend>/</template></el-input>
              </el-form-item>
              <el-form-item :prop="`commands.${index}.description`" :rules="commandFieldRules(index, 'description')">
                <el-input v-model="item.description" type="textarea" :rows="2" maxlength="256" show-word-limit placeholder="命令用途说明" :disabled="busy || !capabilities.commands.write" />
              </el-form-item>
            </article>
          </div>
          <el-button class="full-button" :icon="Plus" :disabled="busy || !capabilities.commands.write || form.commands.length >= 100" @click="addCommand">添加命令</el-button>
          <p v-if="form.commands.length >= 100" class="limit-tip">已达到 Telegram 允许的 100 条上限。</p>
        </el-collapse-item>

        <el-collapse-item name="privacy">
          <template #title>
            <div class="collapse-title">
              <span>隐私政策（Privacy Policy）</span>
              <el-tag v-if="form.privacy_policy_url" size="small" type="success" effect="plain">已配置</el-tag>
              <el-tag v-if="!capabilities.privacyPolicy.write" size="small" type="warning" effect="plain">需拥有者账号</el-tag>
            </div>
          </template>
          <CapabilityAlert :capability="capabilities.privacyPolicy" fallback="需要登录该机器人的拥有者账号；当前只能在 BotFather 中配置。" />
          <el-form-item label="隐私政策网址" prop="privacy_policy_url">
            <el-input v-model.trim="form.privacy_policy_url" type="url" maxlength="2048" placeholder="https://example.com/privacy" :disabled="busy || !capabilities.privacyPolicy.write" />
            <div class="field-help">请输入可公开访问的 HTTPS 完整网址。</div>
          </el-form-item>
          <el-button v-if="form.privacy_policy_url" class="full-button" type="danger" plain :loading="removingPrivacyPolicy" :disabled="busy || !capabilities.privacyPolicy.remove" @click="clearPrivacyPolicy">移除隐私政策</el-button>
        </el-collapse-item>
      </el-collapse>

      <el-alert v-if="saveError" title="部分资料未保存" :description="saveError" type="error" :closable="false" show-icon class="save-error" />
      <div class="sticky-actions">
        <el-button :disabled="busy" @click="loadProfile">重新同步</el-button>
        <el-button type="primary" :loading="saving" :disabled="destructiveBusy" @click="saveProfile">保存全部资料</el-button>
      </div>
    </el-form>
  </div>
</template>

<script setup>
import { computed, defineComponent, h, onBeforeUnmount, reactive, ref, watch } from "vue"
import { ArrowDown, ArrowUp, Delete, Plus } from "@element-plus/icons-vue"
import { ElAlert, ElMessage, ElMessageBox } from "element-plus"
import { getErrorMessage } from "../api/client"
import {
  getBotDescriptionPhoto, getBotProfile, getBotProfilePhoto,
  removeBotDescriptionPhoto, removeBotPrivacyPolicy, removeBotProfilePhoto,
  updateBotCommands, updateBotPrivacyPolicy, updateBotProfile,
  uploadBotDescriptionPhoto, uploadBotProfilePhoto,
} from "../api"

const props = defineProps({ bot: Object, visible: Boolean })
const CapabilityAlert = defineComponent({
  props: { capability: { type: Object, required: true }, fallback: { type: String, required: true }, compact: Boolean },
  setup(componentProps) {
    return () => componentProps.capability.write ? null : h(ElAlert, {
      title: componentProps.capability.reason || componentProps.fallback,
      type: "warning", closable: false, showIcon: true,
      class: componentProps.compact ? "capability-alert capability-alert--compact" : "capability-alert",
    })
  },
})
const formRef = ref(null)
const loading = ref(false)
const saving = ref(false)
const removingBotPhoto = ref(false)
const removingDescriptionPhoto = ref(false)
const removingPrivacyPolicy = ref(false)
const loadError = ref("")
const saveError = ref("")
const expandedSections = ref(["commands"])
const hasBotPhoto = ref(false)
const hasDescriptionPhoto = ref(false)
const descriptionMediaType = ref("")
const botPhotoUrl = ref("")
const descriptionPhotoUrl = ref("")
const selectedBotPhoto = ref(null)
const selectedDescriptionPhoto = ref(null)
const initialCommands = ref("[]")
const initialPrivacyPolicyUrl = ref("")
const mediaErrors = reactive({ botPhoto: "", descriptionPhoto: "" })
const form = reactive({ name: "", short_description: "", description: "", commands: [], privacy_policy_url: "" })
const writable = () => ({ read: true, write: true, remove: true, reason: "" })
const restricted = () => ({ read: false, write: false, remove: false, reason: "" })
const capabilities = reactive({ profile: writable(), photo: writable(), descriptionPhoto: restricted(), commands: restricted(), privacyPolicy: restricted() })
const destructiveBusy = computed(() => removingBotPhoto.value || removingDescriptionPhoto.value || removingPrivacyPolicy.value)
const busy = computed(() => loading.value || saving.value || destructiveBusy.value)
const descriptionMediaNotice = computed(() => {
  if (selectedDescriptionPhoto.value) return ""
  if (!hasDescriptionPhoto.value || !["video", "document"].includes(descriptionMediaType.value)) return ""
  const label = descriptionMediaType.value === "document" ? "文档" : "视频"
  return `当前为${label}描述媒体，可移除或上传图片替换`
})
const rules = {
  name: [{ required: true, message: "请输入 Telegram 显示名称", trigger: "blur" }],
  privacy_policy_url: [{ validator: validatePrivacyPolicy, trigger: ["blur", "change"] }],
}
let commandKey = 0

const profileFieldLabels = {
  name: "名称",
  short_description: "关于",
  description: "详细描述",
  refresh: "重新同步",
  profile_photo: "机器人头像",
  description_photo: "描述图片",
  commands: "命令菜单",
  privacy_policy: "隐私政策",
}
function readableFieldNames(value) {
  const fields = Array.isArray(value)
    ? value
    : value && typeof value === "object"
      ? Object.keys(value)
      : []
  return fields.map((field) => profileFieldLabels[field] || String(field)).join("、")
}
function errorMessage(error, fallback) {
  const detail = error?.response?.data?.detail
  if (Array.isArray(detail)) return detail.map((item) => item?.msg || String(item)).join("；")
  if (detail && typeof detail === "object") {
    const updated = readableFieldNames(detail.updated_fields)
    const failed = readableFieldNames(detail.failed_fields)
    const rawMessage = String(detail.message || error?.response?.data?.message || fallback)
    const message = updated || failed ? rawMessage.split("；已成功：")[0] : rawMessage
    return [message, updated && `已成功：${updated}`, failed && `失败：${failed}`].filter(Boolean).join("；")
  }
  return getErrorMessage(error, fallback)
}
function normalizeCapability(value, fallback) {
  if (typeof value === "boolean") return { read: value, write: value, remove: value, reason: "" }
  if (!value || typeof value !== "object") return { ...fallback }
  const write = value.write ?? value.can_write ?? value.available ?? fallback.write
  return { read: Boolean(value.read ?? value.can_read ?? write ?? fallback.read), write: Boolean(write), remove: Boolean(value.remove ?? value.can_remove ?? write ?? fallback.remove), reason: value.reason || value.message || "" }
}
function profileCapability(profile, keys, fallback) {
  const source = profile.capabilities || {}
  for (const key of keys) if (source[key] !== undefined) return normalizeCapability(source[key], fallback)
  return { ...fallback }
}
function assignCapability(target, value) { Object.assign(target, value) }
function revokeUrl(value) { if (value?.startsWith("blob:")) URL.revokeObjectURL(value) }
function replaceUrl(target, value) { revokeUrl(target.value); target.value = value || "" }
function validateImage(file, label) {
  if (!file) return false
  if (!/^image\/(jpeg|png|webp)$/.test(file.type || "")) { ElMessage.error(`${label}仅支持 JPG、PNG 或 WebP`); return false }
  if (file.size > 10 * 1024 * 1024) { ElMessage.error(`${label}不能超过 10 MB`); return false }
  return true
}
function normalizeCommands(commands) {
  if (!Array.isArray(commands)) return []
  return commands.slice(0, 100).map((item) => ({ _key: ++commandKey, command: String(item?.command || "").replace(/^\/+/, ""), description: String(item?.description || "") }))
}
function commandPayload() { return form.commands.map(({ command, description }) => ({ command: command.trim().replace(/^\/+/, ""), description: description.trim() })) }
function validatePrivacyPolicy(_rule, value, callback) {
  if (!capabilities.privacyPolicy.write || !value) return callback()
  try { const parsed = new URL(value); if (parsed.protocol !== "https:" || !parsed.hostname) throw new Error("invalid"); callback() }
  catch { callback(new Error("请输入以 https:// 开头的完整网址")) }
}
function commandFieldRules(index, field) {
  if (!capabilities.commands.write) return []
  if (field === "description") return [{ required: true, message: "请输入命令说明", trigger: "blur" }, { min: 1, max: 256, message: "命令说明最多 256 个字符", trigger: "blur" }]
  return [{ required: true, message: "请输入命令名称", trigger: "blur" }, { validator: (_rule, value, callback) => {
    const normalized = String(value || "").replace(/^\/+/, "")
    if (!/^[a-z0-9_]{1,32}$/.test(normalized)) return callback(new Error("仅限 1–32 位小写字母、数字或下划线"))
    if (form.commands.some((item, itemIndex) => itemIndex !== index && item.command.trim().replace(/^\/+/, "") === normalized)) return callback(new Error("命令名称不能重复"))
    callback()
  }, trigger: ["blur", "change"] }]
}
async function loadBotPhoto() {
  mediaErrors.botPhoto = ""
  if (!hasBotPhoto.value || !capabilities.photo.read) return replaceUrl(botPhotoUrl, "")
  try { const response = await getBotProfilePhoto(props.bot.id); replaceUrl(botPhotoUrl, URL.createObjectURL(response.data)) }
  catch (error) { replaceUrl(botPhotoUrl, ""); mediaErrors.botPhoto = errorMessage(error, "头像预览加载失败") }
}
async function loadDescriptionPhoto() {
  mediaErrors.descriptionPhoto = ""
  if (descriptionMediaNotice.value) return replaceUrl(descriptionPhotoUrl, "")
  if (!hasDescriptionPhoto.value || !capabilities.descriptionPhoto.read) return replaceUrl(descriptionPhotoUrl, "")
  try { const response = await getBotDescriptionPhoto(props.bot.id); replaceUrl(descriptionPhotoUrl, URL.createObjectURL(response.data)) }
  catch (error) { replaceUrl(descriptionPhotoUrl, ""); mediaErrors.descriptionPhoto = errorMessage(error, "描述图片预览加载失败") }
}
async function loadProfile() {
  if (!props.bot?.id) return
  loading.value = true; loadError.value = ""; saveError.value = ""; selectedBotPhoto.value = null; selectedDescriptionPhoto.value = null
  try {
    const response = await getBotProfile(props.bot.id)
    const profile = response.data?.profile || response.data || {}
    form.name = profile.name || ""; form.short_description = profile.short_description ?? profile.about ?? ""; form.description = profile.description || ""
    form.commands = normalizeCommands(profile.commands); form.privacy_policy_url = profile.privacy_policy_url || profile.privacy_policy || ""
    initialCommands.value = JSON.stringify(commandPayload()); initialPrivacyPolicyUrl.value = form.privacy_policy_url
    hasBotPhoto.value = Boolean(profile.has_photo ?? response.data?.has_photo)
    hasDescriptionPhoto.value = Boolean(
      profile.has_description_media
      ?? response.data?.has_description_media
      ?? profile.has_description_photo
      ?? profile.description_photo_url
      ?? response.data?.has_description_photo,
    )
    descriptionMediaType.value = String(
      profile.description_media_type
      ?? response.data?.description_media_type
      ?? (profile.has_description_document ? "document" : profile.has_description_photo ? "photo" : ""),
    ).toLowerCase()
    assignCapability(capabilities.profile, profileCapability(profile, ["profile", "basic", "text"], writable()))
    assignCapability(capabilities.photo, profileCapability(profile, ["profile_photo", "botpic", "photo"], writable()))
    assignCapability(capabilities.descriptionPhoto, profileCapability(profile, ["description_photo", "description_picture"], restricted()))
    assignCapability(capabilities.commands, profileCapability(profile, ["commands"], restricted()))
    assignCapability(capabilities.privacyPolicy, profileCapability(profile, ["privacy_policy", "privacyPolicy"], restricted()))
    await Promise.all([loadBotPhoto(), loadDescriptionPhoto()]); formRef.value?.clearValidate()
  } catch (error) { loadError.value = errorMessage(error, "请检查 Bot Token 和 Telegram 网络连接") }
  finally { loading.value = false }
}
function selectBotPhoto(uploadFile) { const file = uploadFile.raw; if (!validateImage(file, "机器人头像")) return; selectedBotPhoto.value = file; replaceUrl(botPhotoUrl, URL.createObjectURL(file)) }
function selectDescriptionPhoto(uploadFile) { const file = uploadFile.raw; if (!validateImage(file, "描述图片")) return; selectedDescriptionPhoto.value = file; replaceUrl(descriptionPhotoUrl, URL.createObjectURL(file)) }
async function cancelBotPhoto() { selectedBotPhoto.value = null; await loadBotPhoto() }
async function cancelDescriptionPhoto() { selectedDescriptionPhoto.value = null; await loadDescriptionPhoto() }
function addCommand() { if (form.commands.length < 100) form.commands.push({ _key: ++commandKey, command: "", description: "" }) }
function removeCommand(index) { form.commands.splice(index, 1); formRef.value?.clearValidate() }
function moveCommand(index, offset) { const target = index + offset; if (target < 0 || target >= form.commands.length) return; const [item] = form.commands.splice(index, 1); form.commands.splice(target, 0, item); formRef.value?.clearValidate() }
async function confirmRemoval(message, title) {
  try { await ElMessageBox.confirm(message, title, { type: "warning", confirmButtonText: "确认移除", cancelButtonText: "取消" }); return true }
  catch (reason) { if (reason === "cancel" || reason === "close") return false; throw reason }
}
async function removeBotPhoto() {
  if (!(await confirmRemoval("移除后，Telegram 用户将看不到当前机器人头像。", "移除机器人头像"))) return
  removingBotPhoto.value = true
  try { await removeBotProfilePhoto(props.bot.id); hasBotPhoto.value = false; replaceUrl(botPhotoUrl, ""); ElMessage.success("机器人头像已移除") }
  catch (error) { ElMessage.error(errorMessage(error, "机器人头像移除失败")) }
  finally { removingBotPhoto.value = false }
}
async function removeDescriptionPhoto() {
  if (!(await confirmRemoval("移除后，Telegram 用户将看不到当前描述图片。", "移除描述图片"))) return
  removingDescriptionPhoto.value = true
  try { await removeBotDescriptionPhoto(props.bot.id); hasDescriptionPhoto.value = false; descriptionMediaType.value = ""; replaceUrl(descriptionPhotoUrl, ""); ElMessage.success("描述图片已移除") }
  catch (error) { ElMessage.error(errorMessage(error, "描述图片移除失败")) }
  finally { removingDescriptionPhoto.value = false }
}
async function clearPrivacyPolicy() {
  if (!initialPrivacyPolicyUrl.value) { form.privacy_policy_url = ""; return }
  if (!(await confirmRemoval("移除后，Telegram 用户将无法从机器人资料中打开隐私政策。", "移除隐私政策"))) return
  removingPrivacyPolicy.value = true
  try { await removeBotPrivacyPolicy(props.bot.id); form.privacy_policy_url = ""; initialPrivacyPolicyUrl.value = ""; ElMessage.success("隐私政策已移除") }
  catch (error) { ElMessage.error(errorMessage(error, "隐私政策移除失败")) }
  finally { removingPrivacyPolicy.value = false }
}
async function saveProfile() {
  saveError.value = ""
  if (!(await formRef.value?.validate().catch(() => false))) { ElMessage.warning("请先修正表单中的问题"); return }
  const operations = []
  if (capabilities.profile.write) operations.push({ label: "基础资料", run: () => updateBotProfile(props.bot.id, { name: form.name.trim(), short_description: form.short_description, description: form.description }) })
  if (selectedBotPhoto.value && capabilities.photo.write) operations.push({ label: "机器人头像", run: () => uploadBotProfilePhoto(props.bot.id, selectedBotPhoto.value), success: () => { selectedBotPhoto.value = null; hasBotPhoto.value = true } })
  if (selectedDescriptionPhoto.value && capabilities.descriptionPhoto.write) operations.push({ label: "描述图片", run: () => uploadBotDescriptionPhoto(props.bot.id, selectedDescriptionPhoto.value), success: () => { selectedDescriptionPhoto.value = null; hasDescriptionPhoto.value = true; descriptionMediaType.value = "photo" } })
  const commands = commandPayload()
  if (capabilities.commands.write && JSON.stringify(commands) !== initialCommands.value) operations.push({ label: "命令菜单", run: () => updateBotCommands(props.bot.id, commands), success: () => { initialCommands.value = JSON.stringify(commands) } })
  if (capabilities.privacyPolicy.write && form.privacy_policy_url !== initialPrivacyPolicyUrl.value) operations.push({ label: "隐私政策", run: () => form.privacy_policy_url ? updateBotPrivacyPolicy(props.bot.id, form.privacy_policy_url) : removeBotPrivacyPolicy(props.bot.id), success: () => { initialPrivacyPolicyUrl.value = form.privacy_policy_url } })
  if (!operations.length) { ElMessage.info("当前没有可保存的修改"); return }
  saving.value = true
  const failures = []
  for (const operation of operations) {
    try { await operation.run(); operation.success?.() }
    catch (error) { failures.push(`${operation.label}：${errorMessage(error, "保存失败")}`) }
  }
  saving.value = false
  if (failures.length) { saveError.value = failures.join("；"); ElMessage.error("部分资料保存失败，请查看具体原因"); return }
  ElMessage.success("Telegram 公开资料已更新"); await loadProfile()
}

watch(() => [props.visible, props.bot?.id], ([visible, id]) => { if (visible && id) loadProfile() }, { immediate: true })
onBeforeUnmount(() => { revokeUrl(botPhotoUrl.value); revokeUrl(descriptionPhotoUrl.value) })
</script>

<style scoped>
.mobile-profile-editor { padding-bottom: max(22px, env(safe-area-inset-bottom)); color: var(--el-text-color-primary); }
.profile-tip { margin-bottom: 18px; }
.profile-section { padding-bottom: 18px; border-bottom: 1px solid var(--el-border-color-lighter); }
.profile-section + .profile-section { padding-top: 18px; }
.section-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 10px; margin-bottom: 14px; }
.section-heading h3 { margin: 0; font-size: 16px; line-height: 1.5; }
.section-heading p, .media-copy p, .section-help, .field-help, .limit-tip, .selected-file, .media-error { margin: 3px 0 0; color: var(--el-text-color-secondary); font-size: 13px; line-height: 1.5; }
.capability-alert { margin-bottom: 12px; }
.media-card { margin-top: 12px; padding: 14px; border: 1px solid var(--el-border-color-lighter); border-radius: var(--el-border-radius-base); }
.media-summary { display: flex; align-items: center; gap: 14px; }
.avatar-preview { display: grid; place-items: center; flex: 0 0 76px; width: 76px; height: 76px; overflow: hidden; background: var(--el-fill-color-light); border: 1px solid var(--el-border-color); border-radius: 50%; }
.avatar-preview :deep(.el-avatar) { background: transparent; color: var(--el-text-color-secondary); }
.media-copy { min-width: 0; flex: 1; }
.media-title { line-height: 1.45; }
.description-preview { display: grid; place-items: center; width: 100%; aspect-ratio: 16 / 9; overflow: hidden; color: var(--el-text-color-placeholder); background: var(--el-fill-color-light); border: 1px solid var(--el-border-color); border-radius: var(--el-border-radius-small); font-size: 13px; }
.description-preview img { width: 100%; height: 100%; object-fit: cover; }
.description-media-notice { padding: 14px; line-height: 1.5; text-align: center; }
.description-copy { margin-top: 10px; }
.media-actions { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px; }
.media-actions :deep(.el-button) { min-height: 40px; margin-left: 0; }
.selected-file { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.media-error { color: var(--el-color-danger); }
.advanced-sections { margin-top: 10px; }
.advanced-sections :deep(.el-collapse-item__header) { min-height: 52px; height: auto; padding: 7px 0; line-height: 1.4; }
.advanced-sections :deep(.el-collapse-item__content) { padding: 8px 0 18px; }
.collapse-title { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; min-width: 0; font-weight: 600; }
.command-list { display: grid; gap: 10px; margin: 12px 0; }
.command-card { padding: 12px; background: var(--el-fill-color-lighter); border-radius: var(--el-border-radius-base); }
.command-card-heading { display: flex; align-items: center; justify-content: space-between; min-height: 40px; margin-bottom: 8px; }
.command-actions { display: flex; align-items: center; }
.command-actions :deep(.el-button) { width: 40px; height: 40px; margin-left: 0; }
.command-card :deep(.el-form-item:last-child) { margin-bottom: 0; }
.full-button { width: 100%; min-height: 40px; }
.limit-tip { color: var(--el-color-warning); }
.save-error { margin-top: 16px; }
.sticky-actions { display: grid; grid-template-columns: 1fr 1.35fr; gap: 10px; position: sticky; bottom: 0; z-index: 2; margin: 18px 0 0; padding: 12px 2px max(4px, env(safe-area-inset-bottom)); background: var(--el-bg-color); border-top: 1px solid var(--el-border-color-lighter); }
.sticky-actions .el-button { min-height: 42px; margin-left: 0; }
</style>
