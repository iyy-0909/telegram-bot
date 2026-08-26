<template>
  <div class="guide-page">
    <section class="hero">
      <div class="hero-copy">
        <el-tag effect="plain">从准备到运行</el-tag>
        <h1>使用教程</h1>
        <p>采集账号读取 Telegram 源频道，内容经过过滤、替换、AI 改写和模板处理后，由官方 Bot 分发到目标频道。</p>
        <div class="actions"><el-button type="primary" @click="jump('clone')">创建克隆任务</el-button><el-button @click="jump('listener')">配置实时监听</el-button></div>
      </div>
      <img v-if="heroImage" :src="heroImage" alt="采集账号读取源频道，经内容处理后由 Bot 分发到目标频道的流程示意" />
      <div v-else class="flow-image"><span>采集账号</span><b>→</b><span>内容处理</span><b>→</b><span>分发 Bot</span><b>→</b><span>目标频道</span></div>
    </section>

    <el-alert type="warning" show-icon :closable="false" title="克隆任务和监听任务都必须具备：可用采集账号 + 可用分发 Bot + Bot 拥有目标频道发帖权限" />

    <section class="block">
      <Heading eyebrow="开始前" title="先准备 3 项基础资产" text="缺少任意一项都不要急着建任务，先按顺序检测通过。" />
      <div class="prep-grid">
        <article v-for="item in preparations" :key="item.no" class="prep-card">
          <i>{{ item.no }}</i><div><h3>{{ item.title }}</h3><p>{{ item.desc }}</p><strong>配置位置：{{ item.location }}</strong></div>
          <el-button link type="primary" @click="navigate(item.menu)">去配置 →</el-button>
        </article>
      </div>
      <div class="checks"><b>上线前检查</b><span>账号状态正常且 session 有效</span><span>Bot Token 测试成功</span><span>Bot 已加入目标频道并可发帖</span></div>
    </section>

    <section id="clone" class="block">
      <Heading eyebrow="功能 1" title="克隆任务：批量同步历史内容"><el-button type="primary" @click="navigate('clone')">打开克隆任务</el-button></Heading>
      <p class="lead">适合搬运源频道已经发布的历史消息。可用开始/结束消息链接限定范围，并按原顺序发送到一个或多个目标频道。</p>
      <LocationMap mode="clone" />
      <ol class="steps">
        <li><b>选择采集账号：</b>必须能打开源频道；留空时只会使用“账号管理”里的全局默认账号。</li>
        <li><b>填写源频道与历史范围：</b>源频道可填 @username 或 t.me 链接；开始/结束内容链接用于限定消息区间。</li>
        <li><b>选择分发 Bot 和目标频道：</b>目标频道建议先录入“频道管理”，并确认 Bot 有发帖权限。</li>
        <li><b>按需配置内容处理：</b>不加工就保持关闭；需要清洗、改写或加推广文案时按下节配置。</li>
        <li><b>保存并启动：</b>先在“执行任务”查看少量发送结果，确认无误后再扩大范围。</li>
      </ol>
      <el-alert type="success" show-icon :closable="false" title="需要克隆完成后继续接收新消息：开启“克隆完成后自动监听”，系统会建立关联监听任务。" />
    </section>

    <section class="block">
      <Heading eyebrow="内容加工" title="内容处理在哪里配置、分别有什么用" />
      <div class="path"><b>配置入口</b><span>克隆任务 / 监听任务 → 新增或编辑 → 内容处理、AI 改写、内容模板规则</span></div>
      <div class="process-grid">
        <article v-for="item in processing" :key="item.title"><h3>{{ item.title }}</h3><p>{{ item.use }}</p><div><b>怎么配：</b>{{ item.how }}</div><small>{{ item.note }}</small></article>
      </div>
      <div class="sequence"><b>执行顺序</b><span>条件筛选</span><i>→</i><span>过滤清洗</span><i>→</i><span>替换</span><i>→</i><span>AI 改写</span><i>→</i><span>Head / Body / Footer</span></div>
      <div class="actions"><el-button @click="navigate('settings')">配置内容模板与全局规则</el-button><el-button @click="navigate('ai-settings')">配置 AI 密钥与提示词</el-button></div>
    </section>

    <section id="listener" class="block">
      <Heading eyebrow="功能 2" title="监听任务：持续同步新内容"><el-button type="primary" @click="navigate('rules')">打开监听任务</el-button></Heading>
      <p class="lead">监听任务只处理创建并启用之后出现的新消息。它必须搭载采集账号读取内容，并搭载分发 Bot 把内容发出去。</p>
      <LocationMap mode="listener" />
      <div class="deps"><div><b>① 采集账号</b><span>能访问源频道，session 有效</span></div><strong>＋</strong><div><b>② 分发 Bot</b><span>在目标频道且可发帖</span></div><strong>＋</strong><div><b>③ 目标频道</b><span>接收监听到的新内容</span></div></div>
      <ol class="steps">
        <li><b>优先从克隆任务开启自动监听：</b>做过历史克隆时，账号、Bot、频道和内容规则会保持一致。</li>
        <li><b>也可单独新增：</b>选择监听账号、分发 Bot、源频道和目标频道；可复制现有任务规则。</li>
        <li><b>精准监听：</b>“只监听内容”填写多个关键词时，命中任意一个才继续；留空表示监听全部。</li>
        <li><b>保持启用：</b>修改账号、源频道或规则后会重新注册，新设置只对后续内容生效。</li>
        <li><b>漏发排查：</b>先查看“执行任务”的过滤或失败原因，需要补发时使用当前任务的“一键补齐”。</li>
      </ol>
      <el-alert type="warning" show-icon :closable="false" title="监听任务不会自动补齐创建前的全部历史内容。需要历史内容时先建克隆任务，再开启自动监听。" />
    </section>

    <section class="block troubleshoot"><Heading eyebrow="排查" title="任务不工作时先检查" />
      <div><i>1</i>采集账号是否启用、session 是否有效、是否能读取源频道</div><div><i>2</i>分发 Bot Token 是否可用、是否仍在目标频道、是否有发帖权限</div>
      <div><i>3</i>是否被“只监听内容”、过滤词、二维码过滤或 AI 失败策略跳过</div><div><i>4</i>到任务页“执行任务”查看源链接、目标链接、过滤原因和失败原因</div>
    </section>
  </div>
