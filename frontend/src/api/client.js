import axios from 'axios'

// Vite proxies /api -> http://localhost:8000 (see vite.config.js)
const client = axios.create({
  baseURL: '/api/v1',
  headers: { 'Content-Type': 'application/json' },
})

// Attach the auth token if one has been stored.
client.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

export const candidatesApi = {
  list: () => client.get('/candidates/').then((r) => r.data),
  create: (data) => client.post('/candidates/', data).then((r) => r.data),
  remove: (id) => client.delete(`/candidates/${id}`).then((r) => r.data),
}

export const jobsApi = {
  list: () => client.get('/jobs/').then((r) => r.data),
  create: (data) => client.post('/jobs/', data).then((r) => r.data),
  remove: (id) => client.delete(`/jobs/${id}`).then((r) => r.data),
}

export const matchesApi = {
  findBest: (jobId, limit = 10) =>
    client.get(`/matches/job/${jobId}/find-best`, { params: { limit } }).then((r) => r.data),
}

export default client
