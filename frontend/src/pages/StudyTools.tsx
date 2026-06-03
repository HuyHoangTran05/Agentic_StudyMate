import { useCallback, useEffect, useMemo } from 'react'
import {
  BrainCircuit,
  FileText as FileTextIcon,
  FlaskConical,
  Layers,
  Loader2,
  RefreshCw,
  Sparkles,
} from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import FlashcardViewer from '../components/FlashcardViewer'
import QuizWidget from '../components/QuizWidget'
import { Badge, Button, Card, EmptyState, LoadingState, PageHeader, PageShell } from '../components/ui'
import SelectDropdown from '../components/ui/SelectDropdown'
import { cx } from '../lib/cx'
import { useStudyToolsStore } from '../stores/studyToolsStore'
import type { SummaryResponse } from '../lib/api'
import type { StudyToolType } from '../stores/studyToolsStore'

const tools: { id: StudyToolType; label: string; icon: typeof BrainCircuit; desc: string }[] = [
  { id: 'quiz', label: 'Quiz', icon: BrainCircuit, desc: 'Multiple-choice practice' },
  { id: 'flashcards', label: 'Flashcards', icon: Layers, desc: 'Flip cards for recall' },
  { id: 'summary', label: 'Summary', icon: FileTextIcon, desc: 'Overview and key points' },
]

