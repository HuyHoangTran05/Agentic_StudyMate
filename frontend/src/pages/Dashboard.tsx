import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  ArrowRight,
  Activity,
  Bot,
  BrainCircuit,
  Clock,
  Database,
  FileSearch,
  FileText,
  FlaskConical,
  GitBranch,
  Image,
  MessageSquare,
  Search,
  Sparkles,
  Upload,
} from 'lucide-react'
import { getChatSessions, getDocuments } from '../lib/api'
import type { ChatSession, Document } from '../lib/api'
import { Badge, Card, PageHeader, PageShell } from '../components/ui'
import { cx } from '../lib/cx'

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

  const readyDocs = docs.filter((doc) => doc.status === 'ready').length
  const imageDocs = docs.filter((doc) => doc.image_url || doc.file_type === 'image').length
  const totalChunks = docs.reduce((sum, doc) => sum + doc.total_chunks, 0)

  const stats = [
    { label: 'Indexed Documents', value: docs.length, icon: FileText, tone: 'violet', meta: 'Library total' },
    { label: 'Ready to Chat', value: readyDocs, icon: MessageSquare, tone: 'cyan', meta: 'Queryable now' },
    { label: 'Chat Sessions', value: sessions.length, icon: Clock, tone: 'neutral', meta: 'All time' },
    { label: 'Text Chunks', value: totalChunks, icon: Database, tone: 'emerald', meta: `${imageDocs} image source${imageDocs === 1 ? '' : 's'}` },
  ] as const

  const capabilities = [
    {
      title: 'Hybrid Retrieval',
      desc: 'Dense and keyword search combine for precise document recall.',
      icon: Search,
      tone: 'violet',
    },
    {
      title: 'Graph-Aware Reasoning',
      desc: 'Agent steps connect themes across sources and sessions.',
      icon: GitBranch,
      tone: 'cyan',
    },
    {
      title: 'Vision Ingestion',
      desc: 'PNG and JPG uploads are extracted, indexed, and cited.',
      icon: Image,
      tone: 'cyan',
    },
    {
      title: 'Study Generation',
      desc: 'Quizzes, flashcards, and summaries stay tied to your library.',
      icon: FlaskConical,
      tone: 'violet',
    },
  ] as const

  const quickActions = [
    { label: 'Upload Document', icon: Upload, to: '/upload', desc: 'Index PDF, DOCX, TXT, PNG, or JPG.' },
    { label: 'Start Chat', icon: MessageSquare, to: '/chat', desc: 'Ask cited questions across your sources.' },
    { label: 'Study Tools', icon: FlaskConical, to: '/study-tools', desc: 'Generate quiz, flashcard, or summary sets.' },
    { label: 'Graph Explorer', icon: GitBranch, to: '/graph', desc: 'Inspect Neo4j entity relationships.' },
    { label: 'System Status', icon: Activity, to: '/system', desc: 'Check API, databases, and model configuration.' },
  ]

  return (
    <PageShell wide className="space-y-8">
      <PageHeader
        icon={BrainCircuit}
        eyebrow="System Active"
        title="Agentic Multimodal RAG"
        description="A focused AI study workspace for uploading course materials, asking cited questions, and turning sources into practice tools."
        action={
          <Link
            to="/upload"
            className="inline-flex items-center gap-2 rounded-lg gradient-bg px-4 py-2.5 text-sm font-semibold text-surface-950 shadow-[0_0_32px_rgba(76,215,246,0.16)] transition-all hover:opacity-95"
          >
            Add Source
            <ArrowRight className="h-4 w-4" />
          </Link>
        }
      />

      <Card className="relative overflow-hidden p-6 md:p-8">
        <div className="absolute inset-0 surface-grid opacity-30" />
        <div className="relative grid gap-6 lg:grid-cols-[1fr_280px] lg:items-center">
          <div>
            <Badge tone="cyan" className="mb-4">
              <span className="h-1.5 w-1.5 rounded-full bg-accent-cyan agent-pulse" />
              Knowledge base online
            </Badge>
            <h2 className="font-display text-3xl font-bold text-white md:text-5xl">
              Precision study intelligence, grounded in your own materials.
            </h2>
            <p className="mt-4 max-w-3xl text-sm leading-6 text-text-secondary md:text-base">
              StudyMate keeps retrieval, citations, multimodal upload, and study generation in one calm command center.
            </p>
          </div>
          <div className="rounded-2xl border border-white/10 bg-black/24 p-4">
            <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-white">
              <Bot className="h-4 w-4 text-accent-cyan" />
              Agent Stack
            </div>
            <div className="space-y-2">
              {['Vector search', 'BM25 recall', 'Cited streaming', 'Vision extraction'].map((item) => (
                <div key={item} className="flex items-center justify-between rounded-lg bg-white/[0.035] px-3 py-2 text-sm text-text-secondary">
                  <span>{item}</span>
                  <span className="h-1.5 w-1.5 rounded-full bg-accent-cyan" />
                </div>
              ))}
            </div>
          </div>
        </div>
      </Card>

      <section className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {stats.map(({ label, value, icon: Icon, tone, meta }, index) => (
          <Card key={label} className={cx('p-5 animate-fade-in', index === 1 && 'border-l-2 border-l-accent-cyan')}>
            <div className="mb-5 flex items-center justify-between">
              <div className={cx(
                'flex h-10 w-10 items-center justify-center rounded-lg',
                tone === 'cyan' ? 'bg-accent-cyan/10 text-accent-cyan' :
                  tone === 'emerald' ? 'bg-emerald-400/10 text-accent-emerald' :
                    tone === 'violet' ? 'bg-accent-violet/10 text-accent-violet' : 'bg-white/[0.05] text-text-muted',
              )}>
                <Icon className="h-5 w-5" />
              </div>
              <span className="text-[11px] font-medium text-text-muted">{meta}</span>
            </div>
            <p className="font-display text-3xl font-semibold text-white">
              {loading ? '-' : value.toLocaleString()}
            </p>
            <p className="mt-1 text-sm text-text-secondary">{label}</p>
          </Card>
        ))}
      </section>

      <section className="grid gap-6 lg:grid-cols-[1fr_360px]">
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="font-display text-2xl font-semibold text-white">Engine Capabilities</h2>
            <Badge tone="violet">
              <Sparkles className="h-3.5 w-3.5" />
              Agentic
            </Badge>
          </div>
          <div className="grid gap-4 md:grid-cols-2">
            {capabilities.map(({ title, desc, icon: Icon, tone }) => (
              <Card key={title} interactive className="p-4">
                <div className="flex gap-4">
                  <div className={cx(
                    'flex h-12 w-12 shrink-0 items-center justify-center rounded-lg',
                    tone === 'cyan' ? 'bg-accent-cyan/10 text-accent-cyan' : 'bg-accent-violet/10 text-accent-violet',
                  )}>
                    <Icon className="h-5 w-5" />
                  </div>
                  <div>
                    <h3 className="text-sm font-semibold text-white">{title}</h3>
                    <p className="mt-1 text-sm leading-5 text-text-secondary">{desc}</p>
                  </div>
                </div>
              </Card>
            ))}
          </div>
        </div>

        <div className="space-y-6">
          <div>
            <h2 className="mb-4 font-display text-2xl font-semibold text-white">Quick Actions</h2>
            <div className="space-y-3">
              {quickActions.map(({ label, icon: Icon, to, desc }) => (
                <Link
                  key={to}
                  to={to}
                  className="group flex items-center gap-3 rounded-xl border border-white/10 bg-white/[0.035] p-3 transition-all hover:border-accent-violet/30 hover:bg-white/[0.06]"
                >
                  <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-white/[0.04] text-accent-violet transition-transform group-hover:scale-105">
                    <Icon className="h-5 w-5" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-semibold text-white">{label}</p>
                    <p className="truncate text-xs text-text-muted">{desc}</p>
                  </div>
                  <ArrowRight className="h-4 w-4 text-text-muted transition-transform group-hover:translate-x-0.5 group-hover:text-accent-cyan" />
                </Link>
              ))}
            </div>
          </div>

          <Card className="p-5">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-sm font-semibold uppercase text-text-secondary">Recent Activity</h2>
              <Badge tone="neutral">{sessions.length}</Badge>
            </div>
            {loading ? (
              <p className="text-sm text-text-muted">Loading sessions...</p>
            ) : sessions.length === 0 ? (
              <div className="rounded-xl border border-white/10 bg-white/[0.03] p-5 text-center">
                <FileSearch className="mx-auto mb-3 h-8 w-8 text-text-muted" />
                <p className="text-sm text-text-secondary">No chat sessions yet.</p>
                <Link to="/chat" className="mt-3 inline-flex items-center gap-1 text-xs font-semibold text-accent-cyan">
                  Start first chat
                  <ArrowRight className="h-3.5 w-3.5" />
                </Link>
              </div>
            ) : (
              <div className="space-y-3">
                {sessions.slice(0, 5).map((session) => (
                  <Link key={session.id} to={`/chat/${session.id}`} className="flex items-start gap-3 rounded-lg p-2 transition-colors hover:bg-white/[0.04]">
                    <Clock className="mt-0.5 h-4 w-4 shrink-0 text-text-muted" />
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium text-white">{session.title || 'Untitled chat'}</p>
                      <p className="mt-0.5 text-xs text-text-muted">{new Date(session.created_at).toLocaleDateString()}</p>
                    </div>
                  </Link>
                ))}
              </div>
            )}
          </Card>
        </div>
      </section>
    </PageShell>
  )
}
