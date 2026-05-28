# 部署说明

## 生产环境代理处理

生产环境建议在 `.env` 中设置：

```env
APP_ENV=production
```

当 `APP_ENV=production` 时，系统会在运行时自动忽略账号中配置的本地代理，避免服务器错误连接本地开发代理。

会被自动忽略的本地代理地址包括：

- `127.0.0.1`
- `localhost`
- `0.0.0.0`
- `::1`

例如，本地开发数据库里账号代理是 `127.0.0.1:7897`，上传到线上服务器后，系统不会修改数据库字段，只会在运行时把这个代理当作未配置处理。

如果线上需要使用代理，请配置服务器真实可访问的远程代理地址，例如：

```txt
socks5://1.2.3.4:1080
http://1.2.3.4:7890
```

Bot API 请求同样遵守这个规则。生产环境不要配置本地 Bot API 代理：

```env
BOT_API_PROXY=http://127.0.0.1:7897
```

如果服务器不能直连 `api.telegram.org`，请配置真实远程代理：

```env
BOT_API_PROXY=socks5://user:pass@host:port
```

生产环境启动时，如果发现 `HTTP_PROXY`、`HTTPS_PROXY`、`ALL_PROXY`、`http_proxy`、`https_proxy`、`all_proxy` 指向本地地址，也会自动从运行时环境中清理，避免 `requests` 误走本地开发代理。

生产环境忽略本地代理时，后端日志会出现类似记录：

```txt
生产环境已忽略本地代理 | account_id=1 | account_name=采集账号 | proxy=127.0.0.1:7897
```

## 告警通知配置

系统错误告警继续使用 `.env` 配置，不需要数据库配置。

需要在服务器 `/opt/telegram-bot/.env` 中配置：

```env
CONTROL_BOT_TOKEN=你的告警BotToken
ALERT_CHAT_ID=你的告警频道chat_id或@频道username
```

说明：

- `CONTROL_BOT_TOKEN` 是专门发送错误通知的 Telegram Bot Token。
- `ALERT_CHAT_ID` 是接收告警的频道、群或用户，可以填写 `@username`，也可以填写 `-100` 开头的 chat_id。
- 如果通知频道是私有频道，建议使用 `-100xxxxxxxxxx` 形式的 chat_id，并确保告警 Bot 已加入频道且有发消息权限。
- 修改 `.env` 后需要重启后端容器才会生效。

重启并测试：

```bash
cd /opt/telegram-bot
docker compose restart backend
curl http://127.0.0.1:8000/api/notify/test
docker logs -f tg-backend
```

如果仍看到 `告警未发送：CONTROL_BOT_TOKEN 未配置`，说明容器没有读取到 `.env` 中的 `CONTROL_BOT_TOKEN`。

## 线上重新登录采集账号

当 Telegram 用户号 session 失效时，不要新建一个不相关的账号记录。监听任务、克隆任务通常绑定的是旧的 `account_id`，应优先选择“重新登录已有账号”，保持原 `account_id` 和 `session_path` 不变。

推荐流程：

```bash
cd /opt/telegram-bot
docker compose stop backend
docker compose run --rm -it backend python login_account.py
docker compose up -d
docker logs -f tg-backend
```

注意必须带 `-it`，否则 Docker 里无法输入手机号、验证码和二步验证密码。

脚本启动后会显示已有账号列表：

```txt
ID | 名称 | username | phone | session_path | enabled
```

如果要恢复旧监听任务绑定的账号，例如 `account_id=3`：

1. 选择 `1. 重新登录已有账号`
2. 输入 `account_id=3`
3. Session 路径直接回车，使用原来的 `data/sessions/collector_1`
4. 输入手机号、验证码、二步验证密码

登录成功后，脚本会更新原账号记录，不会创建重复账号：

```txt
登录成功：
id = 3
name = ...
username = ...
phone = ...
session = data/sessions/collector_1
updated_existing = true
```

如果旧 `.session` 文件已被 Telegram 判定失效，脚本会把旧文件改名备份为 `.invalid_时间戳`，然后继续用相同 `session_path` 重新登录。这样任务里的 `account_id` 不需要修改。

## 云台 Bot / 告警通知配置

云台 Bot 使用 `.env` 配置，不做后台配置页。建议使用独立 Bot，不要和客服 Bot、分发 Bot 共用。

服务器 `/opt/telegram-bot/.env` 示例：

```env
CONTROL_BOT_ENABLED=true
CONTROL_BOT_TOKEN=123456789:AAxxxx
CONTROL_CHAT_ID=-100xxxxxxxxxx
CONTROL_ADMIN_IDS=123456789
CONTROL_COMMANDS_ENABLED=true
CONTROL_ALERTS_ENABLED=true
CONTROL_ALERT_THREAD_ID=
CONTROL_COMMAND_THREAD_ID=
CONTROL_POLLING_TIMEOUT=30
CONTROL_NOTIFY_LEVEL=error
```

Telegram 侧配置：

1. 创建一个独立控制 Bot。
2. 创建一个私密群或超级群作为云台。
3. 把控制 Bot 拉进云台群，并设置为管理员。
4. 在群里发送 `/whoami` 获取管理员 Telegram user_id。
5. 把群 chat_id 填入 `CONTROL_CHAT_ID`，管理员 ID 填入 `CONTROL_ADMIN_IDS`。
6. 重启后端。

说明：

- 接收告警可以用频道。
- 如果要执行命令，推荐使用私密群或超级群。
- `CONTROL_CHAT_ID` 是唯一允许处理命令的 chat_id，其他群/私聊会被忽略。
- `CONTROL_ADMIN_IDS` 未配置时，只允许告警，不允许命令控制。
- 如果云台是话题群，可以使用 `CONTROL_ALERT_THREAD_ID` 和 `CONTROL_COMMAND_THREAD_ID`。

重启并查看日志：

```bash
cd /opt/telegram-bot
docker compose down
docker compose up -d --build
docker logs -f tg-backend
```

常用命令：

```text
/help
/whoami
/status
/listeners
/clones
/pause listener 5
/resume listener 5
/run clone 2
```
