/** Thin progress bar shown at the top of the sheet while new data loads (DESIGN.md §5). */
export function ProgressBar({ active }: { active: boolean }) {
  return (
    <div
      className="absolute inset-x-0 top-0 h-0.5 overflow-hidden rounded-t-sheet"
      aria-hidden={!active}
    >
      {active && (
        <div className="h-0.5 w-full bg-forecast" role="progressbar" aria-label="Loading" />
      )}
    </div>
  );
}

export function ErrorNotice({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div
      role="alert"
      className="mb-4 flex items-center gap-3 border-l-[3px] border-over py-1 pl-3 text-ui text-ink"
    >
      <span>Couldn&apos;t load the data ({message}).</span>
      <button
        type="button"
        onClick={onRetry}
        className="rounded-input border border-rule px-2 py-0.5 text-forecast"
      >
        Retry
      </button>
    </div>
  );
}

export function EmptyRange({ onReset }: { onReset: () => void }) {
  return (
    <div className="flex items-center gap-3 text-ui text-ink-soft">
      <span>
        No hour in this range has both a forecast and an actual. Try the full January window.
      </span>
      <button
        type="button"
        onClick={onReset}
        className="rounded-input border border-rule px-2 py-0.5 text-forecast"
      >
        Reset to January
      </button>
    </div>
  );
}
