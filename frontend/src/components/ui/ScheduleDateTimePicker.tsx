'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import * as Popover from '@radix-ui/react-popover';
import './ScheduleDateTimePicker.css';

export type ScheduleDateTimePickerMode = 'datetime' | 'date' | 'time';

export interface ScheduleDateTimePickerProps {
  value: Date;
  onChange: (date: Date) => void;
  mode?: ScheduleDateTimePickerMode;
  minDate?: Date;
  disabled?: boolean;
  className?: string;
  compact?: boolean;
}

const HOURS_12 = Array.from({ length: 12 }, (_, i) => i + 1);
const MINUTES = Array.from({ length: 60 }, (_, i) => i);
const PERIODS = ['AM', 'PM'] as const;

function startOfDay(d: Date): Date {
  const out = new Date(d);
  out.setHours(0, 0, 0, 0);
  return out;
}

function isSameDay(a: Date, b: Date): boolean {
  return (
    a.getFullYear() === b.getFullYear()
    && a.getMonth() === b.getMonth()
    && a.getDate() === b.getDate()
  );
}

function to12Hour(h24: number): { hour12: number; period: 'AM' | 'PM' } {
  const period: 'AM' | 'PM' = h24 >= 12 ? 'PM' : 'AM';
  const h = h24 % 12;
  return { hour12: h === 0 ? 12 : h, period };
}

function to24Hour(hour12: number, period: 'AM' | 'PM'): number {
  if (period === 'AM') return hour12 === 12 ? 0 : hour12;
  return hour12 === 12 ? 12 : hour12 + 12;
}

function formatTriggerValue(value: Date, mode: ScheduleDateTimePickerMode, locale?: string): string {
  if (mode === 'date') {
    return value.toLocaleDateString(locale, { month: 'short', day: 'numeric', year: 'numeric' });
  }
  if (mode === 'time') {
    return value.toLocaleTimeString(locale, { hour: 'numeric', minute: '2-digit' });
  }
  const datePart = value.toLocaleDateString(locale, { month: 'short', day: 'numeric', year: 'numeric' });
  const timePart = value.toLocaleTimeString(locale, { hour: 'numeric', minute: '2-digit' });
  return `${datePart} · ${timePart}`;
}

function buildCalendarDays(viewMonth: Date): (Date | null)[] {
  const year = viewMonth.getFullYear();
  const month = viewMonth.getMonth();
  const first = new Date(year, month, 1);
  const startPad = first.getDay();
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const cells: (Date | null)[] = [];
  for (let i = 0; i < startPad; i++) cells.push(null);
  for (let d = 1; d <= daysInMonth; d++) cells.push(new Date(year, month, d));
  while (cells.length % 7 !== 0) cells.push(null);
  return cells;
}

