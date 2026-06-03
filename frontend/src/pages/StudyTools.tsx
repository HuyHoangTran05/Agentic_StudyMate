import {
  BrainCircuit,
  FileText as FileTextIcon,
  FlaskConical,
  Layers,
  Loader2,
  Sparkles,
} from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import FlashcardViewer from '../components/FlashcardViewer'
import QuizWidget from '../components/QuizWidget'
import { Badge, Button, Card, EmptyState, PageHeader, PageShell } from '../components/ui'
import { cx } from '../lib/cx'
import { useStudyToolsStore } from '../stores/studyToolsStore'
import type { StudyToolType } from '../stores/studyToolsStore'

const tools: { id: StudyToolType; label: string; icon: typeof BrainCircuit; desc: string }[] = [
  { id: 'quiz', label: 'Quiz', icon: BrainCircuit, desc: 'Multiple-choice practice' },
  { id: 'flashcards', label: 'Flashcards', icon: Layers, desc: 'Flip cards for recall' },
  { id: 'summary', label: 'Summary', icon: FileTextIcon, desc: 'Overview and key points' },
]

export default function StudyTools() {
  const {
    documents,
    selectedDoc,
    activeTool,
    numItems,
    isGenerating,
    error,
    quizData,
    flashcardsData,
    summaryData,
    setSelectedDoc,
    setActiveTool,
    setNumItems,
    generateCurrentTool,
  } = useStudyToolsStore()

  return (
    <PageShell className="space-y-8">
      <PageHeader
        icon={FlaskConical}
        eyebrow="Study Lab"
        title="Study Tools"
        description="Generate quiz questions, flashcards, and summaries from ready documents in your library."
      />

      <Card className="p-5 md:p-6">
        <div className="grid gap-6 lg:grid-cols-[1fr_300px]">
          <div className="space-y-6">
            <div>
              <label className="mb-2 block text-xs font-medium text-text-muted">Select document</label>
              <div className="field-surface rounded-xl">
                <select
                  value={selectedDoc}
                  onChange={(event) => setSelectedDoc(event.target.value)}
                  disabled={isGenerating}
                  className="w-full rounded-xl bg-transparent px-4 py-3 text-sm text-white outline-none"
                >
                  <option value="" disabled>Choose a document...</option>
                  {documents.map((doc) => (
                    <option key={doc.id} value={doc.id}>{doc.file_name}</option>
                  ))}
                </select>
              </div>
            </div>

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
              disabled={!selectedDoc || isGenerating}
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
            {error && <p className="mt-4 text-sm text-accent-rose">{error}</p>}
            {documents.length === 0 && (
              <p className="mt-4 text-sm text-text-muted">Upload a ready document before generating study tools.</p>
            )}
          </div>
        </div>
      </Card>

      {!quizData && !flashcardsData && !summaryData && (
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

      {summaryData && (
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
      )}
    </PageShell>
  )
}
