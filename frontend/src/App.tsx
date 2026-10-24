import { useQuery } from '@tanstack/react-query';
import { getHealth } from './api/client';

// ponytail: walking skeleton only; the real shell (DESIGN.md §3) arrives in M4.
export function App() {
  const health = useQuery({ queryKey: ['health'], queryFn: getHealth });
  return (
    <main className="p-8">
      <h1>Wind forecast at the day-ahead cutoff</h1>
      <p>
        API status:{' '}
        {health.isPending
          ? 'checking'
          : health.isError
            ? `couldn't reach the API (${health.error.message})`
            : health.data.status}
      </p>
    </main>
  );
}
