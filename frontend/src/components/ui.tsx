import type { ButtonHTMLAttributes, ElementType, HTMLAttributes, ReactNode } from 'react'
import { Loader2 } from 'lucide-react'
import { cx } from '../lib/cx'

export function Card({
  className,
  interactive = false,
  children,
  ...props
}: HTMLAttributes<HTMLDivElement> & { interactive?: boolean }) {
  return (
    <div
      className={cx(
        'glass rounded-2xl',
        interactive && 'glass-hover transition-all duration-200',
        className,
      )}
      {...props}
    >
      {children}
    </div>
  )
}

type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger'

export function Button({
  className,
  variant = 'primary',
  children,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: ButtonVariant }) {
  const variants: Record<ButtonVariant, string> = {
    primary:
      'gradient-bg text-surface-950 font-semibold hover:shadow-[0_0_32px_rgba(208,188,255,0.22)]',
    secondary:
      'bg-accent-cyan/10 text-accent-cyan border border-accent-cyan/20 hover:bg-accent-cyan/15',
    ghost:
      'bg-white/[0.03] text-text-secondary border border-white/10 hover:bg-white/[0.06] hover:text-white',
    danger:
      'bg-rose-500/12 text-accent-rose border border-rose-400/20 hover:bg-rose-500/18',
  }

  return (
    <button
      className={cx(
        'inline-flex items-center justify-center gap-2 rounded-lg px-4 py-2.5 text-sm transition-all duration-200 active:scale-[0.98] disabled:opacity-50',
        variants[variant],
        className,
      )}
      {...props}
    >
      {children}
    </button>
  )
}

type BadgeTone = 'violet' | 'cyan' | 'emerald' | 'amber' | 'rose' | 'neutral'

export function Badge({
  className,
  tone = 'neutral',
  children,
  ...props
}: HTMLAttributes<HTMLSpanElement> & { tone?: BadgeTone }) {
  const tones: Record<BadgeTone, string> = {
    violet: 'bg-accent-violet/10 text-accent-violet border-accent-violet/20',
    cyan: 'bg-accent-cyan/10 text-accent-cyan border-accent-cyan/20',
    emerald: 'bg-emerald-400/10 text-accent-emerald border-emerald-300/20',
    amber: 'bg-amber-300/10 text-accent-amber border-amber-300/20',
    rose: 'bg-rose-300/10 text-accent-rose border-rose-300/20',
    neutral: 'bg-white/[0.04] text-text-secondary border-white/10',
  }

  return (
    <span
      className={cx(
        'inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-medium',
        tones[tone],
        className,
      )}
      {...props}
    >
      {children}
    </span>
  )
}

export function PageShell({
  className,
  children,
  wide = false,
}: {
  className?: string
  children: ReactNode
  wide?: boolean
}) {
  return (
    <div
      className={cx(
        'mx-auto w-full px-4 py-6 sm:px-6 lg:px-8 lg:py-8',
        wide ? 'max-w-7xl' : 'max-w-6xl',
        className,
      )}
    >
      {children}
    </div>
  )
}

export function PageHeader({
  icon: Icon,
  eyebrow,
  title,
  description,
  action,
}: {
  icon?: ElementType
  eyebrow?: string
  title: string
  description?: string
  action?: ReactNode
}) {
  return (
    <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
      <div className="min-w-0">
        <div className="mb-3 flex items-center gap-3">
          {Icon && (
            <div className="flex h-10 w-10 items-center justify-center rounded-lg gradient-bg text-surface-950 shadow-[0_0_28px_rgba(208,188,255,0.18)]">
              <Icon className="h-5 w-5" />
            </div>
          )}
          {eyebrow && <Badge tone="cyan">{eyebrow}</Badge>}
        </div>
        <h1 className="font-display text-3xl font-bold text-white md:text-4xl">
          {title}
        </h1>
        {description && (
          <p className="mt-3 max-w-2xl text-sm leading-6 text-text-secondary md:text-base">
            {description}
          </p>
        )}
      </div>
      {action && <div className="shrink-0">{action}</div>}
    </div>
  )
}

export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
}: {
  icon?: ElementType
  title: string
  description?: string
  action?: ReactNode
}) {
  return (
    <Card className="p-10 text-center">
      {Icon && (
        <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-white/[0.04] text-text-muted">
          <Icon className="h-7 w-7" />
        </div>
      )}
      <h3 className="font-display text-lg font-semibold text-white">{title}</h3>
      {description && <p className="mt-2 text-sm text-text-muted">{description}</p>}
      {action && <div className="mt-5">{action}</div>}
    </Card>
  )
}

export function LoadingState({ label = 'Loading...' }: { label?: string }) {
  return (
    <div className="flex min-h-48 items-center justify-center">
      <div className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.03] px-4 py-2 text-sm text-text-secondary">
        <Loader2 className="h-4 w-4 animate-spin text-accent-cyan" />
        {label}
      </div>
    </div>
  )
}

export function StatusBadge({ status }: { status: string }) {
  const normalized = status.toLowerCase()
  const tone: BadgeTone =
    normalized === 'ready'
      ? 'emerald'
      : normalized === 'failed'
        ? 'rose'
        : normalized === 'processing'
          ? 'amber'
          : 'neutral'

  return <Badge tone={tone}>{status}</Badge>
}
