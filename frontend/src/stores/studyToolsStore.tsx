/* eslint-disable react-refresh/only-export-components */
import {
  createContext,
  useCallback,
  useContext,
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
  allDocuments: Document[]
  selectedDoc: string
  activeTool: StudyToolType
  numItems: number
  isLoadingDocuments: boolean
  isGenerating: boolean
  error: string | null
  quizData: MCQuestion[] | null
  flashcardsData: Flashcard[] | null
  summaryData: SummaryResponse | null
  setSelectedDoc: (documentId: string) => void
  setActiveTool: (tool: StudyToolType) => void
  setNumItems: (count: number) => void
  refreshDocuments: () => Promise<Document[]>
  generateCurrentTool: () => Promise<void>
}

const StudyToolsContext = createContext<StudyToolsState | null>(null)

export function StudyToolsProvider({ children }: { children: ReactNode }) {
  const [documents, setDocuments] = useState<Document[]>([])
  const [allDocuments, setAllDocuments] = useState<Document[]>([])
  const [selectedDoc, setSelectedDoc] = useState('')
  const [activeTool, setActiveTool] = useState<StudyToolType>('quiz')
  const [numItems, setNumItems] = useState(5)
  const [isLoadingDocuments, setIsLoadingDocuments] = useState(false)
  const [isGenerating, setIsGenerating] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [quizData, setQuizData] = useState<MCQuestion[] | null>(null)
  const [flashcardsData, setFlashcardsData] = useState<Flashcard[] | null>(null)
  const [summaryData, setSummaryData] = useState<SummaryResponse | null>(null)

  const refreshDocuments = useCallback(async () => {
    setIsLoadingDocuments(true)
    try {
      const res = await getDocuments()
      const ready = res.documents.filter((doc) => doc.status === 'ready')
      setAllDocuments(res.documents)
      setDocuments(ready)

      setSelectedDoc((current) => {
        if (current && ready.some((doc) => doc.id === current)) {
          return current
        }
        return ready[0]?.id ?? ''
      })
      setError(null)
      return res.documents
    } catch (err) {
      console.error(err)
      setError('Unable to load ready documents.')
      return []
    } finally {
      setIsLoadingDocuments(false)
    }
  }, [])

  const generateCurrentTool = useCallback(async () => {
    if (!selectedDoc || isGenerating) return
    if (!documents.some((doc) => doc.id === selectedDoc)) {
      setError('Select a ready document before generating study content.')
      return
    }

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
  }, [activeTool, documents, isGenerating, numItems, selectedDoc])

  const value = useMemo<StudyToolsState>(
    () => ({
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
    }),
    [
      activeTool,
      allDocuments,
      documents,
      error,
      flashcardsData,
      generateCurrentTool,
      isLoadingDocuments,
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
