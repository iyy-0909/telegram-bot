export const aiContentTypes = [
  { value: "product", label: "商品服务" },
  { value: "promotion", label: "优惠活动" },
  { value: "notice", label: "通知公告" },
  { value: "tutorial", label: "教程知识" },
  { value: "story", label: "故事观点" },
  { value: "general", label: "混合或未知" },
]

export function contentTypeLabel(value) {
  return aiContentTypes.find((item) => item.value === value)?.label || "仅固定选择"
}
