import { useCallback } from 'react'
import { useDropzone } from 'react-dropzone'
import {
  AlertCircle,
  CheckCircle2,
  CloudUpload,
  FileText,
  Image as ImageIcon,
  Loader2,
  Plus,
  Upload as UploadIcon,
  RefreshCw,
} from 'lucide-react'
import { Badge, Button, Card, PageHeader, PageShell } from '../components/ui'
import { cx } from '../lib/cx'
import { useUploadStore } from '../stores/uploadStore'
import type { UploadJob, UploadJobStatus } from '../stores/uploadStore'

const ACCEPTED_TYPES: Record<string, string[]> = {
  'application/pdf': ['.pdf'],
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
  'text/plain': ['.txt'],
  'image/png': ['.png'],
  'image/jpeg': ['.jpg', '.jpeg'],
}

const statusConfig: Record<UploadJobStatus, { label: string; tone: 'cyan' | 'amber' | 'emerald' | 'rose' | 'neutral' }> = {
  queued: { label: 'Queued', tone: 'neutral' },
  uploading: { label: 'Uploading', tone: 'cyan' },
  processing: { label: 'Processing', tone: 'amber' },
  ready: { label: 'Ready', tone: 'emerald' },
  error: { label: 'Error', tone: 'rose' },
}

export default function Upload() {
  const {
    jobs,
    isUploading,
    hasActiveJobs,
    startUpload,
    refreshUploadStatuses,
    clearCompleted,
  } = useUploadStore()

  const onDrop = useCallback(async (acceptedFiles: File[]) => {
    if (acceptedFiles.length === 0) return
    await startUpload(acceptedFiles)
  }, [startUpload])

  const { getRootProps, getInputProps, isDragActive, open } = useDropzone({
    onDrop,
    accept: ACCEPTED_TYPES,
    disabled: isUploading,
    noClick: true,
  })

  const uploadingImage = jobs.some((job) => job.status === 'uploading' && job.fileType === 'image')
  const uploadLabel = uploadingImage ? 'Extracting text via AI...' : 'Uploading and indexing...'

  return (
    <PageShell wide className="space-y-8">
      <PageHeader
        icon={UploadIcon}
        eyebrow="Source Intake"
        title="Upload Documents"
        description="Add study materials to your intelligence library. Documents and images are routed through the existing ingestion pipeline for semantic search and study tools."
      />

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_380px]">
        <Card
          {...getRootProps()}
          className={cx(
            'relative flex min-h-[420px] cursor-pointer flex-col items-center justify-center overflow-hidden border-2 border-dashed p-8 text-center transition-all duration-300',
            isDragActive
              ? 'scale-[1.01] border-accent-cyan/80 bg-accent-cyan/[0.045]'
              : 'border-accent-cyan/25 hover:border-accent-cyan/60 hover:bg-white/[0.03]',
            isUploading && 'pointer-events-none opacity-70 uploading-state',
          )}
        >
          <input {...getInputProps()} />
          <div className="absolute inset-0 surface-grid opacity-35" />
          <div className="relative z-10 flex max-w-xl flex-col items-center">
            <div
              className={cx(
                'mb-6 flex h-20 w-20 items-center justify-center rounded-full border transition-transform duration-300',
                isDragActive
                  ? 'gradient-bg border-transparent text-surface-950 shadow-[0_0_38px_rgba(76,215,246,0.22)]'
                  : 'border-white/10 bg-surface-650 text-accent-violet group-hover:scale-105',
              )}
            >
              {isUploading ? <Loader2 className="h-9 w-9 animate-spin" /> : <CloudUpload className="h-9 w-9" />}
            </div>

            <h2 className="font-display text-2xl font-semibold text-white md:text-3xl">
              {isUploading ? uploadLabel : isDragActive ? 'Release to upload' : 'Drag and drop files here'}
            </h2>
            <p className="mt-3 max-w-md text-sm leading-6 text-text-secondary">
              {isUploading
                ? 'Upload progress is saved globally, so you can navigate away and return without losing the queue.'
                : 'Click browse or drop files from your computer. Images are analyzed and stored with extracted text.'}
            </p>

            <Button
              type="button"
              className="mt-8 rounded-full px-6"
              onClick={(event) => {
                event.stopPropagation()
                open()
              }}
              disabled={isUploading}
            >
              <Plus className="h-4 w-4" />
              Select Files
            </Button>

            <div className="mt-8 flex flex-wrap justify-center gap-2">
              {['PDF', 'DOCX', 'TXT', 'PNG / JPG'].map((type) => (
                <Badge key={type} tone="neutral">
                  {type}
                </Badge>
              ))}
            </div>
          </div>
        </Card>

        <aside className="space-y-4">
          <div className="flex items-center justify-between border-b border-white/10 pb-3">
            <h2 className="font-display text-lg font-semibold text-white">Processing Queue</h2>
            <Badge tone={hasActiveJobs ? 'cyan' : 'neutral'}>{hasActiveJobs ? 'Active' : `${jobs.length} recent`}</Badge>
          </div>

          {hasActiveJobs && (
            <Card className="overflow-hidden border-accent-cyan/30 p-4 uploading-state">
              <div className="flex items-start gap-3">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border border-accent-cyan/25 bg-accent-cyan/10">
                  <Loader2 className="h-5 w-5 animate-spin text-accent-cyan" />
                </div>
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium text-white">{isUploading ? uploadLabel : 'Processing in the library...'}</p>
                  <div className="mt-2 flex items-center gap-2 text-xs text-accent-cyan">
                    <span className="h-1.5 w-1.5 rounded-full bg-accent-cyan agent-pulse" />
                    Extracting, chunking, and embedding
                  </div>
                  <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-white/[0.06]">
                    <div className="h-full w-2/3 rounded-full gradient-bg" />
                  </div>
                </div>
              </div>
            </Card>
          )}

          <div className="flex gap-2">
            <Button
              type="button"
              variant="ghost"
              className="flex-1"
              onClick={() => refreshUploadStatuses().catch(console.error)}
              disabled={jobs.length === 0}
            >
              <RefreshCw className="h-4 w-4" />
              Refresh
            </Button>
            <Button
              type="button"
              variant="ghost"
              className="flex-1"
              onClick={clearCompleted}
              disabled={jobs.every((job) => job.status === 'queued' || job.status === 'uploading' || job.status === 'processing')}
            >
              Clear done
            </Button>
          </div>

          {jobs.length === 0 && !hasActiveJobs ? (
            <Card className="p-5">
              <div className="flex items-start gap-3">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-white/[0.04] text-text-muted">
                  <FileText className="h-5 w-5" />
                </div>
                <div>
                  <p className="text-sm font-medium text-white">No uploads yet</p>
                  <p className="mt-1 text-xs leading-5 text-text-muted">
                    Upload progress and recent results will remain here while you move around the app.
                  </p>
                </div>
              </div>
            </Card>
          ) : (
            <div className="space-y-3">
              {jobs.map((job) => <UploadJobCard key={job.id} job={job} />)}
            </div>
          )}
        </aside>
      </div>
    </PageShell>
  )
}

