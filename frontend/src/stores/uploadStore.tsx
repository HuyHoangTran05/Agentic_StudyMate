/* eslint-disable react-refresh/only-export-components */
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react'
import type { ReactNode } from 'react'
import {
  getDocuments,
  uploadDocument,
  uploadImageDocument,
} from '../lib/api'
import type { Document } from '../lib/api'

export type UploadJobStatus = 'queued' | 'uploading' | 'processing' | 'ready' | 'error'

export interface UploadJob {
  id: string
  fileName: string
  fileType: string
  status: UploadJobStatus
  message: string
  createdAt: string
  updatedAt: string
  documentId?: string
  backendStatus?: string
  imageUrl?: string
  totalChunks?: number
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

interface UploadStoreState {
  jobs: UploadJob[]
  isUploading: boolean
  hasActiveJobs: boolean
  startUpload: (files: File[]) => Promise<void>
  refreshUploadStatuses: () => Promise<void>
  clearCompleted: () => void
}

const UploadContext = createContext<UploadStoreState | null>(null)

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

const getInitialStatus = (backendStatus?: string): UploadJobStatus => {
  const normalized = backendStatus?.toLowerCase()
  if (normalized === 'ready') return 'ready'
  if (normalized === 'failed' || normalized === 'error') return 'error'
  return 'processing'
}

const getFileType = (file: File) => {
  if (isImageFile(file)) return 'image'
  const extension = file.name.split('.').pop()
  return extension?.toLowerCase() || file.type || 'document'
}

const createJob = (file: File): UploadJob => {
  const now = new Date().toISOString()
  return {
    id: `${Date.now()}-${file.name}-${Math.random().toString(36).slice(2)}`,
    fileName: file.name,
    fileType: getFileType(file),
    status: 'queued',
    message: 'Waiting to upload',
    createdAt: now,
    updatedAt: now,
  }
}

function updateJobFromDocument(job: UploadJob, doc: Document): UploadJob {
  const normalized = doc.status.toLowerCase()
  const status: UploadJobStatus =
    normalized === 'ready'
      ? 'ready'
      : normalized === 'failed' || normalized === 'error'
        ? 'error'
        : 'processing'

  return {
    ...job,
    documentId: doc.id,
    backendStatus: doc.status,
    imageUrl: doc.image_url ?? job.imageUrl,
    totalChunks: doc.total_chunks,
    status,
    message:
      status === 'ready'
        ? 'Ready for analysis.'
        : status === 'error'
          ? 'Processing failed.'
          : 'Processing in the library...',
    updatedAt: new Date().toISOString(),
  }
}

export function UploadProvider({ children }: { children: ReactNode }) {
  const [jobs, setJobs] = useState<UploadJob[]>([])

  const updateJob = useCallback((jobId: string, patch: Partial<UploadJob>) => {
    setJobs((current) =>
      current.map((job) =>
        job.id === jobId ? { ...job, ...patch, updatedAt: new Date().toISOString() } : job
      )
    )
  }, [])

  const refreshUploadStatuses = useCallback(async () => {
    const { documents } = await getDocuments()
    setJobs((current) =>
      current.map((job) => {
        if (job.status !== 'processing' && job.status !== 'uploading') return job

        const matchingDoc = documents.find((doc) =>
          (job.documentId && doc.id === job.documentId) || doc.file_name === job.fileName
        )

        return matchingDoc ? updateJobFromDocument(job, matchingDoc) : job
      })
    )
  }, [])

  const startUpload = useCallback(async (files: File[]) => {
    if (files.length === 0) return

    const newJobs = files.map(createJob)
    setJobs((current) => [...newJobs, ...current].slice(0, 30))

    for (let index = 0; index < files.length; index += 1) {
      const file = files[index]
      const job = newJobs[index]

      updateJob(job.id, {
        status: 'uploading',
        message: isImageFile(file) ? 'Extracting text via AI...' : 'Uploading and indexing...',
      })

      try {
        if (isImageFile(file)) {
          const res = await uploadImageDocument(file)
          const status = getInitialStatus(res.status)
          updateJob(job.id, {
            documentId: res.document_id,
            backendStatus: res.status,
            fileName: res.file_name,
            imageUrl: res.image_url,
            totalChunks: res.total_chunks,
            status,
            message:
              status === 'ready'
                ? `Image ready. Extracted ${res.total_chunks} chunk${res.total_chunks !== 1 ? 's' : ''}.`
                : `Image processed. Waiting for ${res.total_chunks} chunk${res.total_chunks !== 1 ? 's' : ''} to become ready.`,
          })
        } else {
          const res = await uploadDocument(file)
          const status = getInitialStatus(res.status)
          updateJob(job.id, {
            documentId: res.document_id,
            backendStatus: res.status,
            fileName: res.file_name,
            status,
            message: status === 'ready' ? res.message : 'Upload complete. Waiting for processing.',
          })
        }
      } catch (err) {
        const message = getUploadErrorMessage(err)
        updateJob(job.id, {
          status: 'error',
          message,
        })
      }
    }

    await refreshUploadStatuses().catch(console.error)
  }, [refreshUploadStatuses, updateJob])

  const clearCompleted = useCallback(() => {
    setJobs((current) =>
      current.filter((job) => job.status === 'queued' || job.status === 'uploading' || job.status === 'processing')
    )
  }, [])

  const isUploading = jobs.some((job) => job.status === 'queued' || job.status === 'uploading')
  const hasActiveJobs = jobs.some((job) => job.status === 'queued' || job.status === 'uploading' || job.status === 'processing')

  useEffect(() => {
    if (!hasActiveJobs) return

    const intervalId = window.setInterval(() => {
      refreshUploadStatuses().catch(console.error)
    }, 3500)

    return () => window.clearInterval(intervalId)
  }, [hasActiveJobs, refreshUploadStatuses])

  const value = useMemo<UploadStoreState>(
    () => ({
      jobs,
      isUploading,
      hasActiveJobs,
      startUpload,
      refreshUploadStatuses,
      clearCompleted,
    }),
    [clearCompleted, hasActiveJobs, isUploading, jobs, refreshUploadStatuses, startUpload],
  )

  return (
    <UploadContext.Provider value={value}>
      {children}
    </UploadContext.Provider>
  )
}

export function useUploadStore() {
  const context = useContext(UploadContext)
  if (!context) {
    throw new Error('useUploadStore must be used within UploadProvider')
  }
  return context
}
