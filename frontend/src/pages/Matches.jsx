import { useEffect, useState } from 'react'
import { Search, Brain, TrendingUp, Loader2, Briefcase, MapPin, ChevronDown, ChevronUp } from 'lucide-react'
import { getJob, runRanking } from '../api/client'

function ScoreBar({ label, value, max = 1 }) {
  const pct = Math.min((value / max) * 100, 100)
  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="w-20 text-gray-500 capitalize">{label}</span>
      <div className="flex-1 h-2 bg-gray-100 rounded-full overflow-hidden">
        <div
          className="h-full bg-indigo-500 rounded-full"
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="w-10 text-right text-gray-600">{value?.toFixed?.(2) ?? value}</span>
    </div>
  )
}

function MatchCard({ match }) {
  const [expanded, setExpanded] = useState(false)
  const profile = match.profile_summary || {}
  const breakdown = match.score_breakdown || {}

  const getScoreColor = (score) => {
    if (score >= 0.8) return 'text-green-600 bg-green-50'
    if (score >= 0.5) return 'text-yellow-600 bg-yellow-50'
    return 'text-red-600 bg-red-50'
  }

  return (
    <div className="p-6 hover:bg-gray-50">
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <div className="flex flex-wrap items-center gap-2 mb-2">
            <span className="text-xs font-mono bg-indigo-100 text-indigo-700 px-2 py-1 rounded font-bold">
              #{match.rank}
            </span>
            <h4 className="text-lg font-medium text-gray-900">{profile.name}</h4>
            <span className="text-gray-400">·</span>
            <span className="text-gray-600">{profile.title}</span>
            <span className={`text-sm font-bold px-2 py-0.5 rounded ${getScoreColor(match.score)}`}>
              {match.score}
            </span>
          </div>

          <p className="text-sm text-gray-500 mb-2">
            {profile.company} · {profile.location} · {profile.years_of_experience?.toFixed?.(1)} yrs
          </p>

          <p className="text-gray-700 text-sm mb-3">{match.reasoning}</p>

          {profile.skills?.length > 0 && (
            <div className="flex flex-wrap gap-1 mb-3">
              {profile.skills.map((skill) => (
                <span key={skill} className="px-2 py-0.5 text-xs bg-gray-100 text-gray-700 rounded">
                  {skill}
                </span>
              ))}
            </div>
          )}

          <button
            onClick={() => setExpanded(!expanded)}
            className="flex items-center text-xs text-indigo-600 hover:text-indigo-800"
          >
            {expanded ? <ChevronUp className="w-4 h-4 mr-1" /> : <ChevronDown className="w-4 h-4 mr-1" />}
            {expanded ? 'Hide' : 'Show'} score breakdown
          </button>

          {expanded && (
            <div className="mt-3 p-3 bg-gray-50 rounded-lg space-y-1.5">
              {['skills', 'title', 'career', 'experience', 'location', 'semantic', 'behavioral', 'penalties']
                .filter((key) => breakdown[key] != null)
                .map((key) => (
                  <ScoreBar key={key} label={key} value={breakdown[key]} />
                ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default function Matches() {
  const [job, setJob] = useState(null)
  const [matches, setMatches] = useState([])
  const [poolInfo, setPoolInfo] = useState(null)
  const [loading, setLoading] = useState(false)
  const [jobLoading, setJobLoading] = useState(true)
  const [hasRun, setHasRun] = useState(false)
  const [search, setSearch] = useState('')
  const [error, setError] = useState(null)

  useEffect(() => {
    getJob()
      .then(setJob)
      .catch(() => {})
      .finally(() => setJobLoading(false))
  }, [])

  const handleRunRanking = async () => {
    setLoading(true)
    setError(null)
    try {
      const result = await runRanking(50, true)
      setJob(result.job)
      setMatches(result.matches)
      setPoolInfo({ pool: result.pool, pool_size: result.pool_size, ranked_count: result.ranked_count })
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
      m.profile_summary?.title?.toLowerCase().includes(q) ||
      m.profile_summary?.name?.toLowerCase().includes(q)
    )
  })

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <div>
          <h2 className="text-3xl font-bold text-gray-900">Matches</h2>
          <p className="text-gray-500 text-sm mt-1">Rank candidates against the challenge job listing</p>
        </div>
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

      {/* Job listing context */}
      {!jobLoading && job && (
        <div className="bg-white rounded-lg shadow p-5 mb-6 border-l-4 border-indigo-500">
          <div className="flex items-center gap-2 mb-2">
            <Briefcase className="w-5 h-5 text-indigo-600" />
            <h3 className="text-lg font-semibold text-gray-900">Ranking against: {job.title}</h3>
          </div>
          <div className="flex flex-wrap gap-4 text-sm text-gray-600">
            <span>{job.company}</span>
            <span className="flex items-center"><MapPin className="w-3 h-3 mr-1" />{job.location}</span>
            <span>Exp: {job.experience_range}</span>
          </div>
          {poolInfo && (
            <p className="mt-2 text-sm text-indigo-600">
              Ranked {poolInfo.ranked_count} of {poolInfo.pool_size} candidates ({poolInfo.pool} pool)
            </p>
          )}
        </div>
      )}

      <div className="bg-white rounded-lg shadow p-6 mb-6">
        <div className="flex items-center mb-3">
          <TrendingUp className="w-5 h-5 text-indigo-600 mr-2" />
          <h3 className="text-lg font-semibold text-gray-900">Hybrid CPU Ranker</h3>
        </div>
        <p className="text-gray-600 text-sm">
          Per challenge spec: title + career history are decisive signals. TF-IDF semantic match,
          skill trust (anti keyword-stuffing), behavioral Redrob signals (response rate, notice period,
          last active), consulting/CV-only/LangChain trap penalties, and honeypot detection.
          CPU-only, no API calls.
        </p>
      </div>

      {hasRun && (
        <div className="bg-white rounded-lg shadow">
          <div className="p-4 border-b flex items-center justify-between">
            <div className="relative flex-1 mr-4">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-5 h-5" />
              <input
                type="text"
                placeholder="Search matches by name, title, reasoning..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="pl-10 pr-4 py-2 w-full border rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>
            <span className="text-sm text-gray-500 whitespace-nowrap">
              {filtered.length} matches
            </span>
          </div>

          <div className="divide-y divide-gray-200">
            {filtered.map((match) => (
              <MatchCard key={match.candidate_id} match={match} />
            ))}
          </div>
        </div>
      )}

      {!hasRun && !loading && (
        <div className="text-center py-12 bg-white rounded-lg shadow">
          <Brain className="w-12 h-12 text-gray-300 mx-auto mb-4" />
          <p className="text-gray-500 mb-2">Click <strong>Run CPU Ranker</strong> to process candidates</p>
          <p className="text-gray-400 text-sm">Uses sample_candidates.json from the PUB challenge zip</p>
        </div>
      )}
    </div>
  )
}
