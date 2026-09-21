# 本地私聊助手（接入验证中，未启用代发）

目标账号：微信 `XZyule888`、`KTV-XZ8888`；Telegram `@shanghai_xiaozhang`、`@KTV_AZ`。

当前状态必须区分：

- 已实现本地事件去重、账号隔离、接管时间过滤、合并连续消息、按缺失信息提问。
- 模型只在收到符合条件的新私聊后运行；日常监听不调用模型。
- Telegram 使用已有 Telethon 依赖，但目标两个账号尚未登录到本监听器，真实收发未验证。
- 微信目前只有只读列表解析和变化检测函数；**没有完成稳定的账号核验、私聊分类、新好友同意、发送适配**。
- 所有账号默认 `enabled: false`；配置文件并不代表任何后台进程正在运行。
- **不能直接唤醒当前 Codex 对话**。Telegram 工作器调用独立的 Codex 文本提取过程，只处理当前客户必要上下文。
- 不创建周期性 Codex 任务，避免没有新消息时反复消耗模型额度。

## 已实现的接待规则

先问城市和区，再问人数、人均预算；客户已说过的内容不重复问。预算保留客户的人均或总额口径。普通 KTV 场地、消费咨询之外，涉及有偿性服务的推介或安排不自动处理。

当前没有任何已确认的地址、价格及活动资料。`knowledge.md` 用于整理业主资料；本版尚未实现知识库报价。四项资料齐全、客户停止咨询、需要人工处理、模型失败、无法确认发送结果时，会保存到本地待处理状态，不承诺已为客户安排场地。

微信自动同意新好友并发送一次“你好”是用户要求，配置已记录，但微信执行器尚未实现；不要把该配置开关当作可用功能。

## 数据位置

状态、待处理消息及授权 session 存在项目 `data/local_message_assistant/` 下，已被项目现有忽略规则排除。日志不打印聊天正文。各账号上下文互相隔离。

状态库是新的独立文件，未修改项目业务数据库。程序遇到未知状态库版本会停止，不自动迁移。发送前先记录状态，发送超时或进程崩溃后不自动重发，相关会话留给人工核实。

## 本地验证

在本目录运行：

```powershell
..\..\.venv\Scripts\python.exe -m unittest -v test_engine
..\..\.venv\Scripts\python.exe engine.py status
```

可选模型连通测试会消耗一次模型额度，只使用模拟咨询，不向任何客户发送：

```powershell
..\..\.venv\Scripts\python.exe engine.py model-test
```

`config.json` 的 `codex_executable` 是当前电脑已验证的路径；Codex 更新后如路径变化需更新。测试和工作器使用现有 ChatGPT 登录，不读取或复制认证 token。客户文本通过标准输入作为数据传递，不拼入命令行，模型的桌面操作、插件和命令执行能力关闭。

## Telegram 账号接入（需账号本人完成登录）

监听器需要 Telegram API ID、API HASH 和两个独立登录授权。桌面 Telegram 已登录，并不表示 Telethon 已授权；程序不复制桌面 tdata 或复用项目其它账号的 session。

在你自己的终端设置 `LOCAL_ASSISTANT_TELEGRAM_API_ID` 和 `LOCAL_ASSISTANT_TELEGRAM_API_HASH`，然后分别运行：

```powershell
..\..\.venv\Scripts\python.exe telegram_listener.py --login shanghai_xiaozhang
..\..\.venv\Scripts\python.exe telegram_listener.py --login KTV_AZ
```

验证码和二次验证密码仅在本地登录提示中输入。程序会核实最终用户名，不匹配即停止，不自动删除任何 session。

两个账号验证并进行收发验收后，再将对应 Telegram 配置的 `enabled` 改为 `true`，前台运行：

```powershell
..\..\.venv\Scripts\python.exe telegram_listener.py
```

首次启动只接受启动之后的新消息；旧未读消息、群消息、机器人、Telegram 服务账号和自己的消息不触发回复。图片、语音等非文字消息尚未支持。本版尚无开机自启、待处理通知和会话恢复界面。不要同时启动多个监听进程。

## 微信接入的剩余工作

`wechat_watch.mjs` 只能在 Computer Use 的 JavaScript 会话中注入 `sky` 后进行只读采样；它不自行启动监控、不调用模型、不发送消息。列表项变化仅代表候选消息，必须另外验证账号身份、私聊类型、消息方向和唯一消息标识后才能接入发送流程。当前没有通过这部分端到端验收。

还需要核验两个微信账号与窗口的对应关系，稳定打开新好友页面、接受申请并核实成功，再实现只发送一次“你好”；以及测试真实新私聊的完整回复流程。
