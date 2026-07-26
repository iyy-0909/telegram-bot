export const CONTENT_RULE_SECTIONS = [
  {
    key: "contact",
    title: "联系方式配置",
    subtitle: "删除手机号、链接、用户名和命中关键词的内容",
    types: ["contact"],
    placement: "primary",
    compact: true,
  },
  {
    key: "filter",
    title: "关键词过滤配置",
    subtitle: "管理任务可选择的通用过滤关键词",
    types: ["filter"],
    placement: "primary",
    compact: true,
  },
  {
    key: "content",
    title: "内容模板",
    subtitle: "分别维护头部、正文和底部内容",
    types: ["head", "body", "footer"],
    placement: "rules",
  },
  {
    key: "link",
    title: "链接配置",
    subtitle: "配置不同链接类型的保留、替换和删除动作",
    types: ["link"],
    placement: "rules",
  },
]

export const CONTENT_RULE_TYPE_META = {
  head: { label: "头部", tagType: "success" },
  body: { label: "正文", tagType: "warning" },
  footer: { label: "底部", tagType: "info" },
  filter: { label: "过滤", tagType: "danger" },
  link: { label: "链接", tagType: "primary" },
  contact: { label: "联系方式", tagType: "warning" },
}

export function knownContentRuleTypes() {
  return new Set(CONTENT_RULE_SECTIONS.flatMap((section) => section.types))
}
