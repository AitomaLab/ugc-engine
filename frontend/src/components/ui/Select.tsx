"use client";

import React, { useState, useRef, useEffect, useCallback } from 'react';
import { createPortal } from 'react-dom';
import './Select.css';

interface SelectOption {
    value: string;
    label: string;
}

interface SelectProps {
    value: string;
    onChange: (value: string) => void;
    options: SelectOption[];
    className?: string;
    style?: React.CSSProperties;
    placeholder?: string;
}

export default function Select({ value, onChange, options, className = '', style, placeholder = 'Select an option...' }: SelectProps) {
    const [isOpen, setIsOpen] = useState(false);
    const triggerRef = useRef<HTMLButtonElement>(null);
    const dropdownRef = useRef<HTMLDivElement>(null);
    const [dropdownPos, setDropdownPos] = useState<{ top: number; left: number; width: number } | null>(null);

    // Calculate dropdown position from trigger button
    const updatePosition = useCallback(() => {
        if (triggerRef.current) {
            const rect = triggerRef.current.getBoundingClientRect();
            setDropdownPos({
                top: rect.bottom + 4,
                left: rect.left,
                width: rect.width,
            });
        }
    }, []);

    // Close dropdown when clicking outside
    useEffect(() => {
        const handleClickOutside = (event: MouseEvent) => {
            const target = event.target as Node;
            if (
                triggerRef.current && !triggerRef.current.contains(target) &&
                dropdownRef.current && !dropdownRef.current.contains(target)
            ) {
                setIsOpen(false);
            }
        };

        if (isOpen) {
            document.addEventListener('mousedown', handleClickOutside);
        }
        return () => {
            document.removeEventListener('mousedown', handleClickOutside);
        };
    }, [isOpen]);

    // Recalculate position on scroll/resize while open
    useEffect(() => {
        if (!isOpen) return;
        updatePosition();
        window.addEventListener('scroll', updatePosition, true);
        window.addEventListener('resize', updatePosition);
        return () => {
            window.removeEventListener('scroll', updatePosition, true);
            window.removeEventListener('resize', updatePosition);
        };
    }, [isOpen, updatePosition]);

    const selectedOption = options.find(opt => opt.value === value);

    return (
        <div className={`custom-select-wrapper ${className}`} style={style}>
            <button
                ref={triggerRef}
                type="button"
                className={`custom-select-trigger ${isOpen ? 'open' : ''}`}
                onClick={() => setIsOpen(!isOpen)}
            >
                <span className="custom-select-value">
                    {selectedOption ? selectedOption.label : placeholder}
                </span>
                <svg className="custom-select-chevron" viewBox='0 0 24 24' fill='none' stroke='currentColor' strokeWidth='2' strokeLinecap='round' strokeLinejoin='round'>
                    <polyline points='6 9 12 15 18 9'></polyline>
                </svg>
            </button>

            {isOpen && dropdownPos && createPortal(
                <div
                    ref={dropdownRef}
                    className="custom-select-dropdown"
                    style={{
                        position: 'fixed',
                        top: dropdownPos.top,
                        left: dropdownPos.left,
                        width: dropdownPos.width,
                    }}
                >
                    {options.length === 0 ? (
                        <div className="custom-select-empty">No options available</div>
                    ) : (
                        <ul className="custom-select-list">
                            {options.map((option) => {
                                // Render divider/section headers
                                if (option.value.startsWith('__divider')) {
                                    return (
                                        <li
                                            key={option.value}
                                            className="custom-select-divider"
                                            style={{
                                                fontSize: '11px',
                                                fontWeight: 700,
                                                color: 'var(--text-3)',
                                                padding: '8px 12px 4px',
                                                cursor: 'default',
                                                borderTop: '1px solid var(--border)',
                                                marginTop: '4px',
                                                letterSpacing: '0.03em',
                                                textTransform: 'uppercase',
                                            }}
                                        >
                                            {option.label}
                                        </li>
                                    );
                                }
                                return (
                                    <li
                                        key={option.value}
                                        className={`custom-select-item ${option.value === value ? 'selected' : ''}`}
                                        onClick={() => {
                                            onChange(option.value);
                                            setIsOpen(false);
                                        }}
                                    >
                                        {option.label}
                                    </li>
                                );
                            })}
                        </ul>
                    )}
                </div>,
                document.body
            )}
        </div>
    );
}
