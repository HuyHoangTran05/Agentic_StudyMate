import { useCallback, useEffect, useState } from 'react'
import { useDropzone } from 'react-dropzone'
import {
  CloudUpload,
  Image as ImageIcon,
  Library as LibraryIcon,
  Loader2,
  Search,
} from 'lucide-react'
import DocumentCard from '../components/DocumentCard'
import { deleteDocument, getDocuments, uploadDocument, uploadImageDocument } from '../lib/api'
import type { Document } from '../lib/api'
import { Badge, Button, Card, EmptyState, LoadingState, PageHeader, PageShell } from '../components/ui'
import { cx } from '../lib/cx'

const ACCEPTED_TYPES: Record<string, string[]> = {
  'application/pdf': ['.pdf'],
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
  'text/plain': ['.txt'],
  'image/png': ['.png'],
  'image/jpeg': ['.jpg', '.jpeg'],
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

export default function Library() {
  const [documents, setDocuments] = useState<Document[]>([])
  const [loading, setLoading] = useState(true)
  const [uploading, setUploading] = useState(false)
  const [uploadStatus, setUploadStatus] = useState<string | null>(null)
  const [search, setSearch] = useState('')
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null)

  const refreshDocuments = useCallback(async () => {
    const res = await getDocuments()
    setDocuments(res.documents)
  }, [])

  useEffect(() => {
    let cancelled = false

    void getDocuments()
      .then((res) => {
        if (!cancelled) setDocuments(res.documents)
      })
      .catch(console.error)
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [])

  const onDrop = useCallback(async (acceptedFiles: File[]) => {
    if (acceptedFiles.length === 0) return

    setUploading(true)
    setUploadStatus(acceptedFiles.some(isImageFile) ? 'Extracting text via AI...' : 'Uploading documents...')

    try {
      let shouldRefresh = false
      let hadError = false

      for (const file of acceptedFiles) {
        try {
          if (isImageFile(file)) {
            const res = await uploadImageDocument(file)
            const newDoc: Document = {
              id: res.document_id,
              file_name: res.file_name,
              file_type: 'image',
              image_url: res.image_url,
              upload_time: new Date().toISOString(),
              total_chunks: res.total_chunks,
              status: res.status,
            }
            setDocuments((prev) => [newDoc, ...prev.filter((doc) => doc.id !== newDoc.id)])
          } else {
            await uploadDocument(file)
            shouldRefresh = true
          }
        } catch (err) {
          hadError = true
          const msg = getUploadErrorMessage(err)
          if (isDuplicateUploadError(err)) alert(msg)
          setUploadStatus(msg)
        }
      }

      if (shouldRefresh) {
        await refreshDocuments()
      }

      if (!hadError) setUploadStatus('Upload complete')
      window.setTimeout(() => setUploadStatus(null), 2200)
    } finally {
      setUploading(false)
    }
  }, [refreshDocuments])

  const { getRootProps, getInputProps, isDragActive, open } = useDropzone({
    onDrop,
    accept: ACCEPTED_TYPES,
    disabled: uploading,
    noClick: true,
  })

  const handleDelete = async (id: string) => {
    if (deleteConfirm !== id) {
      setDeleteConfirm(id)
      return
    }
    try {
      await deleteDocument(id)
      setDocuments((prev) => prev.filter((doc) => doc.id !== id))
    } catch (err) {
      console.error(err)
    }
    setDeleteConfirm(null)
  }

  const filtered = documents.filter((doc) =>
    doc.file_name.toLowerCase().includes(search.toLowerCase())
  )

  return (
    <PageShell wide className="space-y-6">
      <PageHeader
        icon={LibraryIcon}
        eyebrow="Knowledge Base"
        title="Document Library"
        description={`${documents.length} document${documents.length === 1 ? '' : 's'} uploaded and available for chat, citations, and study generation.`}
        action={
          <div className="field-surface flex w-full items-center gap-2 rounded-full px-4 py-2.5 md:w-80">
            <Search className="h-4 w-4 shrink-0 text-text-muted" />
            <input
              type="text"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search documents..."
              className="min-w-0 flex-1 bg-transparent text-sm text-white outline-none placeholder:text-text-muted"
            />
          </div>
        }
      />

      <Card
        {...getRootProps()}
        className={cx(
          'cursor-pointer border border-dashed p-5 transition-all',
          isDragActive ? 'border-accent-cyan/70 bg-accent-cyan/[0.04]' : 'border-white/12 hover:border-accent-violet/30 hover:bg-white/[0.03]',
          uploading && 'pointer-events-none opacity-70',
        )}
      >
        <input {...getInputProps()} />
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center">
          <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-lg bg-white/[0.04] text-accent-violet">
            {uploading ? <Loader2 className="h-5 w-5 animate-spin" /> : <CloudUpload className="h-5 w-5" />}
          </div>
          <div className="min-w-0 flex-1">
            <p className="text-sm font-medium text-white">
              {uploading ? uploadStatus : isDragActive ? 'Drop files to upload' : 'Drop documents or images here'}
            </p>
            <p className="mt-1 text-xs leading-5 text-text-muted">
              Supports PDF, DOCX, TXT, PNG, and JPG. Images are extracted with AI and stored with a thumbnail.
            </p>
          </div>
          <Button
            type="button"
            variant="ghost"
            className="shrink-0"
            onClick={(event) => {
              event.stopPropagation()
              open()
            }}
            disabled={uploading}
          >
            Browse
          </Button>
          <ImageIcon className="hidden h-4 w-4 text-text-muted sm:block" />
        </div>
      </Card>

      {uploadStatus && !uploading && (
        <Badge tone={uploadStatus === 'File already exists in the library!' ? 'rose' : 'cyan'}>
          {uploadStatus}
        </Badge>
      )}

      {deleteConfirm && (
        <Card className="flex flex-col gap-4 border-rose-300/20 p-4 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-sm text-text-secondary">
            Delete this document? This action cannot be undone.
          </p>
          <div className="flex gap-2">
            <Button variant="ghost" onClick={() => setDeleteConfirm(null)}>
              Cancel
            </Button>
            <Button variant="danger" onClick={() => handleDelete(deleteConfirm)}>
              Delete
            </Button>
          </div>
        </Card>
      )}

      {loading ? (
        <LoadingState label="Loading library..." />
      ) : filtered.length === 0 ? (
        <EmptyState
          icon={LibraryIcon}
          title={search ? 'No matches found' : 'No documents yet'}
          description={search ? 'Try another search term.' : 'Upload your first source to start building your study library.'}
        />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {filtered.map((doc) => (
            <DocumentCard key={doc.id} document={doc} onDelete={handleDelete} />
          ))}
        </div>
      )}
    </PageShell>
  )
}
