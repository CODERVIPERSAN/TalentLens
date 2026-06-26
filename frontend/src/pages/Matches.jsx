import { useEffect, useState } from 'react'
import { Search, Brain, TrendingUp, Loader2 } from 'lucide-react'
import { runRanking } from '../api/client'

export default function Matches() {
  const [matches, setMatches] = useState([])
  const [loading, setLoading] = useState(false)
  const [hasRun, setHasRun] = useState(false)
  const [search, setSearch] = useState('')
  const [error, setError] = useState(null)

  const handleRunRanking = async () => {
    setLoading(true)
    setError(null)
    try {
      const results = await runRanking(50)
      setMatches(results)
      setHasRun(true)
    } catch (err) {
      setError(err.response?.data?.detail || err.message)
    } finally {
      setLoading(false)
    }
  }

  const filtered = matches.filter((m) => {
    const q = search.toLowerCase()
    return (
      m.candidate_id?.toLowerCase().includes(q) ||
      m.reasoning?.toLowerCase().includes(q) ||
      m.profile_summary?.title?.toLowerCase().includes(q)
    )
  })

  const getScoreColor = (score) => {
    if (score >= 0.8) return 'text-green-600'
    if (score >= 0.5) return 'text-yellow-600'
    return 'text-red-600'
  }

  return (
    <div>
      <div className="flex justify-between items-center mb-8">
        <h2 className="text-3xl font-bold text-gray-900">AI-Powered Matches</h2>
        <button
          onClick={handleRunRanking}
          disabled={loading}
          className="flex items-center px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50"
        >
          {loading ? (
            <Loader2 className="w-4 h-4 mr-2 animate-spin" />
          ) : (
            <Brain className="w-4 h-4 mr-2" />
          )}
          {loading ? 'Ranking...' : 'Run CPU Ranker'}
        </button>
      </div>

      {error && (
        <div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">{error}</div>
      )}

      <div className="bg-white rounded-lg shadow p-6 mb-6">
        <div className="flex items-center mb-4">
          <TrendingUp className="w-5 h-5 text-indigo-600 mr-2" />
          <h3 className="text-lg font-semibold text-gray-900">Hybrid Ranker</h3>
        </div>
        <p className="text-gray-600">
          TF-IDF semantic matching + skill/title scoring + behavioral signal modifiers.
          Penalizes consulting-only backgrounds, keyword stuffers, and honeypot profiles.
          Runs entirely on CPU with no external API calls.
        </p>
      </div>

      {hasRun && (
        <div className="bg-white rounded-lg shadow">
          <div className="p-4 border-b">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-5 h-5" />
              <input
                type="text"
                placeholder="Search matches..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="pl-10 pr-4 py-2 w-full border rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>
          </div>

          <div className="divide-y divide-gray-200">
            {filtered.map((match) => (
              <div key={match.candidate_id} className="p-6 hover:bg-gray-50">
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center mb-2 gap-2">
                      <span className="text-xs font-mono bg-gray-100 px-2 py-1 rounded">
                        #{match.rank}
                      </span>
                      <h4 className="text-lg font-medium text-gray-900">
                        {match.profile_summary?.name || match.candidate_id}
                      </h4>
                      <span className="text-gray-400">·</span>
                      <span className="text-gray-600">{match.profile_summary?.title}</span>
                    </div>
                    <p className="text-gray-600 text-sm mb-3">{match.reasoning}</p>
                    <div className="flex items-center gap-4 text-sm text-gray-500">
                      <span>{match.profile_summary?.location}</span>
                      <span>{match.profile_summary?.years_of_experience?.toFixed?.(1)} yrs exp</span>
                      <span className={`font-bold ${getScoreColor(match.score)}`}>
                        Score: {match.score}
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {!hasRun && !loading && (
        <div className="text-center py-12 text-gray-500">
          Click "Run CPU Ranker" to rank sample candidates against the job description.
        </div>
      )}
    </div>
  )
}
