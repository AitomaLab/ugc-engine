import React, { useEffect } from 'react';
import { createPortal } from 'react-dom';
import './MediaPreviewModal.css';

interface MediaPreviewModalProps {
    isOpen: boolean;
    onClose: () => void;
    src: string;
    type: 'image' | 'video' | 'mixed';
}

export default function MediaPreviewModal({ isOpen, onClose, src, type }: MediaPreviewModalProps) {
    useEffect(() => {
        if (isOpen) {
            document.body.style.overflow = 'hidden';

            const handleEscape = (e: KeyboardEvent) => {
                if (e.key === 'Escape') onClose();
            };
            window.addEventListener('keydown', handleEscape);

            return () => {
                document.body.style.overflow = 'unset';
                window.removeEventListener('keydown', handleEscape);
            };
        }
    }, [isOpen, onClose]);

    if (!isOpen) return null;

    // Detect if the asset is an mp4 even if passed as 'mixed'
    const isVideo = type === 'video' || (type === 'mixed' && src.toLowerCase().endsWith('.mp4'));

    const modalContent = (
        <div className="mpm-overlay" onClick={onClose}>
            <div className="mpm-container" onClick={(e) => e.stopPropagation()}>
                <button className="mpm-close-btn" onClick={onClose} aria-label="Close Preview">
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <line x1="18" y1="6" x2="6" y2="18"></line>
                        <line x1="6" y1="6" x2="18" y2="18"></line>
                    </svg>
                </button>
                <div className="mpm-content-wrapper">
                    {isVideo ? (
                        <video
                            src={src}
                            controls
                            autoPlay
                            loop
                            className="mpm-media-element"
                            playsInline
                        />
                    ) : (
                        <img
                            src={src}
                            alt="Visual Asset Preview"
                            className="mpm-media-element"
                        />
                    )}
                </div>
            </div>
        </div>
    );

    return createPortal(modalContent, document.body);
}
