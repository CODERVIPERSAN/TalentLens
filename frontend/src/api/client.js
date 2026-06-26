import axios from 'axios'

const api = axios.create({
  baseURL: '/api/v1',
  headers: { 'Content-Type': 'application/json' },
})

export async function getStats() {
  const { data } = await api.get('/challenge/stats')
  return data
}

export async function getCandidates(skip = 0, limit = 50) {
  const { data } = await api.get('/challenge/candidates', { params: { skip, limit } })
  return data
}

export async function runRanking(topN = 50) {
  const { data } = await api.post('/challenge/rank', { use_sample: true, top_n: topN })
  return data
}

export async function getRankings(limit = 50) {
  const { data } = await api.get('/challenge/rankings', { params: { limit } })
  return data
}

export default api
