import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import Upload from './pages/Upload'
import Chat from './pages/Chat'
import Library from './pages/Library'
import StudyTools from './pages/StudyTools'
import SystemStatus from './pages/SystemStatus'
import GraphExplorer from './pages/GraphExplorer'
import { StudyToolsProvider } from './stores/studyToolsStore'
import { UploadProvider } from './stores/uploadStore'

export default function App() {
  return (
    <StudyToolsProvider>
      <UploadProvider>
        <Layout>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/upload" element={<Upload />} />
            <Route path="/chat" element={<Chat />} />
            <Route path="/chat/:sessionId" element={<Chat />} />
            <Route path="/library" element={<Library />} />
            <Route path="/study-tools" element={<StudyTools />} />
            <Route path="/system" element={<SystemStatus />} />
            <Route path="/graph" element={<GraphExplorer />} />
          </Routes>
        </Layout>
      </UploadProvider>
    </StudyToolsProvider>
  )
}
