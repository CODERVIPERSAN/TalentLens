import { useEffect, useState } from 'react'
import { Search, Loader2 } from 'lucide-react'
import { getCandidates } from '../api/client'

export default function Candidates() {
  const [data, setData] = useState({ candidates: [], total: 0, pool: 'sample' })
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [error, setError] = useState(null)

  useEffect(() => {
    getCandidates(0, 50, true)
      .then(setData)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }, [])

  const filtered = data.candidates.filter((c) => {
    const q = search.toLowerCase()
    return (
      c.name?.toLowerCase().includes(q) ||
      c.title?.toLowerCase().includes(q) ||
      c.candidate_id?.toLowerCase().includes(q) ||
      c.skills?.some((s) => s.toLowerCase().includes(q))
    )
  })

  return (
    <div>
      <div className="flex justify-between items-center mb-8">
        <div>
          <h2 className="text-3xl font-bold text-gray-900">Candidates</h2>
          <p className="text-gray-500 text-sm mt-1">
            {data.total} candidates from PUB challenge ({data.pool} pool)
          </p>
        </div>
      </div>

      {error && (
        <div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">{error}</div>
      )}

      <div className="bg-white rounded-lg shadow">
        <div className="p-4 border-b">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-5 h-5" />
            <input
              type="text"
              placeholder="Search by name, title, skills, ID..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-10 pr-4 py-2 w-full border rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>
        </div>

        {loading ? (
          <div className="p-8 flex justify-center text-gray-500">
            <Loader2 className="w-6 h-6 animate-spin mr-2" />
            Loading candidates from challenge JSON...
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">ID</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Name</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Title</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Company</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Location</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Skills</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Exp</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {filtered.map((candidate) => (
                  <tr key={candidate.candidate_id} className="hover:bg-gray-50">
                    <td className="px-6 py-4 whitespace-nowrap text-xs text-gray-400 font-mono">
                      {candidate.candidate_id}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap font-medium text-gray-900">{candidate.name}</td>
                    <td className="px-6 py-4 whitespace-nowrap text-gray-500">{candidate.title}</td>
                    <td className="px-6 py-4 whitespace-nowrap text-gray-500 text-sm">{candidate.company}</td>
                    <td className="px-6 py-4 whitespace-nowrap text-gray-500">{candidate.location}</td>
                    <td className="px-6 py-4">
                      <div className="flex flex-wrap gap-1 max-w-xs">
                        {candidate.skills?.map((skill) => (
                          <span key={skill} className="px-2 py-1 text-xs bg-indigo-100 text-indigo-700 rounded">
                            {skill}
                          </span>
                        ))}
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-gray-500">
                      {candidate.years_of_experience?.toFixed?.(1) ?? candidate.years_of_experience} yrs
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
