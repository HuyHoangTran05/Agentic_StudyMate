import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  FileText,
  MessageSquare,
  Upload,
  FlaskConical,
  ArrowRight,
  Sparkles,
  TrendingUp,
  Clock,
} from 'lucide-react'
import { getDocuments, getChatSessions } from '../lib/api'
import type { Document, ChatSession } from '../lib/api'

export default function Dashboard() {
  const [docs, setDocs] = useState<Document[]>([])
  const [sessions, setSessions] = useState<ChatSession[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([getDocuments(), getChatSessions()])
      .then(([docRes, sessRes]) => {
        setDocs(docRes.documents)
        setSessions(sessRes)
      })
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  const readyDocs = docs.filter((d) => d.status === 'ready').length
  const totalChunks = docs.reduce((sum, d) => sum + d.total_chunks, 0)

  const stats = [
    { label: 'Documents', value: docs.length, icon: FileText, color: 'from-violet-500 to-purple-600' },
    { label: 'Chat Sessions', value: sessions.length, icon: MessageSquare, color: 'from-cyan-500 to-blue-600' },
    { label: 'Ready to Chat', value: readyDocs, icon: TrendingUp, color: 'from-emerald-500 to-green-600' },
    { label: 'Text Chunks', value: totalChunks, icon: Sparkles, color: 'from-amber-500 to-orange-600' },
  ]

  const quickActions = [
    { label: 'Upload Document', icon: Upload, to: '/upload', desc: 'Add PDFs, DOCX, or TXT files' },
    { label: 'Start Chatting', icon: MessageSquare, to: '/chat', desc: 'Ask questions about your docs' },
    { label: 'Study Tools', icon: FlaskConical, to: '/study-tools', desc: 'Generate quizzes & flashcards' },
  ]

  return (
    <div className="p-6 md:p-8 max-w-6xl mx-auto space-y-8">
      {/* Hero */}
      <div className="relative overflow-hidden rounded-3xl gradient-bg p-8 md:p-10">
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top_right,rgba(255,255,255,0.15),transparent_70%)]" />
        <div className="relative z-10">
          <h1 className="text-3xl md:text-4xl font-bold text-white tracking-tight">
            Welcome to StudyMate
          </h1>
          <p className="mt-3 text-base text-white/70 max-w-xl leading-relaxed">
            Your AI-powered study assistant. Upload documents, chat with them using
            hybrid RAG retrieval, and generate quizzes, flashcards, and summaries.
          </p>
          <Link
            to="/upload"
            className="mt-6 inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-white/15 backdrop-blur text-white text-sm font-medium hover:bg-white/25 transition-all border border-white/10"
          >
            Get Started <ArrowRight className="w-4 h-4" />
          </Link>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 stagger-children">
        {stats.map((stat) => {
          const Icon = stat.icon
          return (
            <div key={stat.label} className="glass rounded-2xl p-5 animate-fade-in hover:shadow-lg hover:shadow-violet-500/5 transition-all">
              <div className={`w-10 h-10 rounded-xl bg-gradient-to-br ${stat.color} flex items-center justify-center mb-3 shadow-lg`}>
                <Icon className="w-5 h-5 text-white" />
              </div>
              <p className="text-2xl font-bold text-white">
                {loading ? '—' : stat.value.toLocaleString()}
              </p>
              <p className="text-xs text-text-muted mt-1">{stat.label}</p>
            </div>
          )
        })}
      </div>

      <div className="grid md:grid-cols-2 gap-6">
        {/* Quick Actions */}
        <div className="space-y-4">
          <h2 className="text-lg font-semibold text-white flex items-center gap-2">
            <Sparkles className="w-5 h-5 text-violet-400" />
            Quick Actions
          </h2>
          <div className="space-y-3 stagger-children">
            {quickActions.map((action) => {
              const Icon = action.icon
              return (
                <Link
                  key={action.to}
                  to={action.to}
                  className="flex items-center gap-4 p-4 glass glass-hover rounded-2xl transition-all group animate-fade-in hover:-translate-y-0.5"
                >
                  <div className="w-11 h-11 rounded-xl gradient-bg-subtle flex items-center justify-center flex-shrink-0 group-hover:scale-105 transition-transform">
                    <Icon className="w-5 h-5 text-violet-400" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-semibold text-white">{action.label}</p>
                    <p className="text-xs text-text-muted mt-0.5">{action.desc}</p>
                  </div>
                  <ArrowRight className="w-4 h-4 text-text-muted group-hover:text-violet-400 group-hover:translate-x-1 transition-all" />
                </Link>
              )
            })}
          </div>
        </div>

        {/* Recent Chats */}
        <div className="space-y-4">
          <h2 className="text-lg font-semibold text-white flex items-center gap-2">
            <Clock className="w-5 h-5 text-cyan-400" />
            Recent Chats
          </h2>
          {loading ? (
            <div className="glass rounded-2xl p-8 text-center">
              <p className="text-sm text-text-muted">Loading...</p>
            </div>
          ) : sessions.length === 0 ? (
            <div className="glass rounded-2xl p-8 text-center space-y-3">
              <MessageSquare className="w-10 h-10 text-text-muted mx-auto" />
              <p className="text-sm text-text-muted">No chat sessions yet</p>
              <Link
                to="/chat"
                className="inline-flex items-center gap-2 text-xs font-medium text-violet-400 hover:text-violet-300"
              >
                Start your first chat <ArrowRight className="w-3 h-3" />
              </Link>
            </div>
          ) : (
            <div className="space-y-2 stagger-children">
              {sessions.slice(0, 5).map((session) => (
                <Link
                  key={session.id}
                  to={`/chat/${session.id}`}
                  className="flex items-center gap-3 p-3.5 glass glass-hover rounded-xl transition-all animate-fade-in group"
                >
                  <div className="w-8 h-8 rounded-lg bg-cyan-500/10 flex items-center justify-center flex-shrink-0">
                    <MessageSquare className="w-4 h-4 text-cyan-400" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-text-secondary group-hover:text-white truncate transition-colors">
                      {session.title || 'Untitled chat'}
                    </p>
                    <p className="text-[11px] text-text-muted mt-0.5">
                      {new Date(session.created_at).toLocaleDateString()}
                    </p>
                  </div>
                </Link>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
