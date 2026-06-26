import { useEffect, useState } from 'react'
import { Users, Briefcase, Target, Brain, Loader2 } from 'lucide-react'
import { getStats } from '../api/client'

export default function Dashboard() {
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    getStats()
      .then(setStats)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }, [])

  const cards = stats ? [
    { label: 'Sample Candidates', value: stats.sample_candidates, icon: Users, iconBg: 'bg-indigo-100', iconColor: 'text-indigo-600' },
    { label: 'Full Pool Size', value: stats.full_pool_size?.toLocaleString(), icon: Briefcase, iconBg: 'bg-green-100', iconColor: 'text-green-600' },
    { label: 'Target Rankings', value: '100', icon: Target, iconBg: 'bg-blue-100', iconColor: 'text-blue-600' },
    { label: 'Ranker Status', value: stats.ranking_ready ? 'Ready' : 'Setup', icon: Brain, iconBg: 'bg-purple-100', iconColor: 'text-purple-600' },
  ] : []

  return (
    <div>
      <h2 className="text-3xl font-bold text-gray-900 mb-8">Dashboard</h2>

      {loading && (
        <div className="flex items-center text-gray-500 mb-6">
          <Loader2 className="w-5 h-5 mr-2 animate-spin" />
          Loading challenge data...
        </div>
      )}

      {error && (
        <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">
          Backend unavailable: {error}. Start the API with{' '}
          <code className="bg-red-100 px-1 rounded">uvicorn app.main:app --reload</code>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        {cards.map(({ label, value, icon: Icon, iconBg, iconColor }) => (
          <div key={label} className="bg-white rounded-lg shadow p-6">
            <div className="flex items-center">
              <div className={`p-3 rounded-full ${iconBg} ${iconColor}`}>
                <Icon className="w-6 h-6" />
              </div>
              <div className="ml-4">
                <p className="text-sm font-medium text-gray-500">{label}</p>
                <p className="text-2xl font-semibold text-gray-900">{value}</p>
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-2">
          Redrob Hackathon — Intelligent Candidate Discovery
        </h3>
        <p className="text-gray-600 mb-4">
          Rank the top 100 candidates from a 100K pool for the{' '}
          <strong>{stats?.job_title || 'Senior AI Engineer'}</strong> role at{' '}
          {stats?.company || 'Redrob AI'}. The ranker uses TF-IDF semantic matching,
          skill/title scoring, behavioral signals, and honeypot detection — all CPU-only
          with no network calls during ranking.
        </p>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="p-4 bg-indigo-50 rounded-lg">
            <h4 className="font-medium text-indigo-900 mb-2">Candidates</h4>
            <p className="text-sm text-indigo-700">Browse sample candidates from the challenge dataset</p>
          </div>
          <div className="p-4 bg-green-50 rounded-lg">
            <h4 className="font-medium text-green-900 mb-2">Jobs</h4>
            <p className="text-sm text-green-700">View the Senior AI Engineer job description requirements</p>
          </div>
          <div className="p-4 bg-blue-50 rounded-lg">
            <h4 className="font-medium text-blue-900 mb-2">Matches</h4>
            <p className="text-sm text-blue-700">Run the CPU ranker and inspect top matches with reasoning</p>
          </div>
        </div>
      </div>
    </div>
  )
}
