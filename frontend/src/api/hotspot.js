import request from './request'

export function getHotspotsByPlatform(platform) {
  return request.get(`/api/hotspots/platform/${platform}`)
}

export function getDailyTop(platform, limit) {
  return request.get(`/api/hotspots/platform/${platform}/daily-top`, {
    params: { limit }
  })
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