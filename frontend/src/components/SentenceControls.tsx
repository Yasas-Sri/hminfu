import type { Aggregation, UrlState } from '../hooks/useUrlState';

// Bodies of the four sentence popovers (DESIGN.md §3.1). Each writes straight to the URL state;
// a value equal to the server default is stored as `undefined` so links stay short.

type Update = (patch: Partial<UrlState>) => void;

export const AGG_LABEL: Record<Aggregation, string> = {
  point: 'the actual half-hour on the hour',
  hourly_mean: 'the average of both half-hours',
};

export const lagLabel = (lag: number) =>
  lag === 0
    ? 'as soon as published'
    : lag === 60
      ? '1 hour after published'
      : `${lag} minutes after published`;

const input = 'rounded-input border border-rule bg-sheet px-2 py-1 text-ui text-ink';
const fieldset = 'm-0 flex flex-col gap-2 border-0 p-0';

export function DaysControl(props: {
  first: string;
  last: string;
  min: string;
  max: string;
  onChange: (first: string, last: string) => void;
  onReset: () => void;
}) {
  const { first, last, min, max, onChange, onReset } = props;
  return (
    <>
      <label className="flex flex-col gap-1">
        First delivery day
        <input
          type="date"
          className={input}
          min={min}
          max={max}
          value={first}
          onChange={(e) => onChange(e.target.value, last)}
        />
      </label>
      <label className="flex flex-col gap-1">
        Last delivery day
        <input
          type="date"
          className={input}
          min={min}
          max={max}
          value={last}
          onChange={(e) => onChange(first, e.target.value)}
        />
      </label>
      <button
        type="button"
        className="self-start text-forecast underline-offset-2 hover:underline"
        onClick={onReset}
      >
        January 2026 window
      </button>
    </>
  );
}

export function CutoffControl({
  value,
  fallback,
  update,
}: {
  value: string;
  fallback: string;
  update: Update;
}) {
  return (
    <label className="flex flex-col gap-1">
      Auction closes (UK time, the day before delivery)
      <input
        type="time"
        className={input}
        value={value}
        onChange={(e) =>
          /^\d\d:\d\d$/.test(e.target.value) &&
          update({ cutoff: e.target.value === fallback ? undefined : e.target.value })
        }
      />
      <span className="text-small text-ink-soft">
        Default 09:50 follows the N2EX GB day-ahead auction.
      </span>
    </label>
  );
}

export function LagControl({ value, update }: { value: number; update: Update }) {
  const set = (v: number) => update({ lag: v === 0 ? undefined : v });
  return (
    <fieldset className={fieldset}>
      <legend className="mb-1">Forecasts usable</legend>
      {[0, 60].map((m) => (
        <label key={m} className="flex items-center gap-2">
          <input type="radio" name="lag" checked={value === m} onChange={() => set(m)} />
          {lagLabel(m)}
        </label>
      ))}
      <label className="flex items-center gap-2">
        Custom minutes
        <input
          type="number"
          min={0}
          max={180}
          className={`${input} w-20`}
          value={value}
          onChange={(e) => {
            const v = Number(e.target.value);
            if (Number.isInteger(v) && v >= 0 && v <= 180) set(v);
          }}
        />
      </label>
      <span className="text-small text-ink-soft">
        Elexon describes its update times as one hour after the raw publish times. Choose 1 hour to
        assume a forecast was usable only then.
      </span>
    </fieldset>
  );
}

export function AggControl({ value, update }: { value: Aggregation; update: Update }) {
  return (
    <fieldset className={fieldset}>
      <legend className="mb-1">Compare each hourly forecast with</legend>
      {(['point', 'hourly_mean'] as const).map((a) => (
        <label key={a} className="flex items-center gap-2">
          <input
            type="radio"
            name="agg"
            checked={value === a}
            onChange={() => update({ agg: a === 'point' ? undefined : a })}
          />
          {AGG_LABEL[a]}
        </label>
      ))}
    </fieldset>
  );
}
