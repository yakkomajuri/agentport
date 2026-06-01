interface Props {
  name: string
  description: string
  onNameChange: (value: string) => void
  onDescriptionChange: (value: string) => void
}

export function TitleBlock({ name, description, onNameChange, onDescriptionChange }: Props) {
  return (
    <div style={{ padding: '4px 0 16px' }}>
      <input
        value={name}
        onChange={(event) => onNameChange(event.target.value)}
        placeholder="Untitled API"
        spellCheck={false}
        aria-label="Integration name"
        style={{
          width: '100%',
          border: 'none',
          outline: 'none',
          background: 'transparent',
          color: 'var(--text)',
          fontSize: 24,
          fontWeight: 700,
          letterSpacing: -0.4,
          lineHeight: 1.2,
          fontFamily: 'inherit',
          padding: 0,
        }}
      />
      <input
        value={description}
        onChange={(event) => onDescriptionChange(event.target.value)}
        placeholder="Add a short description"
        aria-label="Integration description"
        style={{
          width: '100%',
          border: 'none',
          outline: 'none',
          background: 'transparent',
          color: 'var(--text-dim)',
          fontSize: 14,
          fontWeight: 400,
          lineHeight: 1.5,
          fontFamily: 'inherit',
          padding: '6px 0 0',
        }}
      />
    </div>
  )
}