function UploadJobCard({ job }: { job: UploadJob }) {
  const status = statusConfig[job.status]
  const isBusy = job.status === 'queued' || job.status === 'uploading' || job.status === 'processing'

  return (
    <Card
      className={cx(
        'relative overflow-hidden p-4',
        job.status === 'ready' && 'border-emerald-300/20',
        job.status === 'error' && 'border-rose-300/20',
        isBusy && 'border-accent-cyan/20',
      )}
    >
      <div
        className={cx(
          'absolute bottom-0 left-0 top-0 w-1',
          job.status === 'ready' && 'bg-accent-emerald/60',
          job.status === 'error' && 'bg-accent-rose/70',
          isBusy && 'bg-accent-cyan/60',
        )}
      />
      <div className="flex items-start gap-3">
        <div
          className={cx(
            'flex h-10 w-10 shrink-0 items-center justify-center rounded-lg',
            job.status === 'ready' && 'bg-emerald-400/10 text-accent-emerald',
            job.status === 'error' && 'bg-rose-300/10 text-accent-rose',
            isBusy && 'bg-accent-cyan/10 text-accent-cyan',
          )}
        >
          {job.status === 'ready' ? (
            <CheckCircle2 className="h-5 w-5" />
          ) : job.status === 'error' ? (
            <AlertCircle className="h-5 w-5" />
          ) : (
            <Loader2 className="h-5 w-5 animate-spin" />
          )}
        </div>
        <div className="min-w-0 flex-1">
          <p className="flex items-center gap-2 truncate text-sm font-medium text-white">
            {job.imageUrl || job.fileType === 'image' ? (
              <ImageIcon className="h-3.5 w-3.5 text-accent-cyan" />
            ) : (
              <FileText className="h-3.5 w-3.5 text-text-muted" />
            )}
            <span className="truncate">{job.fileName}</span>
          </p>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <Badge tone={status.tone}>{status.label}</Badge>
            {job.documentId && <span className="text-[11px] text-text-muted">ID {job.documentId.slice(0, 8)}</span>}
            {typeof job.totalChunks === 'number' && <span className="text-[11px] text-text-muted">{job.totalChunks} chunks</span>}
          </div>
          <p
            className={cx(
              'mt-2 text-xs leading-5',
              job.status === 'ready' && 'text-accent-emerald',
              job.status === 'error' && 'text-accent-rose',
              isBusy && 'text-accent-cyan',
            )}
          >
            {job.message}
          </p>
        </div>
      </div>
    </Card>
  )
}
