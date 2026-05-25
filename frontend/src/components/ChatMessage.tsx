import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Bot, User, Copy, Check, FileText } from 'lucide-react'
import { useState } from 'react'
import type { Citation } from '../lib/api'

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
        <div className="flex items-start gap-3 max-w-[80%]">
          <div className="rounded-2xl rounded-br-md px-4 py-3 bg-gradient-to-br from-violet-600/80 to-violet-700/80 backdrop-blur border border-violet-500/20">
            {imageUrl && (
              <img
                src={imageUrl}
                alt="Uploaded attachment"
                className="mb-3 max-w-full sm:max-w-xs max-h-72 rounded-xl object-contain border border-white/15"
              />
            )}
            <p className="text-sm text-white leading-relaxed">{content}</p>
          </div>
          <div className="w-8 h-8 rounded-xl bg-violet-500/20 flex items-center justify-center flex-shrink-0 mt-0.5">
            <User className="w-4 h-4 text-violet-400" />
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="flex justify-start animate-fade-in">
      <div className="flex items-start gap-3 max-w-[85%]">
        <div className="w-8 h-8 rounded-xl gradient-bg-subtle flex items-center justify-center flex-shrink-0 mt-0.5">
          <Bot className="w-4 h-4 text-cyan-400" />
        </div>
        <div className="space-y-2 min-w-0">
          {/* Message content */}
          <div className="glass rounded-2xl rounded-bl-md px-4 py-3 relative group">
            <div className="markdown-content text-sm">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
            </div>

            {isStreaming && (
              <div className="flex gap-1 mt-2 pt-2 border-t border-white/5">
                <div className="typing-dot" />
                <div className="typing-dot" />
                <div className="typing-dot" />
              </div>
            )}

            {/* Copy button */}
            {!isStreaming && content && (
              <button
                onClick={handleCopy}
                className="absolute top-2 right-2 p-1.5 rounded-lg bg-white/5 opacity-0 group-hover:opacity-100 transition-opacity hover:bg-white/10"
                title="Copy"
              >
                {copied ? (
                  <Check className="w-3.5 h-3.5 text-emerald-400" />
                ) : (
                  <Copy className="w-3.5 h-3.5 text-text-muted" />
                )}
              </button>
            )}
          </div>

          {/* Citations */}
          {citations && citations.length > 0 && (
            <div className="flex flex-wrap gap-1.5 px-1">
              {citations.map((cite, i) => (
                <span
                  key={i}
                  className="inline-flex items-center gap-1 px-2 py-1 rounded-lg text-[11px] font-medium bg-cyan-500/10 text-cyan-400 border border-cyan-500/20 hover:bg-cyan-500/15 transition-colors cursor-default"
                  title={cite.snippet || undefined}
                >
                  <FileText className="w-3 h-3" />
                  {cite.file_name}
                  {cite.page_number != null && <span className="text-cyan-400/60">p.{cite.page_number}</span>}
                </span>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
