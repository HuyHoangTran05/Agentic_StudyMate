import { useEffect, useId, useMemo, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import type { KeyboardEvent } from 'react'
import { Check, ChevronDown } from 'lucide-react'
import { cx } from '../../lib/cx'

export interface SelectDropdownOption {
  value: string
  label: string
  description?: string
  disabled?: boolean
}

interface SelectDropdownProps {
  value: string
  options: SelectDropdownOption[]
  onChange: (value: string) => void
  placeholder: string
  disabled?: boolean
  label?: string
  className?: string
}

export default function SelectDropdown({
  value,
  options,
  onChange,
  placeholder,
  disabled = false,
  label,
  className,
}: SelectDropdownProps) {
  const [open, setOpen] = useState(false)
  const [activeIndex, setActiveIndex] = useState(-1)
  const containerRef = useRef<HTMLDivElement>(null)
  const buttonRef = useRef<HTMLButtonElement>(null)
  const menuRef = useRef<HTMLDivElement>(null)
  const listboxId = useId()
  const [menuStyle, setMenuStyle] = useState({
    left: 0,
    top: 0,
    width: 0,
  })

  const selectedIndex = options.findIndex((option) => option.value === value)
  const selectedOption = selectedIndex >= 0 ? options[selectedIndex] : null

  const enabledOptions = useMemo(
    () => options.map((option, index) => ({ option, index })).filter(({ option }) => !option.disabled),
    [options],
  )

  useEffect(() => {
    if (!open) return

    const updateMenuPosition = () => {
      const rect = buttonRef.current?.getBoundingClientRect()
      if (!rect) return
      setMenuStyle({
        left: rect.left,
        top: rect.bottom + 8,
        width: rect.width,
      })
    }

    const handlePointerDown = (event: PointerEvent) => {
      const target = event.target as Node
      if (
        !containerRef.current?.contains(target) &&
        !menuRef.current?.contains(target)
      ) {
        setOpen(false)
      }
    }

    updateMenuPosition()
    document.addEventListener('pointerdown', handlePointerDown)
    window.addEventListener('resize', updateMenuPosition)
    window.addEventListener('scroll', updateMenuPosition, true)
    return () => {
      document.removeEventListener('pointerdown', handlePointerDown)
      window.removeEventListener('resize', updateMenuPosition)
      window.removeEventListener('scroll', updateMenuPosition, true)
    }
  }, [open])

  const openDropdown = () => {
    setActiveIndex(selectedIndex >= 0 ? selectedIndex : enabledOptions[0]?.index ?? -1)
    setOpen(true)
  }

  const selectOption = (option: SelectDropdownOption) => {
    if (option.disabled) return
    onChange(option.value)
    setOpen(false)
    buttonRef.current?.focus()
  }

  const moveActive = (direction: 1 | -1) => {
    if (enabledOptions.length === 0) return
    const currentEnabledIndex = enabledOptions.findIndex(({ index }) => index === activeIndex)
    const nextEnabledIndex =
      currentEnabledIndex === -1
        ? direction === 1 ? 0 : enabledOptions.length - 1
        : (currentEnabledIndex + direction + enabledOptions.length) % enabledOptions.length
    setActiveIndex(enabledOptions[nextEnabledIndex].index)
  }

  const handleKeyDown = (event: KeyboardEvent<HTMLButtonElement>) => {
    switch (event.key) {
      case 'ArrowDown':
        event.preventDefault()
        if (!open) {
          openDropdown()
        } else {
          moveActive(1)
        }
        break
      case 'ArrowUp':
        event.preventDefault()
        if (!open) {
          openDropdown()
        } else {
          moveActive(-1)
        }
        break
      case 'Enter':
      case ' ':
        event.preventDefault()
        if (!open) {
          openDropdown()
          return
        }
        if (activeIndex >= 0) selectOption(options[activeIndex])
        break
      case 'Escape':
        event.preventDefault()
        setOpen(false)
        break
      default:
        break
    }
  }

  return (
    <div ref={containerRef} className={cx('relative', className)}>
      {label && (
        <label className="mb-2 block text-xs font-medium text-text-muted">
          {label}
        </label>
      )}
      <button
        ref={buttonRef}
        type="button"
        aria-expanded={open}
        aria-haspopup="listbox"
        aria-controls={listboxId}
        disabled={disabled}
        onClick={() => {
          if (open) {
            setOpen(false)
          } else {
            openDropdown()
          }
        }}
        onKeyDown={handleKeyDown}
        className={cx(
          'field-surface flex w-full items-center justify-between gap-3 rounded-xl px-3 py-2.5 text-left text-sm transition-all',
          disabled && 'opacity-60',
        )}
      >
        <span className={cx('min-w-0 flex-1 truncate', selectedOption ? 'text-white' : 'text-text-muted')}>
          {selectedOption?.label ?? placeholder}
        </span>
        <ChevronDown className={cx('h-4 w-4 shrink-0 text-text-muted transition-transform', open && 'rotate-180 text-accent-cyan')} />
      </button>

      {open && createPortal(
        <div
          ref={menuRef}
          id={listboxId}
          role="listbox"
          aria-activedescendant={activeIndex >= 0 ? `${listboxId}-${activeIndex}` : undefined}
          style={{
            left: menuStyle.left,
            top: menuStyle.top,
            width: menuStyle.width,
          }}
          className="fixed z-[100] max-h-72 overflow-y-auto rounded-xl border border-white/10 bg-surface-950 p-1.5 shadow-2xl shadow-black/60"
        >
          {options.length === 0 ? (
            <div className="px-3 py-2 text-sm text-text-muted">No options available</div>
          ) : (
            options.map((option, index) => {
              const selected = option.value === value
              const active = index === activeIndex

              return (
                <button
                  id={`${listboxId}-${index}`}
                  key={option.value}
                  type="button"
                  role="option"
                  aria-selected={selected}
                  disabled={option.disabled}
                  onMouseEnter={() => setActiveIndex(index)}
                  onClick={() => selectOption(option)}
                  className={cx(
                    'flex w-full items-start gap-3 rounded-lg px-3 py-2.5 text-left transition-colors',
                    selected
                      ? 'bg-accent-violet/14 text-white'
                      : active
                        ? 'bg-white/[0.06] text-white'
                        : 'text-text-secondary',
                    option.disabled && 'cursor-not-allowed opacity-45',
                  )}
                >
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm font-medium">{option.label}</span>
                    {option.description && (
                      <span className="mt-0.5 block truncate text-xs text-text-muted">{option.description}</span>
                    )}
                  </span>
                  {selected && <Check className="mt-0.5 h-4 w-4 shrink-0 text-accent-violet" />}
                </button>
              )
            })
          )}
        </div>,
        document.body,
      )}
    </div>
  )
}
