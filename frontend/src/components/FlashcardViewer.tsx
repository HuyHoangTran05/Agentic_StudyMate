import { useState } from 'react'
import { ChevronLeft, ChevronRight, RotateCcw } from 'lucide-react'
import type { Flashcard } from '../lib/api'

interface Props {
  flashcards: Flashcard[]
}

export default function FlashcardViewer({ flashcards }: Props) {
  const [index, setIndex] = useState(0)
  const [flipped, setFlipped] = useState(false)

  const card = flashcards[index]
  const total = flashcards.length

  const goPrev = () => {
    setFlipped(false)
    setIndex((i) => (i - 1 + total) % total)
  }

  const goNext = () => {
    setFlipped(false)
    setIndex((i) => (i + 1) % total)
  }

  if (!card) return null

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Progress */}
      <div className="flex items-center justify-between text-sm">
        <span className="text-text-secondary">
          Card <span className="font-semibold text-white">{index + 1}</span> of {total}
        </span>
        <div className="flex gap-1.5">
          {flashcards.map((_, i) => (
            <div
              key={i}
              className={`h-1.5 rounded-full transition-all duration-300 ${
                i === index
                  ? 'w-6 bg-gradient-to-r from-violet-500 to-cyan-500'
                  : i < index
                  ? 'w-1.5 bg-violet-500/40'
                  : 'w-1.5 bg-white/10'
              }`}
            />
          ))}
        </div>
      </div>

      {/* Card */}
      <div
        className="flashcard-container cursor-pointer select-none"
        style={{ height: '280px' }}
        onClick={() => setFlipped(!flipped)}
      >
        <div className={`flashcard-inner ${flipped ? 'flipped' : ''}`}>
          {/* Front */}
          <div className="flashcard-face glass border border-white/10">
            <div className="text-center space-y-3">
              <span className="inline-block px-3 py-1 rounded-full text-[10px] font-semibold uppercase tracking-widest bg-violet-500/15 text-violet-400 border border-violet-500/20">
                Question
              </span>
              <p className="text-lg font-medium text-white leading-relaxed">{card.front}</p>
              <p className="text-xs text-text-muted">Click to reveal answer</p>
            </div>
          </div>

          {/* Back */}
          <div className="flashcard-face flashcard-back glass border border-cyan-500/20">
            <div className="text-center space-y-3">
              <span className="inline-block px-3 py-1 rounded-full text-[10px] font-semibold uppercase tracking-widest bg-cyan-500/15 text-cyan-400 border border-cyan-500/20">
                Answer
              </span>
              <p className="text-base text-text-secondary leading-relaxed">{card.back}</p>
            </div>
          </div>
        </div>
      </div>

      {/* Controls */}
      <div className="flex items-center justify-center gap-3">
        <button
          onClick={goPrev}
          className="p-3 rounded-xl glass glass-hover transition-all hover:-translate-x-0.5"
        >
          <ChevronLeft className="w-5 h-5 text-text-secondary" />
        </button>
        <button
          onClick={() => setFlipped(!flipped)}
          className="px-5 py-2.5 rounded-xl gradient-bg text-white text-sm font-medium flex items-center gap-2 hover:shadow-lg hover:shadow-violet-500/20 transition-all"
        >
          <RotateCcw className="w-4 h-4" />
          Flip
        </button>
        <button
          onClick={goNext}
          className="p-3 rounded-xl glass glass-hover transition-all hover:translate-x-0.5"
        >
          <ChevronRight className="w-5 h-5 text-text-secondary" />
        </button>
      </div>
    </div>
  )
}
