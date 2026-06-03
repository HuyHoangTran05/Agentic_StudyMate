import { useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Bot, Check, Copy, FileText, Image, User } from 'lucide-react'
import type { Citation } from '../lib/api'

const DEFAULT_VISIBLE_CITATIONS = 5

interface Props {
  role: 'user' | 'assistant'
  content: string
  imageUrl?: string | null
  citations?: Citation[] | null
  isStreaming?: boolean
  hasVisionSource?: boolean
  metadata?: ChatMessageMetadata
}

export interface ChatMessageMetadata {
  mode?: string
  questionType?: string
  searchQuery?: string
  sourcesSearched?: number
  usedImage?: boolean
  passageCount?: number
  graphCount?: number
  citationCount?: number
  sources?: string[]
}

function getCitationKey(citation: Citation) {
  return `${citation.file_name}::${citation.page_number ?? 'none'}::${citation.chunk_id}`
}

function getUniqueCitations(citations: Citation[]) {
  const seen = new Set<string>()
  return citations.filter((citation) => {
    const key = getCitationKey(citation)
    if (seen.has(key)) return false
    seen.add(key)
    return true
  })
}

function groupCitationsByFile(citations: Citation[]) {
  return citations.reduce<Array<{ fileName: string; citations: Citation[] }>>((groups, citation) => {
    const existingGroup = groups.find((group) => group.fileName === citation.file_name)
    if (existingGroup) {
      existingGroup.citations.push(citation)
      return groups
    }

    groups.push({ fileName: citation.file_name, citations: [citation] })
    return groups
  }, [])
}