export function ScheduleDateTimePicker({
  value,
  onChange,
  mode = 'datetime',
  minDate,
  disabled = false,
  className = '',
  compact = false,
}: ScheduleDateTimePickerProps) {
  const [open, setOpen] = useState(false);
  const [viewMonth, setViewMonth] = useState(() => new Date(value.getFullYear(), value.getMonth(), 1));
  const locale = typeof navigator !== 'undefined' ? navigator.language : undefined;

  const { hour12, period } = useMemo(() => to12Hour(value.getHours()), [value]);
  const minute = value.getMinutes();

  const hourRef = useRef<HTMLDivElement>(null);
  const minuteRef = useRef<HTMLDivElement>(null);
  const periodRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    setViewMonth(new Date(value.getFullYear(), value.getMonth(), 1));
  }, [open, value]);

  useEffect(() => {
    if (!open || mode === 'date') return;
    const scrollSelected = (el: HTMLDivElement | null, selector: string) => {
      const item = el?.querySelector(selector);
      if (item && el) {
        const top = (item as HTMLElement).offsetTop - el.clientHeight / 2 + (item as HTMLElement).clientHeight / 2;
        el.scrollTop = Math.max(0, top);
      }
    };
    requestAnimationFrame(() => {
      scrollSelected(hourRef.current, `[data-hour="${hour12}"]`);
      scrollSelected(minuteRef.current, `[data-minute="${minute}"]`);
      scrollSelected(periodRef.current, `[data-period="${period}"]`);
    });
  }, [open, hour12, minute, period, mode]);

  const weekdays = useMemo(() => {
    const base = new Date(2024, 0, 7);
    return Array.from({ length: 7 }, (_, i) => {
      const d = new Date(base);
      d.setDate(base.getDate() + i);
      return d.toLocaleDateString(locale, { weekday: 'short' }).slice(0, 2);
    });
  }, [locale]);

  const monthLabel = viewMonth.toLocaleDateString(locale, { month: 'long', year: 'numeric' });
  const calendarDays = useMemo(() => buildCalendarDays(viewMonth), [viewMonth]);
  const today = useMemo(() => startOfDay(new Date()), []);
  const minDay = minDate ? startOfDay(minDate) : null;

  const applyDate = useCallback((day: Date) => {
    const next = new Date(value);
    next.setFullYear(day.getFullYear(), day.getMonth(), day.getDate());
    onChange(next);
  }, [onChange, value]);

  const applyTime = useCallback((h12: number, m: number, p: 'AM' | 'PM') => {
    const next = new Date(value);
    next.setHours(to24Hour(h12, p), m, 0, 0);
    onChange(next);
  }, [onChange, value]);

  const showCalendar = mode === 'datetime' || mode === 'date';
  const showTime = mode === 'datetime' || mode === 'time';

  return (
    <div className={`sdtp-wrapper ${compact ? 'sdtp-compact' : ''} ${className}`.trim()}>
    <Popover.Root open={open} onOpenChange={setOpen}>
      <Popover.Trigger asChild>
        <button
          type="button"
          className={`sdtp-trigger ${compact ? 'sdtp-compact-trigger' : ''}`}
          disabled={disabled}
          data-state={open ? 'open' : 'closed'}
        >
          <span className="sdtp-trigger-text">{formatTriggerValue(value, mode, locale)}</span>
          <svg className="sdtp-trigger-icon" viewBox="0 0 24 24" fill="none" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            {mode === 'time' ? (
              <>
                <circle cx="12" cy="12" r="10" />
                <polyline points="12 6 12 12 16 14" />
              </>
            ) : (
              <>
                <rect x="3" y="4" width="18" height="18" rx="2" />
                <line x1="16" y1="2" x2="16" y2="6" />
                <line x1="8" y1="2" x2="8" y2="6" />
                <line x1="3" y1="10" x2="21" y2="10" />
              </>
            )}
          </svg>
        </button>
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Content
          className="sdtp-popover"
          sideOffset={6}
          align="start"
          onOpenAutoFocus={(e) => e.preventDefault()}
        >
          <div className={`sdtp-panel ${mode === 'date' ? 'date-only' : ''} ${mode === 'time' ? 'time-only' : ''}`}>
            {showCalendar && (
              <div className="sdtp-calendar">
                <div className="sdtp-cal-header">
                  <button
                    type="button"
                    className="sdtp-nav-btn"
                    aria-label="Previous month"
                    onClick={() => setViewMonth((m) => new Date(m.getFullYear(), m.getMonth() - 1, 1))}
                  >
                    ‹
                  </button>
                  <span className="sdtp-cal-title">{monthLabel}</span>
                  <button
                    type="button"
                    className="sdtp-nav-btn"
                    aria-label="Next month"
                    onClick={() => setViewMonth((m) => new Date(m.getFullYear(), m.getMonth() + 1, 1))}
                  >
                    ›
                  </button>
                </div>
                <div className="sdtp-weekdays">
                  {weekdays.map((wd) => (
                    <span key={wd} className="sdtp-weekday">{wd}</span>
                  ))}
                </div>
                <div className="sdtp-days">
                  {calendarDays.map((day, idx) => {
                    if (!day) {
                      return <span key={`empty-${idx}`} className="sdtp-day empty" />;
                    }
                    const dayStart = startOfDay(day);
                    const isDisabled = minDay ? dayStart < minDay : false;
                    const selected = isSameDay(day, value);
                    const isToday = isSameDay(day, today);
                    const outside = day.getMonth() !== viewMonth.getMonth();
                    return (
                      <button
                        key={day.toISOString()}
                        type="button"
                        className={`sdtp-day${selected ? ' selected' : ''}${isToday ? ' today' : ''}${outside ? ' outside' : ''}`}
                        disabled={isDisabled}
                        onClick={() => applyDate(day)}
                      >
                        {day.getDate()}
                      </button>
                    );
                  })}
                </div>
                <div className="sdtp-cal-footer">
                  <button
                    type="button"
                    className="sdtp-footer-btn"
                    onClick={() => {
                      const now = new Date();
                      applyDate(now);
                      if (mode === 'datetime') applyTime(to12Hour(now.getHours()).hour12, now.getMinutes(), to12Hour(now.getHours()).period);
                    }}
                  >
                    Today
                  </button>
                  <button
                    type="button"
                    className="sdtp-footer-btn"
                    onClick={() => setOpen(false)}
                  >
                    Done
                  </button>
                </div>
              </div>
            )}
            {showTime && (
              <div className="sdtp-time">
                <div className="sdtp-time-col" ref={hourRef}>
                  {HOURS_12.map((h) => (
                    <button
                      key={h}
                      type="button"
                      data-hour={h}
                      className={`sdtp-time-item${hour12 === h ? ' selected' : ''}`}
                      onClick={() => applyTime(h, minute, period)}
                    >
                      {String(h).padStart(2, '0')}
                    </button>
                  ))}
                </div>
                <span className="sdtp-time-sep">:</span>
                <div className="sdtp-time-col" ref={minuteRef}>
                  {MINUTES.map((m) => (
                    <button
                      key={m}
                      type="button"
                      data-minute={m}
                      className={`sdtp-time-item${minute === m ? ' selected' : ''}`}
                      onClick={() => applyTime(hour12, m, period)}
                    >
                      {String(m).padStart(2, '0')}
                    </button>
                  ))}
                </div>
                <div className="sdtp-time-col" ref={periodRef}>
                  {PERIODS.map((p) => (
                    <button
                      key={p}
                      type="button"
                      data-period={p}
                      className={`sdtp-time-item${period === p ? ' selected' : ''}`}
                      onClick={() => applyTime(hour12, minute, p)}
                    >
                      {p}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
    </div>
  );
}
