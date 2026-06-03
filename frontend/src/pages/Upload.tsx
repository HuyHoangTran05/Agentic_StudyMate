import { useCallback, useState } from 'react'
import { useDropzone } from 'react-dropzone'
import {
  CheckCircle2,
  CloudUpload,
  FileText,
  Image as ImageIcon,
  Loader2,
  Plus,
  Upload as UploadIcon,
  XCircle,
} from 'lucide-react'
import { uploadDocument, uploadImageDocument } from '../lib/api'
import { Badge, Button, Card, PageHeader, PageShell } from '../components/ui'
import { cx } from '../lib/cx'

interface UploadResult {
  file_name: string
  status: 'success' | 'error'
  message: string
  image_url?: string
}

interface UploadError {
  response?: {
    status?: number
    data?: {
      detail?: string | { message?: string }
    }
  }
  message?: string
}

const ACCEPTED_TYPES: Record<string, string[]> = {
  'application/pdf': ['.pdf'],
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
  'text/plain': ['.txt'],
  'image/png': ['.png'],
  'image/jpeg': ['.jpg', '.jpeg'],
}

const isImageFile = (file: File) => file.type === 'image/png' || file.type === 'image/jpeg'

const asUploadError = (err: unknown) => err as UploadError

const isDuplicateUploadError = (err: unknown) => asUploadError(err).response?.status === 409

const getUploadErrorMessage = (err: unknown) => {
  if (isDuplicateUploadError(err)) return 'File already exists in the library!'

  const uploadError = asUploadError(err)
  const detail = uploadError.response?.data?.detail
  if (typeof detail === 'string') return detail
  if (detail?.message) return detail.message
  return uploadError.message || 'Upload failed'
}

export default function Upload() {
  const [uploading, setUploading] = useState(false)
  const [uploadingImage, setUploadingImage] = useState(false)
  const [results, setResults] = useState<UploadResult[]>([])

  const onDrop = useCallback(async (acceptedFiles: File[]) => {
    if (acceptedFiles.length === 0) return

    setUploading(true)
    setUploadingImage(acceptedFiles.some(isImageFile))
    const newResults: UploadResult[] = []

    try {
      for (const file of acceptedFiles) {
        try {
          if (isImageFile(file)) {
            const res = await uploadImageDocument(file)
            newResults.push({
              file_name: res.file_name,
              status: 'success',
              message: `Image processed. Extracted text into ${res.total_chunks} chunk${res.total_chunks !== 1 ? 's' : ''}.`,
              image_url: res.image_url,
            })
          } else {
            const res = await uploadDocument(file)
            newResults.push({ file_name: res.file_name, status: 'success', message: res.message })
          }
        } catch (err) {
          const msg = getUploadErrorMessage(err)
          if (isDuplicateUploadError(err)) alert(msg)
          newResults.push({ file_name: file.name, status: 'error', message: msg })
        }
      }
    } finally {
      setResults((prev) => [...newResults, ...prev])
      setUploading(false)
      setUploadingImage(false)
    }
  }, [])

  const { getRootProps, getInputProps, isDragActive, open } = useDropzone({
    onDrop,
    accept: ACCEPTED_TYPES,
    disabled: uploading,
    noClick: true,
  })

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
            uploading && 'pointer-events-none opacity-70 uploading-state',
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
              {uploading ? <Loader2 className="h-9 w-9 animate-spin" /> : <CloudUpload className="h-9 w-9" />}
            </div>

            <h2 className="font-display text-2xl font-semibold text-white md:text-3xl">
              {uploading ? uploadLabel : isDragActive ? 'Release to upload' : 'Drag and drop files here'}
            </h2>
            <p className="mt-3 max-w-md text-sm leading-6 text-text-secondary">
              {uploading
                ? 'Please keep this page open while StudyMate processes your source material.'
                : 'Click browse or drop files from your computer. Images are analyzed and stored with extracted text.'}
            </p>

            <Button
              type="button"
              className="mt-8 rounded-full px-6"
              onClick={(event) => {
                event.stopPropagation()
                open()
              }}
              disabled={uploading}
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
            <Badge tone={uploading ? 'cyan' : 'neutral'}>{uploading ? 'Active' : `${results.length} results`}</Badge>
          </div>

          {uploading && (
            <Card className="overflow-hidden border-accent-cyan/30 p-4 uploading-state">
              <div className="flex items-start gap-3">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border border-accent-cyan/25 bg-accent-cyan/10">
                  <Loader2 className="h-5 w-5 animate-spin text-accent-cyan" />
                </div>
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium text-white">{uploadLabel}</p>
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

          {results.length === 0 && !uploading ? (
            <Card className="p-5">
              <div className="flex items-start gap-3">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-white/[0.04] text-text-muted">
                  <FileText className="h-5 w-5" />
                </div>
                <div>
                  <p className="text-sm font-medium text-white">No uploads yet</p>
                  <p className="mt-1 text-xs leading-5 text-text-muted">
                    Completed files and duplicate warnings will appear here.
                  </p>
                </div>
              </div>
            </Card>
          ) : (
            <div className="space-y-3">
              {results.map((result, index) => (
                <Card
                  key={`${result.file_name}-${index}`}
                  className={cx(
                    'relative overflow-hidden p-4',
                    result.status === 'success' ? 'border-emerald-300/20' : 'border-rose-300/20',
                  )}
                >
                  <div
                    className={cx(
                      'absolute bottom-0 left-0 top-0 w-1',
                      result.status === 'success' ? 'bg-accent-emerald/60' : 'bg-accent-rose/70',
                    )}
                  />
                  <div className="flex items-start gap-3">
                    <div
                      className={cx(
                        'flex h-10 w-10 shrink-0 items-center justify-center rounded-lg',
                        result.status === 'success' ? 'bg-emerald-400/10 text-accent-emerald' : 'bg-rose-300/10 text-accent-rose',
                      )}
                    >
                      {result.status === 'success' ? <CheckCircle2 className="h-5 w-5" /> : <XCircle className="h-5 w-5" />}
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="flex items-center gap-2 truncate text-sm font-medium text-white">
                        {result.image_url ? <ImageIcon className="h-3.5 w-3.5 text-accent-cyan" /> : <FileText className="h-3.5 w-3.5 text-text-muted" />}
                        <span className="truncate">{result.file_name}</span>
                      </p>
                      <p
                        className={cx(
                          'mt-1 text-xs leading-5',
                          result.status === 'success' ? 'text-accent-emerald' : 'text-accent-rose',
                        )}
                      >
                        {result.message}
                      </p>
                    </div>
                  </div>
                </Card>
              ))}
            </div>
          )}
        </aside>
      </div>
    </PageShell>
  )
}
