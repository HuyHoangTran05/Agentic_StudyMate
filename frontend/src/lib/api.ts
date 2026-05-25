import axios from 'axios';

const api = axios.create({
  baseURL: '/api',
  headers: { 'Content-Type': 'application/json' },
});

/* ─── Types ───────────────────────────────────────────────────────────────── */

export interface Document {
  id: string;
  file_name: string;
  file_type: string;
  image_url: string | null;
  upload_time: string;
  total_chunks: number;
  status: string;
}

export interface Citation {
  file_name: string;
  page_number: number | null;
  chunk_id: string;
  section_title: string | null;
  snippet: string | null;
  image_url: string | null;
}

export interface ChatSession {
  id: string;
  title: string | null;
  created_at: string;
}

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  citations: Citation[] | null;
  created_at: string;
}

export interface MCQOption {
  label: string;
  text: string;
}

export interface MCQuestion {
  question: string;
  options: MCQOption[];
  correct_answer: string;
  explanation: string;
}

export interface Flashcard {
  front: string;
  back: string;
}

export interface QuizResponse {
  document_id: string;
  questions: MCQuestion[];
}

export interface FlashcardResponse {
  document_id: string;
  flashcards: Flashcard[];
}

export interface SummaryResponse {
  document_id: string;
  summary: string;
  key_points: string[];
}

export interface ImageUploadResponse {
  document_id: string;
  file_name: string;
  image_url: string;
  extracted_text: string;
  total_chunks: number;
  status: string;
}

/* ─── Document APIs ───────────────────────────────────────────────────────── */

export async function uploadDocument(file: File): Promise<{ document_id: string; file_name: string; status: string; message: string }> {
  const form = new FormData();
  form.append('file', file);
  const { data } = await api.post('/upload', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return data;
}

export async function uploadImageDocument(file: File): Promise<ImageUploadResponse> {
  const form = new FormData();
  form.append('file', file);
  const { data } = await api.post('/documents/image', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return data;
}

export async function getDocuments(): Promise<{ documents: Document[]; total: number }> {
  const { data } = await api.get('/documents');
  return data;
}

export async function deleteDocument(id: string): Promise<void> {
  await api.delete(`/documents/${id}`);
}

/* ─── Chat APIs ───────────────────────────────────────────────────────────── */

export interface ChatStreamCallbacks {
  onStatus?: (msg: string) => void;
  onChunk?: (text: string) => void;
  onCitations?: (citations: Citation[]) => void;
  onDone?: (data: { question_type: string; sub_questions: string[] | null; sources_searched: number; answer: string }) => void;
  onSession?: (data: { session_id: string }) => void;
  onError?: (error: string) => void;
}

export function streamChat(
  question: string,
  documentIds: string[] | null,
  sessionId: string | null,
  callbacks: ChatStreamCallbacks,
  image?: File | null,
): AbortController {
  const controller = new AbortController();

  const body = image
    ? (() => {
        const form = new FormData();
        form.append('question', question);
        if (documentIds) form.append('document_ids', JSON.stringify(documentIds));
        if (sessionId) form.append('session_id', sessionId);
        form.append('image', image);
        return form;
      })()
    : JSON.stringify({
        question,
        document_ids: documentIds,
        session_id: sessionId,
      });

  fetch('/api/chat', {
    method: 'POST',
    headers: image ? undefined : { 'Content-Type': 'application/json' },
    body,
    signal: controller.signal,
  })
    .then(async (response) => {
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const reader = response.body?.getReader();
      if (!reader) throw new Error('No reader');

      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        let eventType = '';
        for (const line of lines) {
          if (line.startsWith('event: ')) {
            eventType = line.slice(7).trim();
          } else if (line.startsWith('data: ')) {
            const data = line.slice(6);
            switch (eventType) {
              case 'status':
                callbacks.onStatus?.(data);
                break;
              case 'chunk':
                callbacks.onChunk?.(data);
                break;
              case 'citations':
                callbacks.onCitations?.(JSON.parse(data));
                break;
              case 'done':
                callbacks.onDone?.(JSON.parse(data));
                break;
              case 'session':
                callbacks.onSession?.(JSON.parse(data));
                break;
              case 'error':
                callbacks.onError?.(JSON.parse(data).error);
                break;
            }
          }
        }
      }
    })
    .catch((err) => {
      if (err.name !== 'AbortError') {
        callbacks.onError?.(err.message);
      }
    });

  return controller;
}

export async function getChatSessions(): Promise<ChatSession[]> {
  const { data } = await api.get('/chat/sessions');
  return data;
}

export async function getChatHistory(sessionId: string): Promise<{ session_id: string; messages: Message[] }> {
  const { data } = await api.get(`/chat/sessions/${sessionId}`);
  return data;
}

export async function deleteChatSession(sessionId: string): Promise<void> {
  await api.delete(`/chat/sessions/${sessionId}`);
}

/* ─── Study Tools APIs ────────────────────────────────────────────────────── */

export async function generateQuiz(documentId: string, numItems = 5): Promise<QuizResponse> {
  const { data } = await api.post('/study-tools/quiz', { document_id: documentId, num_items: numItems });
  return data;
}

export async function generateFlashcards(documentId: string, numItems = 5): Promise<FlashcardResponse> {
  const { data } = await api.post('/study-tools/flashcards', { document_id: documentId, num_items: numItems });
  return data;
}

export async function generateSummary(documentId: string): Promise<SummaryResponse> {
  const { data } = await api.post('/study-tools/summary', { document_id: documentId, num_items: 1 });
  return data;
}
