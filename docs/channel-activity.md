# 频道更新状态与只读收录信息

## 使用方式

“我的频道”表格在频道名称旁显示更新状态。距上次新内容发布超过 5 × 24 小时为“异常”，正好 5 天仍为“正常”；没有已知内容时间为“未知”。这个状态独立于频道启用状态、Bot 权限、投放状态和收录状态。

编辑频道时可以查看只读的频道上次更新时间，以及各次提交当前被标记为“通过”“拒绝”的记录。记录展示搜索机器人、提交账号、提交时间、结果更新时间和已有错误信息；没有拒绝原因时明确提示未记录。此处复用已有审核结果，不会自动审核，也不是同一次提交的状态变更历史。

## 时间来源

- 系统通过 Bot API 成功发布的新频道内容，使用 Telegram 返回的消息日期。
- 已加载的 Telethon 用户号接收到的频道新消息，使用原消息日期；置顶、改名等服务消息不计入。
- 点击检测、批量检测或保存并检测时，使用频道所属用户的在线账号读取最近内容。首次部署建议进行一次批量检测。
- 没有可访问频道的在线用户号时保留已知时间；没有任何已知时间时显示未知，不用资料修改时间冒充内容时间。
- 保存资料、编辑已发消息和旧消息乱序到达都不会将内容时间错误地重置为现在。

内容日期保存为 UTC，接口输出带 Z 的时间，页面按浏览器本地时区显示。状态每次读取频道接口时重新计算。

## 涉及文件

- `admin/src/components/MyChannelTable.vue`：更新状态列、只读记录、加载与重试、窄屏弹窗。
- `backend/db/models.py`、`backend/db/channel_activity.py`、`backend/db/crud_my_channels.py`：内容时间存储、按账号隔离更新、状态输出。
- `backend/bot/channel_activity.py`、`backend/accounts/manager.py`：新消息观测及检测读取。
- `backend/bot/bot_sender.py`：发送成功后记录内容时间，记录失败不会触发重复发送。
- `backend/api/server.py`：接入现有频道检测流程。
- `backend/migrate_channel_activity.py`、`backend/init_db.py`：可重复执行的迁移，修改 SQLite 表结构前先生成一致性备份。
- `backend/tests/test_channel_activity.py`、`backend/tests/test_account_manager_loading.py`：活动时间及账号加载回归测试。

没有新增依赖。

## 本地验收（2026-09-21）

使用真实前端构建和后端接口，配合独立 SQLite 测试数据库及合成频道，不向 Telegram 发送测试消息。

- 后端 28 项测试通过：新增活动时间 9 项、频道查询及自动检测 8 项、账号加载 7 项、搜索机器人提交 4 项。
- 前端 `npm run build` 通过。依赖注释和现有大体积资源提示不影响构建。
- 浏览器通过 1440 × 1000、768 × 1024、375 × 812 布局检查。375px 页面无横向溢出；表格内部可横向滚动，编辑弹窗正文可滚动，保存按钮可见。
- 已检查正常／异常／未知状态、只读审核记录、无记录、加载中、请求失败及重试恢复、禁用频道提交按钮。
- 已执行编辑保存、列表刷新、重新打开表单，确认最后内容时间及审核记录保持不变。测试环境无 Telegram Bot，保存后按预期提示权限检测不可用。
- 浏览器未发现非预期的前端异常。未进行真实 Telegram 网络联调或线上部署；本机没有 Docker，未执行容器构建。

截图保存在 `.codex-run/channel-activity-screenshots/`：`desktop-table.png`、`desktop-edit.png`、`mobile-table.png`、`mobile-edit.png`、`tablet-table.png`、`empty-reviews.png`、`loading-reviews.png`、`error-reviews.png`、`empty-table.png`。

## 部署

在服务器项目根目录执行：

```sh
docker compose up -d --build backend admin
```

后端启动时自动完成迁移，在原数据库旁生成 `*.bak_channel_activity_*` 备份后添加字段，不会删除数据。迁移失败会阻止启动。前端静态构建与后端需一并更新。

本地开发环境重新启动后端 `run.py` 后生效。首次查看历史频道可使用“批量检测”；无法取得时间的频道继续显示“未知”。
