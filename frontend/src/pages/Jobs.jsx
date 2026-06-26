import { Briefcase, MapPin, Clock, CheckCircle, XCircle } from 'lucide-react'

const REQUIREMENTS = [
  {
    category: 'Must Have',
    items: [
      'Production embeddings-based retrieval (sentence-transformers, BGE, E5)',
      'Vector DB / hybrid search (FAISS, Pinecone, Weaviate, Elasticsearch)',
      'Strong Python with production code quality',
      'Ranking evaluation frameworks (NDCG, MRR, MAP, A/B testing)',
    ],
  },
  {
    category: 'Nice to Have',
    items: [
      'LLM fine-tuning (LoRA, QLoRA, PEFT)',
      'Learning-to-rank models (XGBoost, neural)',
      'HR-tech / marketplace product experience',
      'Distributed systems / inference optimization',
    ],
  },
  {
    category: 'Disqualifiers',
    items: [
      'Pure research background without production deployment',
      'Only LangChain + OpenAI experience (under 12 months)',
      'Entire career at consulting firms (TCS, Infosys, Wipro, etc.)',
      'Computer vision / robotics without NLP/IR exposure',
    ],
  },
]

const JOB_DETAILS = {
  title: 'Senior AI Engineer — Founding Team',
  company: 'Redrob AI',
  location: 'Pune/Noida, India (Hybrid)',
  experience: '5–9 years (flexible with strong signals)',
  notice: 'Sub-30 days preferred',
}

export default function Jobs() {
  return (
    <div>
      <div className="mb-8">
        <h2 className="text-3xl font-bold text-gray-900">Job Description</h2>
        <p className="text-gray-500 mt-1">Target role for candidate ranking</p>
      </div>

      <div className="bg-white rounded-lg shadow p-6 mb-6">
        <h3 className="text-xl font-semibold text-gray-900 mb-4">{JOB_DETAILS.title}</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
          <div className="flex items-center text-gray-600">
            <Briefcase className="w-4 h-4 mr-2 text-indigo-500" />
            {JOB_DETAILS.company}
          </div>
          <div className="flex items-center text-gray-600">
            <MapPin className="w-4 h-4 mr-2 text-indigo-500" />
            {JOB_DETAILS.location}
          </div>
          <div className="flex items-center text-gray-600">
            <Clock className="w-4 h-4 mr-2 text-indigo-500" />
            {JOB_DETAILS.experience}
          </div>
          <div className="flex items-center text-gray-600">
            <CheckCircle className="w-4 h-4 mr-2 text-green-500" />
            Notice: {JOB_DETAILS.notice}
          </div>
        </div>
        <p className="mt-4 text-gray-600">
          Own the intelligence layer of Redrob's product — ranking, retrieval, and matching
          systems. Ship a v2 ranking system with embeddings and hybrid retrieval. Set up
          evaluation infrastructure with offline benchmarks and A/B testing.
        </p>
      </div>

      <div className="space-y-6">
        {REQUIREMENTS.map(({ category, items }) => (
          <div key={category} className="bg-white rounded-lg shadow p-6">
            <h4 className="text-lg font-semibold text-gray-900 mb-3 flex items-center">
              {category === 'Disqualifiers' ? (
                <XCircle className="w-5 h-5 mr-2 text-red-500" />
              ) : (
                <CheckCircle className="w-5 h-5 mr-2 text-green-500" />
              )}
              {category}
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
        ))}
      </div>
    </div>
  )
}
