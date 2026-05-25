import { useState, useEffect, useCallback } from 'react'
import { useDropzone } from 'react-dropzone'
import { Library as LibraryIcon, Search, Loader2, CloudUpload, Image as ImageIcon } from 'lucide-react'
import DocumentCard from '../components/DocumentCard'
import { getDocuments, deleteDocument, uploadDocument, uploadImageDocument } from '../lib/api'
import type { Document } from '../lib/api'

const ACCEPTED_TYPES: Record<string, string[]> = {
  'application/pdf': ['.pdf'],
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
  'text/plain': ['.txt'],
  'image/png': ['.png'],
  'image/jpeg': ['.jpg', '.jpeg'],
}

const isImageFile = (file: File) => file.type === 'image/png' || file.type === 'image/jpeg'

export default function Library() {
  const [documents, setDocuments] = useState<Document[]>([])
  const [loading, setLoading] = useState(true)
  const [uploading, setUploading] = useState(false)
  const [uploadStatus, setUploadStatus] = useState<string | null>(null)
  const [search, setSearch] = useState('')
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null)

  useEffect(() => {
    getDocuments()
      .then((res) => setDocuments(res.documents))
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  const onDrop = useCallback(async (acceptedFiles: File[]) => {
    if (acceptedFiles.length === 0) return

    setUploading(true)
    setUploadStatus(acceptedFiles.some(isImageFile) ? 'Extracting text via AI...' : 'Uploading documents...')

    try {
      let shouldRefresh = false

      for (const file of acceptedFiles) {
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
      }

      if (shouldRefresh) {
        const res = await getDocuments()
        setDocuments(res.documents)
      }
      setUploadStatus('Upload complete')
      setTimeout(() => setUploadStatus(null), 2000)
    } catch (err: any) {
      const msg = err?.response?.data?.detail || err.message || 'Upload failed'
      setUploadStatus(msg)
    } finally {
      setUploading(false)
    }
  }, [])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: ACCEPTED_TYPES,
    disabled: uploading,
  })

  const handleDelete = async (id: string) => {
    if (deleteConfirm !== id) {
      setDeleteConfirm(id)
      return
    }
    try {
      await deleteDocument(id)
      setDocuments((prev) => prev.filter((d) => d.id !== id))
    } catch (err) {
      console.error(err)
    }
    setDeleteConfirm(null)
  }

  const filtered = documents.filter((d) =>
    d.file_name.toLowerCase().includes(search.toLowerCase())
  )

  return (
    <div className="p-6 md:p-8 max-w-6xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center gap-4 justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl gradient-bg flex items-center justify-center shadow-lg shadow-violet-500/20">
              <LibraryIcon className="w-5 h-5 text-white" />
            </div>
            Document Library
          </h1>
          <p className="text-sm text-text-secondary mt-2 ml-[52px]">
            {documents.length} document{documents.length !== 1 ? 's' : ''} uploaded
          </p>
        </div>

        {/* Search */}
        <div className="glass rounded-xl flex items-center gap-2 px-4 py-2.5 w-full md:w-72">
          <Search className="w-4 h-4 text-text-muted flex-shrink-0" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search documents..."
            className="bg-transparent text-sm text-white placeholder:text-text-muted outline-none flex-1"
          />
        </div>
      </div>

      {/* Upload zone */}
      <div
        {...getRootProps()}
        className={`rounded-2xl border border-dashed p-5 transition-all cursor-pointer ${
          isDragActive
            ? 'border-violet-500 bg-violet-500/10'
            : 'border-white/10 hover:border-white/20 hover:bg-white/[0.02]'
        } ${uploading ? 'pointer-events-none opacity-70' : ''}`}
      >
        <input {...getInputProps()} />
        <div className="flex items-center gap-4">
          <div className="w-11 h-11 rounded-xl glass flex items-center justify-center flex-shrink-0">
            {uploading ? (
              <Loader2 className="w-5 h-5 text-violet-400 animate-spin" />
            ) : (
              <CloudUpload className="w-5 h-5 text-violet-400" />
            )}
          </div>
          <div className="min-w-0">
            <p className="text-sm font-medium text-white">
              {uploading ? uploadStatus : 'Drop documents or images here, or browse'}
            </p>
            <p className="text-xs text-text-muted mt-1">
              Supports PDF, DOCX, TXT, PNG, and JPG. Images are extracted with AI and stored with a thumbnail.
            </p>
          </div>
          <ImageIcon className="w-4 h-4 text-text-muted ml-auto hidden sm:block" />
        </div>
      </div>

      {/* Delete confirmation toast */}
      {deleteConfirm && (
        <div className="glass rounded-xl p-4 flex items-center justify-between border border-rose-500/20 animate-fade-in">
          <p className="text-sm text-text-secondary">
            Are you sure you want to delete this document? This action cannot be undone.
          </p>
          <div className="flex gap-2 ml-4 flex-shrink-0">
            <button
              onClick={() => setDeleteConfirm(null)}
              className="px-3 py-1.5 rounded-lg text-xs font-medium glass text-text-secondary hover:text-white transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={() => handleDelete(deleteConfirm)}
              className="px-3 py-1.5 rounded-lg text-xs font-medium bg-rose-500/20 text-rose-400 hover:bg-rose-500/30 transition-colors"
            >
              Delete
            </button>
          </div>
        </div>
      )}

      {/* Content */}
      {loading ? (
        <div className="flex items-center justify-center h-64">
          <Loader2 className="w-8 h-8 text-violet-400 animate-spin" />
        </div>
      ) : filtered.length === 0 ? (
        <div className="glass rounded-2xl p-12 text-center space-y-4">
          <div className="w-16 h-16 rounded-2xl glass flex items-center justify-center mx-auto">
            <LibraryIcon className="w-8 h-8 text-text-muted" />
          </div>
          <h3 className="text-lg font-semibold text-white">
            {search ? 'No matches found' : 'No documents yet'}
          </h3>
          <p className="text-sm text-text-muted">
            {search ? 'Try a different search term' : 'Upload your first document to get started'}
          </p>
        </div>
      ) : (
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4 stagger-children">
          {filtered.map((doc) => (
            <DocumentCard key={doc.id} document={doc} onDelete={handleDelete} />
          ))}
        </div>
      )}
    </div>
  )
}
