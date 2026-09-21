import { createApp, defineComponent, h, ref } from "vue"
import ElementPlus, { ElButton, ElSwitch, ElMessage } from "element-plus"
import { createRequestButton, createRequestSwitch } from "../../frontend-shared/requestActions.mjs"
import "../../frontend-shared/requestButton.css"
import "element-plus/dist/index.css"
import "./style.css"
import App from "./App.vue"

createApp(App).use(ElementPlus)
  .component("RequestButton", createRequestButton({ defineComponent, h, ref }, ElButton, ElMessage.error))
  .component("RequestSwitch", createRequestSwitch({ defineComponent, h, ref }, ElSwitch, ElMessage.error))
  .mount("#app")
