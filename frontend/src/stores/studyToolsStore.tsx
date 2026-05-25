import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react'
import type { ReactNode } from 'react'
import {
  generateFlashcards,
  generateQuiz,
  generateSummary,
  getDocuments,
} from '../lib/api'
import type {
  Document,
  Flashcard,
  MCQuestion,
  SummaryResponse,
} from '../lib/api'

export type StudyToolType = 'quiz' | 'flashcards' | 'summary'

interface StudyToolsState {
  documents: Document[]
  selectedDoc: string
  activeTool: StudyToolType
  numItems: number
  isGenerating: boolean
  error: string | null
  quizData: MCQuestion[] | null
  flashcardsData: Flashcard[] | null
  summaryData: SummaryResponse | null
  setSelectedDoc: (documentId: string) => void
  setActiveTool: (tool: StudyToolType) => void
  setNumItems: (count: number) => void
  refreshDocuments: () => Promise<void>
  generateCurrentTool: () => Promise<void>
}

const StudyToolsContext = createContext<StudyToolsState | null>(null)

export function StudyToolsProvider({ children }: { children: ReactNode }) {
  const [documents, setDocuments] = useState<Document[]>([])
  const [selectedDoc, setSelectedDoc] = useState('')
  const [activeTool, setActiveTool] = useState<StudyToolType>('quiz')
  const [numItems, setNumItems] = useState(5)
  const [isGenerating, setIsGenerating] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [quizData, setQuizData] = useState<MCQuestion[] | null>(null)
  const [flashcardsData, setFlashcardsData] = useState<Flashcard[] | null>(null)
  const [summaryData, setSummaryData] = useState<SummaryResponse | null>(null)

  const refreshDocuments = useCallback(async () => {
    const res = await getDocuments()
    const ready = res.documents.filter((doc) => doc.status === 'ready')
    setDocuments(ready)

    setSelectedDoc((current) => {
      if (current && ready.some((doc) => doc.id === current)) {
        return current
      }
      return ready[0]?.id ?? ''
    })
  }, [])

  useEffect(() => {
    refreshDocuments().catch((err) => {
      console.error(err)
      setError('Unable to load ready documents.')
    })
  }, [refreshDocuments])

  const generateCurrentTool = useCallback(async () => {
    if (!selectedDoc || isGenerating) return

    const tool = activeTool
    const documentId = selectedDoc
    const count = numItems

    setIsGenerating(true)
    setError(null)

    try {
      switch (tool) {
        case 'quiz': {
          const res = await generateQuiz(documentId, count)
          setQuizData(res.questions)
          setFlashcardsData(null)
          setSummaryData(null)
          break
        }
        case 'flashcards': {
          const res = await generateFlashcards(documentId, count)
          setFlashcardsData(res.flashcards)
          setQuizData(null)
          setSummaryData(null)
          break
        }
        case 'summary': {
          const res = await generateSummary(documentId)
          setSummaryData(res)
          setQuizData(null)
          setFlashcardsData(null)
          break
        }
      }
    } catch (err) {
      console.error(err)
      setError('Unable to generate study content right now.')
    } finally {
      setIsGenerating(false)
    }
  }, [activeTool, isGenerating, numItems, selectedDoc])

  const value = useMemo<StudyToolsState>(
    () => ({
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
      refreshDocuments,
      generateCurrentTool,
    }),
    [
      activeTool,
      documents,
      error,
      flashcardsData,
      generateCurrentTool,
      isGenerating,
      numItems,
      quizData,
      refreshDocuments,
      selectedDoc,
      summaryData,
    ],
  )

  return (
    <StudyToolsContext.Provider value={value}>
      {children}
    </StudyToolsContext.Provider>
  )
}

export function useStudyToolsStore() {
  const context = useContext(StudyToolsContext)
  if (!context) {
    throw new Error('useStudyToolsStore must be used within StudyToolsProvider')
  }
  return context
}
