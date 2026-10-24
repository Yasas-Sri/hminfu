import { type ReactNode, useState } from 'react';

interface Props {
  label: string; // aria-label summary of what the chart shows
  table: { head: string[]; rows: (string | number)[][] };
  children: ReactNode;
}

/** A chart plus its accessible alternative: an aria-label and a "Show as table" toggle (DESIGN.md §8). */
export function ChartFrame({ label, table, children }: Props) {
  const [showTable, setShowTable] = useState(false);
  return (
    <figure aria-label={label} className="m-0">
      {children}
      <button
        type="button"
        className="mt-2 text-small text-forecast underline-offset-2 hover:underline"
        aria-expanded={showTable}
        onClick={() => setShowTable((v) => !v)}
      >
        {showTable ? 'Hide table' : 'Show as table'}
      </button>
      {showTable && (
        <div className="mt-2 max-h-80 overflow-auto">
          <table className="w-full text-ui">
            <caption className="sr-only">{label}</caption>
            <thead>
              <tr>
                {table.head.map((h) => (
                  <th
                    key={h}
                    scope="col"
                    className="border-b border-rule px-2 py-1 text-left font-medium"
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {table.rows.map((r, i) => (
                <tr key={i}>
                  {r.map((c, j) => (
                    <td key={j} className={`px-2 py-1 ${j ? 'text-right' : ''}`}>
                      {c}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </figure>
  );
}
