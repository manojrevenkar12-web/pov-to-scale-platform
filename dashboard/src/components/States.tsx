export function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`skeleton ${className}`} aria-hidden="true" />;
}

export function ErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <section className="state state--error" role="alert">
      <h2>The lab results could not be loaded</h2>
      <p>{message}</p>
      <p>
        Serve the built dashboard over HTTP so it can read <code>data/results.json</code>.
      </p>
      <button type="button" className="button" onClick={onRetry}>
        Try again
      </button>
    </section>
  );
}

export function EmptyState() {
  return (
    <section className="state" role="status">
      <h2>No lab results yet</h2>
      <p>
        Run <code>pts lab sim --split dev</code> and <code>pts lab report</code> from the repository root.
      </p>
    </section>
  );
}
