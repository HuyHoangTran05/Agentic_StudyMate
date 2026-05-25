import {
  FlaskConical,
  BrainCircuit,
  Layers,
  FileText as FileTextIcon,
  Loader2,
  Sparkles,
} from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import QuizWidget from '../components/QuizWidget'
import FlashcardViewer from '../components/FlashcardViewer'
import { useStudyToolsStore } from '../stores/studyToolsStore'
import type { StudyToolType } from '../stores/studyToolsStore'

const tools: { id: StudyToolType; label: string; icon: typeof BrainCircuit; desc: string }[] = [
  { id: 'quiz', label: 'Quiz', icon: BrainCircuit, desc: 'Multiple-choice questions' },
  { id: 'flashcards', label: 'Flashcards', icon: Layers, desc: 'Study cards with flip animation' },
  { id: 'summary', label: 'Summary', icon: FileTextIcon, desc: 'Key points & overview' },
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
    <div className="p-6 md:p-8 max-w-5xl mx-auto space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-white flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl gradient-bg flex items-center justify-center shadow-lg shadow-violet-500/20">
            <FlaskConical className="w-5 h-5 text-white" />
          </div>
          Study Tools
        </h1>
        <p className="text-sm text-text-secondary mt-2 ml-[52px]">
          Generate quizzes, flashcards, and summaries from your documents.
        </p>
      </div>

      {/* Controls */}
      <div className="glass rounded-2xl p-6 space-y-6">
        {/* Document selector */}
        <div>
          <label className="text-xs font-medium text-text-muted uppercase tracking-wider mb-2 block">
            Select Document
          </label>
          <select
            value={selectedDoc}
            onChange={(e) => setSelectedDoc(e.target.value)}
            disabled={isGenerating}
            className="w-full bg-surface-700 border border-white/10 rounded-xl px-4 py-3 text-sm text-white outline-none focus:border-violet-500/50 transition-colors"
          >
            <option value="" disabled>Choose a document...</option>
            {documents.map((doc) => (
              <option key={doc.id} value={doc.id}>{doc.file_name}</option>
            ))}
          </select>
        </div>

        {/* Tool type tabs */}
        <div>
          <label className="text-xs font-medium text-text-muted uppercase tracking-wider mb-3 block">
            Tool Type
          </label>
          <div className="grid grid-cols-3 gap-3">
            {tools.map(({ id, label, icon: Icon, desc }) => (
              <button
                key={id}
                disabled={isGenerating}
                onClick={() => setActiveTool(id)}
                className={`p-4 rounded-xl text-left transition-all border ${
                  activeTool === id
                    ? 'bg-violet-500/10 border-violet-500/30'
                    : 'glass border-white/5 hover:border-white/10'
                }`}
              >
                <Icon className={`w-5 h-5 mb-2 ${activeTool === id ? 'text-violet-400' : 'text-text-muted'}`} />
                <p className={`text-sm font-semibold ${activeTool === id ? 'text-white' : 'text-text-secondary'}`}>
                  {label}
                </p>
                <p className="text-[11px] text-text-muted mt-0.5">{desc}</p>
              </button>
            ))}
          </div>
        </div>

        {/* Number of items */}
        {activeTool !== 'summary' && (
          <div>
            <label className="text-xs font-medium text-text-muted uppercase tracking-wider mb-2 block">
              Number of items: {numItems}
            </label>
            <input
              type="range"
              min={3}
              max={15}
              value={numItems}
              onChange={(e) => setNumItems(Number(e.target.value))}
              disabled={isGenerating}
              className="w-full accent-violet-500"
            />
            <div className="flex justify-between text-[11px] text-text-muted mt-1">
              <span>3</span>
              <span>15</span>
            </div>
          </div>
        )}

        {/* Generate button */}
        <button
          onClick={generateCurrentTool}
          disabled={!selectedDoc || isGenerating}
          className={`w-full flex items-center justify-center gap-2 py-3 rounded-xl text-sm font-medium transition-all ${
            selectedDoc && !isGenerating
              ? 'gradient-bg text-white hover:shadow-lg hover:shadow-violet-500/20'
              : 'bg-white/5 text-text-muted cursor-not-allowed'
          }`}
        >
          {isGenerating ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" />
              Generating...
            </>
          ) : (
            <>
              <Sparkles className="w-4 h-4" />
              Generate {activeTool === 'quiz' ? 'Quiz' : activeTool === 'flashcards' ? 'Flashcards' : 'Summary'}
            </>
          )}
        </button>

        {error && (
          <p className="text-sm text-rose-300">{error}</p>
        )}
      </div>

      {/* Results */}
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
        <div className="glass rounded-2xl p-6 space-y-6 animate-fade-in">
          <h2 className="text-lg font-bold text-white">Summary</h2>
          <div className="markdown-content">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{summaryData.summary}</ReactMarkdown>
          </div>

          {summaryData.key_points.length > 0 && (
            <div className="space-y-3 pt-4 border-t border-white/5">
              <h3 className="text-sm font-semibold text-white flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-amber-400" />
                Key Points
              </h3>
              <ul className="space-y-2">
                {summaryData.key_points.map((point, i) => (
                  <li key={i} className="flex items-start gap-3 text-sm text-text-secondary">
                    <span className="w-5 h-5 rounded-md gradient-bg-subtle flex items-center justify-center flex-shrink-0 text-[11px] font-bold text-violet-400 mt-0.5">
                      {i + 1}
                    </span>
                    {point}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
