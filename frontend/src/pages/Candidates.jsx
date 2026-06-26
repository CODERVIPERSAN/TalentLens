import { useEffect, useState } from 'react'
import { Plus, Search, Trash2 } from 'lucide-react'
import { candidatesApi } from '../api/client'

const emptyForm = {
  name: '',
  email: '',
  skills: '',
  experience_years: '',
  resume_text: '',
}

export default function Candidates() {
  const [candidates, setCandidates] = useState([])
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
      setCandidates(await candidatesApi.list())
    } catch (e) {
      setError('Failed to load candidates. Is the backend running?')
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
      await candidatesApi.create({
        name: form.name,
        email: form.email,
        skills: form.skills
          .split(',')
          .map((s) => s.trim())
          .filter(Boolean),
        experience_years: form.experience_years ? Number(form.experience_years) : 0,
        resume_text: form.resume_text || null,
      })
      setForm(emptyForm)
      setShowForm(false)
      await load()
    } catch (e) {
      setError(e.response?.data?.detail || 'Failed to create candidate')
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (id) => {
    try {
      await candidatesApi.remove(id)
      await load()
    } catch (e) {
      setError('Failed to delete candidate')
    }
  }

  const filtered = candidates.filter(
    (c) =>
      c.name.toLowerCase().includes(query.toLowerCase()) ||
      c.email.toLowerCase().includes(query.toLowerCase())
  )

  return (
    <div>
      <div className="flex justify-between items-center mb-8">
        <h2 className="text-3xl font-bold text-gray-900">Candidates</h2>
        <button
          onClick={() => setShowForm((v) => !v)}
          className="flex items-center px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700"
        >
          <Plus className="w-4 h-4 mr-2" />
          Add Candidate
        </button>
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-50 text-red-700 rounded-lg text-sm">{error}</div>
      )}

      {showForm && (
        <form onSubmit={handleSubmit} className="bg-white rounded-lg shadow p-6 mb-6 grid grid-cols-1 md:grid-cols-2 gap-4">
          <input required placeholder="Full name" value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            className="border rounded-lg px-3 py-2" />
          <input required type="email" placeholder="Email" value={form.email}
            onChange={(e) => setForm({ ...form, email: e.target.value })}
            className="border rounded-lg px-3 py-2" />
          <input placeholder="Skills (comma separated)" value={form.skills}
            onChange={(e) => setForm({ ...form, skills: e.target.value })}
            className="border rounded-lg px-3 py-2" />
          <input type="number" step="0.5" min="0" placeholder="Years of experience"
            value={form.experience_years}
            onChange={(e) => setForm({ ...form, experience_years: e.target.value })}
            className="border rounded-lg px-3 py-2" />
          <textarea placeholder="Resume text (optional)" value={form.resume_text}
            onChange={(e) => setForm({ ...form, resume_text: e.target.value })}
            className="border rounded-lg px-3 py-2 md:col-span-2" rows={3} />
          <div className="md:col-span-2 flex gap-2">
            <button type="submit" disabled={saving}
              className="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50">
              {saving ? 'Saving...' : 'Save Candidate'}
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
              placeholder="Search candidates..."
              className="pl-10 pr-4 py-2 w-full border rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>
        </div>

        {loading ? (
          <div className="p-6 text-gray-500">Loading...</div>
        ) : filtered.length === 0 ? (
          <div className="p-6 text-gray-500">No candidates yet. Add your first one.</div>
        ) : (
          <table className="w-full">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Name</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Email</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Skills</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Experience</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {filtered.map((candidate) => (
                <tr key={candidate.id} className="hover:bg-gray-50">
                  <td className="px-6 py-4 whitespace-nowrap font-medium text-gray-900">{candidate.name}</td>
                  <td className="px-6 py-4 whitespace-nowrap text-gray-500">{candidate.email}</td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="flex flex-wrap gap-1">
                      {(candidate.skills || []).map((skill) => (
                        <span key={skill} className="px-2 py-1 text-xs bg-indigo-100 text-indigo-700 rounded">
                          {skill}
                        </span>
                      ))}
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-gray-500">{candidate.experience_years} years</td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <button onClick={() => handleDelete(candidate.id)} className="text-gray-400 hover:text-red-600">
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
