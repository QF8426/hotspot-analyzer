export const PLATFORM_ORDER = ['weibo', 'douyin', 'bilibili']

export const PLATFORM_META = {
  weibo: {
    key: 'weibo',
    label: '微博',
    glyph: '微',
    accent: 'weibo',
    heatLabel: '热度',
    description: '微博热搜与实时话题',
    dailyTitle: '微博今日榜单'
  },
  douyin: {
    key: 'douyin',
    label: '抖音',
    glyph: '抖',
    accent: 'douyin',
    heatLabel: '热度',
    description: '抖音热视频与评论热议',
    dailyTitle: '抖音今日榜单'
  },
  bilibili: {
    key: 'bilibili',
    label: 'B站',
    glyph: 'B',
    accent: 'bilibili',
    heatLabel: '排序值',
    description: 'B站热搜词条与视频讨论',
    dailyTitle: 'B站今日榜单'
  }
}

export function getPlatformMeta(platform) {
  return PLATFORM_META[platform] || {
    key: platform || 'unknown',
    label: platform || '未知平台',
    glyph: '平',
    accent: 'generic',
    heatLabel: '热度',
    description: '平台热点',
    dailyTitle: '平台榜单'
  }
}

export function getPlatformLabel(platform) {
  return getPlatformMeta(platform).label
}

export function getPlatformHeatLabel(platform) {
  return getPlatformMeta(platform).heatLabel
}

export function cleanTitle(title) {
  return String(title || '')
    .replace(/^#+|#+$/g, '')
    .trim()
}

export function normalizeTag(tag, title = '') {
  if (!tag) return ''

  let value = Array.isArray(tag) ? tag.join(' / ') : String(tag)
  value = value
    .replace(/^\[/, '')
    .replace(/\]$/, '')
    .replace(/["']/g, '')
    .trim()

  if (!value) return ''
  if (cleanTitle(value) === cleanTitle(title)) return ''
  return value.length > 14 ? '' : value
}

export function getHotspotId(item, fallback = '') {
  return item?.id ?? item?.hotspotId ?? item?.hotspot_id ?? fallback
}

export function getHotValue(item) {
  return item?.maxHotValue ?? item?.max_hot_value ?? item?.hotValue ?? item?.hot_value ?? null
}

export function getHotspotTime(item) {
  return item?.crawlTime ?? item?.crawl_time ?? item?.createdAt ?? item?.created_at ?? ''
}

export function formatHotValue(value, platform = '') {
  if (value === null || value === undefined || value === '') return '暂无'

  const num = Number(value)
  if (Number.isNaN(num)) return String(value)

  if (platform === 'bilibili') {
    return new Intl.NumberFormat('zh-CN').format(num)
  }

  if (Math.abs(num) >= 100000000) {
    return `${(num / 100000000).toFixed(1).replace(/\.0$/, '')}亿`
  }

  if (Math.abs(num) >= 10000) {
    return `${(num / 10000).toFixed(1).replace(/\.0$/, '')}万`
  }

  return new Intl.NumberFormat('zh-CN').format(num)
}

export function formatDate(value) {
  if (!value) return '暂无日期'

  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return String(value).slice(0, 10)
  }

  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(
    date.getDate()
  ).padStart(2, '0')}`
}

export function formatDateTime(value) {
  if (!value) return '暂无时间'

  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return String(value).replace('T', ' ').slice(0, 16)
  }

  return `${formatDate(date)} ${String(date.getHours()).padStart(2, '0')}:${String(
    date.getMinutes()
  ).padStart(2, '0')}`
}

export function getToday() {
  return formatDate(new Date())
}

export function getYesterday() {
  const date = new Date()
  date.setDate(date.getDate() - 1)
  return formatDate(date)
}

export function parsePlatformList(value) {
  if (Array.isArray(value)) return value.filter(Boolean)
  return String(value || '')
    .split(',')
    .map(item => item.trim())
    .filter(Boolean)
}

export function getTopicPlatforms(topic) {
  if (topic?.relatedPlatforms || topic?.related_platforms) {
    return parsePlatformList(topic.relatedPlatforms || topic.related_platforms)
  }

  const seen = new Set()
  ;(topic?.hotspots || []).forEach(item => {
    if (item?.platform) seen.add(item.platform)
  })
  return Array.from(seen)
}

export function getTopicPrimaryHotspot(topic) {
  return (topic?.hotspots || []).find(item => item.primary || item.isPrimary) || topic?.hotspots?.[0] || null
}

export function getTopicTotalHotValue(topic) {
  const apiValue = Number(topic?.totalHotValue ?? topic?.total_hot_value ?? 0)
  if (apiValue > 0) return apiValue

  return (topic?.hotspots || []).reduce((sum, item) => sum + (Number(getHotValue(item)) || 0), 0)
}

export function buildSummaryText(text, fallback, max = 120) {
  const normalized = String(text || '')
    .replace(/\s+/g, ' ')
    .trim()

  if (!normalized) return fallback
  if (normalized.length <= max) return normalized
  return `${normalized.slice(0, max)}...`
}

export function formatDurationMinutes(value) {
  const num = Number(value || 0)
  if (!num) return '暂无'

  if (num >= 60) {
    const hours = Math.floor(num / 60)
    const minutes = num % 60
    if (!minutes) return `${hours}小时`
    return `${hours}小时${minutes}分钟`
  }

  return `${num}分钟`
}

export function sortHistoryList(list) {
  return [...list].sort((left, right) => {
    const leftHot = Number(left?.maxHotValue ?? 0)
    const rightHot = Number(right?.maxHotValue ?? 0)
    if (leftHot !== rightHot) return rightHot - leftHot

    const leftRank = Number(left?.bestRankNum ?? 999999)
    const rightRank = Number(right?.bestRankNum ?? 999999)
    if (leftRank !== rightRank) return leftRank - rightRank

    return String(right?.title || '').localeCompare(String(left?.title || ''), 'zh-CN')
  })
}
