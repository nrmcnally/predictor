export function SectionCard({ title, eyebrow, description, actions, children, className = "" }) {
  return (
    <section className={`card ${className}`}>
      {(title || actions) && (
        <header className="card-head">
          <div>
            {eyebrow && <p className="eyebrow">{eyebrow}</p>}
            {title && <h2 className="card-title">{title}</h2>}
            {description && <p className="card-description">{description}</p>}
          </div>
          {actions && <div className="card-actions">{actions}</div>}
        </header>
      )}
      {children}
    </section>
  );
}

export function StatTile({ label, value, hint, tone = "default" }) {
  return (
    <div className={`stat-tile tone-${tone}`}>
      <span className="stat-label">{label}</span>
      <strong className="stat-value">{value ?? "N/A"}</strong>
      {hint && <span className="stat-hint">{hint}</span>}
    </div>
  );
}

export function Tag({ children, tone = "neutral", className = "" }) {
  return <span className={`tag tone-${tone} ${className}`}>{children}</span>;
}

export function Spinner({ label }) {
  return (
    <div className="spinner-wrap" role="status">
      <span className="spinner" />
      {label && <span className="spinner-label">{label}</span>}
    </div>
  );
}

export function EmptyState({ title, message, icon = "◇" }) {
  return (
    <div className="empty-state">
      <span className="empty-icon">{icon}</span>
      <h3>{title}</h3>
      {message && <p>{message}</p>}
    </div>
  );
}

export function ErrorNote({ message }) {
  if (!message) {
    return null;
  }

  return (
    <div className="error-note" role="alert">
      {String(message)
        .split("\n")
        .map((line, index) => (
          <p key={index}>{line}</p>
        ))}
    </div>
  );
}

export function MeterBar({ value, tone = "red", label, trail }) {
  const width = Math.max(0, Math.min(100, Number(value) || 0));

  return (
    <div className="meter">
      {(label || trail) && (
        <div className="meter-head">
          <span>{label}</span>
          <strong>{trail}</strong>
        </div>
      )}
      <div className="meter-track">
        <div className={`meter-fill tone-${tone}`} style={{ width: `${width}%` }} />
      </div>
    </div>
  );
}

export function SplitBar({ left, leftLabel, rightLabel }) {
  const leftValue = Math.max(2, Math.min(98, Number(left) || 50));

  return (
    <div className="split-bar-wrap">
      <div className="split-bar">
        <div className="split-left" style={{ width: `${leftValue}%` }} />
        <div className="split-right" style={{ width: `${100 - leftValue}%` }} />
        <span className="split-marker" style={{ left: `${leftValue}%` }} />
      </div>
      {(leftLabel || rightLabel) && (
        <div className="split-labels">
          <span className="corner-red">{leftLabel}</span>
          <span className="corner-blue">{rightLabel}</span>
        </div>
      )}
    </div>
  );
}
