import { useEffect, useState, useCallback } from 'react'
import { Users, Briefcase, Target, Brain, Loader2, RefreshCw, Database } from 'lucide-react'
import { getStats } from '../api/client'
import PoolSelector from '../components/PoolSelector'

export default function Dashboard() {
  const [stats, setStats] = useState(null)
  const [useSample, setUseSample] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const loadStats = useCallback(() => {
    setLoading(true)
    getStats()
      .then((data) => {
        setStats(data)
        setUseSample(data.default_pool === 'sample')
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    loadStats()
  }, [loadStats])

  const cards = stats ? [
    { label: 'Sample Candidates', value: stats.sample_candidates, icon: Users, iconBg: 'bg-indigo-100', iconColor: 'text-indigo-600' },
    { label: 'Full Pool Size', value: stats.full_pool_size?.toLocaleString(), icon: Briefcase, iconBg: 'bg-green-100', iconColor: 'text-green-600' },
    { label: 'Active Pool', value: useSample ? 'Sample (50)' : 'Full (100K)', icon: Database, iconBg: 'bg-blue-100', iconColor: 'text-blue-600' },
    { label: 'Ranker Status', value: stats.ranking_ready ? 'Ready' : 'Setup', icon: Brain, iconBg: 'bg-purple-100', iconColor: 'text-purple-600' },
  ] : []

  const fullSource = stats?.sources?.full_candidates
  const sampleSource = stats?.sources?.sample_candidates

  return (
    <div>
      <div className="flex justify-between items-center mb-8">
        <h2 className="text-3xl font-bold text-gray-900">Dashboard</h2>
        <button
          onClick={loadStats}
          className="flex items-center text-sm text-indigo-600 hover:text-indigo-800"
        >
          <RefreshCw className="w-4 h-4 mr-1" />
          Refresh
        </button>
      </div>

      {loading && (
        <div className="flex items-center text-gray-500 mb-6">
          <Loader2 className="w-5 h-5 mr-2 animate-spin" />
          Loading challenge data...
        </div>
      )}

      {error && (
        <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">
          Backend unavailable: {error}
        </div>
      )}

      {stats && (
        <div className="mb-6">
          <PoolSelector useSample={useSample} onChange={setUseSample} stats={stats} />
          <p className="text-xs text-gray-500 mt-2">
            Ranker uses: <code className="bg-gray-100 px-1 rounded">{stats.active_ranker_file}</code>
          </p>
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

      {stats?.sources && (
        <div className="bg-white rounded-lg shadow p-6 mb-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-3">Data file status</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
            {fullSource && (
              <div className="p-3 bg-green-50 rounded-lg">
                <p className="font-medium text-green-900">Full pool (candidates.jsonl)</p>
                <p className="text-green-700">{fullSource.size_mb} MB · updated {fullSource.modified}</p>
              </div>
            )}
            {sampleSource && (
              <div className="p-3 bg-indigo-50 rounded-lg">
                <p className="font-medium text-indigo-900">Sample (sample_candidates.json)</p>
                <p className="text-indigo-700">{sampleSource.size_mb} MB · updated {sampleSource.modified}</p>
              </div>
            )}
          </div>
          <p className="text-xs text-gray-500 mt-3">
            Updating files in <code className="bg-gray-100 px-1">data/</code> requires clicking Refresh.
            Files inside <code className="bg-gray-100 px-1">[PUB].../</code> folder are NOT used — copy to <code className="bg-gray-100 px-1">data/candidates.jsonl</code>.
          </p>
        </div>
      )}

      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-2">Redrob Hackathon</h3>
        <p className="text-gray-600 mb-4">
          Rank top 100 from <strong>{useSample ? '50 sample' : '100,000 full'}</strong> candidates for{' '}
          <strong>{stats?.job_title || 'Senior AI Engineer'}</strong> at {stats?.company || 'Redrob AI'}.
        </p>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="p-4 bg-indigo-50 rounded-lg">
            <h4 className="font-medium text-indigo-900 mb-2">Candidates</h4>
            <p className="text-sm text-indigo-700">Browse from selected pool (toggle above)</p>
          </div>
          <div className="p-4 bg-green-50 rounded-lg">
            <h4 className="font-medium text-green-900 mb-2">Jobs</h4>
            <p className="text-sm text-green-700">Job listing from data/job.json</p>
          </div>
          <div className="p-4 bg-blue-50 rounded-lg">
            <h4 className="font-medium text-blue-900 mb-2">Matches</h4>
            <p className="text-sm text-blue-700">Run ranker on same pool you select in Matches page</p>
          </div>
        </div>
      </div>
    </div>
  )
}
