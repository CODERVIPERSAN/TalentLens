import { useEffect, useState, useRef } from 'react'
import {
  Search, Brain, TrendingUp, Loader2, Briefcase, MapPin,
  ChevronDown, ChevronUp, Shield, Download, AlertTriangle, CheckCircle, Timer,
} from 'lucide-react'
import { getJob, runRanking, getExportCsvUrl, getStats } from '../api/client'
import PoolSelector from '../components/PoolSelector'

const FIT_STYLES = {
  'Strong Fit': 'bg-emerald-100 text-emerald-800 border-emerald-200',
  'Good Fit': 'bg-blue-100 text-blue-800 border-blue-200',
  'Borderline': 'bg-amber-100 text-amber-800 border-amber-200',
  'Concern': 'bg-red-100 text-red-800 border-red-200',
}

function formatDuration(ms) {
  if (ms == null || ms < 0) return '—'
  const totalSec = ms / 1000
  if (totalSec < 60) return `${totalSec.toFixed(1)}s`
  const min = Math.floor(totalSec / 60)
  const sec = (totalSec % 60).toFixed(1)
  return `${min}m ${sec}s`
}

function RunTimer({ elapsedMs, running, lastRunMs }) {
  if (!running && lastRunMs == null) return null

  return (
    <div className={`flex items-center gap-2 px-4 py-2 rounded-lg border text-sm font-mono ${
      running ? 'bg-amber-50 border-amber-200 text-amber-800' : 'bg-emerald-50 border-emerald-200 text-emerald-800'
    }`}>
      <Timer className={`w-4 h-4 ${running ? 'animate-pulse' : ''}`} />
      {running ? (
        <span>Running: <strong>{formatDuration(elapsedMs)}</strong></span>
      ) : (
        <span>Completed in <strong>{formatDuration(lastRunMs)}</strong></span>
      )}
    </div>
  )
}

function ScoreBar({ label, value, max = 1 }) {
  const pct = Math.min((value / max) * 100, 100)
  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="w-20 text-gray-500 capitalize">{label}</span>
      <div className="flex-1 h-2 bg-gray-100 rounded-full overflow-hidden">
        <div className="h-full bg-indigo-500 rounded-full" style={{ width: `${pct}%` }} />
      </div>
      <span className="w-10 text-right text-gray-600">{value?.toFixed?.(2) ?? value}</span>
    </div>
  )
}

function QualityReport({ report }) {
  if (!report) return null
  const scoreColor = report.quality_score >= 85 ? 'text-emerald-600' : report.quality_score >= 70 ? 'text-blue-600' : 'text-amber-600'

  return (
    <div className="bg-white rounded-lg shadow p-6 mb-6 border border-indigo-100">
      <div className="flex items-center gap-2 mb-4">
        <Shield className="w-5 h-5 text-indigo-600" />
        <h3 className="text-lg font-semibold text-gray-900">Cross-Check Quality Report</h3>
        {report.submission_ready ? (
          <span className="ml-auto flex items-center text-xs text-emerald-700 bg-emerald-50 px-2 py-1 rounded-full">
            <CheckCircle className="w-3 h-3 mr-1" /> Submission Ready
          </span>
        ) : (
          <span className="ml-auto flex items-center text-xs text-amber-700 bg-amber-50 px-2 py-1 rounded-full">
            <AlertTriangle className="w-3 h-3 mr-1" /> Review Needed
          </span>
        )}
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
        <div className="text-center p-3 bg-gray-50 rounded-lg">
          <p className={`text-2xl font-bold ${scoreColor}`}>{report.quality_score}</p>
          <p className="text-xs text-gray-500">Quality Score</p>
        </div>
        <div className="text-center p-3 bg-gray-50 rounded-lg">
          <p className="text-2xl font-bold text-indigo-600">{report.avg_confidence}%</p>
          <p className="text-xs text-gray-500">Avg Confidence</p>
        </div>
        <div className="text-center p-3 bg-gray-50 rounded-lg">
          <p className="text-2xl font-bold text-emerald-600">{report.strong_fit_count}</p>
          <p className="text-xs text-gray-500">Strong Fits</p>
        </div>
        <div className="text-center p-3 bg-gray-50 rounded-lg">
          <p className={`text-2xl font-bold ${report.honeypot_safe ? 'text-emerald-600' : 'text-red-600'}`}>
            {(report.honeypot_rate * 100).toFixed(1)}%
          </p>
          <p className="text-xs text-gray-500">Honeypot Rate</p>
        </div>
      </div>

      <p className="text-sm text-gray-700 bg-indigo-50 p-3 rounded-lg">{report.recommendation}</p>

      {Object.keys(report.flags_summary || {}).length > 0 && (
        <div className="mt-3 flex flex-wrap gap-2">
          {Object.entries(report.flags_summary).map(([flag, count]) => (
            <span key={flag} className="text-xs px-2 py-1 bg-gray-100 text-gray-600 rounded">
              {flag}: {count}
            </span>
          ))}
        </div>
      )}
    </div>
  )
}