export default function StudyTools() {
  const {
    documents,
    allDocuments,
    selectedDoc,
    activeTool,
    numItems,
    isLoadingDocuments,
    isGenerating,
    error,
    quizData,
    flashcardsData,
    summaryData,
    setSelectedDoc,
    setActiveTool,
    setNumItems,
    refreshDocuments,
    generateCurrentTool,
  } = useStudyToolsStore()

  const processingCount = allDocuments.filter((doc) => doc.status === 'processing').length
  const hasProcessingDocuments = processingCount > 0

  const loadDocuments = useCallback(() => {
    refreshDocuments().catch(console.error)
  }, [refreshDocuments])

  useEffect(() => {
    void Promise.resolve().then(loadDocuments)
  }, [loadDocuments])

  useEffect(() => {
    const handleFocus = () => loadDocuments()
    window.addEventListener('focus', handleFocus)
    return () => window.removeEventListener('focus', handleFocus)
  }, [loadDocuments])

  useEffect(() => {
    if (!hasProcessingDocuments) return

    const intervalId = window.setInterval(loadDocuments, 3500)
    return () => window.clearInterval(intervalId)
  }, [hasProcessingDocuments, loadDocuments])

  const documentOptions = useMemo(
    () =>
      documents.map((doc) => ({
        value: doc.id,
        label: doc.file_name,
        description: `${doc.total_chunks} chunks`,
      })),
    [documents],
  )

  const selectedDocIsReady = documents.some((doc) => doc.id === selectedDoc)

  return (
    <PageShell className="space-y-8">
      <PageHeader
        icon={FlaskConical}
        eyebrow="Study Lab"
        title="Study Tools"
        description="Generate quiz questions, flashcards, and summaries from ready documents in your library."
        action={
          <Button variant="ghost" onClick={loadDocuments} disabled={isLoadingDocuments}>
            {isLoadingDocuments ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
            Refresh
          </Button>
        }
      />

      {isLoadingDocuments && allDocuments.length === 0 ? (
        <LoadingState label="Loading documents..." />
      ) : (
        <>
          {hasProcessingDocuments && (
            <Card className="border-amber-300/20 p-4">
              <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <p className="text-sm font-semibold text-white">Documents are still processing. Please wait or refresh.</p>
                  <p className="mt-1 text-xs text-text-muted">
                    {processingCount} document{processingCount === 1 ? '' : 's'} still being indexed for study tools.
                  </p>
                </div>
                <Badge tone="amber">Polling</Badge>
              </div>
            </Card>
          )}

          {documents.length === 0 ? (
            <EmptyState
              icon={FileTextIcon}
              title="No ready documents yet"
              description={
                hasProcessingDocuments
                  ? 'Documents are still processing. Please wait or refresh.'
                  : 'Upload a document first, then return here when it is ready.'
              }
              action={
                <Button variant="ghost" onClick={loadDocuments} disabled={isLoadingDocuments}>
                  {isLoadingDocuments ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
                  Refresh documents
                </Button>
              }
            />
          ) : (
            <StudyToolsPanel
              documentOptions={documentOptions}
              selectedDoc={selectedDoc}
              activeTool={activeTool}
              numItems={numItems}
              isGenerating={isGenerating}
              selectedDocIsReady={selectedDocIsReady}
              error={error}
              setSelectedDoc={setSelectedDoc}
              setActiveTool={setActiveTool}
              setNumItems={setNumItems}
              generateCurrentTool={generateCurrentTool}
            />
          )}
        </>
      )}

      {!quizData && !flashcardsData && !summaryData && documents.length > 0 && (
        <EmptyState
          icon={Sparkles}
          title="Generated study material will appear here"
          description="Choose a ready document, select a tool, then generate your practice set."
        />
      )}

      {quizData && (
        <div className="animate-fade-in">
          <QuizWidget questions={quizData} />
        </div>
      )}

      {flashcardsData && (
        <div className="animate-fade-in">
          <FlashcardViewer flashcards={flashcardsData} />
        </div>
      )}

      {summaryData && <SummaryResult summaryData={summaryData} />}
    </PageShell>
  )
}

function StudyToolsPanel({
  documentOptions,
  selectedDoc,
  activeTool,
  numItems,
  isGenerating,
  selectedDocIsReady,
  error,
  setSelectedDoc,
  setActiveTool,
  setNumItems,
  generateCurrentTool,
}: {
  documentOptions: Array<{ value: string; label: string; description: string }>
  selectedDoc: string
  activeTool: StudyToolType
  numItems: number
  isGenerating: boolean
  selectedDocIsReady: boolean
  error: string | null
  setSelectedDoc: (documentId: string) => void
  setActiveTool: (tool: StudyToolType) => void
  setNumItems: (count: number) => void
  generateCurrentTool: () => Promise<void>
}) {
  return (
    <Card className="p-5 md:p-6">
      <div className="grid gap-6 lg:grid-cols-[1fr_300px]">
        <div className="space-y-6">
          <SelectDropdown
            label="Select ready document"
            value={selectedDoc}
            options={documentOptions}
            onChange={setSelectedDoc}
            placeholder="Choose a ready document..."
            disabled={isGenerating}
          />

          <div>
            <div className="mb-3 flex items-center justify-between">
              <label className="block text-xs font-medium text-text-muted">Tool type</label>
              <Badge tone="violet">{activeTool}</Badge>
            </div>
            <div className="grid gap-3 sm:grid-cols-3">
              {tools.map(({ id, label, icon: Icon, desc }) => (
                <button
                  key={id}
                  disabled={isGenerating}
                  onClick={() => setActiveTool(id)}
                  className={cx(
                    'rounded-xl border p-4 text-left transition-all',
                    activeTool === id
                      ? 'border-accent-cyan/35 bg-accent-cyan/10 text-white'
                      : 'border-white/10 bg-white/[0.025] text-text-secondary hover:border-accent-violet/28 hover:bg-white/[0.05]',
                  )}
                >
                  <Icon className={cx('mb-3 h-5 w-5', activeTool === id ? 'text-accent-cyan' : 'text-text-muted')} />
                  <p className="text-sm font-semibold">{label}</p>
                  <p className="mt-1 text-xs leading-5 text-text-muted">{desc}</p>
                </button>
              ))}
            </div>
          </div>

          {activeTool !== 'summary' && (
            <div>
              <div className="mb-2 flex items-center justify-between">
                <label className="text-xs font-medium text-text-muted">Number of items</label>
                <Badge tone="neutral">{numItems}</Badge>
              </div>
              <input
                type="range"
                min={3}
                max={15}
                value={numItems}
                onChange={(event) => setNumItems(Number(event.target.value))}
                disabled={isGenerating}
                className="w-full accent-accent-cyan"
              />
              <div className="mt-1 flex justify-between text-xs text-text-muted">
                <span>3</span>
                <span>15</span>
              </div>
            </div>
          )}
        </div>

        <div className="rounded-2xl border border-white/10 bg-black/20 p-4">
          <div className="mb-4 flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-accent-cyan" />
            <h2 className="text-sm font-semibold text-white">Generation Control</h2>
          </div>
          <p className="mb-5 text-sm leading-6 text-text-secondary">
            Results stay on this page so you can switch between source material and generated practice quickly.
          </p>
          <Button
            onClick={generateCurrentTool}
            disabled={!selectedDoc || !selectedDocIsReady || isGenerating}
            className="w-full"
          >
            {isGenerating ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Generating...
              </>
            ) : (
              <>
                <Sparkles className="h-4 w-4" />
                Generate {activeTool === 'quiz' ? 'Quiz' : activeTool === 'flashcards' ? 'Flashcards' : 'Summary'}
              </>
            )}
          </Button>
          {!selectedDocIsReady && (
            <p className="mt-4 text-sm text-text-muted">Select a ready document before generating study tools.</p>
          )}
          {error && <p className="mt-4 text-sm text-accent-rose">{error}</p>}
        </div>
      </div>
    </Card>
  )
}

function SummaryResult({ summaryData }: { summaryData: SummaryResponse }) {
  return (
    <Card className="space-y-6 p-6 animate-fade-in">
      <div className="flex items-center justify-between">
        <h2 className="font-display text-xl font-semibold text-white">Summary</h2>
        <Badge tone="cyan">{summaryData.key_points.length} key points</Badge>
      </div>
      <div className="markdown-content">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{summaryData.summary}</ReactMarkdown>
      </div>

      {summaryData.key_points.length > 0 && (
        <div className="space-y-3 border-t border-white/10 pt-5">
          <h3 className="flex items-center gap-2 text-sm font-semibold text-white">
            <Sparkles className="h-4 w-4 text-accent-amber" />
            Key Points
          </h3>
          <ul className="space-y-2">
            {summaryData.key_points.map((point, index) => (
              <li key={index} className="flex items-start gap-3 text-sm leading-6 text-text-secondary">
                <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-lg bg-accent-violet/10 text-xs font-semibold text-accent-violet">
                  {index + 1}
                </span>
                {point}
              </li>
            ))}
          </ul>
        </div>
      )}
    </Card>
  )
}