</template>

<script setup>
import { defineComponent, h } from "vue"
import heroImage from "../assets/guide/system-flow.png"
const emit = defineEmits(["navigate"])
const preparations = [
  { no: 1, title: "采集账号", desc: "Telegram 用户号，负责读取源频道历史消息和实时新消息。", location: "账号管理 → 登录账号", menu: "accounts" },
  { no: 2, title: "分发 Bot", desc: "官方 Bot API 账号，负责把处理后的内容发送到目标频道。", location: "Bot 管理 → 新增 Bot → 测试", menu: "bots" },
  { no: 3, title: "目标频道", desc: "接收内容的频道；把分发 Bot 加为管理员并授予发帖权限。", location: "频道管理 → 我的频道 → 新增 / 检测", menu: "my-channels" },
]
const processing = [
  { title: "过滤与清洗", use: "阻止不需要的内容，或删除链接、联系方式、二维码图片。", how: "选择通用过滤规则，再填当前任务专用过滤词；监听任务还可设置“只监听内容”。", note: "命中过滤会整条跳过；清洗后没有正文也会跳过。" },
  { title: "替换词", use: "把原文中的品牌、联系方式、链接或固定文案换成自己的内容。", how: "在任务“替换词”中填写查找内容和替换内容；通用规则可先在系统设置维护。", note: "适合统一替换品牌名、联系方式和落地链接。" },
  { title: "AI 改写", use: "清洗正文后再重写，可控制比例、模型、最大字数和失败策略。", how: "先到“AI 配置”保存 Grok / DeepSeek 密钥和提示词，再回任务开启并选择提示词。", note: "先少量测试；“回退原文”更稳妥，“跳过”则失败时不发送。" },
  { title: "内容模板规则", use: "给每条消息固定或随机加入头部、正文补充和底部文案。", how: "先到“系统设置 → 内容模板”创建 head、body、footer 规则，再回任务开启对应段。", note: "只选规则会随机取一条；再选具体内容则固定使用该条。" },
]
const Heading = defineComponent({ props: { eyebrow:String,title:String,text:String }, setup(p,{slots}) { return()=>h("div",{class:"heading"},[h("div",[h("span",p.eyebrow),h("h2",p.title)]),p.text?h("p",p.text):slots.default?.()]) } })
const pins = { clone:[["1","基础信息","账号与历史范围"],["2","频道与分发","源频道、Bot、目标频道"],["3","内容处理与 AI","过滤、替换、改写、模板"],["4","任务开关","启用与自动监听"]], listener:[["1","基础信息","监听账号与分发 Bot"],["2","频道与分发","源频道、目标频道"],["3","内容处理与 AI","只监听内容与加工规则"],["4","任务开关","保存后保持启用"]] }
const LocationMap = defineComponent({ props:{mode:String},setup(p){return()=>h("div",{class:"location-map"},[h("aside",[h("b","后台菜单"),h("span",{class:"active"},p.mode==="clone"?"克隆任务":"监听任务")]),h("main",[h("header",[h("b",p.mode==="clone"?"克隆任务":"监听任务"),h("em","＋ 新增任务")]),h("section",pins[p.mode].map(x=>h("div",{class:"pin"},[h("i",x[0]),h("div",[h("b",x[1]),h("small",x[2])])])) )])])}})
function navigate(menu){emit("navigate",menu)}
function jump(id){document.getElementById(id)?.scrollIntoView({behavior:"smooth",block:"start"})}
</script>

