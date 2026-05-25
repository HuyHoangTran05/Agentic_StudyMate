import { useState, useEffect, useRef, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  Send,
  Plus,
  MessageSquare,
  Trash2,
  Loader2,
  Zap,
  Paperclip,
  X,
} from 'lucide-react'
import ChatMessage from '../components/ChatMessage'
import {
  streamChat,
  getChatSessions,
  getChatHistory,
  deleteChatSession,
  getDocuments,
} from '../lib/api'
import type { ChatSession, Message, Citation, Document } from '../lib/api'

export default function Chat() {
  const { sessionId: paramSessionId } = useParams()
  const navigate = useNavigate()

  const [sessions, setSessions] = useState<ChatSession[]>([])
  const [documents, setDocuments] = useState<Document[]>([])
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(paramSessionId || null)
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [isStreaming, setIsStreaming] = useState(false)
  const [streamingContent, setStreamingContent] = useState('')
  const [streamingCitations, setStreamingCitations] = useState<Citation[]>([])
  const [statusMessage, setStatusMessage] = useState('')
  const [selectedDocIds, setSelectedDocIds] = useState<string[] | null>(null)
  const [attachedImage, setAttachedImage] = useState<File | null>(null)
  const [attachedImagePreview, setAttachedImagePreview] = useState<string | null>(null)

  const messagesEndRef = useRef<HTMLDivElement>(null)
  const abortRef = useRef<AbortController | null>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const imageInputRef = useRef<HTMLInputElement>(null)

  // Load sessions and documents on mount
  useEffect(() => {
    getChatSessions().then(setSessions).catch(console.error)
    getDocuments().then((res) => setDocuments(res.documents.filter(d => d.status === 'ready'))).catch(console.error)
  }, [])

  // Load session history when sessionId changes
  useEffect(() => {
    if (paramSessionId) {
      setCurrentSessionId(paramSessionId)
      getChatHistory(paramSessionId)
        .then((res) => setMessages(res.messages))
        .catch(console.error)
    }
  }, [paramSessionId])

  // Auto-scroll
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, streamingContent])

  useEffect(() => {
    return () => {
      if (attachedImagePreview) URL.revokeObjectURL(attachedImagePreview)
    }
  }, [attachedImagePreview])

  const attachImage = (file: File) => {
    if (!['image/png', 'image/jpeg'].includes(file.type)) return
    if (attachedImagePreview) URL.revokeObjectURL(attachedImagePreview)
    setAttachedImage(file)
    setAttachedImagePreview(URL.createObjectURL(file))
  }

  const removeAttachedImage = () => {
    if (attachedImagePreview) URL.revokeObjectURL(attachedImagePreview)
    setAttachedImage(null)
    setAttachedImagePreview(null)
    if (imageInputRef.current) imageInputRef.current.value = ''
  }

  const handleNewChat = () => {
    setCurrentSessionId(null)
    setMessages([])
    setStreamingContent('')
    setStreamingCitations([])
    setStatusMessage('')
    removeAttachedImage()
    navigate('/chat')
    inputRef.current?.focus()
  }

  const handleDeleteSession = async (id: string) => {
    try {
      await deleteChatSession(id)
      setSessions((prev) => prev.filter((s) => s.id !== id))
      if (currentSessionId === id) handleNewChat()
    } catch (err) {
      console.error(err)
    }
  }

  const handleSubmit = useCallback(async () => {
    const question = input.trim() || (attachedImage ? 'What information is in this image?' : '')
    const imageForRequest = attachedImage
    if ((!question && !imageForRequest) || isStreaming) return

    // Add user message optimistically
    const userMsg: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: question,
      citations: null,
      created_at: new Date().toISOString(),
    }
    setMessages((prev) => [...prev, userMsg])
    setInput('')
    removeAttachedImage()
    setIsStreaming(true)
    setStreamingContent('')
    setStreamingCitations([])
    setStatusMessage('Connecting...')

    abortRef.current = streamChat(
      question,
      selectedDocIds,
      currentSessionId,
      {
        onSession: ({ session_id }) => {
          setCurrentSessionId(session_id)
          navigate(`/chat/${session_id}`, { replace: true })
          // Refresh sessions list
          getChatSessions().then(setSessions).catch(console.error)
        },
        onStatus: (msg) => {
          setStatusMessage(msg)
        },
        onChunk: (text) => {
          setStatusMessage('')
          setStreamingContent((prev) => prev + text)
        },
        onCitations: (citations) => {
          setStreamingCitations(citations)
        },
        onDone: (data) => {
          // Add assistant message
          const assistantMsg: Message = {
            id: (Date.now() + 1).toString(),
            role: 'assistant',
            content: data.answer,
            citations: streamingCitations.length > 0 ? streamingCitations : null,
            created_at: new Date().toISOString(),
          }
          setMessages((prev) => [...prev, assistantMsg])
          setStreamingContent('')
          setStreamingCitations([])
          setStatusMessage('')
          setIsStreaming(false)
          // Refresh sessions
          getChatSessions().then(setSessions).catch(console.error)
        },
        onError: (error) => {
          const errorMsg: Message = {
            id: (Date.now() + 1).toString(),
            role: 'assistant',
            content: `⚠️ Error: ${error}`,
            citations: null,
            created_at: new Date().toISOString(),
          }
          setMessages((prev) => [...prev, errorMsg])
          setStreamingContent('')
          setStatusMessage('')
          setIsStreaming(false)
        },
      },
      imageForRequest,
    )
  }, [input, attachedImage, isStreaming, currentSessionId, selectedDocIds, navigate, streamingCitations, attachedImagePreview])

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit()
    }
  }

  const handlePaste = (e: React.ClipboardEvent<HTMLTextAreaElement>) => {
    const imageItem = Array.from(e.clipboardData.items).find((item) =>
      item.type === 'image/png' || item.type === 'image/jpeg'
    )
    const file = imageItem?.getAsFile()
    if (file) {
      attachImage(file)
    }
  }

  return (
    <div className="flex h-[calc(100vh-56px)] md:h-screen">
      {/* ── Session Sidebar ── */}
      <div className="hidden lg:flex w-72 flex-col glass-solid border-r border-white/5">
        <div className="p-4 border-b border-white/5">
          <button
            onClick={handleNewChat}
            className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl gradient-bg text-white text-sm font-medium hover:shadow-lg hover:shadow-violet-500/20 transition-all"
          >
            <Plus className="w-4 h-4" />
            New Chat
          </button>
        </div>

        {/* Document filter */}
        <div className="px-4 py-3 border-b border-white/5">
          <label className="text-[11px] font-medium text-text-muted uppercase tracking-wider mb-2 block">
            Search in
          </label>
          <select
            value={selectedDocIds ? selectedDocIds.join(',') : ''}
            onChange={(e) => {
              const val = e.target.value
              setSelectedDocIds(val ? val.split(',') : null)
            }}
            className="w-full bg-surface-700 border border-white/10 rounded-lg px-3 py-2 text-sm text-text-secondary outline-none focus:border-violet-500/50 transition-colors"
          >
            <option value="">All documents</option>
            {documents.map((doc) => (
              <option key={doc.id} value={doc.id}>{doc.file_name}</option>
            ))}
          </select>
        </div>

        {/* Session list */}
        <div className="flex-1 overflow-y-auto px-2 py-2 space-y-0.5">
          {sessions.map((session) => {
            const isActive = session.id === currentSessionId
            return (
              <div
                key={session.id}
                className={`group flex items-center gap-2 px-3 py-2.5 rounded-xl cursor-pointer transition-all ${
                  isActive ? 'bg-white/5' : 'hover:bg-white/[0.03]'
                }`}
                onClick={() => navigate(`/chat/${session.id}`)}
              >
                <MessageSquare className={`w-4 h-4 flex-shrink-0 ${isActive ? 'text-violet-400' : 'text-text-muted'}`} />
                <span className={`text-sm truncate flex-1 ${isActive ? 'text-white font-medium' : 'text-text-secondary'}`}>
                  {session.title || 'Untitled'}
                </span>
                <button
                  onClick={(e) => { e.stopPropagation(); handleDeleteSession(session.id) }}
                  className="p-1 rounded-md text-text-muted hover:text-rose-400 hover:bg-rose-500/10 opacity-0 group-hover:opacity-100 transition-all"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>
            )
          })}
        </div>
      </div>

      {/* ── Chat Area ── */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-4 md:px-8 py-6 space-y-6">
          {messages.length === 0 && !isStreaming && (
            <div className="flex items-center justify-center h-full">
              <div className="text-center space-y-4 max-w-md">
                <div className="w-16 h-16 rounded-2xl gradient-bg-subtle flex items-center justify-center mx-auto">
                  <Zap className="w-8 h-8 text-violet-400" />
                </div>
                <h2 className="text-xl font-bold text-white">Ask anything about your documents</h2>
                <p className="text-sm text-text-muted leading-relaxed">
                  I'll search through your uploaded files using hybrid retrieval,
                  evaluate the context, and generate a cited answer.
                </p>
                <div className="flex flex-wrap gap-2 justify-center pt-2">
                  {['Summarize the key points', 'Compare concepts', 'Explain in detail'].map((suggestion) => (
                    <button
                      key={suggestion}
                      onClick={() => { setInput(suggestion); inputRef.current?.focus() }}
                      className="px-3 py-1.5 rounded-lg text-xs font-medium glass glass-hover text-text-secondary hover:text-white transition-all"
                    >
                      {suggestion}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          )}

          {messages.map((msg) => (
            <ChatMessage
              key={msg.id}
              role={msg.role}
              content={msg.content}
              citations={msg.citations}
            />
          ))}

          {/* Streaming message */}
          {isStreaming && streamingContent && (
            <ChatMessage
              role="assistant"
              content={streamingContent}
              citations={streamingCitations.length > 0 ? streamingCitations : undefined}
              isStreaming
            />
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Status bar */}
        {statusMessage && (
          <div className="px-4 md:px-8 pb-2">
            <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full glass text-xs text-text-secondary animate-fade-in">
              <Loader2 className="w-3 h-3 animate-spin text-violet-400" />
              {statusMessage}
            </div>
          </div>
        )}

        {/* Input area */}
        <div className="p-4 md:px-8 md:pb-6 border-t border-white/5">
          <div className="max-w-4xl mx-auto space-y-3">
            {attachedImagePreview && (
              <div className="inline-flex items-start gap-2 glass rounded-xl p-2 border border-white/10">
                <img
                  src={attachedImagePreview}
                  alt="Attached preview"
                  className="w-20 h-20 rounded-lg object-cover border border-white/10"
                />
                <button
                  onClick={removeAttachedImage}
                  className="p-1.5 rounded-lg text-text-muted hover:text-white hover:bg-white/10 transition-colors"
                  title="Remove image"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
            )}

            <div className="flex items-end gap-3">
            <div className="flex-1 glass rounded-2xl flex items-end px-4 py-3 focus-within:border-violet-500/30 transition-colors">
              <input
                ref={imageInputRef}
                type="file"
                accept="image/png,image/jpeg"
                className="hidden"
                onChange={(e) => {
                  const file = e.target.files?.[0]
                  if (file) attachImage(file)
                }}
              />
              <button
                type="button"
                onClick={() => imageInputRef.current?.click()}
                disabled={isStreaming}
                className="p-1.5 mr-2 rounded-lg text-text-muted hover:text-white hover:bg-white/10 transition-colors disabled:opacity-50"
                title="Attach image"
              >
                <Paperclip className="w-4 h-4" />
              </button>
              <textarea
                ref={inputRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                onPaste={handlePaste}
                placeholder="Ask a question about your documents..."
                rows={1}
                className="flex-1 bg-transparent text-sm text-white placeholder:text-text-muted outline-none resize-none max-h-32 leading-relaxed"
                style={{ minHeight: '24px' }}
                onInput={(e) => {
                  const el = e.currentTarget
                  el.style.height = 'auto'
                  el.style.height = Math.min(el.scrollHeight, 128) + 'px'
                }}
              />
            </div>
            <button
              onClick={handleSubmit}
              disabled={(!input.trim() && !attachedImage) || isStreaming}
              className={`p-3 rounded-xl transition-all flex-shrink-0 ${
                (input.trim() || attachedImage) && !isStreaming
                  ? 'gradient-bg text-white hover:shadow-lg hover:shadow-violet-500/20 hover:scale-105'
                  : 'bg-white/5 text-text-muted cursor-not-allowed'
              }`}
            >
              {isStreaming ? (
                <Loader2 className="w-5 h-5 animate-spin" />
              ) : (
                <Send className="w-5 h-5" />
              )}
            </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
