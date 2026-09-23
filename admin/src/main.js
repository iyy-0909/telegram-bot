import { createApp, defineComponent, h, ref } from 'vue'
import ElementPlus, { ElButton, ElSwitch, ElMessage, ElInput } from 'element-plus'
import { Search } from '@element-plus/icons-vue'
import { createTableSearch } from '../../frontend-shared/tableSearch.mjs'
import '../../frontend-shared/tableSearch.css'
import { createRequestButton, createRequestSwitch } from '../../frontend-shared/requestActions.mjs'
import '../../frontend-shared/requestButton.css'
import 'element-plus/dist/index.css'
import axios from 'axios'
import App from './App.vue'
import { redirectToMobileSite } from './deviceRedirect'
import {
  installAuthSessionInterceptors,
  installAuthStorageListener,
} from './authSession'

installAuthSessionInterceptors(axios)
installAuthStorageListener()

if (!redirectToMobileSite()) {
  createApp(App).use(ElementPlus)
    .component('TableSearch', createTableSearch({ defineComponent, h }, ElInput, Search))
    .component('RequestButton', createRequestButton({ defineComponent, h, ref }, ElButton, ElMessage.error))
    .component('RequestSwitch', createRequestSwitch({ defineComponent, h, ref }, ElSwitch, ElMessage.error))
    .mount('#app')
}
