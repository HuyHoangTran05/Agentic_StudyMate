import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import Upload from './pages/Upload'
import Chat from './pages/Chat'
import Library from './pages/Library'
import StudyTools from './pages/StudyTools'
import { StudyToolsProvider } from './stores/studyToolsStore'

export default function App() {
  return (
    <StudyToolsProvider>
      <Layout>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/upload" element={<Upload />} />
          <Route path="/chat" element={<Chat />} />
          <Route path="/chat/:sessionId" element={<Chat />} />
          <Route path="/library" element={<Library />} />
          <Route path="/study-tools" element={<StudyTools />} />
        </Routes>
      </Layout>
    </StudyToolsProvider>
  )
}
