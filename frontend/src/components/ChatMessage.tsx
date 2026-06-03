import { useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Bot, Check, Copy, FileText, User } from 'lucide-react'
import type { Citation } from '../lib/api'
import { cx } from '../lib/cx'

interface Props {
  role: 'user' | 'assistant'
  content: string
  imageUrl?: string | null
  citations?: Citation[] | null
  isStreaming?: boolean
}

export default function ChatMessage({ role, content, imageUrl, citations, isStreaming }: Props) {
  const [copied, setCopied] = useState(false)

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

          {citations && citations.length > 0 && (
            <div className="flex flex-wrap gap-1.5 px-1">
              {citations.map((citation, index) => (
                <span
                  key={`${citation.file_name}-${citation.chunk_id}-${index}`}
                  className={cx(
                    'inline-flex max-w-full items-center gap-1.5 rounded-full border border-accent-cyan/22 bg-accent-cyan/10 px-2.5 py-1 text-[11px] font-medium text-accent-cyan',
                    'hover:border-accent-cyan/40 hover:bg-accent-cyan/14',
                  )}
                  title={citation.snippet || undefined}
                >
                  <FileText className="h-3 w-3 shrink-0" />
                  <span className="max-w-48 truncate">{citation.file_name}</span>
                  {citation.page_number != null && (
                    <span className="text-accent-cyan/70">p.{citation.page_number}</span>
                  )}
                </span>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
