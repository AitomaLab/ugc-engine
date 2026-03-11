"use client";

import React, { useState, useRef, useEffect } from 'react';
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
    const dropdownRef = useRef<HTMLDivElement>(null);

    // Close dropdown when clicking outside
    useEffect(() => {
        const handleClickOutside = (event: MouseEvent) => {
            if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
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

    const selectedOption = options.find(opt => opt.value === value);

    return (
        <div className={`custom-select-wrapper ${className}`} style={style} ref={dropdownRef}>
            <button
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

            {isOpen && (
                <div className="custom-select-dropdown">
                    {options.length === 0 ? (
                        <div className="custom-select-empty">No options available</div>
                    ) : (
                        <ul className="custom-select-list">
                            {options.map((option) => (
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
                            ))}
                        </ul>
                    )}
                </div>
            )}
        </div>
    );
}
