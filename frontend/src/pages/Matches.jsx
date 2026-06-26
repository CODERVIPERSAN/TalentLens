import { useEffect, useState } from 'react'
import { Brain, TrendingUp } from 'lucide-react'
import { jobsApi, matchesApi } from '../api/client'

export default function Matches() {
  const [jobs, setJobs] = useState([])
  const [selectedJob, setSelectedJob] = useState('')
  const [matches, setMatches] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    jobsApi
      .list()
      .then((data) => {
        setJobs(data)
        if (data.length > 0) setSelectedJob(String(data[0].id))
      })
      .catch(() => setError('Failed to load jobs. Is the backend running?'))
  }, [])

  const runAnalysis = async () => {
    if (!selectedJob) return
    setLoading(true)
    setError('')
    try {
      const data = await matchesApi.findBest(selectedJob)
      setMatches(data.matches || [])
    } catch (e) {
      setError(e.response?.data?.detail || 'Failed to run analysis')
    } finally {
      setLoading(false)
    }
  }

  const getScoreColor = (score) => {
    if (score >= 80) return 'text-green-600'
    if (score >= 60) return 'text-yellow-600'
    return 'text-red-600'
  }

  return (
    <div>
      <div className="flex justify-between items-center mb-8">
        <h2 className="text-3xl font-bold text-gray-900">AI-Powered Matches</h2>
        <div className="flex items-center gap-2">
          <select
            value={selectedJob}
            onChange={(e) => setSelectedJob(e.target.value)}
            className="border rounded-lg px-3 py-2"
          >
            {jobs.length === 0 && <option value="">No jobs available</option>}
            {jobs.map((job) => (
              <option key={job.id} value={job.id}>{job.title}</option>
            ))}
          </select>
          <button
            onClick={runAnalysis}
            disabled={!selectedJob || loading}
            className="flex items-center px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50"
          >
            <Brain className="w-4 h-4 mr-2" />
            {loading ? 'Analyzing...' : 'Run AI Analysis'}
          </button>
        </div>
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-50 text-red-700 rounded-lg text-sm">{error}</div>
      )}

      <div className="bg-white rounded-lg shadow p-6 mb-6">
        <div className="flex items-center mb-4">
          <TrendingUp className="w-5 h-5 text-indigo-600 mr-2" />
          <h3 className="text-lg font-semibold text-gray-900">Match Insights</h3>
        </div>
        <p className="text-gray-600">
          Select a job and run the analysis to rank candidates by semantic similarity,
          skill overlap, and experience fit.
        </p>
      </div>

      <div className="bg-white rounded-lg shadow">
        {matches.length === 0 ? (
          <div className="p-6 text-gray-500">
            No matches yet. Select a job and click "Run AI Analysis".
          </div>
        ) : (
          <div className="divide-y divide-gray-200">
            {matches.map((match) => (
              <div key={match.candidate_id} className="p-6 hover:bg-gray-50">
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center mb-2">
                      <h4 className="text-lg font-medium text-gray-900">{match.candidate_name}</h4>
                      <span className="mx-2 text-gray-400">·</span>
                      <span className="text-sm text-gray-500">{match.candidate_email}</span>
                    </div>
                    <p className="text-gray-600 text-sm mb-3">{match.analysis?.analysis}</p>
                    <div className="flex flex-wrap gap-3 text-xs text-gray-500 mb-3">
                      <span>Skills: {match.analysis?.skill_match_score}%</span>
                      <span>Experience: {match.analysis?.experience_match_score}%</span>
                      <span>Semantic: {match.analysis?.semantic_similarity_score}%</span>
                    </div>
                    {match.analysis?.matched_skills?.length > 0 && (
                      <div className="flex flex-wrap gap-1 mb-1">
                        {match.analysis.matched_skills.map((s) => (
                          <span key={s} className="px-2 py-1 text-xs bg-green-100 text-green-700 rounded">{s}</span>
                        ))}
                      </div>
                    )}
                    {match.analysis?.missing_skills?.length > 0 && (
                      <div className="flex flex-wrap gap-1">
                        {match.analysis.missing_skills.map((s) => (
                          <span key={s} className="px-2 py-1 text-xs bg-red-100 text-red-700 rounded">{s}</span>
                        ))}
                      </div>
                    )}
                  </div>
                  <div className="ml-4 text-right">
                    <span className="text-sm text-gray-500 block">Match Score</span>
                    <span className={`text-2xl font-bold ${getScoreColor(match.match_score)}`}>
                      {match.match_score}%
                    </span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
