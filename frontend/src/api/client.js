import axios from 'axios'

const api = axios.create({
  baseURL: '/api/v1',
  headers: { 'Content-Type': 'application/json' },
})

export async function getStats() {
  const { data } = await api.get('/challenge/stats')
  return data
}

export async function getJob() {
  const { data } = await api.get('/challenge/job')
  return data
}

export async function getCandidates(skip = 0, limit = 50, useSample = true) {
  const { data } = await api.get('/challenge/candidates', {
    params: { skip, limit, use_sample: useSample },
  })
  return data
}

export async function runRanking(topN = 50, useSample = true) {
  const { data } = await api.post('/challenge/rank', {
    use_sample: useSample,
    top_n: topN,
  })
  return data
}

export async function getRankings(limit = 100) {
  const { data } = await api.get('/challenge/rankings', { params: { limit } })
  return data
}

export async function getAuditReport() {
  const { data } = await api.get('/challenge/audit')
  return data
}

export function getExportCsvUrl() {
  return '/api/v1/challenge/export-csv'
}

export default api
