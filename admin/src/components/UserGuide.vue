<template>
  <div class="guide-page">
    <el-card class="guide-card">
      <template #header>
        <div class="guide-header">
          <div>
            <div class="guide-title">使用教程</div>
            <div class="guide-subtitle">
              按推荐顺序完成账号、Bot、频道、规则、任务、客服和云台配置。
            </div>
          </div>
        </div>
      </template>

      <el-alert
        title="推荐流程：账号管理 → Bot 管理 → 我的频道 → 内容模板/过滤词 → 克隆任务 → 监听任务 → 客服机器人 → 云台告警"
        type="info"
        show-icon
        :closable="false"
      />

      <el-collapse v-model="activeSections" class="guide-collapse">
        <el-collapse-item title="1. 系统能做什么" name="overview">
          <p>
            本系统用于把 Telegram 源频道内容同步到一个或多个目标频道。采集账号使用 Telethon 读取源频道，
            官方 Bot API 负责把文本、图片、视频、文件、相册等内容发送到目标频道。
          </p>
          <ul>
            <li>克隆任务：批量同步历史内容，可设置开始消息链接和结束消息链接。</li>
            <li>监听任务：实时监听源频道新内容，并按目标频道单独去重发送。</li>
            <li>我的频道：统一维护所有目标频道，减少手动输入错误。</li>
            <li>内容模板规则：按 head、body、footer 给内容追加固定或随机文案。</li>
            <li>客服机器人：客户私聊 Bot 后，消息进入客服群话题，客服在 Telegram 群内直接回复。</li>
            <li>云台 Bot：通过 Telegram 群接收告警，也可以查询和启停任务。</li>
          </ul>
        </el-collapse-item>

        <el-collapse-item title="2. 第一次使用前准备" name="prepare">
          <ul>
            <li>准备一个能读取源频道的 Telegram 用户号，并通过 <code>login_account.py</code> 登录生成 session。</li>
            <li>准备一个或多个官方 Bot，用于向目标频道发送内容。</li>
            <li>把分发 Bot 加入目标频道，并授予发送消息、发送媒体、编辑消息等必要权限。</li>
            <li>如果使用客服机器人，请单独准备客服 Bot，并拉入客服群。</li>
            <li>如果使用云台告警，请单独准备云台 Bot，不建议和客服 Bot 共用。</li>
          </ul>
          <p class="guide-tip">
            源频道和目标频道支持 <code>@username</code>、<code>https://t.me/xxx</code>、<code>t.me/xxx</code>
            等格式。目标频道建议先录入“我的频道”。
          </p>
        </el-collapse-item>

        <el-collapse-item title="3. 账号管理" name="accounts">
          <p>
            账号管理里的账号只负责采集源频道内容，不负责向目标频道发送。目标频道发送由 Bot API 完成。
          </p>
          <ul>
            <li>本地或线上登录账号时，请使用 <code>backend/login_account.py</code>。</li>
            <li>重新登录已有账号时，应选择旧账号 ID，保持原来的 <code>account_id</code> 不变。</li>
            <li>如果线上提示 session 失效，需要停止后端后用 Docker 交互方式重新登录。</li>
            <li>生产环境会自动忽略 <code>127.0.0.1</code>、<code>localhost</code> 等本地代理，避免服务器误连本地代理。</li>
          </ul>
          <p class="guide-tip">
            如果监听任务提示“监听账号不存在”，通常是任务绑定的 <code>account_id</code> 和账号表不一致，
            重新登录时不要创建重复账号。
          </p>
        </el-collapse-item>

        <el-collapse-item title="4. Bot 管理" name="bots">
          <p>
            Bot 管理用于维护分发 Bot。页面会显示 Bot 名称、状态和 <code>@botname</code>，Token 不应直接暴露给普通操作人员。
          </p>
          <ul>
            <li>新增 Bot 后先点击测试，确认 Token 可用。</li>
            <li>把 Bot 加入目标频道，并设置为管理员或授予发帖权限。</li>
            <li>Bot 链接和 username 支持点击复制，方便配置频道权限。</li>
            <li>403、not a member、not enough rights 一般表示 Bot 未加入频道或权限不足。</li>
          </ul>
        </el-collapse-item>

        <el-collapse-item title="5. 我的频道" name="my-channels">
          <p>
            我的频道是目标频道资产库。克隆任务、监听任务、附加目标等需要选择目标频道的地方，
            都优先从这里选择，避免反复手动输入。
          </p>
          <ul>
            <li>新增频道时，username 和 chat_id 至少填写一个。</li>
            <li>username 没有写 <code>@</code> 时系统会自动兼容。</li>
            <li>绑定 Bot 后可以检测 Bot 是否在频道、是否管理员、是否可发帖、是否可管理话题。</li>
            <li>检测成功会写入真实 chat_id、频道名称、频道类型和权限信息。</li>
            <li>username、chat_id、绑定 Bot 支持点击复制。</li>
          </ul>
        </el-collapse-item>

        <el-collapse-item title="6. 内容模板和过滤规则" name="templates">
          <p>
            内容处理建议分两层：通用规则放在模板/规则库里，单个任务只填写需要补充的个性规则。
          </p>
          <h4>内容模板规则</h4>
          <ul>
            <li>模板分为 <code>head</code>、<code>body</code>、<code>footer</code> 三种类型。</li>
            <li>每条规则可以包含多条内容，例如“规则 A”下面有内容 1、内容 2、内容 3。</li>
            <li>任务里启用某种类型后，可以选择规则随机内容，也可以指定规则下某一条固定内容。</li>
            <li>拼接顺序是：head + 原始内容 + body + footer。</li>
          </ul>
          <h4>过滤关键词</h4>
          <ul>
            <li>通用过滤词适合放常见违禁词、广告词、无效内容。</li>
            <li>任务补充过滤词只影响当前克隆或监听任务。</li>
            <li>过滤命中后整条内容跳过，不再拼接模板。</li>
            <li>原文经过删除联系方式、删除整行后如果变成空文本，系统会跳过，并在监听缓存里显示空内容原因。</li>
          </ul>
        </el-collapse-item>

        <el-collapse-item title="7. 克隆任务" name="clone">
          <p>
            克隆任务用于同步历史消息。新增任务时先选择分发 Bot，再选择目标频道；如果目标频道未加入“我的频道”，
            仍可手动填写目标频道。
          </p>
          <ul>
            <li>源频道：支持 <code>@username</code> 和 <code>https://t.me/xxx</code>。</li>
            <li>开始内容链接：填写后从该消息开始克隆，包含该消息。</li>
            <li>结束内容链接：填写后克隆到该消息结束，包含该消息。</li>
            <li>内容间隔单位是分钟，用于控制每条内容之间的等待时间。</li>
            <li>单条媒体超过大小限制会跳过整条内容，避免发送失败阻塞任务。</li>
            <li>某个目标失败不会影响其他目标继续发送；任意目标成功后会写入去重记录。</li>
            <li>克隆完成后，如果源频道最新内容和目标频道最新内容一致，可以自动进入监听。</li>
          </ul>
        </el-collapse-item>

        <el-collapse-item title="8. 监听任务" name="listener">
          <p>
            监听任务用于实时同步新消息。监听任务支持多个源频道和多个目标频道，发送时按目标频道单独去重。
          </p>
          <ul>
            <li>新增任务时可以克隆某条已有任务规则，再按需要修改源频道、目标频道和规则。</li>
            <li>源频道和目标频道支持点击复制，便于排查。</li>
            <li>补齐按钮会检查源频道和目标频道最新内容；即使系统判断一致，也可以确认后强行补齐最新一条。</li>
            <li>相册按一条内容处理，只等待内容间隔，不再单独使用相册间隔。</li>
            <li>监听发送缓存用于显示最近执行结果，主要看状态、源链接、目标链接和失败原因。</li>
          </ul>
          <p class="guide-tip">
            如果监听一直没有发送，优先检查：任务是否启用、账号是否存在、账号是否能读取源频道、Bot 是否有目标频道权限。
          </p>
        </el-collapse-item>

        <el-collapse-item title="9. 发送缓存" name="send-logs">
          <p>
            克隆任务和监听任务页面下方的发送缓存用于快速查看最近执行结果。列表不会频繁自动刷新，
            默认更偏向手动刷新，避免线上页面一直请求接口。
          </p>
          <ul>
            <li>最新记录显示在上方。</li>
            <li>同一条任务内容不会在表格里重复堆多行，而是更新状态和结果。</li>
            <li>成功记录会显示源链接、目标链接、目标频道、任务名称和消息 ID。</li>
            <li>失败记录会显示错误原因，例如权限不足、Bot 不在频道、媒体下载失败、空内容跳过。</li>
            <li>链接、频道、目标字段支持复制，线上复制失败时可手动选中文本复制。</li>
          </ul>
        </el-collapse-item>

        <el-collapse-item title="10. 客服机器人" name="support">
          <p>
            客服机器人采用 Telegram 群内客服模式，不在后台做聊天输入框。客户私聊 Bot 后，
            系统把消息同步到客服群；客服在对应客户话题里直接回复，Bot 再转发给客户。
          </p>
          <h4>配置步骤</h4>
          <ol>
            <li>准备一个客服 Bot，可以选择已有 Bot，也可以填写独立 Token。</li>
            <li>创建 Telegram 超级群，建议开启 Topics 话题功能。</li>
            <li>把客服 Bot 拉进客服群，并设置为管理员。</li>
            <li>授予 Bot 管理话题权限，否则无法自动为每个客户创建独立话题。</li>
            <li>Bot 加入群后会在 General 自动发送当前群 chat_id，通常是 <code>-100</code> 开头。</li>
            <li>把这个 chat_id 填到后台客服设置里。</li>
            <li>配置欢迎语、营业时间、非营业时间回复和快捷回复。</li>
            <li>点击检测 Bot，确认 Token、群 ID、话题权限正常。</li>
          </ol>
          <h4>客服怎么回复</h4>
          <ul>
            <li>客户首次私聊 Bot 后，系统自动创建客户资料和会话。</li>
            <li>开启 Topics 后，每个客户会有一个独立客服话题。</li>
            <li>客服在该话题内发送文本、图片、视频、文件、语音、贴纸等内容，即可回复客户。</li>
            <li>不要在 General 里直接回复客户，General 主要用于系统提示和异常兜底。</li>
          </ul>
          <h4>客服群命令</h4>
          <ul>
            <li><code>/info</code>：查看当前客户信息。</li>
            <li><code>/close</code>：关闭当前会话。</li>
            <li><code>/block</code>：拉黑当前客户。</li>
            <li><code>/unblock</code>：取消拉黑当前客户。</li>
          </ul>
        </el-collapse-item>

        <el-collapse-item title="11. 批量替换历史联系方式" name="bulk-replace">
          <p>
            批量替换用于编辑系统已经发送过的频道消息，例如把旧联系方式替换成新联系方式。
            第一版只基于系统已有发送记录处理，不扫描完整频道历史。
          </p>
          <ul>
            <li>先选择一个或多个“我的频道”。</li>
            <li>填写旧内容和新内容，例如把 <code>123455</code> 替换为 <code>111111</code>。</li>
            <li>先点击扫描预览，确认命中内容后再执行。</li>
            <li>文本消息使用 <code>editMessageText</code>，媒体 caption 使用 <code>editMessageCaption</code>。</li>
            <li>Bot 必须有编辑目标频道消息的权限，否则会记录失败原因。</li>
            <li>单条失败不会影响其他消息继续处理。</li>
          </ul>
        </el-collapse-item>

        <el-collapse-item title="12. 云台 Bot 和错误告警" name="control-bot">
          <p>
            云台 Bot 是运维控制 Bot，用于接收系统告警，也可以在 Telegram 群里执行简单命令。
            它通过 Docker 根目录的 <code>.env</code> 配置，不在后台页面配置。
          </p>
          <h4>必须配置</h4>
          <ul>
            <li><code>CONTROL_BOT_TOKEN</code>：云台 Bot Token。</li>
            <li><code>CONTROL_CHAT_ID</code>：云台群 ID。</li>
            <li><code>CONTROL_ADMIN_IDS</code>：允许执行命令的 Telegram 数字用户 ID，多个用英文逗号分隔。</li>
          </ul>
          <h4>常用命令</h4>
          <ul>
            <li><code>/status</code>：查看系统状态。</li>
            <li><code>/accounts</code>：查看采集账号。</li>
            <li><code>/listeners</code>：查看监听任务。</li>
            <li><code>/clones</code>：查看克隆任务。</li>
            <li><code>/pause listener 任务ID</code>：暂停监听任务。</li>
            <li><code>/resume listener 任务ID</code>：恢复监听任务。</li>
            <li><code>/recent_errors</code>：查看最近错误。</li>
          </ul>
          <p class="guide-tip">
            修改 <code>.env</code> 后需要重新创建容器：<code>docker compose up -d --force-recreate</code>。
          </p>
        </el-collapse-item>

        <el-collapse-item title="13. 常见问题排查" name="faq">
          <ul>
            <li>目标没有收到内容：检查 Bot 是否在目标频道、是否有发帖和媒体权限。</li>
            <li>403 权限错误：通常是 Bot 未加入目标频道，或没有管理员/发帖权限。</li>
            <li>监听任务不启动：检查任务是否启用、账号 ID 是否存在、账号 session 是否有效。</li>
            <li>自动监听发送空内容：检查过滤词、删除整行、删除旧联系方式是否把原文处理为空。</li>
            <li>相册 caption 丢失：确认源频道相册完整可读，系统会尽量重新拉取完整相册内容。</li>
            <li>客服 Bot 409 conflict：同一个 Bot Token 只能有一个 polling 实例运行。</li>
            <li>客服消息都进 General：检查客服群是否开启 Topics，以及 Bot 是否有 Manage Topics 权限。</li>
            <li>云台无回复：检查 <code>CONTROL_CHAT_ID</code>、<code>CONTROL_ADMIN_IDS</code> 和容器环境变量是否生效。</li>
            <li>线上代理错误：生产环境不要使用 <code>127.0.0.1</code> 作为 Bot API 或账号代理。</li>
          </ul>
        </el-collapse-item>
      </el-collapse>
    </el-card>
  </div>
</template>

<script setup>
import { ref } from "vue"

const activeSections = ref(["overview", "prepare", "my-channels", "clone", "listener", "support", "control-bot"])
</script>

<style scoped>
.guide-page {
  width: 100%;
}

.guide-card {
  border-radius: 8px;
}

.guide-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.guide-title {
  font-size: 16px;
  font-weight: 600;
  color: #303133;
}

.guide-subtitle {
  margin-top: 4px;
  font-size: 12px;
  color: #909399;
}

.guide-collapse {
  margin-top: 16px;
}

.guide-tip {
  padding: 10px 12px;
  border-left: 3px solid #409eff;
  border-radius: 4px;
  background: #ecf5ff;
}

p {
  line-height: 1.8;
  color: #374151;
}

ul,
ol {
  margin: 0;
  padding-left: 20px;
  color: #374151;
  line-height: 1.9;
}

h4 {
  margin: 14px 0 8px;
  color: #303133;
  font-size: 14px;
}

code {
  padding: 2px 6px;
  border-radius: 4px;
  background: #f5f7fa;
  color: #c45656;
  word-break: break-all;
}
</style>
