import { createApp } from 'vue'
import ElementPlus from 'element-plus'
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
  createApp(App).use(ElementPlus).mount('#app')
}