function MatchCard({ match }) {
  const [expanded, setExpanded] = useState(false)
  const profile = match.profile_summary || {}
  const breakdown = match.score_breakdown || {}
  const audit = match.audit || {}
  const fitStyle = FIT_STYLES[audit.fit_tier] || FIT_STYLES['Borderline']

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
            <span className={`text-xs font-medium px-2 py-0.5 rounded border ${fitStyle}`}>
              {audit.fit_tier || '—'}
            </span>
            <span className="text-xs text-gray-500">{audit.confidence}% conf.</span>
          </div>

          <p className="text-sm text-gray-500 mb-2">
            {profile.company} · {profile.location} · {profile.years_of_experience?.toFixed?.(1)} yrs
            {profile.response_rate != null && ` · RR ${(profile.response_rate * 100).toFixed(0)}%`}
          </p>

          <p className="text-gray-700 text-sm mb-3">{match.reasoning}</p>

          {audit.audit_flags?.length > 0 && (
            <div className="flex flex-wrap gap-1 mb-3">
              {audit.audit_flags.map((flag) => (
                <span key={flag} className="text-xs px-2 py-0.5 bg-amber-50 text-amber-700 border border-amber-200 rounded">
                  {flag}
                </span>
              ))}
            </div>
          )}

          {profile.skills?.length > 0 && (
            <div className="flex flex-wrap gap-1 mb-3">
              {profile.skills.map((skill) => (
                <span key={skill} className="px-2 py-0.5 text-xs bg-gray-100 text-gray-700 rounded">{skill}</span>
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
              {['skills', 'title', 'career', 'experience', 'location', 'semantic', 'tenure', 'education', 'behavioral', 'penalties']
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
  const [qualityReport, setQualityReport] = useState(null)
  const [poolInfo, setPoolInfo] = useState(null)
  const [loading, setLoading] = useState(false)
  const [jobLoading, setJobLoading] = useState(true)
  const [hasRun, setHasRun] = useState(false)
  const [search, setSearch] = useState('')
  const [error, setError] = useState(null)
  const [memoryWarning, setMemoryWarning] = useState(null)
  const [useSample, setUseSample] = useState(false)
  const [stats, setStats] = useState(null)
  const [elapsedMs, setElapsedMs] = useState(0)
  const [lastRunMs, setLastRunMs] = useState(null)
  const startTimeRef = useRef(null)

  useEffect(() => {
    getJob().then(setJob).catch(() => {}).finally(() => setJobLoading(false))
    getStats().then((data) => {
      setStats(data)
      setUseSample(data.default_pool === 'sample')
    }).catch(() => {})
  }, [])

  useEffect(() => {
    if (!loading) return undefined

    startTimeRef.current = performance.now()
    setElapsedMs(0)

    const interval = setInterval(() => {
      setElapsedMs(performance.now() - startTimeRef.current)
    }, 100)

    return () => clearInterval(interval)
  }, [loading])

  const handleRunRanking = async () => {
    setLoading(true)
    setError(null)
    setMemoryWarning(null)
    setLastRunMs(null)
    const t0 = performance.now()
    try {
      const result = await runRanking(100, useSample)
      const duration = performance.now() - t0
      setLastRunMs(duration)
      setJob(result.job)
      setMatches(result.matches)
      setQualityReport(result.quality_report)
      setMemoryWarning(result.memory_warning || null)
      setPoolInfo({
        pool: result.pool,
        pool_size: result.pool_size,
        ranked_count: result.ranked_count,
        duration_ms: duration,
        submission_file: result.submission_file,
      })
      setHasRun(true)
    } catch (err) {
      setLastRunMs(performance.now() - t0)
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
      m.profile_summary?.name?.toLowerCase().includes(q) ||
      m.audit?.fit_tier?.toLowerCase().includes(q)
    )
  })

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <div>
          <h2 className="text-3xl font-bold text-gray-900">Matches</h2>
          <p className="text-gray-500 text-sm mt-1">Pro ranker with cross-check audit & confidence scoring</p>
        </div>
        <div className="flex gap-2 items-center">
          <RunTimer elapsedMs={elapsedMs} running={loading} lastRunMs={lastRunMs} />
          {hasRun && (
            <a
              href={getExportCsvUrl()}
              className="flex items-center px-4 py-2 border border-indigo-600 text-indigo-600 rounded-lg hover:bg-indigo-50"
            >
              <Download className="w-4 h-4 mr-2" />
              Export CSV
            </a>
          )}
          <button
            onClick={handleRunRanking}
            disabled={loading}
            className="flex items-center px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50"
          >
            {loading ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Brain className="w-4 h-4 mr-2" />}
            {loading ? 'Ranking...' : 'Run Pro Ranker'}
          </button>
        </div>
      </div>

      {memoryWarning && (
        <div className="mb-4 p-4 bg-amber-50 border border-amber-200 rounded-lg text-amber-800 text-sm">{memoryWarning}</div>
      )}

      {error && (
        <div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">{error}</div>
      )}

      {stats && (
        <div className="mb-4">
          <PoolSelector useSample={useSample} onChange={setUseSample} stats={stats} />
          {!useSample && (
            <p className="text-xs text-amber-600 mt-2">
              Full pool uses streaming ranker (~1 min, ~300MB RAM). Close extra browser tabs if the system feels slow.
            </p>
          )}
        </div>
      )}

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
              Ranked {poolInfo.ranked_count} of {poolInfo.pool_size} ({poolInfo.pool} pool) · 3-stage pipeline
              {poolInfo.duration_ms != null && (
                <span className="ml-2 text-emerald-700 font-medium">
                  · {formatDuration(poolInfo.duration_ms)}
                </span>
              )}
              {poolInfo.submission_file && (
                <span className="block mt-1 text-xs text-gray-500">
                  Saved to <code className="bg-gray-100 px-1 rounded">{poolInfo.submission_file}</code>
                </span>
              )}
            </p>
          )}
        </div>
      )}

      <div className="bg-white rounded-lg shadow p-6 mb-6">
        <div className="flex items-center mb-3">
          <TrendingUp className="w-5 h-5 text-indigo-600 mr-2" />
          <h3 className="text-lg font-semibold text-gray-900">TalentLens Pro Ranker v2</h3>
        </div>
        <p className="text-gray-600 text-sm">
          <strong>Stage 1 Recall</strong> → TF-IDF shortlist (2,500 from 100K) ·
          <strong> Stage 2 Precision</strong> → title/career/skills/behavioral deep score ·
          <strong> Stage 3 Audit</strong> → cross-check confidence, honeypot scan, trap demotion.
          Beats keyword stuffers by prioritizing career proof over skill lists.
        </p>
      </div>

      {loading && (
        <div className="mb-4 p-4 bg-amber-50 border border-amber-200 rounded-lg flex items-center justify-between">
          <div className="flex items-center text-amber-800">
            <Loader2 className="w-5 h-5 mr-2 animate-spin" />
            <span>
              Ranking {useSample ? '50 sample' : '100,000 full'} candidates on CPU…
            </span>
          </div>
          <span className="font-mono text-lg font-semibold text-amber-900">
            {formatDuration(elapsedMs)}
          </span>
        </div>
      )}

      {hasRun && <QualityReport report={qualityReport} />}

      {hasRun && (
        <div className="bg-white rounded-lg shadow">
          <div className="p-4 border-b flex items-center justify-between">
            <div className="relative flex-1 mr-4">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-5 h-5" />
              <input
                type="text"
                placeholder="Search by name, title, fit tier, reasoning..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="pl-10 pr-4 py-2 w-full border rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>
            <span className="text-sm text-gray-500 whitespace-nowrap">{filtered.length} matches</span>
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
          <p className="text-gray-500 mb-2">Click <strong>Run Pro Ranker</strong> to rank + audit candidates</p>
          <p className="text-gray-400 text-sm">Iterative cross-check · confidence scoring · honeypot detection</p>
        </div>
      )}
    </div>
  )
}
