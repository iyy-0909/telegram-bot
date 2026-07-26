<template>
  <div class="guide-page">
    <el-card class="guide-card">
      <template #header>
        <div class="guide-header">
          <div>
            <div class="guide-title">使用教程</div>
            <div class="guide-subtitle">
              按推荐顺序完成账号、Bot、频道、搜索机器人、规则、任务和告警配置。
            </div>
          </div>
        </div>
      </template>

      <el-alert
        title="推荐流程：账号管理 → Bot 管理 → 频道管理 → 搜索机器人 → 系统设置/内容规则 → 克隆任务 → 监听任务 → 云台告警"
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
            <li>搜索机器人：维护搜索机器人，并记录每个频道在不同机器人中的审核、收录和拉黑状态。</li>
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
            <li>新增账号请使用账号管理中的“登录账号”，系统会自动分配并保存登录凭证。</li>
            <li>重新登录已有账号时，应点击该账号的“重新登录”；系统会保留原来的账号 ID 和登录凭证路径。</li>
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
            <li>分组用于管理频道所属城市，也是匹配搜索机器人的依据；搜索机器人本身不需要设置分组。</li>
            <li>绑定 Bot 后可以检测 Bot 是否在频道、是否管理员、是否可发帖、是否可管理话题。</li>
            <li>检测成功会写入真实 chat_id、频道名称、频道类型和权限信息。</li>
            <li>点击“提交”可以把当前频道提交到搜索机器人；点击“查看”可以查看该频道对应的全部机器人状态。</li>
            <li>只要该频道被任意一个搜索机器人有效收录，频道表格的收录状态就显示“已收录”。</li>
            <li>username、chat_id、绑定 Bot 支持点击复制。</li>
          </ul>
        </el-collapse-item>

        <el-collapse-item title="6. 搜索机器人和频道提交" name="search-bots">
          <p>
            搜索机器人用于收录和检索频道。机器人管理只负责维护机器人资料；频道提交统一从“频道管理 → 我的频道”发起。
            一个频道可以依次提交给多个机器人，每个频道与机器人的对应关系都会单独保留。
          </p>
          <h4>添加搜索机器人</h4>
          <ol>
            <li>进入“频道管理 → 搜索机器人”。</li>
            <li>点击“新增机器人”，填写机器人名称和机器人 ID（例如 <code>@jisou</code>）。</li>
            <li>操作账号和月活等字段可以后续补充；新增时不是必填项。</li>
            <li>点击“检测”可以更新机器人状态和可获取的公开信息。</li>
          </ol>
          <h4>提交频道</h4>
          <ol>
            <li>进入“频道管理 → 我的频道”，确认频道已经设置城市分组。</li>
            <li>在频道操作栏点击“提交”，选择需要提交的搜索机器人。</li>
            <li>自动添加模式会把搜索机器人加入频道并设置为管理员；请选择需要授予的 Telegram 频道权限。</li>
            <li>操作账号可以留空，但机器人必须已经配置默认操作账号；否则需要选择一个拥有该频道管理权限的账号。</li>
            <li>提交会立即执行，不进入全局内容发送队列。</li>
          </ol>
          <h4>人工登记和状态维护</h4>
          <ul>
            <li>如果已经在 Telegram 手动添加机器人，可以选择“手动登记”，不需要操作账号，也不会执行 Telegram 操作。</li>
            <li>人工登记的权限会标记为“未验证”；自动添加会回查 Telegram 实际权限并显示验证结果。</li>
            <li>点击频道的“查看”，可以看到该频道在机器人 A、机器人 B 等不同机器人中的审核、收录和拉黑状态。</li>
            <li>“机器人收录”需要先选择频道分组，再查看各搜索机器人已提交、已收录、已拉黑和未提交的频道情况。</li>
            <li>点击“更新状态”可以维护审核、收录和拉黑结果；点击“调整权限”可以重新设置管理员权限并回查。</li>
            <li>频道在机器人 A 被拉黑后，仍可提交到机器人 B，历史记录不会被覆盖。</li>
          </ul>
        </el-collapse-item>

        <el-collapse-item title="7. 内容模板和过滤规则" name="templates">
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
            <li>监听任务的“只监听内容”用于设置必须命中的关键词；源内容没有命中时不会发送。</li>
            <li>过滤命中后整条内容跳过，不再拼接模板。</li>
            <li>联系方式删除可以使用系统规则，也可以在内容规则模板中配置；命中后按所选规则处理。</li>
            <li>原文经过删除联系方式、删除整行后如果变成空文本，系统会跳过，并在监听缓存里显示空内容原因。</li>
          </ul>
        </el-collapse-item>

        <el-collapse-item title="8. 克隆任务" name="clone">
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
            <li>“克隆任务”页签用于创建和控制任务；“执行任务”页签用于查看最近发送结果。</li>
          </ul>
        </el-collapse-item>

        <el-collapse-item title="9. 监听任务" name="listener">
          <p>
            监听任务用于实时同步新消息。监听任务支持多个源频道和多个目标频道，发送时按目标频道单独去重。
          </p>
          <ul>
            <li>新增任务时可以克隆某条已有任务规则，再按需要修改源频道、目标频道和规则。</li>
            <li>源频道和目标频道支持点击复制，便于排查。</li>
            <li>“只监听内容”填写必须命中的关键词；“过滤词”填写需要跳过的关键词，两类规则按当前任务独立生效。</li>
            <li>点击“一键补齐”后，系统先检查可补齐数量，再由用户填写本次补齐条数。</li>
            <li>补齐任务会进入首页排队任务列表，并与克隆、监听发送共用全局限流。</li>
            <li>相册按一条内容处理，只等待内容间隔，不再单独使用相册间隔。</li>
            <li>“监听任务”页签用于管理任务；“执行任务”页签用于查看状态、源链接、目标链接、过滤原因和失败原因。</li>
          </ul>
          <p class="guide-tip">
            如果监听一直没有发送，优先检查：任务是否启用、账号是否存在、账号是否能读取源频道、Bot 是否有目标频道权限。
          </p>
        </el-collapse-item>

        <el-collapse-item title="10. 执行任务记录" name="send-logs">
          <p>
            克隆任务和监听任务页面都提供“执行任务”页签，用于快速查看最近执行结果。列表不会频繁自动刷新，
            建议需要时手动点击刷新，避免线上页面持续请求接口。
          </p>
          <ul>
            <li>最新记录显示在上方。</li>
            <li>两个任务页面默认打开任务管理页签，切换到“执行任务”后再查看日志。</li>
            <li>执行表格固定显示约十行高度，更多记录在表格内部滚动。</li>
            <li>监听执行任务支持按事件类型筛选；监听和克隆执行任务都支持搜索任务、频道、消息和错误。</li>
            <li>成功记录会显示源链接、目标链接、目标频道、任务名称和消息 ID。</li>
            <li>过滤记录会显示命中的关键词或条件；失败记录会显示权限不足、Bot 不在频道、媒体下载失败等原因。</li>
            <li>链接、频道、目标字段支持复制，线上复制失败时可手动选中文本复制。</li>
          </ul>
        </el-collapse-item>

        <el-collapse-item title="11. 客服机器人" name="support">
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

        <el-collapse-item title="12. 批量替换历史联系方式" name="bulk-replace">
          <p>
            批量替换用于编辑系统已经发送过的频道消息，例如把旧联系方式替换成新联系方式。
            第一版只基于系统已有发送记录处理，不扫描完整频道历史。
          </p>
          <ul>
            <li>先选择一个或多个“我的频道”。</li>
            <li>填写旧内容和新内容，例如把 <code>123455</code> 替换为 <code>111111</code>。</li>
            <li>需要移除整条历史内容时，可以选择删除整条内容，而不是填写替换文本。</li>
            <li>先点击扫描预览，确认命中内容后再执行。</li>
            <li>文本消息使用 <code>editMessageText</code>，媒体 caption 使用 <code>editMessageCaption</code>。</li>
            <li>Bot 必须有编辑目标频道消息的权限，否则会记录失败原因。</li>
            <li>单条失败不会影响其他消息继续处理。</li>
          </ul>
        </el-collapse-item>

        <el-collapse-item title="13. 云台 Bot 和错误告警" name="control-bot">
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

        <el-collapse-item title="14. 常见问题排查" name="faq">
          <ul>
            <li>目标没有收到内容：检查 Bot 是否在目标频道、是否有发帖和媒体权限。</li>
            <li>403 权限错误：通常是 Bot 未加入目标频道，或没有管理员/发帖权限。</li>
            <li>监听任务不启动：检查任务是否启用、账号 ID 是否存在、账号 session 是否有效。</li>
            <li>监听长时间没有新记录：先确认源频道是否更新，再查看“执行任务”页签中的过滤、去重或账号异常记录。</li>
            <li>自动监听发送空内容：检查过滤词、删除整行、删除旧联系方式是否把原文处理为空。</li>
            <li>搜索机器人添加失败：检查操作账号是否有频道管理权限，以及机器人 ID 是否正确。</li>
            <li>搜索机器人权限不一致：进入频道提交状态，点击“调整权限”重新应用并回查 Telegram 实际权限。</li>
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

const activeSections = ref(["overview", "prepare", "my-channels", "search-bots", "clone", "listener", "send-logs"])
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
