'use client';

import { useState, useEffect, useRef, useCallback } from 'react';

/**
 * Progressive rendering hook — renders items in batches as the user scrolls.
 *
 * Instead of rendering 200+ cards at once (which freezes the UI),
 * this shows the first `batchSize` items and loads more when a
 * sentinel element near the bottom enters the viewport.
 *
 * Usage:
 *   const { visibleItems, sentinelRef, hasMore } = useProgressiveList(allItems, 12);
 *   // render visibleItems in your grid
 *   // place <div ref={sentinelRef} /> after the grid
 */
export function useProgressiveList<T>(items: T[], batchSize = 12) {
  const [visibleCount, setVisibleCount] = useState(batchSize);
  const sentinelRef = useRef<HTMLDivElement | null>(null);

  // Reset visible count when the number of items changes (e.g. project switch, filter change)
  // Using items.length instead of items reference to avoid resetting on every render
  // (since .filter() creates a new array reference each time)
  useEffect(() => {
    setVisibleCount(batchSize);
  }, [items.length, batchSize]);

  // IntersectionObserver watches the sentinel div at the bottom of the grid.
  // When the user scrolls near it, we show the next batch.
  useEffect(() => {
    const el = sentinelRef.current;
    if (!el) return;

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setVisibleCount((prev) => Math.min(prev + batchSize, items.length));
        }
      },
      { rootMargin: '200px' } // start loading 200px before the sentinel is visible
    );

    observer.observe(el);
    return () => observer.disconnect();
  }, [items.length, batchSize]);

  const visibleItems = items.slice(0, visibleCount);
  const hasMore = visibleCount < items.length;

  const resetCount = useCallback(() => {
    setVisibleCount(batchSize);
  }, [batchSize]);

  return { visibleItems, sentinelRef, hasMore, resetCount };
}
