import { useState, useCallback } from 'react'
import { useDropzone } from 'react-dropzone'
import { Upload as UploadIcon, FileText, CheckCircle2, XCircle, Loader2, CloudUpload } from 'lucide-react'
import { uploadDocument } from '../lib/api'

interface UploadResult {
  file_name: string
  status: 'success' | 'error'
  message: string
}

const ACCEPTED_TYPES: Record<string, string[]> = {
  'application/pdf': ['.pdf'],
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
  'text/plain': ['.txt'],
}

export default function Upload() {
  const [uploading, setUploading] = useState(false)
  const [results, setResults] = useState<UploadResult[]>([])

  const onDrop = useCallback(async (acceptedFiles: File[]) => {
    if (acceptedFiles.length === 0) return

    setUploading(true)
    const newResults: UploadResult[] = []

    for (const file of acceptedFiles) {
      try {
        const res = await uploadDocument(file)
        newResults.push({ file_name: res.file_name, status: 'success', message: res.message })
      } catch (err: any) {
        const msg = err?.response?.data?.detail || err.message || 'Upload failed'
        newResults.push({ file_name: file.name, status: 'error', message: msg })
      }
    }

    setResults((prev) => [...newResults, ...prev])
    setUploading(false)
  }, [])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: ACCEPTED_TYPES,
    disabled: uploading,
  })

  return (
    <div className="p-6 md:p-8 max-w-3xl mx-auto space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-white flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl gradient-bg flex items-center justify-center shadow-lg shadow-violet-500/20">
            <UploadIcon className="w-5 h-5 text-white" />
          </div>
          Upload Documents
        </h1>
        <p className="text-sm text-text-secondary mt-2 ml-[52px]">
          Upload PDF, DOCX, or TXT files to start chatting with your study materials.
        </p>
      </div>

      {/* Drop zone */}
      <div
        {...getRootProps()}
        className={`
          relative rounded-2xl border-2 border-dashed p-12 text-center
          transition-all duration-300 cursor-pointer group
          ${isDragActive
            ? 'border-violet-500 bg-violet-500/10 scale-[1.01]'
            : 'border-white/10 hover:border-white/20 hover:bg-white/[0.02]'
          }
          ${uploading ? 'pointer-events-none opacity-60' : ''}
        `}
      >
        <input {...getInputProps()} />

        <div className="space-y-4">
          <div className={`w-16 h-16 rounded-2xl mx-auto flex items-center justify-center transition-all ${
            isDragActive
              ? 'gradient-bg shadow-lg shadow-violet-500/25 scale-110'
              : 'glass group-hover:scale-105'
          }`}>
            {uploading ? (
              <Loader2 className="w-7 h-7 text-violet-400 animate-spin" />
            ) : (
              <CloudUpload className={`w-7 h-7 ${isDragActive ? 'text-white' : 'text-violet-400'}`} />
            )}
          </div>

          {uploading ? (
            <div>
              <p className="text-base font-medium text-white">Uploading...</p>
              <p className="text-sm text-text-muted mt-1">Please wait while your files are processed</p>
            </div>
          ) : isDragActive ? (
            <div>
              <p className="text-base font-medium text-white">Drop files here</p>
              <p className="text-sm text-violet-400 mt-1">Release to upload</p>
            </div>
          ) : (
            <div>
              <p className="text-base font-medium text-white">
                Drag & drop files here, or <span className="text-violet-400">browse</span>
              </p>
              <p className="text-sm text-text-muted mt-1">Supports PDF, DOCX, and TXT</p>
            </div>
          )}
        </div>

        {/* Decorative corner accents */}
        <div className="absolute top-3 left-3 w-4 h-4 border-t-2 border-l-2 border-violet-500/30 rounded-tl-lg" />
        <div className="absolute top-3 right-3 w-4 h-4 border-t-2 border-r-2 border-violet-500/30 rounded-tr-lg" />
        <div className="absolute bottom-3 left-3 w-4 h-4 border-b-2 border-l-2 border-violet-500/30 rounded-bl-lg" />
        <div className="absolute bottom-3 right-3 w-4 h-4 border-b-2 border-r-2 border-violet-500/30 rounded-br-lg" />
      </div>

      {/* Results */}
      {results.length > 0 && (
        <div className="space-y-3 stagger-children">
          <h2 className="text-sm font-semibold text-text-secondary uppercase tracking-wider">Upload Results</h2>
          {results.map((r, i) => (
            <div
              key={`${r.file_name}-${i}`}
              className={`flex items-center gap-3 p-4 rounded-xl border animate-fade-in ${
                r.status === 'success'
                  ? 'glass border-emerald-500/20'
                  : 'glass border-rose-500/20'
              }`}
            >
              <div className={`w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0 ${
                r.status === 'success' ? 'bg-emerald-500/15' : 'bg-rose-500/15'
              }`}>
                {r.status === 'success' ? (
                  <CheckCircle2 className="w-5 h-5 text-emerald-400" />
                ) : (
                  <XCircle className="w-5 h-5 text-rose-400" />
                )}
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-white flex items-center gap-2">
                  <FileText className="w-3.5 h-3.5 text-text-muted" />
                  {r.file_name}
                </p>
                <p className={`text-xs mt-0.5 ${
                  r.status === 'success' ? 'text-emerald-400/80' : 'text-rose-400/80'
                }`}>
                  {r.message}
                </p>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
