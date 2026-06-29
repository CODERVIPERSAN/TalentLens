import { useEffect, useState } from 'react'
import { Briefcase, MapPin, Clock, CheckCircle, XCircle, Loader2, AlertTriangle } from 'lucide-react'
import { getJob } from '../api/client'

export default function Jobs() {
  const [job, setJob] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    getJob()
      .then(setJob)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }, [])

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20 text-gray-500">
        <Loader2 className="w-6 h-6 animate-spin mr-2" />
        Loading job listing from challenge data...
      </div>
    )
  }

  if (error || !job) {
    return (
      <div className="p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">
        Failed to load job: {error}
      </div>
    )
  }

  const sections = [
    { key: 'must_have', label: 'Must Have', icon: CheckCircle, color: 'green' },
    { key: 'nice_to_have', label: 'Nice to Have', icon: CheckCircle, color: 'blue' },
    { key: 'disqualifiers', label: 'Disqualifiers', icon: XCircle, color: 'red' },
    { key: 'hackathon_notes', label: 'Hackathon Notes', icon: AlertTriangle, color: 'amber' },
  ]

  return (
    <div>
      <div className="mb-8">
        <h2 className="text-3xl font-bold text-gray-900">Job Listing</h2>
        <p className="text-gray-500 mt-1">From PUB India challenge — target role for CPU ranker</p>
      </div>

      <div className="bg-white rounded-lg shadow p-6 mb-6 border-l-4 border-indigo-500">
        <div className="flex items-start justify-between">
          <div>
            <h3 className="text-xl font-semibold text-gray-900">{job.title}</h3>
            <p className="text-indigo-600 font-medium mt-1">{job.company}</p>
          </div>
          <span className="px-3 py-1 text-xs font-medium bg-green-100 text-green-700 rounded-full uppercase">
            {job.status || 'active'}
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm mt-4">
          <div className="flex items-center text-gray-600">
            <MapPin className="w-4 h-4 mr-2 text-indigo-500" />
            {job.location}
          </div>
          <div className="flex items-center text-gray-600">
            <Briefcase className="w-4 h-4 mr-2 text-indigo-500" />
            {job.employment_type}
          </div>
          <div className="flex items-center text-gray-600">
            <Clock className="w-4 h-4 mr-2 text-indigo-500" />
            Experience: {job.experience_range}
          </div>
          <div className="flex items-center text-gray-600">
            <CheckCircle className="w-4 h-4 mr-2 text-green-500" />
            Notice: {job.notice_period}
          </div>
        </div>

        <p className="mt-4 text-gray-700">{job.summary}</p>

        {job.mandate?.length > 0 && (
          <div className="mt-4">
            <h4 className="text-sm font-semibold text-gray-900 mb-2">First 90 Days</h4>
            <ul className="space-y-1">
              {job.mandate.map((item) => (
                <li key={item} className="text-sm text-gray-600 flex items-start">
                  <span className="mr-2 mt-1.5 w-1.5 h-1.5 rounded-full bg-indigo-400 flex-shrink-0" />
                  {item}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>

      <div className="space-y-6">
        {sections.map(({ key, label, icon: Icon, color }) => {
          const items = job[key]
          if (!items?.length) return null
          const iconColor = color === 'red' ? 'text-red-500' : color === 'amber' ? 'text-amber-500' : 'text-green-500'
          return (
            <div key={key} className="bg-white rounded-lg shadow p-6">
              <h4 className="text-lg font-semibold text-gray-900 mb-3 flex items-center">
                <Icon className={`w-5 h-5 mr-2 ${iconColor}`} />
                {label}
              </h4>
              <ul className="space-y-2">
                {items.map((item) => (
                  <li key={item} className="text-gray-600 text-sm flex items-start">
                    <span className="mr-2 mt-1.5 w-1.5 h-1.5 rounded-full bg-indigo-400 flex-shrink-0" />
                    {item}
                  </li>
                ))}
              </ul>
            </div>
          )
        })}
      </div>
    </div>
  )
}
