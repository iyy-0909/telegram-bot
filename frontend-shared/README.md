# 请求按钮

桌面端和移动端统一注册 `RequestButton`，内部继续使用 Element Plus 的按钮和样式。

- `@click` 必须返回整个异步操作的 Promise，包括校验、确认、请求和刷新。
- 请求期间立即拦截连续点击，显示 loading 并禁用按钮；成功、异常或取消后恢复。
- 本地同步操作没有 loading；原有 `loading`、`disabled`、权限限制仍然有效。
- 表单通过回车或原生 submit 触发时，仍须在提交函数中、首次 await 之前设置保护状态，并在 finally 中释放。
- 原生样式的按钮使用 `<request-button native>`。

Vue 的 `emit()` 不返回父组件异步处理结果。需要等待结果的子组件使用 `requestActions` 回调属性，由 `useRequestEmit(rawEmit, props)` 转发并返回 Promise。父组件例如：

```vue
<BotTable :request-actions="{ test: testBotHandler, delete: deleteBotHandler }" />
```

模型更新等通知继续使用普通事件；没有提供回调时，`useRequestEmit` 保留原事件行为。相同组件、操作及记录的并发回调共享完成结果，其他记录可独立操作。不要在转发函数中丢弃 Promise。

两端均从仓库根目录的 `frontend-shared/` 引用，Docker 构建上下文也必须为仓库根目录：

```sh
docker compose build admin
docker build -f admin-mobile/Dockerfile .
```

验证：在 `admin/` 和 `admin-mobile/` 分别运行 `npm run build`、`node --test tests/*.test.mjs`。
