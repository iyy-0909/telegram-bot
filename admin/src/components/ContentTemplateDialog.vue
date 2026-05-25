<template>
  <el-dialog
    :model-value="visible"
    @update:model-value="$emit('update:visible', $event)"
    :title="isEdit ? '编辑内容模板规则' : '添加内容模板规则'"
    width="760px"
  >
    <el-form label-width="100px">
      <el-form-item label="规则类型">
        <el-select v-model="localForm.type">
          <el-option label="头部 head" value="head" />
          <el-option label="正文 body" value="body" />
          <el-option label="底部 footer" value="footer" />
        </el-select>
      </el-form-item>

      <el-form-item label="规则名称">
        <el-input v-model="localForm.name" placeholder="例如 A规则 / 上海footer" />
      </el-form-item>

      <el-form-item label="启用">
        <el-switch v-model="localForm.enabled" />
      </el-form-item>

      <el-divider content-position="left">规则内容</el-divider>

      <div class="content-list">
        <div
          v-for="(item, index) in localForm.items"
          :key="item.local_key"
          class="content-item"
        >
          <div class="content-item-head">
            <span>内容 {{ index + 1 }}</span>
            <div class="content-actions">
              <el-switch v-model="item.enabled" active-text="启用" />
              <el-input-number
                v-model="item.weight"
                :min="1"
                :step="1"
                controls-position="right"
                class="weight-input"
              />
              <el-button
                type="danger"
                text
                @click="removeItem(index)"
              >
                删除
              </el-button>
            </div>
          </div>

          <el-input
            v-model="item.content"
            type="textarea"
            :rows="4"
            placeholder="填写这条模板内容"
          />
        </div>
      </div>

      <el-button class="add-content-button" @click="addItem">
        添加一条内容
      </el-button>
    </el-form>

    <template #footer>
      <el-button @click="$emit('update:visible', false)">取消</el-button>
      <el-button type="primary" @click="submit">保存规则</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { reactive, watch } from "vue"

const props = defineProps({
  visible: Boolean,
  form: Object,
  isEdit: Boolean,
})

const emit = defineEmits(["update:visible", "submit"])

let localKeySeed = 1

const localForm = reactive({
  id: null,
  name: "",
  type: "footer",
  enabled: true,
  items: [],
})

watch(
  () => props.form,
  (val) => {
    if (!val) return

    Object.assign(localForm, {
      id: val.id || null,
      name: val.name || "",
      type: val.type || "footer",
      enabled: val.enabled ?? true,
      items: normalizeItems(val.items || []),
    })

    if (!localForm.items.length) {
      addItem()
    }
  },
  { immediate: true, deep: true },
)

function addItem() {
  localForm.items.push({
    id: null,
    local_key: localKeySeed++,
    content: "",
    enabled: true,
    weight: 1,
  })
}

function removeItem(index) {
  localForm.items.splice(index, 1)

  if (!localForm.items.length) {
    addItem()
  }
}

function submit() {
  emit("submit", {
    id: localForm.id,
    name: (localForm.name || "").trim(),
    type: localForm.type,
    enabled: localForm.enabled,
    items: localForm.items.map((item, index) => ({
      id: normalizeTemplateId(item.id),
      name: `内容 ${index + 1}`,
      content: item.content || "",
      enabled: item.enabled ?? true,
      weight: toPositiveNumber(item.weight, 1),
    })),
  })
}

function normalizeItems(items) {
  return (items || []).map((item) => ({
    id: normalizeTemplateId(item.id),
    local_key: localKeySeed++,
    content: item.content || "",
    enabled: item.enabled ?? true,
    weight: toPositiveNumber(item.weight, 1),
  }))
}

function normalizeTemplateId(value) {
  if (value === null || value === undefined || value === "") {
    return null
  }

  const numberValue = Number(value)
  return Number.isInteger(numberValue) && numberValue > 0 ? numberValue : null
}

function toPositiveNumber(value, fallback) {
  const numberValue = Number(value)

  if (!Number.isFinite(numberValue) || numberValue < 1) {
    return fallback
  }

  return Math.floor(numberValue)
}
</script>

<style scoped>
.content-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.content-item {
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  padding: 12px;
  background: #fafafa;
}

.content-item-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  margin-bottom: 8px;
  font-size: 13px;
  font-weight: 600;
  color: #303133;
}

.content-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.weight-input {
  width: 96px;
}

.add-content-button {
  margin-top: 12px;
}
</style>
