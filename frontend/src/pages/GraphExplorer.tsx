import { useCallback, useEffect, useMemo, useState } from 'react'
import type { FormEvent } from 'react'
import {
  AlertCircle,
  Database,
  FileText,
  GitBranch,
  Info,
  Loader2,
  Network,
  RefreshCw,
  Search,
  Sigma,
  Waypoints,
} from 'lucide-react'
import { Badge, Button, Card, EmptyState, LoadingState, PageHeader, PageShell } from '../components/ui'
import SelectDropdown from '../components/ui/SelectDropdown'
import { getDocuments, getGraphTriplets, rebuildDocumentGraph } from '../lib/api'
import type { Document, GraphTriplet } from '../lib/api'

const limitOptions = [
  { value: '50', label: '50 triplets' },
  { value: '100', label: '100 triplets' },
  { value: '250', label: '250 triplets' },
  { value: '500', label: '500 triplets' },
]

function pageLabel(page: number | null) {
  return typeof page === 'number' ? `Page ${page}` : 'No page'
}

function displayValue(value: string | null | undefined, fallback = '-') {
  return value && value.trim() ? value : fallback
}

type RebuildNotice = {
  tone: 'emerald' | 'amber' | 'rose'
  message: string
  detail?: string
} | null

export default function GraphExplorer() {
  const [documents, setDocuments] = useState<Document[]>([])
  const [triplets, setTriplets] = useState<GraphTriplet[]>([])
  const [searchInput, setSearchInput] = useState('')
  const [query, setQuery] = useState('')
  const [documentId, setDocumentId] = useState('')
  const [limit, setLimit] = useState(100)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [rebuilding, setRebuilding] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [graphMessage, setGraphMessage] = useState<string | null>(null)
  const [rebuildNotice, setRebuildNotice] = useState<RebuildNotice>(null)

  const documentOptions = useMemo(
    () => [
      { value: '', label: 'All documents', description: 'No document filter' },
      ...documents.map((doc) => ({
        value: doc.id,
        label: doc.file_name,
        description: `${doc.status} | ${doc.total_chunks.toLocaleString()} chunks`,
        disabled: doc.status === 'failed',
      })),
    ],
    [documents],
  )

  const loadDocuments = useCallback(async () => {
    try {
      const data = await getDocuments()
      setDocuments(data.documents)
    } catch (err) {
      console.error(err)
    }
  }, [])

  const loadTriplets = useCallback(async () => {
    setError(null)
    setGraphMessage(null)
    setRefreshing(true)
    try {
      const data = await getGraphTriplets({
        q: query || undefined,
        document_id: documentId || undefined,
        limit,
      })
      setTriplets(data.triplets)
      setGraphMessage(data.message || null)
      if (data.status === 'error') {
        setError(data.message || 'Neo4j is unavailable. Start Neo4j and refresh.')
      }
    } catch (err) {
      console.error(err)
      setTriplets([])
      setError(err instanceof Error ? err.message : 'Unable to load graph triplets.')
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [documentId, limit, query])

  useEffect(() => {
    loadDocuments().catch(console.error)
  }, [loadDocuments])

  useEffect(() => {
    loadTriplets().catch(console.error)
  }, [loadTriplets])

  const stats = useMemo(() => {
    const sources = new Set(triplets.map((item) => item.source).filter(Boolean))
    const relations = new Set(triplets.map((item) => item.relation).filter(Boolean))
    const targets = new Set(triplets.map((item) => item.target).filter(Boolean))
    return [
      { label: 'Triplets loaded', value: triplets.length, icon: GitBranch, tone: 'violet' },
      { label: 'Unique sources', value: sources.size, icon: Waypoints, tone: 'cyan' },
      { label: 'Relations', value: relations.size, icon: Sigma, tone: 'emerald' },
      { label: 'Unique targets', value: targets.size, icon: Network, tone: 'amber' },
    ] as const
  }, [triplets])

  const selectedDocument = useMemo(
    () => documents.find((doc) => doc.id === documentId) ?? null,
    [documentId, documents],
  )

  const handleSearch = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setQuery(searchInput.trim())
  }

  const handleRebuildGraph = useCallback(async () => {
    if (!selectedDocument || rebuilding) return

    setRebuilding(true)
    setRebuildNotice(null)
    try {
      const data = await rebuildDocumentGraph(selectedDocument.id)
      const tone = data.status === 'error' ? 'rose' : data.status === 'warning' ? 'amber' : 'emerald'
      setRebuildNotice({
        tone,
        message: data.message,
        detail: `${data.chunks_processed.toLocaleString()} chunk${data.chunks_processed === 1 ? '' : 's'} checked for ${data.file_name}.`,
      })

      if (data.status === 'ok' || data.status === 'queued') {
        window.setTimeout(() => {
          loadTriplets().catch(console.error)
        }, 3500)
      }
    } catch (err) {
      const responseMessage = (err as { response?: { data?: { detail?: string; message?: string } } }).response?.data
      setRebuildNotice({
        tone: 'rose',
        message: responseMessage?.message || responseMessage?.detail || 'Unable to start knowledge graph rebuild.',
      })
    } finally {
      setRebuilding(false)
    }
  }, [loadTriplets, rebuilding, selectedDocument])

  return (
    <PageShell wide className="space-y-8">
      <PageHeader
        icon={GitBranch}
        eyebrow="GraphRAG"
        title="Graph Explorer"
        description="Inspect entity relationships extracted from your documents."
        action={
          <Button variant="ghost" onClick={() => loadTriplets()} disabled={refreshing}>
            {refreshing ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
            Refresh
          </Button>
        }
      />

      <Card className="p-4 md:p-5">
        <form onSubmit={handleSearch} className="grid gap-3 lg:grid-cols-[1fr_260px_170px_auto] lg:items-end">
          <label className="block">
            <span className="mb-2 block text-xs font-medium text-text-muted">Search graph</span>
            <div className="field-surface flex items-center gap-2 rounded-xl px-3 py-2.5">
              <Search className="h-4 w-4 shrink-0 text-text-muted" />
              <input
                value={searchInput}
                onChange={(event) => setSearchInput(event.target.value)}
                placeholder="Search entities or relations..."
                className="min-w-0 flex-1 bg-transparent text-sm text-white outline-none placeholder:text-text-muted"
              />
            </div>
          </label>

          <SelectDropdown
            label="Document"
            value={documentId}
            options={documentOptions}
            onChange={setDocumentId}
            placeholder="All documents"
          />

          <SelectDropdown
            label="Limit"
            value={String(limit)}
            options={limitOptions}
            onChange={(value) => setLimit(Number(value))}
            placeholder="100 triplets"
          />

          <Button type="submit" variant="secondary" className="w-full lg:w-auto">
            <Search className="h-4 w-4" />
            Search
          </Button>
        </form>

        {selectedDocument && (
          <div className="mt-4 flex flex-col gap-3 rounded-xl border border-white/10 bg-white/[0.025] p-3 md:flex-row md:items-center md:justify-between">
            <div className="min-w-0">
              <p className="truncate text-sm font-semibold text-white">{selectedDocument.file_name}</p>
              <p className="mt-1 text-xs leading-5 text-text-muted">
                Use this if the document was uploaded before Neo4j was configured or if graph extraction failed.
              </p>
            </div>
            <Button
              type="button"
              variant="ghost"
              onClick={handleRebuildGraph}
              disabled={rebuilding}
              className="shrink-0"
            >
              {rebuilding ? <Loader2 className="h-4 w-4 animate-spin" /> : <GitBranch className="h-4 w-4" />}
              Rebuild Knowledge Graph
            </Button>
          </div>
        )}
      </Card>

      <section className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {stats.map(({ label, value, icon: Icon, tone }) => (
          <Card key={label} className="p-5">
            <div className="mb-4 flex items-center justify-between">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-white/[0.04] text-accent-cyan">
                <Icon className="h-5 w-5" />
              </div>
              <Badge tone={tone}>{label}</Badge>
            </div>
            <p className="font-display text-3xl font-semibold text-white">{value.toLocaleString()}</p>
          </Card>
        ))}
      </section>

      {graphMessage && !error && (
        <Card className="border-amber-300/20 bg-amber-300/[0.045] p-4">
          <div className="flex gap-3">
            <Info className="mt-0.5 h-4 w-4 shrink-0 text-accent-amber" />
            <p className="text-sm leading-6 text-text-secondary">{graphMessage}</p>
          </div>
        </Card>
      )}

      {rebuildNotice && (
        <Card className="p-4">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex gap-3">
              <Info className="mt-0.5 h-4 w-4 shrink-0 text-accent-cyan" />
              <div>
                <p className="text-sm font-medium text-white">{rebuildNotice.message}</p>
                {rebuildNotice.detail && (
                  <p className="mt-1 text-xs text-text-muted">{rebuildNotice.detail}</p>
                )}
              </div>
            </div>
            <Badge tone={rebuildNotice.tone}>
              {rebuildNotice.tone === 'emerald' ? 'Queued' : rebuildNotice.tone === 'amber' ? 'Warning' : 'Error'}
            </Badge>
          </div>
        </Card>
      )}

      {loading ? (
        <LoadingState label="Loading graph triplets..." />
      ) : error ? (
        <EmptyState
          icon={AlertCircle}
          title="Graph data unavailable"
          description={error}
          action={
            <Button variant="ghost" onClick={() => loadTriplets()} disabled={refreshing}>
              Try again
            </Button>
          }
        />
      ) : triplets.length === 0 && selectedDocument ? (
        <Card className="p-6 md:p-7">
          <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
            <div className="max-w-3xl">
              <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-accent-violet/10 text-accent-violet">
                <Database className="h-6 w-6" />
              </div>
              <Badge tone="amber" className="mb-3">0 triplets linked to this document</Badge>
              <h2 className="font-display text-2xl font-semibold text-white">
                No graph relationships found for this document
              </h2>
              <p className="mt-3 text-sm leading-6 text-text-secondary">
                Vector/BM25 retrieval may still work, but no Neo4j triplets were found for this file.
              </p>
              <div className="mt-5 rounded-xl border border-white/10 bg-white/[0.03] p-4">
                <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-white">
                  <FileText className="h-4 w-4 text-accent-cyan" />
                  {selectedDocument.file_name}
                </div>
                <ul className="space-y-2 text-sm leading-6 text-text-secondary">
                  <li>This document may have been uploaded before GraphRAG was enabled.</li>
                  <li>Neo4j may not have been configured or running during ingestion.</li>
                  <li>The document may not contain extractable text relationships.</li>
                  <li>Triplet extraction may have failed or returned no relationships.</li>
                  <li>Try uploading or re-ingesting the document again after Neo4j and LLM are configured.</li>
                </ul>
              </div>
            </div>
            <div className="flex flex-col gap-2 sm:flex-row lg:flex-col">
              <Button variant="secondary" onClick={handleRebuildGraph} disabled={rebuilding}>
                {rebuilding ? <Loader2 className="h-4 w-4 animate-spin" /> : <GitBranch className="h-4 w-4" />}
                Rebuild Knowledge Graph
              </Button>
              <Button variant="ghost" onClick={() => loadTriplets()} disabled={refreshing}>
                {refreshing ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
                Refresh
              </Button>
            </div>
          </div>
        </Card>
      ) : triplets.length === 0 ? (
        <EmptyState
          icon={Database}
          title="No graph triplets found"
          description="Upload and process documents, make sure Neo4j and the LLM are configured during ingestion, then refresh this page."
        />
      ) : (
        <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_420px]">
          <Card className="overflow-hidden">
            <div className="border-b border-white/10 px-5 py-4">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <h2 className="text-sm font-semibold text-white">Triplet Table</h2>
                  <p className="mt-1 text-xs text-text-muted">Source, relation, target, and originating document.</p>
                </div>
                <Badge tone="cyan">{triplets.length.toLocaleString()} loaded</Badge>
              </div>
            </div>
            <div className="overflow-x-auto">
              <table className="min-w-full text-left text-sm">
                <thead className="border-b border-white/10 bg-white/[0.025] text-xs uppercase text-text-muted">
                  <tr>
                    <th className="px-5 py-3 font-medium">Source</th>
                    <th className="px-5 py-3 font-medium">Relation</th>
                    <th className="px-5 py-3 font-medium">Target</th>
                    <th className="px-5 py-3 font-medium">File</th>
                    <th className="px-5 py-3 font-medium">Page</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/10">
                  {triplets.map((triplet, index) => (
                    <tr key={`${triplet.source}-${triplet.relation}-${triplet.target}-${triplet.chunk_id}-${index}`} className="hover:bg-white/[0.03]">
                      <td className="max-w-[220px] px-5 py-3 text-white">
                        <span className="line-clamp-2">{displayValue(triplet.source)}</span>
                      </td>
                      <td className="px-5 py-3">
                        <Badge tone="violet">{displayValue(triplet.relation)}</Badge>
                      </td>
                      <td className="max-w-[220px] px-5 py-3 text-text-secondary">
                        <span className="line-clamp-2">{displayValue(triplet.target)}</span>
                      </td>
                      <td className="max-w-[240px] px-5 py-3 text-text-secondary">
                        <span className="line-clamp-2">{displayValue(triplet.file_name)}</span>
                      </td>
                      <td className="px-5 py-3 text-text-muted">{pageLabel(triplet.page_number)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>

          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <h2 className="font-display text-xl font-semibold text-white">Relationship Cards</h2>
              <Badge tone="neutral">Compact view</Badge>
            </div>
            <div className="max-h-[760px] space-y-3 overflow-y-auto pr-1">
              {triplets.map((triplet, index) => (
                <Card key={`${triplet.chunk_id}-${index}`} className="p-4">
                  <div className="flex flex-wrap items-center gap-2 text-sm">
                    <span className="rounded-lg bg-accent-cyan/10 px-2.5 py-1 font-medium text-accent-cyan">
                      {displayValue(triplet.source)}
                    </span>
                    <span className="text-text-muted">-&gt;</span>
                    <Badge tone="violet">{displayValue(triplet.relation)}</Badge>
                    <span className="text-text-muted">-&gt;</span>
                    <span className="rounded-lg bg-white/[0.04] px-2.5 py-1 font-medium text-white">
                      {displayValue(triplet.target)}
                    </span>
                  </div>
                  <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-text-muted">
                    <FileText className="h-3.5 w-3.5" />
                    <span>{displayValue(triplet.file_name, 'Unknown document')}</span>
                    <span>|</span>
                    <span>{pageLabel(triplet.page_number)}</span>
                    {triplet.section_title && (
                      <>
                        <span>|</span>
                        <span>{triplet.section_title}</span>
                      </>
                    )}
                  </div>
                  {triplet.snippet && (
                    <details className="mt-3 rounded-lg border border-white/10 bg-white/[0.025] px-3 py-2">
                      <summary className="cursor-pointer text-xs font-medium text-text-secondary">Snippet preview</summary>
                      <p className="mt-2 text-xs leading-5 text-text-muted">{triplet.snippet}</p>
                    </details>
                  )}
                </Card>
              ))}
            </div>
          </div>
        </div>
      )}
    </PageShell>
  )
}