<style scoped>
.guide-page{display:flex;flex-direction:column;gap:16px;max-width:1240px;margin:auto;color:var(--el-text-color-primary)}.hero,.block{background:#fff;border:1px solid var(--el-border-color-lighter);border-radius:10px}.hero{display:grid;grid-template-columns:.9fr 1.1fr;min-height:300px;overflow:hidden}.hero-copy{padding:34px;align-self:center}.hero h1{margin:12px 0 8px;font-size:32px}.hero p,.lead{line-height:1.8;color:var(--el-text-color-regular)}.hero img{width:100%;height:300px;object-fit:cover}.flow-image{display:flex;align-items:center;justify-content:center;gap:10px;background:var(--el-fill-color-light)}.flow-image span,.sequence span{padding:10px;background:#fff;border:1px solid var(--el-border-color);border-radius:6px}.actions{display:flex;gap:10px;margin-top:18px}.block{padding:24px}.heading{display:flex;align-items:flex-end;justify-content:space-between;gap:14px;margin-bottom:18px}.heading span{font-size:12px;font-weight:700;color:var(--el-color-primary)}.heading h2{margin:4px 0 0;font-size:22px}.heading p{margin:0;color:var(--el-text-color-secondary)}
.prep-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}.prep-card{display:grid;grid-template-columns:auto 1fr;gap:12px;padding:16px;border:1px solid var(--el-border-color);border-radius:8px}.prep-card i,.troubleshoot i{display:grid;place-items:center;width:28px;height:28px;border-radius:50%;background:var(--el-color-primary);color:#fff;font-style:normal;font-weight:700}.prep-card h3,.process-grid h3{margin:0 0 6px}.prep-card p,.process-grid p{margin:0 0 8px;line-height:1.6;color:var(--el-text-color-regular)}.prep-card strong{font-size:12px;color:var(--el-color-primary)}.prep-card .el-button{grid-column:2;justify-self:start}.checks{display:flex;flex-wrap:wrap;gap:12px 20px;margin-top:14px;padding:12px;background:var(--el-fill-color-light);font-size:13px}.checks span:before{content:'✓';margin-right:6px;color:var(--el-color-success);font-weight:700}
.location-map{display:grid;grid-template-columns:170px 1fr;min-height:260px;margin:18px 0;border:1px solid var(--el-border-color);border-radius:8px;overflow:hidden}.location-map aside{padding:18px;background:#111827;color:#fff}.location-map aside b,.location-map aside span{display:block}.location-map aside span{margin-top:20px;padding:10px;background:var(--el-color-primary);border-radius:5px}.location-map main{padding:18px;background:var(--el-fill-color-lighter)}.location-map header{display:flex;justify-content:space-between}.location-map em{padding:7px 11px;border-radius:5px;background:var(--el-color-primary);color:#fff;font-style:normal}.location-map section{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:14px}.pin{display:flex;gap:10px;min-height:68px;padding:13px;background:#fff;border:1px solid var(--el-border-color);border-radius:7px}.pin>i{display:grid;place-items:center;flex:0 0 26px;height:26px;border-radius:50%;background:var(--el-color-danger);color:#fff;font-style:normal}.pin b,.pin small{display:block}.pin small{margin-top:5px;color:var(--el-text-color-secondary)}
.steps{display:grid;gap:10px;padding-left:22px;line-height:1.7}.path{display:flex;gap:16px;margin-bottom:14px;padding:12px 14px;background:var(--el-color-primary-light-9);border-left:3px solid var(--el-color-primary)}.process-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}.process-grid article{padding:16px;border:1px solid var(--el-border-color);border-radius:8px}.process-grid div{line-height:1.65}.process-grid small{display:block;margin-top:8px;color:var(--el-text-color-secondary)}.sequence{display:flex;align-items:center;flex-wrap:wrap;gap:9px;margin-top:14px;padding:12px;background:var(--el-fill-color-light)}.sequence i{color:var(--el-text-color-secondary)}.deps{display:flex;align-items:stretch;gap:12px;margin:18px 0}.deps div{flex:1;padding:16px;border:1px solid var(--el-color-primary-light-5);border-radius:8px;background:var(--el-color-primary-light-9)}.deps b,.deps span{display:block}.deps span{margin-top:6px;color:var(--el-text-color-regular)}.deps>strong{align-self:center;font-size:24px}.troubleshoot{display:grid;grid-template-columns:1fr 1fr;gap:10px}.troubleshoot .heading{grid-column:1/-1}.troubleshoot>div:not(.heading){display:flex;align-items:center;gap:10px;padding:12px;background:var(--el-fill-color-light);line-height:1.5}
@media(max-width:900px){.hero{grid-template-columns:1fr}.hero img{height:210px;order:-1}.hero-copy{padding:22px}.block{padding:18px}.heading{align-items:flex-start;flex-direction:column}.prep-grid,.process-grid{grid-template-columns:1fr}.location-map{grid-template-columns:1fr}.location-map aside{display:none}.deps{flex-direction:column}.deps>strong{align-self:center;transform:rotate(90deg)}.troubleshoot{grid-template-columns:1fr}.path{flex-direction:column;gap:5px}}
@media(max-width:520px){.hero h1{font-size:26px}.actions{align-items:stretch;flex-direction:column}.location-map section{grid-template-columns:1fr}.checks{flex-direction:column}.heading :deep(.el-button){width:100%}.flow-image{flex-wrap:wrap;padding:20px}}
</style>
