import {
  AlertCircle,
  CheckCircle2,
  Clock,
  FileText,
  FileType,
  FileType2,
  Image as ImageIcon,
  Loader2,
  Trash2,
} from 'lucide-react'
import type { Document } from '../lib/api'
import { cx } from '../lib/cx'
import { Card, StatusBadge } from './ui'

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

const statusIcons: Record<string, typeof CheckCircle2> = {
  ready: CheckCircle2,
  processing: Loader2,
  failed: AlertCircle,
}

export default function DocumentCard({ document: doc, onDelete }: Props) {
  const Icon = fileIcons[doc.file_type] || FileText
  const StatusIcon = statusIcons[doc.status] || Loader2

  const uploadDate = new Date(doc.upload_time).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  })

  return (
    <Card interactive className="group p-5 animate-fade-in">
      <div className="mb-4 flex items-start gap-3">
        {doc.image_url ? (
          <img
            src={doc.image_url}
            alt={doc.file_name}
            className="h-12 w-12 shrink-0 rounded-lg border border-white/10 object-cover"
          />
        ) : (
          <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-lg bg-accent-violet/10 text-accent-violet">
            <Icon className="h-5 w-5" />
          </div>
        )}
        <div className="min-w-0 flex-1">
          <h3 className="truncate text-sm font-semibold text-white" title={doc.file_name}>
            {doc.file_name}
          </h3>
          <p className="mt-1 text-xs font-medium text-text-muted">{doc.file_type}</p>
        </div>
      </div>

      <div className="mb-4 flex items-center gap-4 text-xs text-text-muted">
        <span className="flex items-center gap-1.5">
          <Clock className="h-3.5 w-3.5" />
          {uploadDate}
        </span>
        <span>{doc.total_chunks} chunks</span>
      </div>

      <div className="flex items-center justify-between">
        <span className="inline-flex items-center gap-1.5">
          <StatusIcon className={cx('h-3.5 w-3.5', doc.status === 'processing' && 'animate-spin')} />
          <StatusBadge status={doc.status} />
        </span>

        {onDelete && (
          <button
            onClick={() => onDelete(doc.id)}
            className="rounded-lg p-2 text-text-muted opacity-0 transition-all hover:bg-rose-400/10 hover:text-accent-rose group-hover:opacity-100"
            title="Delete document"
          >
            <Trash2 className="h-4 w-4" />
          </button>
        )}
      </div>
    </Card>
  )
}
