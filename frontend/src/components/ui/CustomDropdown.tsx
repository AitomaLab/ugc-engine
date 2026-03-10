import { useState, useRef, useEffect } from 'react';

export function CustomDropdown({
    value,
    onChange,
    options,
    className = ""
}: {
    value: string;
    onChange: (val: string) => void;
    options: { value: string; label: string }[];
    className?: string;
}) {
    const [isOpen, setIsOpen] = useState(false);
    const dropdownRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        function handleClickOutside(event: MouseEvent) {
            if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
                setIsOpen(false);
            }
        }
        document.addEventListener('mousedown', handleClickOutside);
        return () => document.removeEventListener('mousedown', handleClickOutside);
    }, []);

    const selectedLabel = options.find(o => o.value === value)?.label || '';

    return (
        <div className={`relative inline-block ${className}`} ref={dropdownRef}>
            <button
                type='button'
                onClick={() => setIsOpen(!isOpen)}
                className='filter-select pr-8 flex items-center justify-between w-full h-full'
                style={{ textAlign: 'left' }}
            >
                <span className='truncate mr-2'>{selectedLabel || 'Select...'}</span>
                <div className='pointer-events-none absolute right-3 flex items-center'>
                    <svg style={{ width: '16px', height: '16px' }} className={`fill-[var(--text-3)] transition-transform ${isOpen ? 'rotate-180' : ''}`} xmlns='http://www.w3.org/2000/svg' viewBox='0 0 20 20'><path d='M9.293 12.95l.707.707L15.657 8l-1.414-1.414L10 10.828 5.757 6.586 4.343 8z' /></svg>
                </div>
            </button>
            {isOpen && (
                <div className='absolute z-50 mt-1 min-w-full bg-white/90 backdrop-blur-md border border-[#E8ECF4] rounded-xl shadow-xl py-1 max-h-60 overflow-y-auto animate-in fade-in zoom-in-95 duration-150'>
                    {options.map(opt => (
                        <button
                            key={opt.value}
                            type='button'
                            className={`block w-full text-left truncate px-4 py-2 text-xs hover:bg-[#337AFF]/5 transition-colors ${value === opt.value ? 'text-[#337AFF] font-semibold bg-[#337AFF]/5' : 'text-[#4A5568]'}`}
                            onClick={() => {
                                onChange(opt.value);
                                setIsOpen(false);
                            }}
                        >
                            {opt.label}
                        </button>
                    ))}
                </div>
            )}
        </div>
    );
}
