'use client';

import { useState, useEffect, useRef, useCallback } from 'react';

/**
 * Progressive rendering hook — renders items in batches as the user scrolls.
 *
 * Instead of rendering 200+ cards at once (which freezes the UI),
 * this shows the first `batchSize` items and loads more when the
 * user scrolls near the bottom of the container.
 *
 * Usage:
 *   const { visibleItems, scrollContainerRef, hasMore } = useProgressiveList(allItems, 12);
 *   // put ref={scrollContainerRef} on your scrollable container
 *   // render visibleItems in your grid
 */
export function useProgressiveList<T>(items: T[], batchSize = 12) {
  const [visibleCount, setVisibleCount] = useState(batchSize);
  const scrollContainerRef = useRef<HTMLDivElement | null>(null);
  // Keep a ref for sentinelRef for backward compat (not used in new approach)
  const sentinelRef = useRef<HTMLDivElement | null>(null);

  // Reset visible count when the source list changes
  useEffect(() => {
    setVisibleCount(batchSize);
  }, [items.length, batchSize]);

  // Scroll-based loading: when user scrolls near bottom, show more items
  useEffect(() => {
    const container = scrollContainerRef.current;
    if (!container) return;

    const handleScroll = () => {
      const { scrollTop, scrollHeight, clientHeight } = container;
      // Load more when within 300px of the bottom
      if (scrollHeight - scrollTop - clientHeight < 300) {
        setVisibleCount((prev) => {
          const next = prev + batchSize;
          return Math.min(next, items.length);
        });
      }
    };

    container.addEventListener('scroll', handleScroll, { passive: true });
    // Also check immediately in case the container is already scrolled or content fits
    handleScroll();

    return () => container.removeEventListener('scroll', handleScroll);
  }, [items.length, batchSize, visibleCount]);

  const visibleItems = items.slice(0, visibleCount);
  const hasMore = visibleCount < items.length;

  const resetCount = useCallback(() => {
    setVisibleCount(batchSize);
  }, [batchSize]);

  return { visibleItems, sentinelRef, hasMore, resetCount, scrollContainerRef };
}
