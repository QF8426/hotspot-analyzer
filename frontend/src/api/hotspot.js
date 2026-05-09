import request from './request'

export function getHotspotsByPlatform(platform) {
  return request.get(`/api/hotspots/platform/${platform}`)
}

export function getDailyTop(platform, limit) {
  const params = {}

  if (limit !== undefined && limit !== null && Number(limit) > 0) {
    params.limit = limit
  }

  return request.get(`/api/hotspots/platform/${platform}/daily-top`, { params })
}

export function getHistoryHotspots(platform, date) {
  return request.get(`/api/hotspots/platform/${platform}/history`, {
    params: { date }
  })
}

export function getPlatformStats() {
  return request.get('/api/stats/platform')
}

export function searchHotspots(keyword) {
  return request.get('/api/hotspots/search', {
    params: { keyword }
  })
}

export function getHotspotDetail(id) {
  return request.get(`/api/hotspots/${id}`)
}

export function getTrend(id) {
  return request.get(`/api/hotspots/${id}/trend`)
}

export function getCrossPlatformTopics(params = {}) {
  return request.get('/api/cross-platform/topics', { params })
}

export function getCrossPlatformTopicDetail(id) {
  return request.get(`/api/cross-platform/topics/${id}`)
}
