import { useEffect, useState } from 'react'
import { Plus, Search, Trash2 } from 'lucide-react'
import { jobsApi } from '../api/client'

const emptyForm = {
  title: '',
  description: '',
  requirements: '',
  skills: '',
  min_experience_years: '',
  location: '',
  status: 'active',
}

export default function Jobs() {
  const [jobs, setJobs] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [query, setQuery] = useState('')
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState(emptyForm)
  const [saving, setSaving] = useState(false)

  const load = async () => {
    setLoading(true)
    setError('')
    try {
      setJobs(await jobsApi.list())
    } catch (e) {
      setError('Failed to load jobs. Is the backend running?')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  const handleSubmit = async (e) => {
    e.preventDefault()
    setSaving(true)
    setError('')
    try {
      await jobsApi.create({
        title: form.title,
        description: form.description,
        requirements: form.requirements.split(',').map((s) => s.trim()).filter(Boolean),
        skills: form.skills.split(',').map((s) => s.trim()).filter(Boolean),
        min_experience_years: form.min_experience_years ? Number(form.min_experience_years) : 0,
        location: form.location || null,
        status: form.status,
      })
      setForm(emptyForm)
      setShowForm(false)
      await load()
    } catch (e) {
      setError(e.response?.data?.detail || 'Failed to create job')
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (id) => {
    try {
      await jobsApi.remove(id)
      await load()
    } catch (e) {
      setError('Failed to delete job')
    }
  }

  const getStatusColor = (status) => {
    switch (status) {
      case 'active': return 'bg-green-100 text-green-700'
      case 'draft': return 'bg-gray-100 text-gray-700'
      case 'closed': return 'bg-red-100 text-red-700'
      default: return 'bg-gray-100 text-gray-700'
    }
  }

  const filtered = jobs.filter((j) => j.title.toLowerCase().includes(query.toLowerCase()))

  return (
    <div>
      <div className="flex justify-between items-center mb-8">
        <h2 className="text-3xl font-bold text-gray-900">Jobs</h2>
        <button
          onClick={() => setShowForm((v) => !v)}
          className="flex items-center px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700"
        >
          <Plus className="w-4 h-4 mr-2" />
          Create Job
        </button>
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-50 text-red-700 rounded-lg text-sm">{error}</div>
      )}

      {showForm && (
        <form onSubmit={handleSubmit} className="bg-white rounded-lg shadow p-6 mb-6 grid grid-cols-1 md:grid-cols-2 gap-4">
          <input required placeholder="Job title" value={form.title}
            onChange={(e) => setForm({ ...form, title: e.target.value })}
            className="border rounded-lg px-3 py-2" />
          <input placeholder="Location" value={form.location}
            onChange={(e) => setForm({ ...form, location: e.target.value })}
            className="border rounded-lg px-3 py-2" />
          <textarea required placeholder="Description" value={form.description}
            onChange={(e) => setForm({ ...form, description: e.target.value })}
            className="border rounded-lg px-3 py-2 md:col-span-2" rows={3} />
          <input placeholder="Requirements (comma separated)" value={form.requirements}
            onChange={(e) => setForm({ ...form, requirements: e.target.value })}
            className="border rounded-lg px-3 py-2" />
          <input placeholder="Skills (comma separated)" value={form.skills}
            onChange={(e) => setForm({ ...form, skills: e.target.value })}
            className="border rounded-lg px-3 py-2" />
          <input type="number" step="0.5" min="0" placeholder="Min years of experience"
            value={form.min_experience_years}
            onChange={(e) => setForm({ ...form, min_experience_years: e.target.value })}
            className="border rounded-lg px-3 py-2" />
          <select value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value })}
            className="border rounded-lg px-3 py-2">
            <option value="draft">Draft</option>
            <option value="active">Active</option>
            <option value="closed">Closed</option>
          </select>
          <div className="md:col-span-2 flex gap-2">
            <button type="submit" disabled={saving}
              className="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50">
              {saving ? 'Saving...' : 'Save Job'}
            </button>
            <button type="button" onClick={() => { setShowForm(false); setForm(emptyForm) }}
              className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200">
              Cancel
            </button>
          </div>
        </form>
      )}

      <div className="bg-white rounded-lg shadow">
        <div className="p-4 border-b">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-5 h-5" />
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search jobs..."
              className="pl-10 pr-4 py-2 w-full border rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>
        </div>

        {loading ? (
          <div className="p-6 text-gray-500">Loading...</div>
        ) : filtered.length === 0 ? (
          <div className="p-6 text-gray-500">No jobs yet. Create your first one.</div>
        ) : (
          <table className="w-full">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Title</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Location</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Min Exp.</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {filtered.map((job) => (
                <tr key={job.id} className="hover:bg-gray-50">
                  <td className="px-6 py-4 whitespace-nowrap font-medium text-gray-900">{job.title}</td>
                  <td className="px-6 py-4 whitespace-nowrap text-gray-500">{job.location || '—'}</td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <span className={`px-2 py-1 text-xs font-medium rounded ${getStatusColor(job.status)}`}>
                      {job.status}
                    </span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-gray-500">{job.min_experience_years} years</td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <button onClick={() => handleDelete(job.id)} className="text-gray-400 hover:text-red-600">
                      <Trash2 className="w-5 h-5" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
