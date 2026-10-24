import { type ReactNode, useRef } from 'react';

interface Props {
  label: string; // current value, shown inside the sentence
  title: string; // accessible name of the popover
  children: ReactNode;
}

/**
 * A sentence chip that opens a popover (DESIGN.md §5). Uses a modal <dialog>: the browser traps
 * focus, closes on Esc and restores focus to the chip. Clicking outside the panel closes it too.
 */
export function Chip({ label, title, children }: Props) {
  const button = useRef<HTMLButtonElement>(null);
  const dialog = useRef<HTMLDialogElement>(null);

  const open = () => {
    const d = dialog.current;
    const r = button.current?.getBoundingClientRect();
    if (!d || !r) return;
    const width = Math.min(320, window.innerWidth - 32);
    d.style.top = `${r.bottom + 6}px`;
    d.style.left = `${Math.max(16, Math.min(r.left, window.innerWidth - width - 16))}px`;
    d.style.width = `${width}px`;
    d.showModal();
  };
  const close = () => dialog.current?.close();

  return (
    <>
      <button
        ref={button}
        type="button"
        onClick={open}
        aria-haspopup="dialog"
        className="inline rounded-chip border border-rule px-2 py-0.5 text-forecast underline-offset-4 hover:underline"
      >
        {label}
      </button>
      <dialog
        ref={dialog}
        aria-label={title}
        className="fixed m-0 rounded-sheet border border-rule bg-sheet p-0 text-ui text-ink"
        onClick={(e) => e.target === dialog.current && close()}
      >
        <div className="flex flex-col gap-3 p-4">{children}</div>
      </dialog>
    </>
  );
}
