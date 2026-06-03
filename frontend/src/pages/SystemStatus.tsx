import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  Activity,
  AlertCircle,
  ArrowRight,
  BrainCircuit,
  CheckCircle2,
  Cpu,
  Database,
  FileText,
  GitBranch,
  HardDrive,
  Loader2,
  Network,
  RefreshCw,
  Server,
} from 'lucide-react'
import { Badge, Button, Card, EmptyState, LoadingState, PageHeader, PageShell } from '../components/ui'
import { getSystemStatus } from '../lib/api'
import type { SystemServiceStatus, SystemStatus } from '../lib/api'
import { cx } from '../lib/cx'

const statusTone: Record<SystemServiceStatus, 'emerald' | 'amber' | 'rose' | 'neutral' | 'cyan'> = {
  ok: 'emerald',
  configured: 'emerald',
  warning: 'amber',
  error: 'rose',
  not_configured: 'neutral',
}

const statusLabel: Record<SystemServiceStatus, string> = {
  ok: 'OK',
  configured: 'Configured',
  warning: 'Warning',
  error: 'Error',
  not_configured: 'Not configured',
}

function getOverallStatus(status: SystemStatus): SystemServiceStatus {
  const statuses = [
    status.api.status,
    status.database.status,
    status.qdrant.status,
    status.neo4j.status,
    status.llm.status,
  ]

  if (statuses.includes('error')) return 'error'
  if (statuses.includes('warning') || statuses.includes('not_configured')) return 'warning'
  return 'ok'
}

function formatNumber(value: number | null | undefined) {
  return typeof value === 'number' ? value.toLocaleString() : '-'
}

