import { useEffect, useState } from 'react'
import { Users, Briefcase, Target, Brain } from 'lucide-react'
import { candidatesApi, jobsApi } from '../api/client'

export default function Dashboard() {
  const [stats, setStats] = useState({ candidates: 0, jobs: 0, activeJobs: 0 })

  useEffect(() => {
    Promise.all([candidatesApi.list(), jobsApi.list()])
      .then(([candidates, jobs]) => {
        setStats({
          candidates: candidates.length,
          jobs: jobs.length,
          activeJobs: jobs.filter((j) => j.status === 'active').length,
        })
      })
      .catch(() => {})
  }, [])

  const cards = [
    { label: 'Total Candidates', value: stats.candidates, icon: Users, color: 'bg-indigo-100 text-indigo-600' },
    { label: 'Total Jobs', value: stats.jobs, icon: Briefcase, color: 'bg-green-100 text-green-600' },
    { label: 'Active Jobs', value: stats.activeJobs, icon: Target, color: 'bg-blue-100 text-blue-600' },
    { label: 'AI Matching', value: 'On', icon: Brain, color: 'bg-purple-100 text-purple-600' },
  ]

  return (
    <div>
      <h2 className="text-3xl font-bold text-gray-900 mb-8">Dashboard</h2>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        {cards.map((card) => (
          <div key={card.label} className="bg-white rounded-lg shadow p-6">
            <div className="flex items-center">
              <div className={`p-3 rounded-full ${card.color}`}>
                <card.icon className="w-6 h-6" />
              </div>
              <div className="ml-4">
                <p className="text-sm font-medium text-gray-500">{card.label}</p>
                <p className="text-2xl font-semibold text-gray-900">{card.value}</p>
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Welcome to TalentLens</h3>
        <p className="text-gray-600">
          TalentLens is an AI-powered talent intelligence platform that analyzes candidates beyond keywords,
          matching the right people to the right roles before traditional ATS scoring.
        </p>
        <div className="mt-4 grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="p-4 bg-indigo-50 rounded-lg">
            <h4 className="font-medium text-indigo-900 mb-2">Smart Matching</h4>
            <p className="text-sm text-indigo-700">AI-powered candidate-job matching using semantic analysis</p>
          </div>
          <div className="p-4 bg-green-50 rounded-lg">
            <h4 className="font-medium text-green-900 mb-2">Skill Extraction</h4>
            <p className="text-sm text-green-700">Automatically extract and analyze skills from resumes</p>
          </div>
          <div className="p-4 bg-blue-50 rounded-lg">
            <h4 className="font-medium text-blue-900 mb-2">Deep Insights</h4>
            <p className="text-sm text-blue-700">Get detailed analysis and match scores for better decisions</p>
          </div>
        </div>
      </div>
    </div>
  )
}
