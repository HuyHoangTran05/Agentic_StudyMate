import { FileText, FileType, FileType2, Trash2, Clock, CheckCircle2, AlertCircle, Loader2, Image as ImageIcon } from 'lucide-react'
import type { Document } from '../lib/api'

interface Props {
  document: Document
  onDelete?: (id: string) => void
}

const fileIcons: Record<string, typeof FileText> = {
  pdf: FileType,
  docx: FileType2,
  txt: FileText,
  image: ImageIcon,
}

const statusConfig: Record<string, { icon: typeof CheckCircle2; color: string; label: string }> = {
  ready: { icon: CheckCircle2, color: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20', label: 'Ready' },
  processing: { icon: Loader2, color: 'text-amber-400 bg-amber-500/10 border-amber-500/20', label: 'Processing' },
  failed: { icon: AlertCircle, color: 'text-rose-400 bg-rose-500/10 border-rose-500/20', label: 'Failed' },
}

export default function DocumentCard({ document: doc, onDelete }: Props) {
  const Icon = fileIcons[doc.file_type] || FileText
  const status = statusConfig[doc.status] || statusConfig.processing
  const StatusIcon = status.icon

  const uploadDate = new Date(doc.upload_time).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  })

  return (
    <div className="glass glass-hover rounded-2xl p-5 transition-all duration-300 hover:shadow-lg hover:shadow-violet-500/5 hover:-translate-y-0.5 group animate-fade-in">
      {/* Header */}
      <div className="flex items-start gap-3 mb-4">
        {doc.image_url ? (
          <img
            src={doc.image_url}
            alt={doc.file_name}
            className="w-11 h-11 rounded-xl object-cover border border-white/10 flex-shrink-0"
          />
        ) : (
          <div className="w-11 h-11 rounded-xl gradient-bg-subtle flex items-center justify-center flex-shrink-0">
            <Icon className="w-5 h-5 text-violet-400" />
          </div>
        )}
        <div className="min-w-0 flex-1">
          <h3 className="text-sm font-semibold text-white truncate" title={doc.file_name}>
            {doc.file_name}
          </h3>
          <p className="text-xs text-text-muted uppercase tracking-wide mt-0.5">
            {doc.file_type}
          </p>
        </div>
      </div>

      {/* Stats */}
      <div className="flex items-center gap-4 mb-4 text-xs text-text-muted">
        <span className="flex items-center gap-1.5">
          <Clock className="w-3.5 h-3.5" />
          {uploadDate}
        </span>
        <span>{doc.total_chunks} chunks</span>
      </div>

      {/* Footer */}
      <div className="flex items-center justify-between">
        <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-[11px] font-medium border ${status.color}`}>
          <StatusIcon className={`w-3 h-3 ${doc.status === 'processing' ? 'animate-spin' : ''}`} />
          {status.label}
        </span>

        {onDelete && (
          <button
            onClick={() => onDelete(doc.id)}
            className="p-2 rounded-lg text-text-muted hover:text-rose-400 hover:bg-rose-500/10 transition-colors opacity-0 group-hover:opacity-100"
            title="Delete document"
          >
            <Trash2 className="w-4 h-4" />
          </button>
        )}
      </div>
    </div>
  )
}
