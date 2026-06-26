import { useState } from 'react'
import { Search, Brain, TrendingUp } from 'lucide-react'

export default function Matches() {
  const [matches] = useState([
    { id: 1, candidate: 'John Doe', job: 'Senior Software Engineer', score: 92, analysis: 'Strong match with excellent technical skills and relevant experience' },
    { id: 2, candidate: 'Jane Smith', job: 'Product Manager', score: 88, analysis: 'Good fit with strong leadership background' },
    { id: 3, candidate: 'Bob Johnson', job: 'Data Scientist', score: 75, analysis: 'Moderate match, would benefit from more ML experience' },
  ])

  const getScoreColor = (score) => {
    if (score >= 80) return 'text-green-600'
    if (score >= 60) return 'text-yellow-600'
    return 'text-red-600'
  }

  return (
    <div>
      <div className="flex justify-between items-center mb-8">
        <h2 className="text-3xl font-bold text-gray-900">AI-Powered Matches</h2>
        <button className="flex items-center px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700">
          <Brain className="w-4 h-4 mr-2" />
          Run AI Analysis
        </button>
      </div>
      
      <div className="bg-white rounded-lg shadow p-6 mb-6">
        <div className="flex items-center mb-4">
          <TrendingUp className="w-5 h-5 text-indigo-600 mr-2" />
          <h3 className="text-lg font-semibold text-gray-900">Match Insights</h3>
        </div>
        <p className="text-gray-600">
          Our AI analyzes candidates beyond keywords using semantic embeddings and skill matching to find the best fits for your open positions.
        </p>
      </div>
      
      <div className="bg-white rounded-lg shadow">
        <div className="p-4 border-b">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-5 h-5" />
            <input
              type="text"
              placeholder="Search matches..."
              className="pl-10 pr-4 py-2 w-full border rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>
        </div>
        
        <div className="divide-y divide-gray-200">
          {matches.map((match) => (
            <div key={match.id} className="p-6 hover:bg-gray-50">
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center mb-2">
                    <h4 className="text-lg font-medium text-gray-900">{match.candidate}</h4>
                    <span className="mx-2 text-gray-400">→</span>
                    <h4 className="text-lg font-medium text-gray-900">{match.job}</h4>
                  </div>
                  <p className="text-gray-600 text-sm mb-3">{match.analysis}</p>
                  <div className="flex items-center">
                    <span className="text-sm text-gray-500 mr-2">Match Score:</span>
                    <span className={`text-2xl font-bold ${getScoreColor(match.score)}`}>
                      {match.score}%
                    </span>
                  </div>
                </div>
                <button className="ml-4 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 text-sm">
                  View Details
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
