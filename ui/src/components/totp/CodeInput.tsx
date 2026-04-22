import { useEffect, useRef } from 'react'

interface CodeInputProps {
  value: string
  onChange: (value: string) => void
  onComplete?: (value: string) => void
  length?: number
  autoFocus?: boolean
  disabled?: boolean
  hasError?: boolean
}

export function CodeInput({
  value,
  onChange,
  onComplete,
  length = 6,
  autoFocus = true,
  disabled = false,
  hasError = false,
}: CodeInputProps) {
  const refs = useRef<Array<HTMLInputElement | null>>([])

  useEffect(() => {
    if (autoFocus && refs.current[0]) refs.current[0].focus()
  }, [autoFocus])

  const digits = value.split('')
  while (digits.length < length) digits.push('')

  function setChar(index: number, char: string) {
    const sanitized = char.replace(/\D/g, '').slice(0, 1)
    const next = digits.slice()
    next[index] = sanitized
    const joined = next.join('').slice(0, length)
    onChange(joined)
    if (sanitized && index < length - 1) {
      refs.current[index + 1]?.focus()
    }
    if (next.every((digit) => digit !== '')) {
      onComplete?.(next.join('').slice(0, length))
    }
  }

  function handleKeyDown(index: number, e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === 'Backspace' && !digits[index] && index > 0) {
      refs.current[index - 1]?.focus()
      e.preventDefault()
      return
    }
    if (e.key === 'ArrowLeft' && index > 0) {
      refs.current[index - 1]?.focus()
      e.preventDefault()
    }
    if (e.key === 'ArrowRight' && index < length - 1) {
      refs.current[index + 1]?.focus()
      e.preventDefault()
    }
  }

  function handlePaste(e: React.ClipboardEvent<HTMLInputElement>) {
    const pasted = e.clipboardData.getData('text').replace(/\D/g, '').slice(0, length)
    if (!pasted) return
    e.preventDefault()
    onChange(pasted)
    const focusIndex = Math.min(pasted.length, length - 1)
    refs.current[focusIndex]?.focus()
    if (pasted.length === length) onComplete?.(pasted)
  }

  return (
    <div
      style={{
        display: 'flex',
        gap: 8,
      }}
    >
      {Array.from({ length }).map((_, i) => {
        const isGap = i === Math.floor((length - 1) / 2)
        return (
          <div
            key={i}
            style={{ display: 'flex', alignItems: 'center', gap: 8 }}
          >
            <input
              ref={(el) => {
                refs.current[i] = el
              }}
              type="text"
              inputMode="numeric"
              autoComplete={i === 0 ? 'one-time-code' : 'off'}
              value={digits[i]}
              onChange={(e) => setChar(i, e.target.value)}
              onKeyDown={(e) => handleKeyDown(i, e)}
              onPaste={handlePaste}
              disabled={disabled}
              maxLength={1}
              aria-label={`Digit ${i + 1}`}
              style={{
                width: 40,
                height: 48,
                textAlign: 'center',
                fontSize: 20,
                fontFamily: 'var(--font-mono, monospace)',
                fontVariantNumeric: 'tabular-nums',
                letterSpacing: 0,
                color: 'var(--text)',
                background: 'var(--surface)',
                border: `1px solid ${
                  hasError ? 'var(--red)' : digits[i] ? 'var(--border-strong)' : 'var(--border)'
                }`,
                borderRadius: 8,
                outline: 'none',
                transition: 'border-color 120ms, box-shadow 120ms',
                caretColor: 'var(--blue)',
                boxShadow: 'none',
              }}
              onFocus={(e) => {
                e.currentTarget.style.borderColor = hasError ? 'var(--red)' : 'var(--blue)'
                e.currentTarget.style.boxShadow = `0 0 0 3px ${
                  hasError
                    ? 'color-mix(in srgb, var(--red) 15%, transparent)'
                    : 'color-mix(in srgb, var(--blue) 18%, transparent)'
                }`
              }}
              onBlur={(e) => {
                e.currentTarget.style.boxShadow = 'none'
                e.currentTarget.style.borderColor = hasError
                  ? 'var(--red)'
                  : digits[i]
                    ? 'var(--border-strong)'
                    : 'var(--border)'
              }}
            />
            {isGap && i < length - 1 && (
              <span
                aria-hidden
                style={{
                  width: 6,
                  height: 1,
                  background: 'var(--border-strong)',
                  flexShrink: 0,
                }}
              />
            )}
          </div>
        )
      })}
    </div>
  )
}
