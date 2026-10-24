import { useSyncExternalStore } from 'react';

/** True while the media query matches (e.g. the < 640 px layout in DESIGN.md §8). */
export function useMedia(query: string): boolean {
  return useSyncExternalStore(
    (onChange) => {
      const m = window.matchMedia?.(query); // absent in jsdom
      m?.addEventListener('change', onChange);
      return () => m?.removeEventListener('change', onChange);
    },
    () => window.matchMedia?.(query).matches ?? false,
    () => false,
  );
}
