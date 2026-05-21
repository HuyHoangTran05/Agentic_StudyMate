import { useState } from 'react'
import { CheckCircle2, XCircle, RotateCcw, Trophy } from 'lucide-react'
import type { MCQuestion } from '../lib/api'

interface Props {
  questions: MCQuestion[]
}

export default function QuizWidget({ questions }: Props) {
  const [currentQ, setCurrentQ] = useState(0)
  const [selected, setSelected] = useState<string | null>(null)
  const [revealed, setRevealed] = useState(false)
  const [score, setScore] = useState(0)
  const [finished, setFinished] = useState(false)

  const q = questions[currentQ]
  const total = questions.length
  const isCorrect = selected === q?.correct_answer

  const handleSelect = (label: string) => {
    if (revealed) return
    setSelected(label)
  }

  const handleReveal = () => {
    if (!selected) return
    setRevealed(true)
    if (selected === q.correct_answer) {
      setScore((s) => s + 1)
    }
  }

  const handleNext = () => {
    if (currentQ + 1 >= total) {
      setFinished(true)
      return
    }
    setCurrentQ((c) => c + 1)
    setSelected(null)
    setRevealed(false)
  }

  const handleRestart = () => {
    setCurrentQ(0)
    setSelected(null)
    setRevealed(false)
    setScore(0)
    setFinished(false)
  }

  if (finished) {
    const pct = Math.round((score / total) * 100)
    return (
      <div className="glass rounded-2xl p-8 text-center space-y-6 animate-fade-in">
        <div className="w-16 h-16 rounded-2xl gradient-bg flex items-center justify-center mx-auto shadow-lg shadow-violet-500/25">
          <Trophy className="w-8 h-8 text-white" />
        </div>
        <div>
          <h3 className="text-2xl font-bold text-white">Quiz Complete!</h3>
          <p className="text-text-secondary mt-2">
            You scored <span className="font-bold text-white">{score}</span> out of {total} ({pct}%)
          </p>
        </div>
        <div className="w-full bg-surface-700 rounded-full h-3 overflow-hidden">
          <div
            className="h-full rounded-full gradient-bg transition-all duration-1000"
            style={{ width: `${pct}%` }}
          />
        </div>
        <button
          onClick={handleRestart}
          className="inline-flex items-center gap-2 px-6 py-2.5 rounded-xl gradient-bg text-white text-sm font-medium hover:shadow-lg hover:shadow-violet-500/20 transition-all"
        >
          <RotateCcw className="w-4 h-4" />
          Try Again
        </button>
      </div>
    )
  }

  if (!q) return null

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Progress bar */}
      <div className="space-y-2">
        <div className="flex justify-between text-xs text-text-muted">
          <span>Question {currentQ + 1} of {total}</span>
          <span>Score: {score}/{currentQ + (revealed ? 1 : 0)}</span>
        </div>
        <div className="w-full bg-surface-700 rounded-full h-1.5 overflow-hidden">
          <div
            className="h-full rounded-full gradient-bg transition-all duration-500"
            style={{ width: `${((currentQ + (revealed ? 1 : 0)) / total) * 100}%` }}
          />
        </div>
      </div>

      {/* Question */}
      <div className="glass rounded-2xl p-6">
        <h3 className="text-base font-semibold text-white leading-relaxed mb-5">{q.question}</h3>

        <div className="space-y-2.5">
          {q.options.map((opt) => {
            const isThis = selected === opt.label
            const isAnswer = opt.label === q.correct_answer

            let optStyle = 'glass glass-hover border-white/5'
            if (revealed && isAnswer) {
              optStyle = 'bg-emerald-500/15 border-emerald-500/30 text-emerald-400'
            } else if (revealed && isThis && !isCorrect) {
              optStyle = 'bg-rose-500/15 border-rose-500/30 text-rose-400'
            } else if (isThis) {
              optStyle = 'bg-violet-500/15 border-violet-500/30'
            }

            return (
              <button
                key={opt.label}
                onClick={() => handleSelect(opt.label)}
                disabled={revealed}
                className={`w-full text-left flex items-center gap-3 px-4 py-3 rounded-xl border transition-all ${optStyle}`}
              >
                <span className={`w-7 h-7 rounded-lg flex items-center justify-center text-xs font-bold flex-shrink-0 ${
                  isThis && !revealed ? 'gradient-bg text-white' : 'bg-white/5 text-text-muted'
                } ${revealed && isAnswer ? 'bg-emerald-500/20 text-emerald-400' : ''}`}>
                  {opt.label}
                </span>
                <span className={`text-sm ${
                  revealed && isAnswer ? 'text-emerald-400 font-medium' : 'text-text-secondary'
                }`}>
                  {opt.text}
                </span>
                {revealed && isAnswer && <CheckCircle2 className="w-4 h-4 text-emerald-400 ml-auto flex-shrink-0" />}
                {revealed && isThis && !isCorrect && <XCircle className="w-4 h-4 text-rose-400 ml-auto flex-shrink-0" />}
              </button>
            )
          })}
        </div>

        {/* Explanation */}
        {revealed && (
          <div className="mt-4 p-4 rounded-xl bg-cyan-500/5 border border-cyan-500/10 animate-fade-in">
            <p className="text-sm text-text-secondary">
              <span className="font-semibold text-cyan-400">Explanation: </span>
              {q.explanation}
            </p>
          </div>
        )}
      </div>

      {/* Actions */}
      <div className="flex justify-end gap-3">
        {!revealed ? (
          <button
            onClick={handleReveal}
            disabled={!selected}
            className={`px-5 py-2.5 rounded-xl text-sm font-medium transition-all ${
              selected
                ? 'gradient-bg text-white hover:shadow-lg hover:shadow-violet-500/20'
                : 'bg-white/5 text-text-muted cursor-not-allowed'
            }`}
          >
            Check Answer
          </button>
        ) : (
          <button
            onClick={handleNext}
            className="px-5 py-2.5 rounded-xl gradient-bg text-white text-sm font-medium hover:shadow-lg hover:shadow-violet-500/20 transition-all"
          >
            {currentQ + 1 >= total ? 'See Results' : 'Next Question'}
          </button>
        )}
      </div>
    </div>
  )
}
