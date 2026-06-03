import { useCallback, useEffect, useRef, useState } from 'react'
import type { ClipboardEvent, KeyboardEvent } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import {
  FileSearch,
  Image as ImageIcon,
  Loader2,
  MessageSquare,
  Paperclip,
  Plus,
  Send,
  Trash2,
  X,
  Zap,
} from 'lucide-react'
import ChatMessage from '../components/ChatMessage'
import type { ChatMessageMetadata } from '../components/ChatMessage'
import {
  deleteChatSession,
  getChatHistory,
  getChatSessions,
  getDocuments,
  streamChat,
} from '../lib/api'
import type { ChatSession, Citation, Document, Message } from '../lib/api'
import type { ChatDoneData } from '../lib/api'
import { Badge, Button, Card, EmptyState } from '../components/ui'
import SelectDropdown from '../components/ui/SelectDropdown'
import { cx } from '../lib/cx'

type ChatUiMessage = Message & {
  metadata?: ChatMessageMetadata
}

function findMatchingLocalMessage(localMessages: ChatUiMessage[], incoming: ChatUiMessage): ChatUiMessage | undefined {
  return localMessages.find((local) => local.id === incoming.id)
    ?? localMessages.find((local) =>
      local.role === incoming.role
      && local.role === 'user'
      && local.content === incoming.content
      && Boolean(local.image_url)
    )
}

function mergeMessagePreservingLocalImage(localMessages: ChatUiMessage[], incoming: ChatUiMessage): ChatUiMessage {
  const local = findMatchingLocalMessage(localMessages, incoming)
  return {
    ...local,
    ...incoming,
    image_url: local?.image_url ?? incoming.image_url ?? null,
    citations: incoming.citations ?? local?.citations ?? null,
    metadata: incoming.metadata ?? local?.metadata,
  }
}

function mergeMessagesPreservingImages(localMessages: ChatUiMessage[], incomingMessages: ChatUiMessage[]): ChatUiMessage[] {
  return incomingMessages.map((incoming) => mergeMessagePreservingLocalImage(localMessages, incoming))
}

function appendMessagePreservingImages(localMessages: ChatUiMessage[], incoming: ChatUiMessage): ChatUiMessage[] {
  const existingIndex = localMessages.findIndex((local) => local.id === incoming.id)
  if (existingIndex === -1) {
    return [...localMessages, mergeMessagePreservingLocalImage(localMessages, incoming)]
  }

  return localMessages.map((local, index) =>
    index === existingIndex ? mergeMessagePreservingLocalImage([local], incoming) : local
  )
}

function previousUserMessageHasImage(messages: ChatUiMessage[], messageIndex: number): boolean {
  for (let index = messageIndex - 1; index >= 0; index -= 1) {
    const message = messages[index]
    if (message.role === 'user') return Boolean(message.image_url)
  }

  return false
}

function buildMessageMetadata(data: ChatDoneData, usedImage: boolean): ChatMessageMetadata {
  return {
    mode: data.metadata?.mode,
    questionType: data.question_type || undefined,
    searchQuery: data.metadata?.search_query || data.sub_questions?.[0] || undefined,
    sourcesSearched: data.metadata?.passage_count != null || data.metadata?.graph_count != null
      ? (data.metadata?.passage_count ?? 0) + (data.metadata?.graph_count ?? 0)
      : data.sources_searched,
    usedImage: data.metadata?.used_image ?? usedImage,
    passageCount: data.metadata?.passage_count,
    graphCount: data.metadata?.graph_count,
    citationCount: data.metadata?.citation_count,
    sources: data.metadata?.sources,
  }
}

