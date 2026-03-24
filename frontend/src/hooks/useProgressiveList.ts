'use client';

import { useState, useEffect, useRef, useCallback } from 'react';

/**
 * Progressive rendering hook — renders items in batches as the user scrolls.
 *
 * Instead of rendering 200+ cards at once (which freezes the UI),
 * this shows the first `batchSize` items and loads more when the
 * user scrolls near the bottom.
 *
 * **Dual mode:**
 * - If you put `ref={scrollContainerRef}` on a scrollable container,
 *   it listens to that container's scroll events (e.g. inside a modal).
 * - If `scrollContainerRef` is not attached to any element, it falls
 *   back to listening on the **window** scroll (e.g. full-page lists).
 *
 * Usage:
 *   const { visibleItems, scrollContainerRef, sentinelRef, hasMore } = useProgressiveList(allItems, 12);
 */
export function useProgressiveList<T>(items: T[], batchSize = 12) {
  const [visibleCount, setVisibleCount] = useState(batchSize);
  const scrollContainerRef = useRef<HTMLDivElement | null>(null);
  const sentinelRef = useRef<HTMLDivElement | null>(null);

  // Reset visible count when the source list changes
  useEffect(() => {
    setVisibleCount(batchSize);
  }, [items.length, batchSize]);

  // Scroll-based loading
  useEffect(() => {
    const container = scrollContainerRef.current;

    const loadMore = () => {
      setVisibleCount((prev) => {
        const next = prev + batchSize;
        return Math.min(next, items.length);
      });
    };

    // --- Container mode (modal / nested scrollable div) ---
    if (container) {
      const handleScroll = () => {
        const { scrollTop, scrollHeight, clientHeight } = container;
        if (scrollHeight - scrollTop - clientHeight < 300) {
          loadMore();
        }
      };
      container.addEventListener('scroll', handleScroll, { passive: true });
      handleScroll(); // check immediately
      return () => container.removeEventListener('scroll', handleScroll);
    }

    // --- Window mode (full-page scroll) ---
    const handleWindowScroll = () => {
      const scrollY = window.scrollY || document.documentElement.scrollTop;
      const windowHeight = window.innerHeight;
      const docHeight = document.documentElement.scrollHeight;
      if (docHeight - scrollY - windowHeight < 400) {
        loadMore();
      }
    };
    window.addEventListener('scroll', handleWindowScroll, { passive: true });
    handleWindowScroll(); // check immediately
    return () => window.removeEventListener('scroll', handleWindowScroll);
  }, [items.length, batchSize, visibleCount]);

  const visibleItems = items.slice(0, visibleCount);
  const hasMore = visibleCount < items.length;

  const resetCount = useCallback(() => {
    setVisibleCount(batchSize);
  }, [batchSize]);

  return { visibleItems, sentinelRef, hasMore, resetCount, scrollContainerRef };
}
