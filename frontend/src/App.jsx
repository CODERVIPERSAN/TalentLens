import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import Candidates from './pages/Candidates'
import Jobs from './pages/Jobs'
import Matches from './pages/Matches'
import Architecture from './pages/Architecture'

function App() {
  return (
    <Router>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Dashboard />} />
          <Route path="candidates" element={<Candidates />} />
          <Route path="jobs" element={<Jobs />} />
          <Route path="matches" element={<Matches />} />
          <Route path="architecture" element={<Architecture />} />
        </Route>
      </Routes>
    </Router>
  )
}

export default App