export default function Chat() {
  const { sessionId: paramSessionId } = useParams()
  const navigate = useNavigate()

  const [sessions, setSessions] = useState<ChatSession[]>([])
  const [documents, setDocuments] = useState<Document[]>([])
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(paramSessionId || null)
  const [messages, setMessages] = useState<ChatUiMessage[]>([])
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
  const optimisticImageUrlsRef = useRef<string[]>([])
  const citationsRef = useRef<Citation[]>([])

  useEffect(() => {
    getChatSessions().then(setSessions).catch(console.error)
    getDocuments()
      .then((res) => setDocuments(res.documents.filter((doc) => doc.status === 'ready')))
      .catch(console.error)
  }, [])

  useEffect(() => {
    if (paramSessionId) {
      let cancelled = false

      void Promise.resolve()
        .then(() => {
          if (!cancelled) setCurrentSessionId(paramSessionId)
          return getChatHistory(paramSessionId)
        })
        .then((res) => {
          if (!cancelled) {
            setMessages((prev) => mergeMessagesPreservingImages(prev, res.messages))
          }
        })
        .catch(console.error)

      return () => {
        cancelled = true
      }
    }
  }, [paramSessionId])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, streamingContent])

  useEffect(() => {
    return () => {
      if (attachedImagePreview) URL.revokeObjectURL(attachedImagePreview)
    }
  }, [attachedImagePreview])

  useEffect(() => {
    const optimisticImageUrls = optimisticImageUrlsRef.current
    return () => {
      optimisticImageUrls.forEach((url) => URL.revokeObjectURL(url))
      abortRef.current?.abort()
    }
  }, [])

  const removeAttachedImage = useCallback(() => {
    if (attachedImagePreview) URL.revokeObjectURL(attachedImagePreview)
    setAttachedImage(null)
    setAttachedImagePreview(null)
    if (imageInputRef.current) imageInputRef.current.value = ''
  }, [attachedImagePreview])

  const attachImage = useCallback((file: File) => {
    if (!['image/png', 'image/jpeg'].includes(file.type)) return
    if (attachedImagePreview) URL.revokeObjectURL(attachedImagePreview)
    setAttachedImage(file)
    setAttachedImagePreview(URL.createObjectURL(file))
  }, [attachedImagePreview])

  const handleNewChat = useCallback(() => {
    setCurrentSessionId(null)
    setMessages([])
    setStreamingContent('')
    setStreamingCitations([])
    citationsRef.current = []
    setStatusMessage('')
    removeAttachedImage()
    navigate('/chat')
    inputRef.current?.focus()
  }, [navigate, removeAttachedImage])

  const handleDeleteSession = async (id: string) => {
    try {
      await deleteChatSession(id)
      setSessions((prev) => prev.filter((session) => session.id !== id))
      if (currentSessionId === id) handleNewChat()
    } catch (err) {
      console.error(err)
    }
  }

  const handleSubmit = useCallback(async () => {
    const question = input.trim() || (attachedImage ? 'What information is in this image?' : '')
    const imageForRequest = attachedImage
    if ((!question && !imageForRequest) || isStreaming) return

    const optimisticImageUrl = imageForRequest ? URL.createObjectURL(imageForRequest) : null
    if (optimisticImageUrl) optimisticImageUrlsRef.current.push(optimisticImageUrl)

    const userMsg: ChatUiMessage = {
      id: Date.now().toString(),
      role: 'user',
      content: question,
      image_url: optimisticImageUrl,
      citations: null,
      created_at: new Date().toISOString(),
    }

    setMessages((prev) => [...prev, userMsg])
    setInput('')
    removeAttachedImage()
    setIsStreaming(true)
    setStreamingContent('')
    setStreamingCitations([])
    citationsRef.current = []
    setStatusMessage('Connecting...')

    abortRef.current = streamChat(
      question,
      selectedDocIds,
      currentSessionId,
      {
        onSession: ({ session_id, image_url }) => {
          setCurrentSessionId(session_id)
          if (image_url) {
            setMessages((prev) =>
              prev.map((message) =>
                message.id === userMsg.id ? { ...message, image_url: message.image_url ?? image_url } : message
              )
            )
          }
          navigate(`/chat/${session_id}`, { replace: true })
          getChatSessions().then(setSessions).catch(console.error)
        },
        onStatus: (message) => {
          setStatusMessage(message)
        },
        onChunk: (text) => {
          setStatusMessage('')
          setStreamingContent((prev) => prev + text)
        },
        onCitations: (citations) => {
          citationsRef.current = citations
          setStreamingCitations(citations)
        },
        onDone: (data) => {
          const assistantMsg: ChatUiMessage = {
            id: (Date.now() + 1).toString(),
            role: 'assistant',
            content: data.answer,
            image_url: null,
            citations: citationsRef.current.length > 0 ? citationsRef.current : null,
            created_at: new Date().toISOString(),
            metadata: buildMessageMetadata(data, Boolean(imageForRequest || userMsg.image_url)),
          }
          setMessages((prev) => appendMessagePreservingImages(prev, assistantMsg))
          setStreamingContent('')
          setStreamingCitations([])
          citationsRef.current = []
          setStatusMessage('')
          setIsStreaming(false)
          getChatSessions().then(setSessions).catch(console.error)
        },
        onError: (error) => {
          const errorMsg: ChatUiMessage = {
            id: (Date.now() + 1).toString(),
            role: 'assistant',
            content: `Error: ${error}`,
            image_url: null,
            citations: null,
            created_at: new Date().toISOString(),
          }
          setMessages((prev) => appendMessagePreservingImages(prev, errorMsg))
          setStreamingContent('')
          setStreamingCitations([])
          citationsRef.current = []
          setStatusMessage('')
          setIsStreaming(false)
        },
      },
      imageForRequest,
    )
  }, [attachedImage, currentSessionId, input, isStreaming, navigate, removeAttachedImage, selectedDocIds])

  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      handleSubmit()
    }
  }

  const handlePaste = (event: ClipboardEvent<HTMLTextAreaElement>) => {
    const imageItem = Array.from(event.clipboardData.items).find((item) =>
      item.type === 'image/png' || item.type === 'image/jpeg'
    )
    const file = imageItem?.getAsFile()
    if (file) attachImage(file)
  }

  const selectedDocumentValue = selectedDocIds ? selectedDocIds.join(',') : ''
  const documentScopeOptions = [
    { value: '', label: 'All ready documents', description: `${documents.length} source${documents.length === 1 ? '' : 's'} available` },
    ...documents.map((doc) => ({
      value: doc.id,
      label: doc.file_name,
      description: `${doc.total_chunks} chunks`,
    })),
  ]
  const lastUserMessage = [...messages].reverse().find((message) => message.role === 'user')
  const streamingHasVisionSource = Boolean(lastUserMessage?.image_url)

  return (
    <div className="flex h-[calc(100dvh-3.5rem)] min-h-0 overflow-hidden md:h-screen">
      <aside className="hidden w-72 shrink-0 flex-col border-r border-white/10 bg-surface-950/70 lg:flex">
        <div className="border-b border-white/10 p-4">
          <Button onClick={handleNewChat} className="w-full">
            <Plus className="h-4 w-4" />
            New Chat
          </Button>
        </div>

        <div className="border-b border-white/10 p-4">
          <SelectDropdown
            label="Search scope"
            value={selectedDocumentValue}
            options={documentScopeOptions}
            placeholder="All ready documents"
            onChange={(value) => setSelectedDocIds(value ? [value] : null)}
          />
          <p className="mt-2 text-xs text-text-muted">{documents.length} ready source{documents.length === 1 ? '' : 's'}</p>
        </div>

        <div className="flex-1 overflow-y-auto p-2">
          <div className="px-2 py-2 text-xs font-medium uppercase text-text-muted">Sessions</div>
          {sessions.length === 0 ? (
            <div className="m-2 rounded-xl border border-white/10 bg-white/[0.03] p-4 text-sm text-text-muted">
              No sessions yet.
            </div>
          ) : (
            <div className="space-y-1">
              {sessions.map((session) => {
                const isActive = session.id === currentSessionId
                return (
                  <div
                    key={session.id}
                    className={cx(
                      'group flex cursor-pointer items-start gap-2 rounded-lg px-3 py-2.5 transition-all',
                      isActive
                        ? 'border border-white/10 bg-surface-600/70 text-white'
                        : 'text-text-secondary hover:bg-white/[0.04] hover:text-white',
                    )}
                    onClick={() => navigate(`/chat/${session.id}`)}
                  >
                    <MessageSquare className={cx('mt-0.5 h-4 w-4 shrink-0', isActive ? 'text-accent-cyan' : 'text-text-muted')} />
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium">{session.title || 'Untitled'}</p>
                      <p className="mt-0.5 text-xs text-text-muted">{new Date(session.created_at).toLocaleDateString()}</p>
                    </div>
                    <button
                      onClick={(event) => {
                        event.stopPropagation()
                        handleDeleteSession(session.id)
                      }}
                      className="rounded-md p-1 text-text-muted opacity-0 transition-all hover:bg-rose-400/10 hover:text-accent-rose group-hover:opacity-100"
                      title="Delete session"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      </aside>

      <section className="relative flex min-w-0 flex-1 flex-col overflow-hidden bg-surface-950/35">
        <header className="z-10 flex h-16 shrink-0 items-center justify-between border-b border-white/10 bg-surface-950/78 px-4 backdrop-blur-xl md:px-6">
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.035] px-3 py-1.5">
              <span className="h-2 w-2 rounded-full bg-accent-cyan agent-pulse" />
              <span className="text-sm font-medium text-accent-cyan">StudyMate Omni</span>
            </div>
            <Badge tone="neutral" className="hidden sm:inline-flex">
              {selectedDocIds ? 'Focused source' : 'All sources'}
            </Badge>
          </div>
          <Button variant="ghost" className="lg:hidden" onClick={handleNewChat}>
            <Plus className="h-4 w-4" />
            New
          </Button>
        </header>

        <div className="flex-1 overflow-y-auto px-4 py-6 md:px-8">
          <div className="mx-auto max-w-3xl space-y-6 pb-32">
            {messages.length === 0 && !isStreaming && (
              <EmptyState
                icon={Zap}
                title="Ask anything about your documents"
                description="StudyMate will retrieve relevant context, stream an answer, and attach citation badges when sources are found."
                action={
                  <div className="flex flex-wrap justify-center gap-2">
                    {['Summarize the key points', 'Compare concepts', 'Explain this diagram'].map((suggestion) => (
                      <button
                        key={suggestion}
                        onClick={() => {
                          setInput(suggestion)
                          inputRef.current?.focus()
                        }}
                        className="rounded-full border border-white/10 bg-white/[0.04] px-3 py-1.5 text-xs font-medium text-text-secondary transition-colors hover:border-accent-cyan/30 hover:text-white"
                      >
                        {suggestion}
                      </button>
                    ))}
                  </div>
                }
              />
            )}

            {messages.map((message, index) => (
              <ChatMessage
                key={message.id}
                role={message.role}
                content={message.content}
                imageUrl={message.image_url}
                citations={message.citations}
                hasVisionSource={message.role === 'assistant' ? previousUserMessageHasImage(messages, index) : undefined}
                metadata={message.role === 'assistant' ? message.metadata : undefined}
              />
            ))}

            {isStreaming && streamingContent && (
              <ChatMessage
                role="assistant"
                content={streamingContent}
                imageUrl={null}
                citations={streamingCitations.length > 0 ? streamingCitations : undefined}
                isStreaming
                hasVisionSource={streamingHasVisionSource}
                metadata={{ usedImage: streamingHasVisionSource }}
              />
            )}

            <div ref={messagesEndRef} />
          </div>
        </div>

        <div className="absolute bottom-0 left-0 right-0 z-20 bg-gradient-to-t from-surface-950 via-surface-950/96 to-transparent px-4 pb-4 pt-12 md:px-8 md:pb-6">
          <div className="mx-auto max-w-3xl space-y-3">
            {statusMessage && (
              <div className="inline-flex items-center gap-2 rounded-full border border-accent-cyan/20 bg-accent-cyan/10 px-3 py-1.5 text-xs text-accent-cyan animate-fade-in">
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                {statusMessage}
              </div>
            )}

            {attachedImagePreview && (
              <Card className="inline-flex items-start gap-2 p-2">
                <img
                  src={attachedImagePreview}
                  alt="Attached preview"
                  className="h-20 w-20 rounded-lg border border-white/10 object-cover"
                />
                <button
                  onClick={removeAttachedImage}
                  className="rounded-lg p-1.5 text-text-muted transition-colors hover:bg-white/[0.08] hover:text-white"
                  title="Remove image"
                >
                  <X className="h-4 w-4" />
                </button>
              </Card>
            )}

            <div className="field-surface flex items-end gap-2 rounded-xl p-2 shadow-2xl shadow-black/30">
              <input
                ref={imageInputRef}
                type="file"
                accept="image/png,image/jpeg"
                className="hidden"
                onChange={(event) => {
                  const file = event.target.files?.[0]
                  if (file) attachImage(file)
                }}
              />
              <button
                type="button"
                onClick={() => imageInputRef.current?.click()}
                disabled={isStreaming}
                className="shrink-0 rounded-lg p-2 text-text-muted transition-colors hover:bg-white/[0.08] hover:text-white disabled:opacity-50"
                title="Attach image"
              >
                <Paperclip className="h-5 w-5" />
              </button>
              <textarea
                ref={inputRef}
                value={input}
                onChange={(event) => setInput(event.target.value)}
                onKeyDown={handleKeyDown}
                onPaste={handlePaste}
                placeholder="Message StudyMate..."
                rows={1}
                className="max-h-32 min-h-11 flex-1 resize-none bg-transparent px-1 py-2.5 text-sm leading-6 text-white outline-none placeholder:text-text-muted"
                onInput={(event) => {
                  const element = event.currentTarget
                  element.style.height = 'auto'
                  element.style.height = `${Math.min(element.scrollHeight, 128)}px`
                }}
              />
              <button
                onClick={handleSubmit}
                disabled={(!input.trim() && !attachedImage) || isStreaming}
                className={cx(
                  'flex h-10 w-10 shrink-0 items-center justify-center rounded-lg transition-all',
                  (input.trim() || attachedImage) && !isStreaming
                    ? 'gradient-bg text-surface-950 hover:opacity-95'
                    : 'bg-white/[0.06] text-text-muted',
                )}
                title="Send"
              >
                {isStreaming ? <Loader2 className="h-5 w-5 animate-spin" /> : <Send className="h-5 w-5" />}
              </button>
            </div>
            <div className="flex items-center justify-center gap-2 text-[11px] text-text-muted">
              <FileSearch className="h-3.5 w-3.5" />
              Verify critical answers against the cited source material.
              {attachedImage && <ImageIcon className="h-3.5 w-3.5 text-accent-cyan" />}
            </div>
          </div>
        </div>
      </section>
    </div>
  )
}
