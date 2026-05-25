<template>
  <el-dialog
    :model-value="visible"
    :title="isEdit ? '编辑规则' : '新增规则'"
    width="620px"
    @close="handleClose"
  >
    <el-form
      :model="localForm"
      label-width="120px"
      class="rule-form"
    >
      <el-form-item label="源频道">
        <el-input
          v-model="localForm.source"
          placeholder="例如：@source_channel"
        />
      </el-form-item>

      <el-form-item label="目标频道">
        <el-input
          v-model="localForm.target"
          placeholder="例如：@target_channel"
        />
      </el-form-item>

      <el-form-item label="启用">
        <el-switch
          v-model="localForm.enabled"
          active-text="开启"
          inactive-text="关闭"
        />
      </el-form-item>

      <el-form-item label="删除旧联系方式">
        <el-switch
          v-model="localForm.remove_contact_lines"
          active-text="删除"
          inactive-text="保留"
        />
      </el-form-item>

      <el-form-item label="过滤关键词">
        <el-input
          v-model="localForm.blocked_keywords"
          type="textarea"
          :rows="4"
          placeholder='例如：["极搜","yiso","soso"]'
        />
      </el-form-item>

      <el-form-item label="替换词">
        <ReplaceRulesEditor v-model="localForm.replace_words" />
      </el-form-item>

      <!-- 旧 Footer 功能已停用。请使用内容模板规则里的 footer。 -->
      <!--
      <el-form-item label="旧 Footer">
        <el-input v-model="localForm.footer" type="textarea" :rows="4" />
      </el-form-item>
      -->
    </el-form>

    <template #footer>
      <el-button @click="handleClose">
        取消
      </el-button>

      <el-button
        type="primary"
        @click="handleSubmit"
      >
        保存
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { reactive, watch } from "vue"
import ReplaceRulesEditor from "./ReplaceRulesEditor.vue"

const props = defineProps({
  visible: {
    type: Boolean,
    default: false,
  },
  form: {
    type: Object,
    required: true,
  },
  isEdit: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits([
  "update:visible",
  "submit",
])

const localForm = reactive({
  id: null,
  source: "",
  target: "",
  enabled: true,
  blocked_keywords: "[]",
  replace_words: "{}",
  footer: "",
  remove_contact_lines: true,
  clone_task_id: null,
})

watch(
  () => props.visible,
  (visible) => {
    if (visible) {
      Object.assign(localForm, {
        id: props.form.id ?? null,
        source: props.form.source || "",
        target: props.form.target || "",
        enabled: props.form.enabled ?? true,
        blocked_keywords: props.form.blocked_keywords || "[]",
        replace_words: props.form.replace_words || "{}",
        footer: "",
        remove_contact_lines: props.form.remove_contact_lines ?? true,
        clone_task_id: props.form.clone_task_id || null,
      })
    }
  },
  {
    immediate: true,
  },
)

const handleClose = () => {
  emit("update:visible", false)
}

const handleSubmit = () => {
  emit("submit", {
    id: localForm.id,
    source: localForm.source,
    target: localForm.target,
    enabled: localForm.enabled,
    blocked_keywords: localForm.blocked_keywords || "[]",
    replace_words: localForm.replace_words || "{}",
    footer: "",
    remove_contact_lines: localForm.remove_contact_lines,
    clone_task_id: localForm.clone_task_id,
  })
}
</script>

<style scoped>
.rule-form {
  padding-right: 12px;
}
</style>
