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
        title="推荐流程：账号管理 → Bot 管理 → 频道管理 → 搜索机器人 → 系统设置/内容规则 → 克隆任务 → 监听任务 → 系统告警"
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
            <li>系统告警：在后台集中查看错误、警告、恢复记录并确认已读。</li>
            <li>云台 Bot：保留 Telegram 命令查询和任务控制，不再推送告警。</li>
          </ul>
        </el-collapse-item>

        <el-collapse-item title="2. 第一次使用前准备" name="prepare">
          <ul>
            <li>准备一个能读取源频道的 Telegram 用户号，并通过 <code>login_account.py</code> 登录生成 session。</li>
            <li>准备一个或多个官方 Bot，用于向目标频道发送内容。</li>
            <li>把分发 Bot 加入目标频道，并授予发送消息、发送媒体、编辑消息等必要权限。</li>
            <li>如果使用客服机器人，请单独准备客服 Bot，并拉入客服群。</li>
            <li>如需在 Telegram 中执行云台命令，可单独准备云台 Bot；不配置也不影响后台系统告警。</li>
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
            <li>账号管理中只能有一个全局默认账号；新建克隆任务未选择采集账号时，会自动使用该默认账号。</li>
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
            <li>操作账号和备注可以后续补充；新增时不是必填项。</li>
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
            <li>如果已经在 Telegram 手动添加机器人，可以选择“手动登记”；提交账号优先从系统账号中选择，系统中没有时填写 Telegram 数字 ID。</li>
            <li>手动登记只保存提交和收录记录，不会使用所填账号执行 Telegram 操作。</li>
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
          <h4>过滤与内容处理顺序</h4>
          <ol>
            <li>监听任务先检查“只监听内容”：留空表示全部监听；填写多项时，命中任意一项即可继续。</li>
            <li>合并“通用过滤词”和“任务补充过滤词”；命中任意过滤词都会跳过整条内容。</li>
            <li>媒体中检测到二维码时，开启二维码过滤的任务会跳过整条消息或整个相册。</li>
            <li>开启“删除旧联系方式”后，按联系方式配置删除手机号、链接、用户名或关键词所在的整行。</li>
            <li>独占一整行的普通网址会被清理，然后系统再次检查过滤词。</li>
            <li>执行替换词中的“删除整行”，再执行“替换文本”，最后压缩多余空行。</li>
            <li>处理后没有可发送文本时跳过；有内容时再拼接 Head、原文、Body、Footer。</li>
            <li>最后按链接配置处理 Telegram 链接实体，并通过全局发送队列发送。</li>
          </ol>
          <p class="guide-tip">
            “只监听内容”匹配不区分大小写；过滤词和替换文本按原文精确匹配。需要同时命中多个条件时，
            当前版本不能直接表达“全部命中”，建议使用更完整的组合短语。
          </p>
          <h4>替换词怎么配置</h4>
          <ul>
            <li>替换文本：填写“命中文本”和“替换为”，会替换原文中所有相同内容。</li>
            <li>删除整行：只填写“命中文本”，任何包含该文本的整行都会被删除。</li>
            <li>每条规则都可以单独启用或停用；停用的规则不会参与处理。</li>
          </ul>
          <h4>链接配置动作</h4>
          <div class="guide-table-wrap">
            <table class="guide-table">
              <thead>
                <tr>
                  <th>动作</th>
                  <th>处理结果</th>
                  <th>适用说明</th>
                </tr>
              </thead>
              <tbody>
                <tr><td>目标链接</td><td>替换成该源消息在当前目标频道的发送链接</td><td>主要用于源频道内部消息链接；找不到历史映射时执行“找不到映射”规则</td></tr>
                <tr><td>降级文本</td><td>保留显示文字，取消可点击链接</td><td>适合外部频道、用户名、Bot 或广告链接</td></tr>
                <tr><td>保留</td><td>保留原文字和原链接</td><td>用于可信链接</td></tr>
                <tr><td>直接删除</td><td>删除链接对应的显示文字</td><td>适合不希望保留任何痕迹的链接</td></tr>
                <tr><td>替换链接</td><td>保留显示文字，把链接改成指定网址</td><td>必须填写完整替换网址</td></tr>
              </tbody>
            </table>
          </div>
          <p>
            链接规则可分别配置源频道内部消息、找不到映射、目标频道、外部频道、用户名、Bot、
            普通外部网址和邀请链接。规则主要作用于 Telegram 的可点击链接实体。
          </p>
        </el-collapse-item>

        <el-collapse-item title="8. 克隆任务" name="clone">
          <p>
            克隆任务用于按消息顺序同步历史内容。采集账号负责读取源频道，分发 Bot 负责发送目标频道。
            保存任务后，还需要在任务列表点击“开始”才会真正执行。
          </p>
          <h4>新增和编辑字段</h4>
          <div class="guide-table-wrap">
            <table class="guide-table">
              <thead>
                <tr>
                  <th>字段</th>
                  <th>怎么填写</th>
                  <th>作用和规则</th>
                </tr>
              </thead>
              <tbody>
                <tr><td>任务名称</td><td>必填，例如“北京频道历史克隆”</td><td>用于任务列表、队列和日志识别</td></tr>
                <tr><td>采集账号</td><td>可选</td><td>留空使用账号管理中的全局默认账号；没有可用默认账号时无法保存</td></tr>
                <tr><td>开始内容链接</td><td>可空，例如 <code>https://t.me/source/100</code></td><td>从该消息开始并包含该消息；留空从尚未处理的最早内容开始</td></tr>
                <tr><td>结束内容链接</td><td>可空，例如 <code>https://t.me/source/200</code></td><td>处理到该消息并包含该消息；留空处理到当前最新</td></tr>
                <tr><td>源频道</td><td>必填，支持 <code>@username</code>、频道链接或可访问的 chat_id</td><td>采集账号必须能够读取该频道</td></tr>
                <tr><td>分发 Bot</td><td>建议明确选择</td><td>留空时按目标绑定关系或第一个启用 Bot 发送</td></tr>
                <tr><td>目标频道</td><td>至少一个，可多选或手动输入</td><td>同一条内容依次分发到所有目标</td></tr>
                <tr><td>内容间隔分钟</td><td>最小 1 分钟</td><td>一条文本或一个相册处理完成后，到下一条内容的等待时间</td></tr>
                <tr><td>目标间隔秒</td><td>最小 1 秒</td><td>同一内容发送多个目标时使用；与全局发送间隔取较大值</td></tr>
                <tr><td>内容处理</td><td>选择过滤、链接、联系方式、替换词和模板</td><td>具体执行顺序见第 7 节</td></tr>
                <tr><td>过滤二维码图片</td><td>按需要开启</td><td>任意媒体检测到二维码时跳过整条内容或整个相册</td></tr>
                <tr><td>克隆完成后自动监听</td><td>需要持续同步新内容时开启</td><td>系统会建立与克隆任务关联的监听任务</td></tr>
                <tr><td>启用任务</td><td>按需要开启</td><td>保存任务配置；实际执行仍需点击“开始”</td></tr>
              </tbody>
            </table>
          </div>
          <h4>执行和状态控制</h4>
          <ul>
            <li>开始：从当前进度继续扫描，按源消息 ID 从小到大处理。</li>
            <li>暂停：当前内容安全处理完成后退出；点击“继续”从现有进度恢复。</li>
            <li>停止：软停止当前 Worker，不会在发送成功但尚未记录进度时强制中断。</li>
            <li>编辑源频道、账号、范围、Bot 或目标频道前，建议先停止正在运行的任务再保存。</li>
            <li>单条媒体超过大小限制会跳过整条内容，避免发送失败阻塞任务。</li>
            <li>某个目标失败不会影响其他目标继续发送；任意目标成功后会写入去重记录。</li>
            <li>过滤掉的消息也会推进进度并写入去重，避免下次继续时反复检查。</li>
            <li>重置只清空任务进度，不等于强制重发；已经存在的去重记录仍会阻止重复发送。</li>
            <li>删除运行中的克隆任务前必须先停止；删除后会同时删除由该克隆任务自动生成的监听任务。</li>
            <li>“克隆任务”页签用于创建和控制任务；“执行任务”页签用于查看最近发送结果。</li>
          </ul>
          <p class="guide-tip">
            克隆去重以“克隆任务 + 源消息或相册”为单位。只要任意目标发送成功，该内容就会记为已处理；
            如果需要单独补发某个失败目标，建议建立单目标任务或使用对应监听任务的一键补齐。
          </p>
        </el-collapse-item>

        <el-collapse-item title="9. 监听任务" name="listener">
          <p>
            监听任务用于实时同步源频道新内容。新增时可以一次填写多个源频道，系统会为每个源频道创建一条独立任务；
            每条任务可以发送到多个目标，并按目标频道分别去重。
          </p>
          <h4>新增和编辑字段</h4>
          <div class="guide-table-wrap">
            <table class="guide-table">
              <thead>
                <tr>
                  <th>字段</th>
                  <th>怎么填写</th>
                  <th>作用和规则</th>
                </tr>
              </thead>
              <tbody>
                <tr><td>复制规则</td><td>新增时可选择已有监听任务</td><td>复制账号、Bot、目标频道和内容规则，再修改当前任务</td></tr>
                <tr><td>任务名称</td><td>必填，例如“上海频道实时监听”</td><td>用于任务、日志和告警识别</td></tr>
                <tr><td>监听账号</td><td>必填</td><td>负责接收源频道更新；建议先用该账号加入或订阅源频道</td></tr>
                <tr><td>分发 Bot</td><td>建议明确选择</td><td>必须在目标频道中并具有发送文本和媒体权限</td></tr>
                <tr><td>源频道</td><td>至少一个，可添加多行</td><td>每个源频道保存为一条独立监听任务</td></tr>
                <tr><td>目标频道</td><td>至少一个，可多选</td><td>同一源内容按目标分别发送和记录结果</td></tr>
                <tr><td>通用过滤词</td><td>选择系统内容规则</td><td>与当前任务补充过滤词合并，命中任意项就过滤整条内容</td></tr>
                <tr><td>任务补充过滤词</td><td>输入关键词后回车</td><td>只影响当前监听任务</td></tr>
                <tr><td>只监听内容</td><td>可空；输入关键词后回车</td><td>留空监听全部；填写后命中任意一项才允许发送</td></tr>
                <tr><td>链接/联系方式/替换词</td><td>选择规则并按需添加替换项</td><td>具体执行顺序见第 7 节</td></tr>
                <tr><td>删除旧联系方式</td><td>按需要开启</td><td>未选择联系方式配置时使用系统默认删除规则</td></tr>
                <tr><td>过滤二维码图片</td><td>按需要开启</td><td>检测到二维码后记录过滤原因并跳过发送</td></tr>
                <tr><td>Head/Body/Footer</td><td>开启后选择规则组，可再指定固定内容</td><td>不指定内容时从已启用内容中随机选择</td></tr>
                <tr><td>启用任务</td><td>需要实时接收时开启</td><td>保存后立即重新加载监听处理器；关闭后停止监听和健康告警</td></tr>
              </tbody>
            </table>
          </div>
          <h4>订阅、去重和修改</h4>
          <ul>
            <li>保存时系统会检查监听账号是否已订阅源频道；可以强制继续，但公开频道未订阅时实时更新可能不稳定。</li>
            <li>监听按“任务 + 目标频道 + 源消息 ID 或相册 ID”去重，一个目标失败不会阻止其他目标。</li>
            <li>修改监听任务并保存后会重新注册监听；新的账号、源频道、目标频道和规则对后续内容生效。</li>
            <li>相册会先短暂缓存并补拉完整媒体，再作为一条内容过滤和发送。</li>
          </ul>
          <h4>一键补齐</h4>
          <ul>
            <li>点击“一键补齐”后，系统先检查可补齐数量，再由用户填写本次补齐条数。</li>
            <li>补齐只处理当前一条监听任务，不会合并其他相同目标频道的监听任务。</li>
            <li>系统按每个目标频道最后一次成功发送的源消息 ID，计算各目标分别缺少哪些内容。</li>
            <li>补齐任务会进入首页排队任务列表，并与克隆、监听发送共用全局限流。</li>
            <li>补齐仍执行过滤词、联系方式、二维码、替换、模板、链接和目标级去重规则。</li>
            <li>“监听任务”页签用于管理任务；“执行任务”页签用于查看状态、源链接、目标链接、过滤原因和失败原因。</li>
          </ul>
          <p class="guide-tip">
            如果监听一直没有发送，按顺序检查：任务是否启用、账号是否已加载并能读取源频道、账号是否订阅源频道、
            执行记录是否显示过滤或去重、分发 Bot 是否在目标频道并拥有发送权限。
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

        <el-collapse-item title="13. 系统告警和云台命令" name="control-bot">
          <p>
            错误和警告统一进入后台“系统告警”页面，Telegram 不再发送告警或每 10 分钟重复提醒。
            运营人员可以按状态、级别、模块和关键词筛选，查看详情后标记已读。
          </p>
          <h4>云台命令（可选）</h4>
          <p>云台 Bot 仅用于在 Telegram 群里执行简单命令，通过 Docker 根目录的 <code>.env</code> 配置。</p>
          <ul>
            <li><code>CONTROL_BOT_TOKEN</code>：云台 Bot Token。</li>
            <li><code>CONTROL_CHAT_ID</code>：云台群 ID。</li>
            <li><code>CONTROL_ADMIN_IDS</code>：允许执行命令的 Telegram 数字用户 ID，多个用英文逗号分隔。</li>
            <li><code>CONTROL_ALERTS_ENABLED=false</code>：线上建议明确关闭旧 Telegram 告警出口。</li>
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

.guide-table-wrap {
  width: 100%;
  overflow-x: auto;
  border: 1px solid var(--el-border-color-lighter);
}

.guide-table {
  width: 100%;
  min-width: 720px;
  border-collapse: collapse;
  table-layout: fixed;
  color: #374151;
  font-size: 13px;
}

.guide-table th,
.guide-table td {
  padding: 9px 12px;
  border-right: 1px solid var(--el-border-color-lighter);
  border-bottom: 1px solid var(--el-border-color-lighter);
  text-align: left;
  vertical-align: top;
  line-height: 1.6;
  overflow-wrap: anywhere;
}

.guide-table th {
  background: var(--el-fill-color-light);
  color: var(--el-text-color-secondary);
  font-weight: 600;
}

.guide-table th:first-child,
.guide-table td:first-child {
  width: 148px;
}

.guide-table th:last-child,
.guide-table td:last-child {
  border-right: 0;
}

.guide-table tbody tr:last-child td {
  border-bottom: 0;
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

@media (max-width: 768px) {
  .guide-subtitle {
    line-height: 1.6;
  }

  .guide-table {
    min-width: 680px;
  }

  .guide-table th,
  .guide-table td {
    padding: 8px 10px;
  }
}
</style>