export default function ChatMessage({
  role,
  content,
  imageUrl,
  citations,
  isStreaming,
  hasVisionSource,
  metadata,
}: Props) {
  const [copied, setCopied] = useState(false)
  const [showAllSources, setShowAllSources] = useState(false)

  const handleCopy = () => {
    navigator.clipboard.writeText(content)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  if (role === 'user') {
    return (
      <div className="flex justify-end animate-fade-in">
        <div className="flex max-w-[88%] flex-col items-end gap-2 sm:max-w-[78%]">
          {imageUrl && (
            <div className="overflow-hidden rounded-xl border border-white/10 bg-surface-750">
              <img
                src={imageUrl}
                alt="Uploaded attachment"
                className="max-h-72 max-w-full object-contain sm:max-w-sm"
              />
            </div>
          )}
          <div className="flex items-start gap-3">
            <div className="rounded-2xl rounded-tr-md border border-white/10 bg-surface-600 px-4 py-3 shadow-lg shadow-black/20">
              <p className="whitespace-pre-wrap text-sm leading-6 text-white">{content}</p>
            </div>
            <div className="mt-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-accent-violet/12 text-accent-violet ring-1 ring-accent-violet/18">
              <User className="h-4 w-4" />
            </div>
          </div>
        </div>
      </div>
    )
  }

  const uniqueCitations = getUniqueCitations(citations ?? [])
  const visibleCitations = showAllSources
    ? uniqueCitations
    : uniqueCitations.slice(0, DEFAULT_VISIBLE_CITATIONS)
  const citationGroups = groupCitationsByFile(visibleCitations)
  const hasDocumentSources = uniqueCitations.length > 0
  const metadataSources = new Set((metadata?.sources ?? []).map((source) => source.toLowerCase()))
  const isVisionRag =
    metadata?.mode === 'image_rag'
    || metadata?.questionType === 'image_rag'
    || metadata?.usedImage
    || metadataSources.has('vision')
    || hasVisionSource
  const hasDocumentMetadata = metadataSources.has('documents')
  const hasGraphMetadata = metadataSources.has('graph')
  const hasSearchQuery = Boolean(metadata?.searchQuery)
  const hasSourcesSearched = typeof metadata?.sourcesSearched === 'number'
  const hasPassageCount = typeof metadata?.passageCount === 'number'
  const hasGraphCount = typeof metadata?.graphCount === 'number'
  const displayedCitationCount = metadata?.citationCount ?? uniqueCitations.length
  const shouldShowSourceSummary = Boolean(
    isVisionRag
    || hasDocumentSources
    || hasDocumentMetadata
    || hasGraphMetadata
    || hasSearchQuery
    || hasSourcesSearched
    || hasPassageCount
    || hasGraphCount,
  )

  return (
    <div className="flex justify-start animate-fade-in">
      <div className="flex max-w-full gap-3 lg:max-w-[90%]">
        <div className="mt-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-accent-violet/25 bg-surface-650 text-accent-violet shadow-sm shadow-accent-violet/10">
          <Bot className="h-4 w-4" />
        </div>
        <div className="min-w-0 flex-1 space-y-3">
          <div className="group relative overflow-hidden rounded-2xl border border-white/10 bg-surface-800/72 p-4 shadow-lg shadow-black/20 backdrop-blur-md">
            <div className="absolute left-0 top-0 h-[2px] w-full bg-gradient-to-r from-accent-violet via-accent-cyan to-transparent opacity-60" />
            <div className="markdown-content text-sm">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
            </div>

            {isStreaming && (
              <div className="mt-3 flex gap-1 border-t border-white/10 pt-3">
                <div className="typing-dot" />
                <div className="typing-dot" />
                <div className="typing-dot" />
              </div>
            )}

            {!isStreaming && content && (
              <button
                onClick={handleCopy}
                className="absolute right-2 top-2 rounded-lg bg-white/[0.04] p-1.5 text-text-muted opacity-0 transition-all hover:bg-white/[0.08] hover:text-white group-hover:opacity-100"
                title="Copy"
              >
                {copied ? <Check className="h-3.5 w-3.5 text-accent-emerald" /> : <Copy className="h-3.5 w-3.5" />}
              </button>
            )}
          </div>

          {shouldShowSourceSummary && (
            <div className="space-y-2">
              <div className="flex flex-wrap items-center gap-1.5 px-1">
                {isVisionRag && (
                  <span className="inline-flex items-center gap-1.5 rounded-full border border-accent-violet/20 bg-accent-violet/10 px-2.5 py-1 text-[11px] font-medium text-accent-violet">
                    <Image className="h-3 w-3" />
                    Vision RAG
                  </span>
                )}
                {(hasDocumentSources || hasDocumentMetadata) && (
                  <>
                    <span className="inline-flex items-center gap-1.5 rounded-full border border-accent-cyan/20 bg-accent-cyan/10 px-2.5 py-1 text-[11px] font-medium text-accent-cyan">
                      <FileText className="h-3 w-3" />
                      Documents
                    </span>
                    {displayedCitationCount > 0 && (
                      <span className="inline-flex items-center rounded-full border border-white/10 bg-white/[0.04] px-2.5 py-1 text-[11px] font-medium text-text-secondary">
                        {displayedCitationCount} source{displayedCitationCount === 1 ? '' : 's'}
                      </span>
                    )}
                  </>
                )}
                {hasGraphMetadata && (
                  <span className="inline-flex items-center rounded-full border border-accent-violet/20 bg-accent-violet/10 px-2.5 py-1 text-[11px] font-medium text-accent-violet">
                    Graph
                  </span>
                )}
                {hasSourcesSearched && (
                  <span className="inline-flex items-center rounded-full border border-white/10 bg-white/[0.04] px-2.5 py-1 text-[11px] font-medium text-text-secondary">
                    Sources searched: {metadata?.sourcesSearched}
                  </span>
                )}
                {hasPassageCount && (
                  <span className="inline-flex items-center rounded-full border border-white/10 bg-white/[0.04] px-2.5 py-1 text-[11px] font-medium text-text-secondary">
                    Passages: {metadata?.passageCount}
                  </span>
                )}
                {hasGraphCount && (
                  <span className="inline-flex items-center rounded-full border border-white/10 bg-white/[0.04] px-2.5 py-1 text-[11px] font-medium text-text-secondary">
                    Graph relationships: {metadata?.graphCount}
                  </span>
                )}
              </div>

              {hasSearchQuery && (
                <div className="rounded-xl border border-accent-violet/15 bg-accent-violet/[0.055] px-3 py-2">
                  <p className="text-[11px] font-medium text-accent-violet">Search query</p>
                  <p className="mt-0.5 break-words text-xs leading-5 text-text-secondary">
                    {metadata?.searchQuery}
                  </p>
                </div>
              )}

              {isVisionRag && !hasDocumentSources && (
                <div className="rounded-xl border border-white/10 bg-white/[0.035] px-3 py-2 text-xs leading-5 text-text-secondary">
                  Generated from image understanding. No document citations were returned.
                </div>
              )}

              {hasDocumentSources && (
                <div className="overflow-hidden rounded-2xl border border-white/10 bg-surface-850/78 shadow-lg shadow-black/20">
                  <div className="flex items-center justify-between gap-3 border-b border-white/10 px-3 py-2">
                    <p className="text-xs font-semibold text-white">Sources</p>
                    {uniqueCitations.length > DEFAULT_VISIBLE_CITATIONS && (
                      <button
                        type="button"
                        onClick={() => setShowAllSources((current) => !current)}
                        className="rounded-md px-2 py-1 text-xs font-medium text-accent-cyan transition-colors hover:bg-accent-cyan/10 hover:text-accent-cyan"
                      >
                        {showAllSources ? 'Hide sources' : 'Show all sources'}
                      </button>
                    )}
                  </div>

                  <div className="divide-y divide-white/10">
                    {citationGroups.map((group) => (
                      <div key={group.fileName} className="bg-white/[0.015]">
                        {group.citations.map((citation) => (
                          <div
                            key={getCitationKey(citation)}
                            className="px-3 py-2.5 transition-colors hover:bg-white/[0.035]"
                          >
                            <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                              <span className="min-w-0 max-w-full truncate text-xs font-semibold text-white">
                                {citation.file_name}
                              </span>
                              {citation.page_number != null && (
                                <span className="rounded-full border border-white/10 bg-white/[0.04] px-2 py-0.5 text-[10px] font-medium text-text-secondary">
                                  p.{citation.page_number}
                                </span>
                              )}
                            </div>
                            {citation.section_title && (
                              <p className="mt-1 truncate text-[11px] font-medium text-accent-violet">
                                {citation.section_title}
                              </p>
                            )}
                            {citation.snippet && (
                              <p className="mt-1 max-h-10 overflow-hidden text-xs leading-5 text-text-muted">
                                {citation.snippet}
                              </p>
                            )}
                          </div>
                        ))}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
