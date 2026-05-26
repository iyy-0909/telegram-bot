<template>
  <div class="guide-page">
    <el-card class="guide-card">
      <template #header>
        <div class="guide-header">
          <div>
            <div class="guide-title">使用教程</div>
            <div class="guide-subtitle">
              按照下面顺序配置采集账号、分发 Bot、客服机器人、克隆任务和监听任务。
            </div>
          </div>
        </div>
      </template>

      <el-alert
        title="推荐使用流程：账号管理 → Bot 管理 → 我的频道 → 客服机器人 → 克隆任务 → 监听任务 → 运行日志"
        type="info"
        show-icon
        :closable="false"
      />

      <el-collapse v-model="activeSections" class="guide-collapse">
        <el-collapse-item title="1. 系统是做什么的" name="overview">
          <p>
            本系统用于把 Telegram 源频道内容转发到目标频道。用户号负责读取源频道内容，
            官方 Bot API 负责把内容发送到目标频道。
          </p>
          <p>
            克隆任务用于批量同步历史内容；监听任务用于实时同步新内容。克隆任务完成后，
            如果源频道最新内容和目标频道最新内容一致，系统会自动进入监听。
          </p>
        </el-collapse-item>

        <el-collapse-item title="2. 第一次使用前需要准备什么" name="prepare">
          <ul>
            <li>一个可读取源频道的 Telegram 用户号。</li>
            <li>一个或多个官方 Telegram Bot。</li>
            <li>把 Bot 加入目标频道，并给 Bot 发送消息/媒体所需权限。</li>
            <li>确认源频道和目标频道填写格式，例如：@channel_name。</li>
          </ul>
        </el-collapse-item>

        <el-collapse-item title="3. 账号管理" name="accounts">
          <p>
            账号管理里的账号用于读取源频道。新建账号后，需要填写账号名称和 session 路径。
            账号必须能正常读取源频道，否则克隆任务和监听任务都无法获取源内容。
          </p>
        </el-collapse-item>

        <el-collapse-item title="4. Bot 管理和目标绑定" name="bots">
          <p>
            Bot 管理用于维护官方 Bot Token。添加 Bot 后，建议先使用测试功能确认 Bot 可用。
          </p>
          <p>
            目标绑定用于指定某个目标频道使用哪个 Bot 发送。如果目标频道没有绑定 Bot，
            系统会尝试使用可用的默认 Bot。
          </p>
          <p>
            如果出现 403 Forbidden、bot is not a member 或 not enough rights，通常表示 Bot
            没有加入目标频道，或者没有足够权限。
          </p>
        </el-collapse-item>

        <el-collapse-item title="5. 系统设置" name="settings">
          <ul>
            <li>全局发送间隔：所有克隆和监听发送共用，避免发送太快。</li>
            <li>重试次数：发送异常时最多重试几次。</li>
            <li>重试等待：每次重试前等待的秒数。</li>
          </ul>
        </el-collapse-item>

        <el-collapse-item title="6. 克隆任务" name="clone">
          <p>
            克隆任务用于把源频道历史内容同步到目标频道。新增任务时需要填写任务名称、
            源频道、目标频道、账号、内容间隔分钟、过滤关键词、替换词和 footer。
          </p>
          <ul>
            <li>源频道开始内容链接：填写后从这条消息开始克隆，包含这条消息。</li>
            <li>源频道结束内容链接：填写后克隆到这条消息结束，包含这条消息。</li>
            <li>内容间隔分钟：每条内容发送完成后的等待时间。</li>
            <li>目标间隔秒：同一条内容发送到多个目标时，目标之间的间隔。</li>
            <li>启用监听：克隆完成并确认最新内容一致后，自动生成监听任务。</li>
          </ul>
          <p>
            纯文本、单媒体和相册都会按“一条内容”处理。单个目标失败不会影响其他目标继续发送。
          </p>
        </el-collapse-item>

        <el-collapse-item title="7. 监听任务" name="listener">
          <p>
            监听任务用于实时同步源频道新消息。监听任务使用用户号读取源频道，
            使用官方 Bot API 发送到目标频道。
          </p>
          <ul>
            <li>启动：启用实时监听。</li>
            <li>停止：停止实时监听。</li>
            <li>补齐：检查源频道和目标频道最新内容是否一致。</li>
            <li>去重：按目标频道单独去重，同一目标不会重复发送同一条源消息。</li>
          </ul>
        </el-collapse-item>

        <el-collapse-item title="8. 客服机器人" name="support">
          <p>
            客服机器人用于接收客户私聊咨询。客户给 Bot 发消息后，系统会把消息转发到内部客服群；
            客服人员在 Telegram 客服群的话题里直接回复，Bot 会把回复转发给对应客户。
          </p>

          <h4>配置步骤</h4>
          <ol>
            <li>先在 Bot 管理里添加一个客服 Bot，或准备一个单独的 Bot Token。</li>
            <li>创建一个 Telegram 超级群，并开启 Topics 话题功能。</li>
            <li>把客服 Bot 拉进客服群，并设置为管理员。</li>
            <li>给客服 Bot 开启“管理话题 / Manage Topics”权限，否则无法自动为客户创建独立话题。</li>
            <li>在后台进入“客服机器人”，点击“新增客服 Bot”。</li>
            <li>选择已有 Bot，或填写独立 Bot Token。</li>
            <li>把客服 Bot 拉进群后，Bot 会在 General 自动发送当前群的 chat_id，通常是 -100 开头的群 ID。</li>
            <li>把 Bot 自动发送的客服群 chat_id 填到后台。</li>
            <li>填写欢迎语、非营业时间回复和营业时间。</li>
            <li>开启 polling。</li>
            <li>点击“检测”，确认 Bot Token 可用，并且客服群话题权限正常。</li>
          </ol>

          <h4>客服怎么回复客户</h4>
          <ul>
            <li>客户首次私聊 Bot 后，系统会自动创建客户资料和会话。</li>
            <li>如果客服群开启 Topics，系统会给每个客户创建独立话题。</li>
            <li>客户消息会进入对应客户话题。</li>
            <li>客服在该话题内直接发送文本、图片、视频、文件、语音等内容，即可回复客户。</li>
            <li>不要在 General 里直接发客户回复，General 里的普通消息不会发送给客户。</li>
          </ul>

          <h4>客服群命令</h4>
          <ul>
            <li><code>/info</code>：查看当前客户信息。</li>
            <li><code>/close</code>：关闭当前客户会话。</li>
            <li><code>/block</code>：拉黑当前客户，后续不再转发客服回复。</li>
            <li><code>/unblock</code>：取消拉黑当前客户。</li>
          </ul>

          <h4>注意事项</h4>
          <ul>
            <li>生产环境只允许一个后端实例使用同一个客服 Bot polling，否则 Telegram 会返回 409 conflict。</li>
            <li>如果检测提示缺少 Manage Topics 权限，请回 Telegram 群里给 Bot 补管理员和管理话题权限。</li>
            <li>客户拉黑 Bot 后，客服回复会失败，系统会自动标记客户为已拉黑。</li>
            <li>欢迎语可以发送文本，也可以配置媒体 file_id；媒体 file_id 必须来自该 Bot 可用的 Telegram 文件。</li>
            <li>不要把客服 Bot Token 发给无关人员，后台不会回显已保存 Token。</li>
          </ul>
        </el-collapse-item>

        <el-collapse-item title="9. 过滤、替换和 footer" name="rules">
          <ul>
            <li>过滤关键词：命中后整条内容跳过。</li>
            <li>替换词：把指定文字替换为新文字。</li>
            <li>删除整行：命中关键词后删除这一整行。</li>
            <li>删除旧联系方式：自动删除包含手机号、Telegram 用户名、链接等联系方式的整行。</li>
            <li>Footer：发送时追加到内容末尾。</li>
          </ul>
        </el-collapse-item>

        <el-collapse-item title="10. 运行日志和发送缓存" name="logs">
          <p>
            运行日志用于查看系统运行状态和错误原因。克隆任务和监听任务页面下方会显示最近发送缓存，
            最新记录在最上方。
          </p>
          <p>
            发送缓存会展示源链接、目标链接、目标频道、消息 ID 和发送结果，便于快速核对内容。
          </p>
        </el-collapse-item>

        <el-collapse-item title="11. 常见问题" name="faq">
          <ul>
            <li>目标没有收到内容：先检查 Bot 是否在目标频道，是否有发消息和发媒体权限。</li>
            <li>内容被删得太多：检查是否开启“删除旧联系方式”，以及删除整行规则是否过宽。</li>
            <li>监听没有生效：检查监听任务是否启动，账号是否能读取源频道。</li>
            <li>发送太快或太慢：调整系统设置里的全局发送间隔，以及克隆任务里的内容间隔分钟。</li>
            <li>客服 Bot 没有收到群消息：检查 polling 是否开启，并确认 BotFather 里的 Group Privacy 是否影响群消息接收。</li>
            <li>客服消息都跑到 General：检查客服群是否开启 Topics，以及 Bot 是否有 Manage Topics 权限。</li>
          </ul>
        </el-collapse-item>
      </el-collapse>
    </el-card>
  </div>
</template>

<script setup>
import { ref } from "vue"

const activeSections = ref(["overview", "prepare", "clone", "listener", "support"])
</script>

<style scoped>
.guide-page {
  width: 100%;
}

.guide-card {
  border-radius: 12px;
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

p {
  line-height: 1.8;
  color: #374151;
}

ul {
  margin: 0;
  padding-left: 20px;
  color: #374151;
  line-height: 1.9;
}

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
}
</style>
