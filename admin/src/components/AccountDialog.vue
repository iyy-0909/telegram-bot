<template>
  <el-dialog
    :model-value="visible"
    @update:model-value="$emit('update:visible', $event)"
    :title="isEdit ? '编辑账号' : '新增账号'"
    width="600px"
  >
    <el-form label-width="120px">
      <el-form-item label="账号名称">
        <el-input v-model="localForm.name" placeholder="例如 主账号" />
      </el-form-item>

      <el-form-item label="Session路径">
        <el-input v-model="localForm.session_path" placeholder="例如 data/sessions/main_1" />
      </el-form-item>

      <el-form-item label="代理">
        <el-input v-model="localForm.proxy" placeholder="暂时可留空" />
      </el-form-item>

      <el-form-item label="启用">
        <el-switch v-model="localForm.enabled" />
      </el-form-item>

      <el-form-item label="备注">
        <el-input v-model="localForm.remark" type="textarea" :rows="3" />
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="$emit('update:visible', false)">取消</el-button>
      <el-button type="primary" @click="submit">保存</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { reactive, watch } from "vue"

const props = defineProps({
  visible: Boolean,
  form: Object,
  isEdit: Boolean
})

const emit = defineEmits(["update:visible", "submit"])

const localForm = reactive({
  id: null,
  name: "",
  session_path: "",
  proxy: "",
  enabled: true,
  remark: ""
})

watch(
  () => props.form,
  (val) => {
    if (!val) return
    Object.assign(localForm, val)
  },
  { immediate: true, deep: true }
)

function submit() {
  emit("submit", { ...localForm })
}
</script>