export default function SystemStatusPage() {
  const [status, setStatus] = useState<SystemStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const loadStatus = useCallback(async () => {
    setError(null)
    setRefreshing(true)
    try {
      const data = await getSystemStatus()
      setStatus(data)
    } catch (err) {
      console.error(err)
      setError(err instanceof Error ? err.message : 'Unable to load system status.')
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [])

  useEffect(() => {
    loadStatus().catch(console.error)
  }, [loadStatus])

  const overallStatus = status ? getOverallStatus(status) : 'warning'

  const services = useMemo(() => {
    if (!status) return []
    return [
      {
        title: 'Backend API',
        icon: Server,
        status: status.api.status,
        detail: 'FastAPI service',
        meta: 'GET /api/system/status',
        error: status.api.error,
      },
      {
        title: 'SQLite',
        icon: Database,
        status: status.database.status,
        detail: `${formatNumber(status.database.documents)} documents, ${formatNumber(status.database.chunks)} chunks`,
        meta: 'Metadata database',
        error: status.database.error,
      },
      {
        title: 'Qdrant',
        icon: Network,
        status: status.qdrant.status,
        detail: `${status.qdrant.host}:${status.qdrant.port}`,
        meta: status.qdrant.collection,
        error: status.qdrant.error,
      },
      {
        title: 'Neo4j',
        icon: GitBranch,
        status: status.neo4j.status,
        detail: status.neo4j.uri,
        meta: 'Graph relationships',
        error: status.neo4j.error,
        action: { to: '/graph', label: 'Open graph' },
      },
      {
        title: 'LLM',
        icon: BrainCircuit,
        status: status.llm.status,
        detail: status.llm.provider ?? 'No provider',
        meta: status.llm.text_model,
        error: status.llm.error,
      },
      {
        title: 'Embedding / Reranker',
        icon: Cpu,
        status: 'configured' as SystemServiceStatus,
        detail: status.models.embedding_model,
        meta: status.models.reranker_model,
      },
    ]
  }, [status])

  const dataCards = status
    ? [
        { label: 'Documents', value: status.database.documents, icon: FileText, tone: 'violet' },
        { label: 'Ready documents', value: status.database.ready_documents, icon: CheckCircle2, tone: 'emerald' },
        { label: 'Processing', value: status.database.processing_documents, icon: Loader2, tone: 'amber' },
        { label: 'Failed', value: status.database.failed_documents, icon: AlertCircle, tone: 'rose' },
        { label: 'Chunks', value: status.database.chunks, icon: Database, tone: 'cyan' },
        { label: 'Qdrant points', value: status.qdrant.points, icon: HardDrive, tone: 'cyan' },
        { label: 'Neo4j triplets', value: status.neo4j.triplets, icon: GitBranch, tone: 'violet' },
      ]
    : []

  return (
    <PageShell wide className="space-y-8">
      <PageHeader
        icon={Activity}
        eyebrow="Diagnostics"
        title="System Status"
        description="Monitor local RAG services and data readiness."
        action={
          <Button variant="ghost" onClick={() => loadStatus()} disabled={refreshing}>
            {refreshing ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
            Refresh
          </Button>
        }
      />

      {loading ? (
        <LoadingState label="Checking system status..." />
      ) : error ? (
        <EmptyState
          icon={AlertCircle}
          title="Unable to load system status"
          description={error}
          action={
            <Button variant="ghost" onClick={() => loadStatus()} disabled={refreshing}>
              Try again
            </Button>
          }
        />
      ) : status ? (
        <>
          <Card className="relative overflow-hidden p-5 md:p-6">
            <div className="absolute inset-0 surface-grid opacity-25" />
            <div className="relative flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
              <div>
                <Badge tone={statusTone[overallStatus]} className="mb-3">
                  {statusLabel[overallStatus]}
                </Badge>
                <h2 className="font-display text-2xl font-semibold text-white">
                  {overallStatus === 'ok' ? 'All core services are healthy' : 'Some services need attention'}
                </h2>
                <p className="mt-2 text-sm text-text-secondary">
                  API, metadata, vector search, graph search, and model configuration are checked independently.
                </p>
              </div>
              <div className="grid grid-cols-2 gap-2 text-sm md:grid-cols-3">
                <MiniStatus label="API" status={status.api.status} />
                <MiniStatus label="Qdrant" status={status.qdrant.status} />
                <MiniStatus label="Neo4j" status={status.neo4j.status} />
              </div>
            </div>
          </Card>

          <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {services.map((service) => (
              <ServiceCard key={service.title} {...service} />
            ))}
          </section>

          <section className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            {dataCards.map(({ label, value, icon: Icon, tone }) => (
              <Card key={label} className="p-5">
                <div className="mb-4 flex items-center justify-between">
                  <div className={cx(
                    'flex h-10 w-10 items-center justify-center rounded-lg',
                    tone === 'emerald' && 'bg-emerald-400/10 text-accent-emerald',
                    tone === 'amber' && 'bg-amber-300/10 text-accent-amber',
                    tone === 'rose' && 'bg-rose-300/10 text-accent-rose',
                    tone === 'cyan' && 'bg-accent-cyan/10 text-accent-cyan',
                    tone === 'violet' && 'bg-accent-violet/10 text-accent-violet',
                  )}>
                    <Icon className={cx('h-5 w-5', label === 'Processing' && Number(value) > 0 && 'animate-spin')} />
                  </div>
                </div>
                <p className="font-display text-3xl font-semibold text-white">{formatNumber(value)}</p>
                <p className="mt-1 text-sm text-text-secondary">{label}</p>
              </Card>
            ))}
          </section>
        </>
      ) : null}
    </PageShell>
  )
}

function MiniStatus({ label, status }: { label: string; status: SystemServiceStatus }) {
  return (
    <div className="rounded-xl border border-white/10 bg-white/[0.035] px-3 py-2">
      <p className="text-[11px] text-text-muted">{label}</p>
      <Badge tone={statusTone[status]} className="mt-1">
        {statusLabel[status]}
      </Badge>
    </div>
  )
}

function ServiceCard({
  title,
  icon: Icon,
  status,
  detail,
  meta,
  error,
  action,
}: {
  title: string
  icon: typeof Server
  status: SystemServiceStatus
  detail: string
  meta: string
  error?: string
  action?: { to: string; label: string }
}) {
  return (
    <Card interactive className="p-5">
      <div className="mb-4 flex items-start justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-lg bg-white/[0.04] text-accent-cyan">
            <Icon className="h-5 w-5" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-white">{title}</h3>
            <p className="mt-1 text-xs text-text-muted">{meta}</p>
          </div>
        </div>
        <Badge tone={statusTone[status]}>{statusLabel[status]}</Badge>
      </div>
      <p className="break-words text-sm leading-5 text-text-secondary">{detail}</p>
      {error && (
        <p className="mt-3 rounded-lg border border-rose-300/15 bg-rose-300/[0.055] px-3 py-2 text-xs leading-5 text-accent-rose">
          {error}
        </p>
      )}
      {action && (
        <Link
          to={action.to}
          className="mt-4 inline-flex items-center gap-1.5 text-xs font-semibold text-accent-cyan transition-colors hover:text-white"
        >
          {action.label}
          <ArrowRight className="h-3.5 w-3.5" />
        </Link>
      )}
    </Card>
  )
}
