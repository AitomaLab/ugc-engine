'use client';

import { useState, useRef, useEffect, useCallback } from 'react';
import { creativeFetch } from '@/lib/creative-os-api';
import type { PromptOption, EnhanceResponse } from '@/lib/creative-os-api';
import { useApp } from '@/providers/AppProvider';
import { useTranslation } from '@/lib/i18n';

type BarState = 'idle' | 'enhancing' | 'generating' | 'complete';

interface CreateBarProps {
    activeTab: 'images' | 'videos';
    projectId: string;
    onGenerated: () => void;
    preloadImage?: any;
    onPreloadConsumed?: () => void;
}

const IMAGE_MODES = [
    { id: 'cinematic', label: 'Cinematic' },
    { id: 'iphone_look', label: 'iPhone Look' },
    { id: 'luxury', label: 'Luxury' },
    { id: 'ugc', label: 'UGC' },
];
const VIDEO_MODES = [
    { id: 'ugc', label: 'UGC', clipLengths: [8] },
    { id: 'cinematic_video', label: 'Cinematic', clipLengths: [5, 10] },
    { id: 'ai_clone', label: 'AI Clone', clipLengths: [15, 30] },
    { id: 'seedance_2_ugc', label: 'UGC (Seedance 2.0)', clipLengths: [5, 8, 10, 15] },
    { id: 'seedance_2_cinematic', label: 'Cinematic (Seedance 2.0)', clipLengths: [5, 7, 10, 15] },
    { id: 'seedance_2_product', label: 'Product Scene (Seedance 2.0)', clipLengths: [5, 7, 10] },
];
const ASPECT_RATIOS = ['9:16', '16:9', '1:1'];
const QUALITIES = ['2K', '4K'];
const LANGUAGES = ['EN', 'ES'];

export function CreateBar({ activeTab, projectId, onGenerated, preloadImage, onPreloadConsumed }: CreateBarProps) {
    const { session } = useApp();
    const { t } = useTranslation();
    const textareaRef = useRef<HTMLTextAreaElement>(null);
    const barRef = useRef<HTMLDivElement>(null);
    const fileInputRef = useRef<HTMLInputElement>(null);
    const mentionListRef = useRef<HTMLDivElement>(null);

    // ── Compute the pixel position of the '@' character in the textarea ──
    // Stored as state so it can be passed as an inline style prop on the dropdown div.
    const [mentionPos, setMentionPos] = useState<{ bottom: number; left: number; width: number; maxHeight: number } | null>(null);

    const computeMentionPosition = useCallback((cursorIndex: number) => {
        const textarea = textareaRef.current;
        if (!textarea) return;

        const textareaRect = textarea.getBoundingClientRect();
        const textareaStyles = window.getComputedStyle(textarea);

        // Build a hidden mirror div that replicates the textarea's text layout
        const mirror = document.createElement('div');
        mirror.style.position = 'absolute';
        mirror.style.visibility = 'hidden';
        mirror.style.whiteSpace = 'pre-wrap';
        mirror.style.wordWrap = 'break-word';
        mirror.style.overflow = 'hidden';
        mirror.style.width = `${textarea.clientWidth}px`;
        mirror.style.font = textareaStyles.font;
        mirror.style.fontSize = textareaStyles.fontSize;
        mirror.style.fontFamily = textareaStyles.fontFamily;
        mirror.style.lineHeight = textareaStyles.lineHeight;
        mirror.style.letterSpacing = textareaStyles.letterSpacing;
        mirror.style.padding = textareaStyles.padding;
        mirror.style.border = textareaStyles.border;
        mirror.style.boxSizing = textareaStyles.boxSizing;

        // Insert text up to the '@' position, then a marker span
        const textBeforeAt = textarea.value.slice(0, cursorIndex);
        mirror.appendChild(document.createTextNode(textBeforeAt));
        const marker = document.createElement('span');
        marker.textContent = '@';
        mirror.appendChild(marker);
        document.body.appendChild(mirror);

        // Measure the marker's Y position relative to the mirror
        const markerRect = marker.getBoundingClientRect();
        const mirrorRect = mirror.getBoundingClientRect();
        const relativeTop = markerRect.top - mirrorRect.top;
        document.body.removeChild(mirror);

        // The '@' Y position in viewport coords
        const atY = textareaRect.top + relativeTop - textarea.scrollTop;
        const headerHeight = 72;
        const gap = 8;
        const availableHeight = Math.max(120, Math.min(340, atY - headerHeight - gap));

        setMentionPos({
            bottom: window.innerHeight - atY + gap,
            left: textareaRect.left,
            width: textareaRect.width,
            maxHeight: availableHeight,
        });
    }, []);

    // Inline style for the mention dropdown — overrides the CSS class positioning
    const mentionDropdownStyle: React.CSSProperties = mentionPos ? {
        position: 'fixed',
        bottom: mentionPos.bottom,
        left: mentionPos.left,
        width: mentionPos.width,
        maxHeight: mentionPos.maxHeight,
        top: 'auto',
        right: 'auto',
    } : {};

    const [barState, setBarState] = useState<BarState>('idle');
    const [prompt, setPrompt] = useState('');
    const [mode, setMode] = useState(activeTab === 'images' ? 'cinematic' : 'ugc');
    const [error, setError] = useState('');
    const [scriptLoading, setScriptLoading] = useState(false);

    // Settings
    const [aspectRatio, setAspectRatio] = useState('9:16');
    const [quality, setQuality] = useState('4K');
    const [language, setLanguage] = useState('EN');
    const [clipLength, setClipLength] = useState(5);
    const [fullVideo, setFullVideo] = useState(false);
    const [videoLength, setVideoLength] = useState(15);
    const [bgMusic, setBgMusic] = useState(true);
    const [captions, setCaptions] = useState(true);
    const [multiShot, setMultiShot] = useState(false);
    const [multiShotLength, setMultiShotLength] = useState(10);

    // Asset references
    const [selectedProduct, setSelectedProduct] = useState<any>(null);
    const [selectedInfluencer, setSelectedInfluencer] = useState<any>(null);
    const [selectedImage, setSelectedImage] = useState<any>(null);
    const [customUpload, setCustomUpload] = useState<string | null>(null);
    const [productPickerOpen, setProductPickerOpen] = useState(false);
    const [influencerPickerOpen, setInfluencerPickerOpen] = useState(false);
    const [imagePickerOpen, setImagePickerOpen] = useState(false);
    const [products, setProducts] = useState<any[]>([]);
    const [influencers, setInfluencers] = useState<any[]>([]);
    const [projectImages, setProjectImages] = useState<any[]>([]);

    // Active dropdown — only one open at a time (fixes the click propagation issue)
    const [activeDropdown, setActiveDropdown] = useState<string | null>(null);

    // @mention autocomplete state
    const [mentionOpen, setMentionOpen] = useState(false);
    const [mentionFilter, setMentionFilter] = useState('');
    const [mentionIndex, setMentionIndex] = useState(0);
    const [mentionCursorStart, setMentionCursorStart] = useState(0);
    // When set, the dropdown renders a shot picker for this asset instead of
    // the mention list (products / models with multiple views).
    const [mentionShotPicker, setMentionShotPicker] = useState<{ id: string; type: 'product' | 'influencer'; name: string; views: string[] } | null>(null);
    // Picked app clip for digital products (drives composite + B-roll).
    const [pickedAppClipId, setPickedAppClipId] = useState<string | null>(null);

    useEffect(() => {
        setMode(activeTab === 'images' ? 'cinematic' : 'ugc');
        setClipLength(5); setFullVideo(false); setMultiShot(false); setBarState('idle');
    }, [activeTab]);

    // Auto-load image from "Create Video" button in image modal
    useEffect(() => {
        if (preloadImage && activeTab === 'videos') {
            setSelectedImage(preloadImage);
            onPreloadConsumed?.();
            // Focus the prompt textarea so the user can start typing
            setTimeout(() => textareaRef.current?.focus(), 200);
        }
    }, [preloadImage, activeTab, onPreloadConsumed]);

    useEffect(() => {
        if (activeTab === 'videos') {
            const mc = VIDEO_MODES.find(m => m.id === mode);
            if (mc && !mc.clipLengths.includes(clipLength)) setClipLength(mc.clipLengths[0]);
        }
    }, [mode, activeTab, clipLength]);

    useEffect(() => {
        if (textareaRef.current) {
            textareaRef.current.style.height = 'auto';
            textareaRef.current.style.height = Math.min(textareaRef.current.scrollHeight, 80) + 'px';
        }
    }, [prompt]);

    // Close dropdowns on click outside the bar
    useEffect(() => {
        const handler = (e: MouseEvent) => {
            if (barRef.current && !barRef.current.contains(e.target as Node)) {
                setActiveDropdown(null);
            }
        };
        document.addEventListener('mousedown', handler);
        return () => document.removeEventListener('mousedown', handler);
    }, []);

    const loadProducts = useCallback(async () => {
        try {
            const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/products`, {
                headers: { 'Authorization': `Bearer ${(await (await import('@/lib/supabaseClient')).supabase.auth.getSession()).data.session?.access_token}` },
            });
            if (res.ok) setProducts(await res.json());
        } catch {}
    }, []);

    const loadInfluencers = useCallback(async () => {
        try {
            const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/influencers`, {
                headers: { 'Authorization': `Bearer ${(await (await import('@/lib/supabaseClient')).supabase.auth.getSession()).data.session?.access_token}` },
            });
            if (res.ok) setInfluencers(await res.json());
        } catch {}
    }, []);

    const loadProjectImages = useCallback(async () => {
        try {
            const imgs = await creativeFetch<any[]>(`/creative-os/projects/${projectId}/assets/images`);
            setProjectImages(imgs.filter((img: any) => img.image_url && img.status === 'image_completed'));
        } catch {}
    }, [projectId]);

    const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (file) {
            const reader = new FileReader();
            reader.onload = (ev) => {
                setCustomUpload(ev.target?.result as string);
            };
            reader.readAsDataURL(file);
        }
        if (fileInputRef.current) fileInputRef.current.value = '';
    };

    const toggleDropdown = (id: string) => {
        setActiveDropdown(prev => prev === id ? null : id);
    };

    const modes = activeTab === 'images' ? IMAGE_MODES : VIDEO_MODES;
    const currentMode = modes.find(m => m.id === mode) || modes[0];
    const currentVideoMode = VIDEO_MODES.find(m => m.id === mode);

    // ── AI Script Generator ──
    const handleGenerateScript = async () => {
        if (scriptLoading || !session) return;
        setScriptLoading(true); setError('');

        try {
            // Resolve influencer from explicit selection or from pre-generated image metadata
            let scriptInfluencerId = selectedInfluencer?.id;
            if (!scriptInfluencerId && selectedImage?.analysis_json?.influencer_id) {
                scriptInfluencerId = selectedImage.analysis_json.influencer_id;
            }

            const result = await creativeFetch<{ script: string }>('/creative-os/generate/video/ai-script', {
                method: 'POST',
                body: JSON.stringify({
                    project_id: projectId,
                    product_id: selectedProduct?.id || selectedImage?.product_id || undefined,
                    influencer_id: scriptInfluencerId || undefined,
                    reference_image_url: selectedImage?.image_url || undefined,
                    language: language.toLowerCase(),
                    clip_length: fullVideo ? videoLength : clipLength,
                    full_video_mode: fullVideo,
                    context: prompt.trim() || undefined,
                }),
            });

            if (result?.script) {
                // Append to existing prompt or set as new
                setPrompt(prev => {
                    const separator = prev.trim() ? '\n\n' : '';
                    return prev + separator + result.script;
                });
                // Auto-resize textarea
                setTimeout(() => {
                    if (textareaRef.current) {
                        textareaRef.current.style.height = 'auto';
                        textareaRef.current.style.height = textareaRef.current.scrollHeight + 'px';
                        // Move cursor to end
                        textareaRef.current.selectionStart = textareaRef.current.value.length;
                        textareaRef.current.selectionEnd = textareaRef.current.value.length;
                        textareaRef.current.focus();
                    }
                }, 100);
            }
        } catch (err) {
            console.error('AI Script failed:', err);
            setError('Failed to generate AI script');
        } finally {
            setScriptLoading(false);
        }
    };

    const handleGenerate = async () => {
        if (barState !== 'idle' || !prompt.trim() || !session) return;
        const userPrompt = prompt.trim();
        setPrompt(''); // Clear prompt immediately for snappy UX
        setBarState('enhancing'); setError('');

        try {
            // If user uploaded a custom image, upload via backend (server-side, bypasses RLS)
            let uploadedImageUrl: string | undefined;
            if (customUpload) {
                try {
                    console.log(`[CreateBar] Uploading custom image via backend...`);
                    const uploadResult = await creativeFetch<{ url: string }>('/creative-os/upload/image', {
                        method: 'POST',
                        body: JSON.stringify({ data: customUpload }),
                    });
                    if (uploadResult?.url) {
                        uploadedImageUrl = uploadResult.url;
                        console.log(`[CreateBar] Upload OK: ${uploadedImageUrl}`);
                    } else {
                        console.error('[CreateBar] Upload returned no URL');
                        setError('Image upload failed — no URL returned');
                    }
                } catch (e: any) {
                    console.error('[CreateBar] Custom image upload failed:', e);
                    setError(t('creativeOs.createBar.uploadFailed').replace('{msg}', e.message || t('creativeOs.createBar.unknownError')));
                }
            }

            if (activeTab === 'images') {
                // UGC mode requires a product — show friendly error if missing
                if (mode === 'ugc' && !selectedProduct?.id) {
                    setError('UGC mode requires a product. Please select a product from the inputs above before generating.');
                    setBarState('idle');
                    return;
                }

                // Step 1: Auto-enhance the prompt
                const enhanced = await creativeFetch<EnhanceResponse>('/creative-os/generate/image/enhance', {
                    method: 'POST',
                    body: JSON.stringify({
                        prompt: userPrompt, mode, language: language.toLowerCase(),
                        project_id: projectId, product_id: selectedProduct?.id, influencer_id: selectedInfluencer?.id,
                    }),
                });
                const bestPrompt = enhanced.options?.[0]?.prompt || userPrompt;

                // Step 2: Auto-execute with the enhanced prompt
                setBarState('generating');
                await creativeFetch('/creative-os/generate/image/execute', {
                    method: 'POST',
                    body: JSON.stringify({
                        prompt: bestPrompt, mode, project_id: projectId,
                        product_id: selectedProduct?.id, influencer_id: selectedInfluencer?.id,
                        reference_image_url: uploadedImageUrl || undefined,
                        aspect_ratio: aspectRatio, quality: quality.toLowerCase(),
                    }),
                });
            } else {
                // Videos: call video endpoint directly (no enhance step)

                setBarState('generating');

                // Parse @mentions from prompt and build element_refs
                const mentionRegex = /@([\w]+)/g;
                const elementRefs: Array<{ name: string; type: string; image_url?: string }> = [];
                let mentionedProductId: string | undefined;
                let mentionedInfluencerId: string | undefined;
                let match;
                while ((match = mentionRegex.exec(userPrompt)) !== null) {
                    const tag = match[1].toLowerCase();
                    // Find matching product or influencer
                    const matchedProduct = products.find((p: any) =>
                        (p.name || p.product_name || '').toLowerCase().replace(/\s+/g, '_') === tag
                    );
                    const matchedInfluencer = influencers.find((inf: any) =>
                        (inf.name || '').toLowerCase().replace(/\s+/g, '_') === tag
                    );
                    if (matchedProduct) {
                        elementRefs.push({
                            name: `element_${tag}`,
                            type: 'product',
                            image_url: matchedProduct.image_url,
                        });
                        // Also resolve product_id from @mention (first match wins)
                        if (!mentionedProductId) {
                            mentionedProductId = matchedProduct.id;
                            console.log('[CreateBar] @mention resolved product_id:', mentionedProductId, `(@${tag})`);
                        }
                    } else if (matchedInfluencer) {
                        elementRefs.push({
                            name: `element_${tag}`,
                            type: 'influencer',
                            image_url: matchedInfluencer.image_url,
                        });
                        // Also resolve influencer_id from @mention (first match wins)
                        if (!mentionedInfluencerId) {
                            mentionedInfluencerId = matchedInfluencer.id;
                            console.log('[CreateBar] @mention resolved influencer_id:', mentionedInfluencerId, `(@${tag})`);
                        }
                    }
                }

                // ── Resolve product_id and influencer_id ──
                // Priority: explicitly selected > @mention > inherited from selected image > undefined
                let resolvedProductId = selectedProduct?.id || mentionedProductId;
                let resolvedInfluencerId = selectedInfluencer?.id || mentionedInfluencerId;

                if (selectedImage && !resolvedProductId && selectedImage.product_id) {
                    resolvedProductId = selectedImage.product_id;
                    console.log('[CreateBar] Inherited product_id from selected image:', resolvedProductId);
                }
                if (selectedImage && !resolvedInfluencerId) {
                    const imgMeta = selectedImage.analysis_json;
                    if (imgMeta && typeof imgMeta === 'object' && imgMeta.influencer_id) {
                        resolvedInfluencerId = imgMeta.influencer_id;
                        console.log('[CreateBar] Inherited influencer_id from selected image:', resolvedInfluencerId);
                    }
                }

                // Multi-Shot mode requires a product (from any source)
                if (fullVideo && !resolvedProductId) {
                    setError('Multi-Shot mode requires a product. Select one, use @product_name in your prompt, or select a generated image.');
                    setPrompt(userPrompt);
                    setBarState('idle');
                    return;
                }

                const isCinematicMulti = mode === 'cinematic_video' && multiShot;
                const videoPayload: any = {
                    prompt: userPrompt, mode, project_id: projectId,
                    product_id: resolvedProductId, influencer_id: resolvedInfluencerId,
                    reference_image_url: selectedImage?.image_url || uploadedImageUrl || undefined,
                    language: language.toLowerCase(),
                    clip_length: isCinematicMulti ? multiShotLength : (fullVideo ? videoLength : clipLength),
                    full_video_mode: fullVideo, video_length: videoLength,
                    background_music: bgMusic, captions,
                    multi_shot_mode: isCinematicMulti,
                };
                if (elementRefs.length > 0) {
                    videoPayload.element_refs = elementRefs;
                }
                if (pickedAppClipId) {
                    videoPayload.app_clip_id = pickedAppClipId;
                    videoPayload.product_type = 'digital';
                }
                console.log('[CreateBar] Video payload:', {
                    mode, full_video_mode: fullVideo, multi_shot_mode: isCinematicMulti,
                    clip_length: videoPayload.clip_length,
                    reference_image_url: videoPayload.reference_image_url,
                    product_id: videoPayload.product_id,
                    influencer_id: videoPayload.influencer_id,
                    inherited_from_image: !selectedProduct?.id && !!resolvedProductId || !selectedInfluencer?.id && !!resolvedInfluencerId,
                    element_refs: elementRefs,
                });
                await creativeFetch('/creative-os/generate/video/', {
                    method: 'POST',
                    body: JSON.stringify(videoPayload),
                });
            }

            setBarState('complete');
            // Delay refetch slightly to ensure DB record is committed
            setTimeout(() => onGenerated(), 1500);
            // Second refetch to catch any race conditions
            setTimeout(() => onGenerated(), 5000);
            setTimeout(() => setBarState('idle'), 3000);
        } catch (err: any) {
            setError(err.message || t('creativeOs.createBar.generationFailed'));
            setPrompt(userPrompt); // Restore prompt on error so user doesn't lose input
            setBarState('idle');
        }
    };

    // ── @Mention helpers ──
    const mentionItems = [
        ...products.map((p: any) => {
            const isDigital = p.type === 'digital';
            const appClips = Array.isArray(p.app_clips) ? p.app_clips.filter((c: any) => c.first_frame_url) : [];
            let views: string[];
            let clipsByFrame: Record<string, { clip_id: string; video_url?: string }> | undefined;
            let thumb = p.image_url;
            if (isDigital && appClips.length) {
                views = appClips.map((c: any) => c.first_frame_url);
                clipsByFrame = Object.fromEntries(
                    appClips.map((c: any) => [c.first_frame_url, { clip_id: c.id, video_url: c.video_url }])
                );
                if (!thumb) thumb = views[0];
            } else {
                const extras = Array.isArray(p.product_views) ? p.product_views.filter(Boolean) : [];
                views = p.image_url ? [p.image_url, ...extras.filter((v: string) => v !== p.image_url)] : extras;
            }
            return {
                id: p.id,
                name: p.name || p.product_name || t('creativeOs.createBar.productFallback'),
                type: 'product' as const,
                image_url: thumb,
                views: views.length > 1 ? views : undefined,
                product_type: isDigital ? 'digital' as const : 'physical' as const,
                clipsByFrame,
            };
        }),
        ...influencers.map((inf: any) => {
            const extras = Array.isArray(inf.character_views) ? inf.character_views.filter(Boolean) : [];
            const views = inf.image_url ? [inf.image_url, ...extras.filter((v: string) => v !== inf.image_url)] : extras;
            return {
                id: inf.id,
                name: inf.name || t('creativeOs.createBar.modelFallback'),
                type: 'influencer' as const,
                image_url: inf.image_url,
                views: views.length > 1 ? views : undefined,
            };
        }),
    ];

    const filteredMentions = mentionItems.filter(m =>
        m.name.toLowerCase().includes(mentionFilter.toLowerCase())
    );

    const handlePromptChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
        const val = e.target.value;
        const cursor = e.target.selectionStart;
        setPrompt(val);

        // Detect @mention trigger
        const textBefore = val.slice(0, cursor);
        const atMatch = textBefore.match(/@([\w\s]*)$/);
        if (atMatch) {
            const filter = atMatch[1];
            setMentionFilter(filter);
            setMentionCursorStart(cursor - filter.length - 1); // position of '@'
            setMentionIndex(0);
            if (!mentionOpen) {
                // Load data on first @
                loadProducts();
                loadInfluencers();
            }
            setMentionOpen(true);
            // Compute dropdown position at the '@' character
            computeMentionPosition(cursor - filter.length - 1);
        } else {
            setMentionOpen(false);
            setMentionPos(null);
        }
    };

    const finalizeMentionInsert = (item: typeof mentionItems[0], chosenImageUrl?: string) => {
        const before = prompt.slice(0, mentionCursorStart);
        const after = prompt.slice(textareaRef.current?.selectionStart || mentionCursorStart);
        const tag = `@${item.name.toLowerCase().replace(/\s+/g, '_')}`;
        const newPrompt = before + tag + ' ' + after;
        setPrompt(newPrompt);
        setMentionOpen(false);
        setMentionShotPicker(null);

        if (item.type === 'product' && chosenImageUrl && (item as any).clipsByFrame?.[chosenImageUrl]) {
            setPickedAppClipId((item as any).clipsByFrame[chosenImageUrl].clip_id);
        } else if (item.type === 'product' && !chosenImageUrl && (item as any).clipsByFrame) {
            const entries = Object.entries((item as any).clipsByFrame as Record<string, { clip_id: string }>);
            if (entries.length === 1) setPickedAppClipId(entries[0][1].clip_id);
        }

        // Auto-select this item as product/influencer if not already selected.
        // If the user picked a specific shot, override the selected asset's
        // image_url so downstream generators pick up the chosen view.
        if (item.type === 'product' && !selectedProduct) {
            const match = products.find((p: any) => p.id === item.id);
            if (match) setSelectedProduct(chosenImageUrl ? { ...match, image_url: chosenImageUrl } : match);
        } else if (item.type === 'influencer' && !selectedInfluencer) {
            const match = influencers.find((inf: any) => inf.id === item.id);
            if (match) setSelectedInfluencer(chosenImageUrl ? { ...match, image_url: chosenImageUrl } : match);
        }

        // Re-focus textarea
        setTimeout(() => {
            if (textareaRef.current) {
                const pos = before.length + tag.length + 1;
                textareaRef.current.focus();
                textareaRef.current.setSelectionRange(pos, pos);
            }
        }, 0);
    };

    const insertMention = (item: typeof mentionItems[0]) => {
        if ((item.type === 'product' || item.type === 'influencer') && item.views && item.views.length > 1) {
            setMentionShotPicker({ id: item.id, type: item.type, name: item.name, views: item.views });
            return;
        }
        finalizeMentionInsert(item);
    };

    const handleKeyDown = (e: React.KeyboardEvent) => {
        // Compute the same order as the dropdown: models first, then products
        const orderedMentions = [
            ...filteredMentions.filter(m => m.type === 'influencer'),
            ...filteredMentions.filter(m => m.type === 'product'),
        ];
        if (mentionOpen && orderedMentions.length > 0) {
            if (e.key === 'ArrowDown') {
                e.preventDefault();
                setMentionIndex(i => Math.min(i + 1, orderedMentions.length - 1));
                return;
            }
            if (e.key === 'ArrowUp') {
                e.preventDefault();
                setMentionIndex(i => Math.max(i - 1, 0));
                return;
            }
            if (e.key === 'Enter' || e.key === 'Tab') {
                e.preventDefault();
                insertMention(orderedMentions[mentionIndex]);
                return;
            }
            if (e.key === 'Escape') {
                e.preventDefault();
                setMentionOpen(false);
                return;
            }
        }
        if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleGenerate(); }
    };

    const estimatedCost = fullVideo ? (videoLength === 15 ? 156 : 245) : (activeTab === 'images' ? 12 : 35);

    let btnLabel = t('creativeOs.createBar.generateBtn');
    if (activeTab === 'videos') btnLabel = fullVideo ? t('creativeOs.createBar.generateVideoBtn') : t('creativeOs.createBar.animateBtn');
    if (barState === 'enhancing') btnLabel = t('creativeOs.createBar.enhancingBtn');
    if (barState === 'generating') btnLabel = t('creativeOs.createBar.generatingBtn');

    const placeholder = activeTab === 'images'
        ? t('creativeOs.createBar.imagePlaceholder')
        : t('creativeOs.createBar.videoPlaceholder');

    return (
        <>
            {/* Product Picker */}
            {productPickerOpen && <PickerModal title={t('creativeOs.createBar.selectProduct')} items={products} onSelect={p => { setSelectedProduct(p); setProductPickerOpen(false); }} onClose={() => setProductPickerOpen(false)} onLoad={loadProducts} />}
            {influencerPickerOpen && <PickerModal title={t('creativeOs.createBar.selectModel')} items={influencers} onSelect={inf => { setSelectedInfluencer(inf); setInfluencerPickerOpen(false); }} onClose={() => setInfluencerPickerOpen(false)} onLoad={loadInfluencers} />}
            {imagePickerOpen && <PickerModal title={t('creativeOs.createBar.selectImage')} items={projectImages} onSelect={img => { setSelectedImage(img); setImagePickerOpen(false); }} onClose={() => setImagePickerOpen(false)} onLoad={loadProjectImages} />}

            {/* Hidden file input for custom uploads */}
            <input ref={fileInputRef} type="file" accept="image/*" style={{ display: 'none' }} onChange={handleFileUpload} />

            {/* ═══════ MAIN CREATE BAR ═══════ */}
            <div className="co-bar-wrapper" ref={barRef}>
                {error && <div className="co-bar-error">{error}</div>}
                {barState === 'complete' && <div className="co-bar-success">{activeTab === 'images' ? t('creativeOs.createBar.successImage') : t('creativeOs.createBar.successVideo')}</div>}

                <div className="co-bar-card">
                    {/* ── ROW 1: References + Prompt ── */}
                    <div className="co-bar-row1">
                        <div className="co-ref-group">
                            <RefSlot
                                item={selectedProduct}
                                type="product"
                                onClick={() => { setProductPickerOpen(true); loadProducts(); }}
                                onClear={() => setSelectedProduct(null)}
                            />
                            <RefSlot
                                item={selectedInfluencer}
                                type="model"
                                onClick={() => { setInfluencerPickerOpen(true); loadInfluencers(); }}
                                onClear={() => setSelectedInfluencer(null)}
                            />
                            {activeTab === 'videos' && (
                                <RefSlot
                                    item={selectedImage}
                                    type="image"
                                    onClick={() => { setImagePickerOpen(true); loadProjectImages(); }}
                                    onClear={() => setSelectedImage(null)}
                                />
                            )}
                            <div className="co-ref-box" role="button" tabIndex={0} onClick={() => fileInputRef.current?.click()} onKeyDown={e => { if (e.key === 'Enter') fileInputRef.current?.click(); }}>
                                {customUpload ? (
                                    <div className="co-ref-box-img-wrap">
                                        <img src={customUpload} alt="" className="co-ref-box-img" />
                                        <button className="co-ref-box-clear" onClick={(e) => { e.stopPropagation(); setCustomUpload(null); }}>
                                            <svg viewBox="0 0 24 24" width="10" height="10" fill="none" stroke="white" strokeWidth="3"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
                                        </button>
                                    </div>
                                ) : (
                                    <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="#8A93B0" strokeWidth="1.5">
                                        <rect x="3" y="3" width="18" height="18" rx="3"/>
                                        <path d="M12 8v8M8 12h8"/>
                                    </svg>
                                )}
                            </div>
                        </div>
                        <div className="co-mention-wrapper">
                            <textarea
                                ref={textareaRef} value={prompt}
                                onChange={handlePromptChange}
                                onKeyDown={handleKeyDown}
                                placeholder={placeholder}
                                disabled={barState === 'enhancing' || barState === 'generating'}
                                rows={1}
                                className="co-bar-input"
                            />
                            {mentionOpen && mentionShotPicker && (
                                <div className="co-mention-dropdown" ref={mentionListRef} style={mentionDropdownStyle}>
                                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '4px 6px 8px' }}>
                                        <button
                                            type="button"
                                            onMouseDown={(e) => { e.preventDefault(); setMentionShotPicker(null); }}
                                            style={{ border: '1px solid rgba(13,27,62,0.15)', background: 'white', borderRadius: 6, padding: '2px 8px', cursor: 'pointer', fontSize: 11 }}
                                        >
                                            {t('creativeOs.createBar.mentionBack')}
                                        </button>
                                        <span style={{ fontSize: 11, fontWeight: 600 }}>
                                            {t('creativeOs.createBar.mentionPickShot').replace('{name}', mentionShotPicker.name)}
                                        </span>
                                    </div>
                                    <div className="co-mention-grid">
                                        {mentionShotPicker.views.map((url, i) => (
                                            <div
                                                key={`${url}-${i}`}
                                                className="co-mention-card"
                                                onMouseDown={(e) => {
                                                    e.preventDefault();
                                                    const match = mentionItems.find(m => m.id === mentionShotPicker.id && m.type === mentionShotPicker.type);
                                                    if (match) finalizeMentionInsert(match, url);
                                                }}
                                                title={i === 0 ? t('creativeOs.mention.profileImage') : t('creativeOs.createBar.mentionShot').replace('{n}', String(i + 1))}
                                            >
                                                {/* eslint-disable-next-line @next/next/no-img-element */}
                                                <img src={url} alt="" className="co-mention-card-img" />
                                                <span className="co-mention-card-name">{i === 0 ? t('creativeOs.createBar.mentionProfile') : t('creativeOs.createBar.mentionShot').replace('{n}', String(i + 1))}</span>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            )}
                            {mentionOpen && !mentionShotPicker && filteredMentions.length > 0 && (() => {
                                const mentionModels = filteredMentions.filter(m => m.type === 'influencer');
                                const mentionProducts = filteredMentions.filter(m => m.type === 'product');
                                const ordered = [...mentionModels, ...mentionProducts];
                                return (
                                <div className="co-mention-dropdown" ref={mentionListRef} style={mentionDropdownStyle}>
                                    {mentionModels.length > 0 && (
                                        <>
                                            <div className="co-mention-header">{t('creativeOs.createBar.models')}</div>
                                            <div className="co-mention-grid">
                                                {mentionModels.map((item) => {
                                                    const idx = ordered.indexOf(item);
                                                    return (
                                                        <div
                                                            key={item.id}
                                                            className={`co-mention-card ${idx === mentionIndex ? 'active' : ''}`}
                                                            onMouseDown={(e) => { e.preventDefault(); insertMention(item); }}
                                                            onMouseEnter={() => setMentionIndex(idx)}
                                                        >
                                                            {item.image_url ? (
                                                                <img src={item.image_url} alt="" className="co-mention-card-img" />
                                                            ) : (
                                                                <div className="co-mention-card-img co-mention-card-empty" />
                                                            )}
                                                            <span className="co-mention-card-name">{item.name}</span>
                                                        </div>
                                                    );
                                                })}
                                            </div>
                                        </>
                                    )}
                                    {mentionProducts.length > 0 && (
                                        <>
                                            <div className="co-mention-header">{t('creativeOs.createBar.products')}</div>
                                            <div className="co-mention-grid">
                                                {mentionProducts.map((item) => {
                                                    const idx = ordered.indexOf(item);
                                                    return (
                                                        <div
                                                            key={item.id}
                                                            className={`co-mention-card ${idx === mentionIndex ? 'active' : ''}`}
                                                            onMouseDown={(e) => { e.preventDefault(); insertMention(item); }}
                                                            onMouseEnter={() => setMentionIndex(idx)}
                                                        >
                                                            {item.image_url ? (
                                                                <img src={item.image_url} alt="" className="co-mention-card-img" />
                                                            ) : (
                                                                <div className="co-mention-card-img co-mention-card-empty" />
                                                            )}
                                                            <span className="co-mention-card-name">{item.name}</span>
                                                        </div>
                                                    );
                                                })}
                                            </div>
                                        </>
                                    )}
                                </div>
                                );
                            })()}
                        </div>
                    </div>

                    {/* ── ROW 2: Mode + Settings + Action ── */}
                    <div className="co-bar-row2">
                        <div className="co-bar-settings">
                            {/* Mode */}
                            <Dropdown label={t('creativeOs.createBar.modeLabel').replace('{name}', currentMode.label)} id="mode" activeDropdown={activeDropdown} onToggle={toggleDropdown} variant="primary">
                                {modes.map(m => (
                                    <button key={m.id} className={`co-dd-item ${mode === m.id ? 'active' : ''}`} onClick={() => { setMode(m.id); setActiveDropdown(null); }}>
                                        {m.label}
                                    </button>
                                ))}
                            </Dropdown>

                            {/* Aspect Ratio */}
                            <Dropdown label={aspectRatio} id="ar" activeDropdown={activeDropdown} onToggle={toggleDropdown}>
                                {ASPECT_RATIOS.map(ar => (
                                    <button key={ar} className={`co-dd-item ${aspectRatio === ar ? 'active' : ''}`} onClick={() => { setAspectRatio(ar); setActiveDropdown(null); }}>
                                        {ar}
                                    </button>
                                ))}
                            </Dropdown>

                            {/* Quality (images only) */}
                            {activeTab === 'images' && (
                                <Dropdown label={quality} id="qual" activeDropdown={activeDropdown} onToggle={toggleDropdown}>
                                    {QUALITIES.map(q => (
                                        <button key={q} className={`co-dd-item ${quality === q ? 'active' : ''}`} onClick={() => { setQuality(q); setActiveDropdown(null); }}>
                                            {q}
                                        </button>
                                    ))}
                                </Dropdown>
                            )}

                            {/* Videos-only settings */}
                            {activeTab === 'videos' && (
                                <>
                                    <Dropdown label={language} id="lang" activeDropdown={activeDropdown} onToggle={toggleDropdown}>
                                        {LANGUAGES.map(l => (
                                            <button key={l} className={`co-dd-item ${language === l ? 'active' : ''}`} onClick={() => { setLanguage(l); setActiveDropdown(null); }}>
                                                {l}
                                            </button>
                                        ))}
                                    </Dropdown>

                                    {!fullVideo && !multiShot && (
                                        <Dropdown label={t('creativeOs.createBar.clipLabel').replace('{n}', String(clipLength))} id="clip" activeDropdown={activeDropdown} onToggle={toggleDropdown}>
                                            {(currentVideoMode?.clipLengths || [5]).map(cl => (
                                                <button key={cl} className={`co-dd-item ${clipLength === cl ? 'active' : ''}`} onClick={() => { setClipLength(cl); setActiveDropdown(null); }}>
                                                    {cl}s
                                                </button>
                                            ))}
                                        </Dropdown>
                                    )}

                                    {mode === 'cinematic_video' ? (
                                        <>
                                            <div className="co-toggle-inline">
                                                <ToggleSwitch checked={multiShot} onChange={(v) => { setMultiShot(v); if (v) setFullVideo(false); }} />
                                                <span className="co-toggle-label">{t('creativeOs.createBar.multiShot')}{multiShot ? <span className="co-toggle-badge">{t('creativeOs.createBar.on')}</span> : ''}</span>
                                            </div>
                                            {multiShot && (
                                                <div className="co-slider-inline">
                                                    <input
                                                        type="range"
                                                        min={3}
                                                        max={15}
                                                        step={1}
                                                        value={multiShotLength}
                                                        onChange={e => setMultiShotLength(Number(e.target.value))}
                                                        className="co-duration-slider"
                                                    />
                                                    <span className="co-slider-value">{multiShotLength}s</span>
                                                </div>
                                            )}
                                        </>
                                    ) : (
                                        <div className="co-toggle-inline">
                                            <ToggleSwitch checked={fullVideo} onChange={(v) => { setFullVideo(v); if (v) setMultiShot(false); }} />
                                            <span className="co-toggle-label">{t('creativeOs.createBar.multiShot')}{fullVideo ? <span className="co-toggle-badge">{t('creativeOs.createBar.on')}</span> : ''}</span>
                                        </div>
                                    )}

                                    {/* AI Script button */}
                                    <button
                                        onClick={handleGenerateScript}
                                        disabled={scriptLoading || barState !== 'idle'}
                                        className="co-ai-script-btn"
                                        title={t('creativeOs.createBar.aiScriptTitle')}
                                    >
                                        {scriptLoading ? t('creativeOs.createBar.writingBtn') : <><svg width="14" height="14" viewBox="40 40 300 300" fill="currentColor" style={{display:'inline',verticalAlign:'-2px'}}><path d="M67.27 185.02L52.28 189.16L67.27 193.29C124.52 209.07 169.24 253.79 185.02 311.04L189.15 326.03L193.29 311.04C209.07 253.79 253.79 209.07 311.04 193.29L326.03 189.16L311.04 185.02C253.79 169.24 209.07 124.52 193.29 67.27L189.15 52.28L185.02 67.27C169.24 124.52 124.52 169.24 67.27 185.02Z"/></svg> {t('creativeOs.createBar.aiScript')}</>}
                                    </button>
                                </>
                            )}
                        </div>

                        <button onClick={handleGenerate} disabled={!prompt.trim() || barState === 'enhancing' || barState === 'generating'} className="co-bar-generate">
                            {(barState === 'enhancing' || barState === 'generating') && <Spinner />}
                            {btnLabel}
                        </button>
                    </div>

                    {/* ── ROW 3: Full Video Settings ── */}
                    {activeTab === 'videos' && fullVideo && (
                        <div className="co-bar-row3">
                            <div className="co-bar-settings">
                                <span className="co-row3-label">{t('creativeOs.createBar.videoLength')}</span>
                                <Dropdown label={`${videoLength}s`} id="vl" activeDropdown={activeDropdown} onToggle={toggleDropdown}>
                                    {[15, 30].map(vl => (
                                        <button key={vl} className={`co-dd-item ${videoLength === vl ? 'active' : ''}`} onClick={() => { setVideoLength(vl); setActiveDropdown(null); }}>
                                            {vl}s
                                        </button>
                                    ))}
                                </Dropdown>
                                <div className="co-toggle-inline">
                                    <ToggleSwitch checked={bgMusic} onChange={setBgMusic} />
                                    <span className="co-toggle-label">{t('creativeOs.createBar.bgMusic')}</span>
                                </div>
                                <div className="co-toggle-inline">
                                    <ToggleSwitch checked={captions} onChange={setCaptions} />
                                    <span className="co-toggle-label">{t('creativeOs.createBar.captions')}</span>
                                </div>
                            </div>
                            <span className="co-cost-label">Est. cost: <strong>{estimatedCost} credits</strong></span>
                        </div>
                    )}

                </div>

                <style suppressHydrationWarning>{`
                    .co-bar-wrapper {
                        position: fixed; bottom: 16px; left: 50%; transform: translateX(-50%);
                        width: 94%; max-width: 900px; z-index: 1000;
                        animation: coSlideUp 0.4s cubic-bezier(0.16, 1, 0.3, 1);
                    }
                    .co-bar-card {
                        background: rgba(255,255,255,0.98); backdrop-filter: blur(24px);
                        border-radius: 20px; border: 1px solid rgba(51,122,255,0.08);
                        box-shadow: 0 8px 40px rgba(0,0,0,0.10), 0 0 0 1px rgba(51,122,255,0.04);
                        padding: 14px 16px 12px;
                    }
                    .co-bar-row1 { display: flex; align-items: center; gap: 10px; margin-bottom: 10px; }
                    .co-ref-group { display: flex; align-items: center; gap: 6px; flex-shrink: 0; }
                    .co-bar-input {
                        flex: 1; border: none; outline: none; background: transparent;
                        font-size: 14px; color: #0D1B3E; padding: 4px 0; min-width: 0;
                        resize: none; line-height: 1.5; font-family: inherit; max-height: 80px;
                    }
                    .co-bar-input::placeholder { color: #A0A8C4; }
                    .co-bar-row2 { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
                    .co-bar-row3 {
                        display: flex; align-items: center; justify-content: space-between; gap: 8px;
                        margin-top: 8px; padding-top: 8px; border-top: 1px solid rgba(51,122,255,0.06);
                    }
                    .co-bar-settings { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
                    .co-row3-label { font-size: 11px; font-weight: 700; color: #337AFF; letter-spacing: 0.5px; text-transform: uppercase; margin-right: 2px; }
                    .co-cost-label { font-size: 12px; color: #4A5578; white-space: nowrap; flex-shrink: 0; }
                    .co-cost-label strong { color: #337AFF; font-weight: 700; }

                    /* Multi-Shot Duration Slider */
                    .co-slider-inline {
                        display: flex; align-items: center; gap: 6px;
                        padding: 2px 8px 2px 4px; border-radius: 8px;
                        background: rgba(51,122,255,0.04); border: 1px solid rgba(51,122,255,0.12);
                    }
                    .co-duration-slider {
                        -webkit-appearance: none; appearance: none;
                        width: 80px; height: 4px; border-radius: 2px;
                        background: linear-gradient(90deg, #337AFF 0%, #A0A8C4 100%);
                        outline: none; cursor: pointer;
                    }
                    .co-duration-slider::-webkit-slider-thumb {
                        -webkit-appearance: none; appearance: none;
                        width: 14px; height: 14px; border-radius: 50%;
                        background: #337AFF; border: 2px solid white;
                        box-shadow: 0 1px 4px rgba(51,122,255,0.4);
                        cursor: pointer; transition: transform 0.1s;
                    }
                    .co-duration-slider::-webkit-slider-thumb:hover { transform: scale(1.2); }
                    .co-duration-slider::-moz-range-thumb {
                        width: 14px; height: 14px; border-radius: 50%;
                        background: #337AFF; border: 2px solid white;
                        box-shadow: 0 1px 4px rgba(51,122,255,0.4);
                        cursor: pointer;
                    }
                    .co-slider-value {
                        font-size: 12px; font-weight: 700; color: #337AFF;
                        min-width: 24px; text-align: center;
                    }

                    /* Generate Button */
                    .co-bar-generate {
                        padding: 10px 20px; border-radius: 24px; border: none;
                        background: linear-gradient(135deg, #5B7BFF, #337AFF);
                        color: white; font-size: 13px; font-weight: 700; cursor: pointer;
                        white-space: nowrap; display: flex; align-items: center; gap: 6px;
                        transition: all 0.2s; flex-shrink: 0;
                        box-shadow: 0 4px 14px rgba(51,122,255,0.35);
                    }
                    .co-bar-generate:hover { box-shadow: 0 6px 20px rgba(51,122,255,0.45); transform: translateY(-1px); }
                    .co-bar-generate:disabled { opacity: 0.5; cursor: not-allowed; transform: none; box-shadow: none; }

                    .co-ai-script-btn {
                        padding: 5px 12px; border-radius: 16px; border: 1.5px solid rgba(108,92,231,0.3);
                        background: rgba(108,92,231,0.08); color: #6C5CE7; font-size: 12px; font-weight: 600;
                        cursor: pointer; white-space: nowrap; transition: all 0.2s; flex-shrink: 0;
                    }
                    .co-ai-script-btn:hover { background: rgba(108,92,231,0.15); border-color: #6C5CE7; }
                    .co-ai-script-btn:disabled { opacity: 0.5; cursor: not-allowed; }

                    /* Ref Boxes — all same size */
                    .co-ref-box {
                        width: 38px; height: 38px; border-radius: 10px; overflow: hidden;
                        border: 1.5px dashed rgba(138,147,176,0.25); background: rgba(51,122,255,0.02);
                        cursor: pointer; display: flex; align-items: center; justify-content: center;
                        transition: all 0.15s; padding: 0; position: relative; flex-shrink: 0;
                    }
                    .co-ref-box:hover { border-color: #337AFF; background: rgba(51,122,255,0.06); }
                    .co-ref-box.filled { border: 2px solid rgba(51,122,255,0.25); }
                    .co-ref-box-img-wrap { width: 100%; height: 100%; position: relative; }
                    .co-ref-box-img { width: 100%; height: 100%; object-fit: cover; display: block; }
                    .co-ref-box-clear {
                        position: absolute; top: -4px; right: -4px;
                        width: 16px; height: 16px; border-radius: 50%;
                        background: rgba(0,0,0,0.6); border: none; cursor: pointer;
                        display: flex; align-items: center; justify-content: center;
                        opacity: 0; transition: opacity 0.15s;
                    }
                    .co-ref-box:hover .co-ref-box-clear { opacity: 1; }

                    /* Dropdown */
                    .co-dd { position: relative; user-select: none; }
                    .co-dd-trigger {
                        padding: 5px 10px; border-radius: 8px; border: 1px solid rgba(51,122,255,0.12);
                        background: rgba(51,122,255,0.04); color: #4A5578; font-size: 12px;
                        font-weight: 500; cursor: pointer; white-space: nowrap;
                        display: flex; align-items: center; gap: 4px; transition: all 0.15s;
                    }
                    .co-dd-trigger.primary {
                        background: rgba(51,122,255,0.08); color: #337AFF; font-weight: 600;
                        border-color: rgba(51,122,255,0.18);
                    }
                    .co-dd-trigger:hover { border-color: rgba(51,122,255,0.3); }
                    .co-dd-menu {
                        position: absolute; bottom: calc(100% + 4px); left: 0;
                        min-width: max-content;
                        border-radius: 10px; background: white; border: 1px solid rgba(51,122,255,0.10);
                        box-shadow: 0 8px 24px rgba(0,0,0,0.12); overflow: hidden; z-index: 1001;
                        animation: coFadeIn 0.12s ease;
                    }
                    .co-dd-item {
                        display: block; width: 100%; padding: 8px 14px; border: none;
                        background: transparent; cursor: pointer; text-align: left;
                        font-size: 12px; color: #4A5578; transition: background 0.1s;
                        white-space: nowrap;
                    }
                    .co-dd-item:hover { background: rgba(51,122,255,0.06); }
                    .co-dd-item.active { color: #337AFF; font-weight: 600; background: rgba(51,122,255,0.06); }

                    /* Toggle */
                    .co-toggle-inline { display: flex; align-items: center; gap: 6px; }
                    .co-toggle-label { font-size: 12px; color: #4A5578; font-weight: 500; white-space: nowrap; }
                    .co-toggle-badge {
                        display: inline-block; margin-left: 4px; padding: 1px 6px;
                        border-radius: 4px; background: rgba(51,122,255,0.1); color: #337AFF;
                        font-size: 10px; font-weight: 700; letter-spacing: 0.3px;
                    }
                    .co-toggle-track {
                        width: 32px; height: 18px; border-radius: 9px; position: relative;
                        cursor: pointer; transition: background 0.2s; flex-shrink: 0;
                    }
                    .co-toggle-track.on { background: linear-gradient(135deg, #5B7BFF, #337AFF); }
                    .co-toggle-track.off { background: rgba(138,147,176,0.25); }
                    .co-toggle-knob {
                        width: 14px; height: 14px; border-radius: 50%; background: white;
                        position: absolute; top: 2px; transition: left 0.2s;
                        box-shadow: 0 1px 3px rgba(0,0,0,0.15);
                    }

                    /* Options Overlay */
                    .co-options-overlay {
                        position: fixed; bottom: 140px; left: 50%; transform: translateX(-50%);
                        width: 92%; max-width: 900px; z-index: 999; display: flex; gap: 10px;
                        animation: coSlideUp 0.3s cubic-bezier(0.16, 1, 0.3, 1);
                    }
                    .co-option-card {
                        flex: 1; padding: 14px; border-radius: 14px;
                        border: 1px solid rgba(51,122,255,0.10); background: rgba(255,255,255,0.97);
                        backdrop-filter: blur(20px); cursor: pointer; text-align: left;
                        transition: all 0.2s; box-shadow: 0 4px 20px rgba(0,0,0,0.06);
                    }
                    .co-option-card:hover { border-color: rgba(51,122,255,0.35); box-shadow: 0 4px 24px rgba(51,122,255,0.15); }
                    .co-option-title { font-size: 11px; font-weight: 700; color: #337AFF; margin-bottom: 4px; text-transform: uppercase; letter-spacing: 0.3px; }
                    .co-option-text { font-size: 12px; color: #4A5578; line-height: 1.5; display: -webkit-box; -webkit-line-clamp: 4; -webkit-box-orient: vertical; overflow: hidden; }
                    .co-options-close {
                        position: absolute; top: -8px; right: -8px; width: 24px; height: 24px;
                        border-radius: 50%; border: 1px solid rgba(0,0,0,0.08); background: white;
                        cursor: pointer; font-size: 12px; color: #666; display: flex;
                        align-items: center; justify-content: center; box-shadow: 0 2px 8px rgba(0,0,0,0.08);
                    }

                    /* Messages */
                    .co-bar-error { margin-bottom: 6px; padding: 7px 14px; border-radius: 10px; background: rgba(239,68,68,0.06); border: 1px solid rgba(239,68,68,0.10); color: #EF4444; font-size: 12px; text-align: center; }
                    .co-bar-success { margin-bottom: 6px; padding: 7px 14px; border-radius: 10px; background: rgba(34,197,94,0.06); border: 1px solid rgba(34,197,94,0.10); color: #22C55E; font-size: 12px; font-weight: 600; text-align: center; }

                    /* @Mention dropdown — grid/mosaic */
                    .co-mention-wrapper { position: relative; flex: 1; min-width: 0; display: flex; align-items: center; }
                    .co-mention-wrapper .co-bar-input { width: 100%; }
                    .co-mention-dropdown {
                        position: absolute; bottom: calc(100% + 6px); left: 0; right: 0;
                        max-height: 340px; overflow-y: auto;
                        background: rgba(255,255,255,0.99); backdrop-filter: blur(20px);
                        border-radius: 14px; border: 1px solid rgba(51,122,255,0.12);
                        box-shadow: 0 8px 32px rgba(0,0,0,0.12), 0 0 0 1px rgba(51,122,255,0.04);
                        z-index: 1100; animation: coFadeIn 0.12s ease;
                        padding: 4px 4px 2px;
                    }
                    .co-mention-header {
                        padding: 4px 6px 2px; font-size: 9px; font-weight: 700;
                        color: #8A93B0; text-transform: uppercase; letter-spacing: 0.5px;
                    }
                    .co-mention-grid {
                        display: flex; flex-wrap: nowrap;
                        gap: 2px; padding: 2px 0 4px;
                        overflow-x: auto; overflow-y: hidden;
                        scrollbar-width: none; -ms-overflow-style: none;
                    }
                    .co-mention-grid::-webkit-scrollbar { display: none; }
                    .co-mention-card {
                        display: flex; flex-direction: column; align-items: center;
                        padding: 3px 2px; border-radius: 8px; cursor: pointer;
                        transition: all 0.12s; border: 1.5px solid transparent;
                        flex-shrink: 0;
                    }
                    .co-mention-card:hover, .co-mention-card.active {
                        background: rgba(51,122,255,0.06);
                        border-color: rgba(51,122,255,0.25);
                    }
                    .co-mention-card-img {
                        width: 56px; height: 56px; border-radius: 8px; object-fit: cover;
                        border: 1px solid rgba(51,122,255,0.08); margin-bottom: 2px;
                    }
                    .co-mention-card-empty {
                        background: linear-gradient(135deg, rgba(91,123,255,0.08), rgba(168,123,255,0.08));
                    }
                    .co-mention-card-name {
                        font-size: 9px; font-weight: 600; color: #0D1B3E;
                        max-width: 64px; overflow: hidden; text-overflow: ellipsis;
                        white-space: nowrap; text-align: center; line-height: 1.2;
                    }

                    @keyframes coSlideUp { from { opacity: 0; transform: translateX(-50%) translateY(12px); } to { opacity: 1; transform: translateX(-50%) translateY(0); } }
                    @keyframes coFadeIn { from { opacity: 0; transform: translateY(3px); } to { opacity: 1; transform: translateY(0); } }
                    @keyframes coSpin { to { transform: rotate(360deg); } }
                `}</style>
            </div>
        </>
    );
}

// ── Sub-components ──────────────────────────────────────────────────

function RefSlot({ item, type, onClick, onClear }: { item: any; type: 'product' | 'model' | 'image'; onClick: () => void; onClear: () => void }) {
    const hasImage = item && item.image_url;

    // Product icon — box/package
    const ProductIcon = () => (
        <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="#5B7BFF" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/>
            <polyline points="3.27 6.96 12 12.01 20.73 6.96"/>
            <line x1="12" y1="22.08" x2="12" y2="12"/>
        </svg>
    );

    // Model icon — person
    const ModelIcon = () => (
        <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="#A87BFF" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
            <circle cx="12" cy="7" r="4"/>
        </svg>
    );

    // Image icon — landscape photo
    const ImageIcon = () => (
        <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="#3BAFDA" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
            <rect x="3" y="3" width="18" height="18" rx="2" ry="2"/>
            <circle cx="8.5" cy="8.5" r="1.5"/>
            <polyline points="21 15 16 10 5 21"/>
        </svg>
    );

    return (
        <div className={`co-ref-box ${hasImage ? 'filled' : ''}`} onClick={hasImage ? undefined : onClick}>
            {hasImage ? (
                <div className="co-ref-box-img-wrap">
                    <img src={item.image_url} alt="" className="co-ref-box-img" />
                    <div className="co-ref-box-clear" role="button" onClick={(e) => { e.stopPropagation(); onClear(); }}>
                        <svg viewBox="0 0 24 24" width="10" height="10" fill="none" stroke="white" strokeWidth="3"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
                    </div>
                </div>
            ) : (
                type === 'product' ? <ProductIcon /> : type === 'model' ? <ModelIcon /> : <ImageIcon />
            )}
        </div>
    );
}

function Dropdown({ label, id, activeDropdown, onToggle, children, variant }: {
    label: string; id: string; activeDropdown: string | null; onToggle: (id: string) => void; children: React.ReactNode; variant?: string;
}) {
    const isOpen = activeDropdown === id;
    return (
        <div className="co-dd">
            <button className={`co-dd-trigger ${variant === 'primary' ? 'primary' : ''}`} onClick={() => onToggle(id)}>
                {label}
                <svg viewBox="0 0 24 24" width="10" height="10" fill="none" stroke="currentColor" strokeWidth="2.5" style={{ transition: 'transform 0.15s', transform: isOpen ? 'rotate(180deg)' : 'none' }}>
                    <polyline points="6 9 12 15 18 9"/>
                </svg>
            </button>
            {isOpen && <div className="co-dd-menu">{children}</div>}
        </div>
    );
}

function ToggleSwitch({ checked, onChange }: { checked: boolean; onChange: (v: boolean) => void }) {
    return (
        <div className={`co-toggle-track ${checked ? 'on' : 'off'}`} onClick={() => onChange(!checked)}>
            <div className="co-toggle-knob" style={{ left: checked ? '16px' : '2px' }} />
        </div>
    );
}

function PickerModal({ title, items, onSelect, onClose, onLoad }: {
    title: string; items: any[]; onSelect: (item: any) => void; onClose: () => void; onLoad: () => void;
}) {
    const { t } = useTranslation();
    const [search, setSearch] = useState('');
    useEffect(() => { onLoad(); }, [onLoad]);
    const isImagePicker = title === t('creativeOs.createBar.selectImage');
    const isModelPicker = title === t('creativeOs.createBar.selectModel');

    const filtered = search.trim()
        ? items.filter(item => {
            const name = (item.name || item.product_name || '').toLowerCase();
            return name.includes(search.trim().toLowerCase());
          })
        : items;

    return (
        <div style={{ position: 'fixed', inset: 0, zIndex: 2000, display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'rgba(0,0,0,0.35)', backdropFilter: 'blur(6px)' }} onClick={onClose}>
            <div onClick={e => e.stopPropagation()} style={{
                width: '92%',
                maxWidth: isImagePicker ? '600px' : '720px',
                maxHeight: '80vh',
                borderRadius: '20px',
                background: 'white',
                boxShadow: '0 24px 64px rgba(0,0,0,0.18)',
                overflow: 'hidden',
                display: 'flex',
                flexDirection: 'column',
                animation: 'coFadeIn 0.2s ease',
            }}>
                {/* Header */}
                <div style={{
                    padding: '18px 24px',
                    borderBottom: '1px solid rgba(51,122,255,0.08)',
                    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                }}>
                    <h3 style={{ margin: 0, fontSize: '18px', fontWeight: 700, color: '#0D1B3E', letterSpacing: '-0.3px' }}>{title}</h3>
                    <button onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: '20px', color: '#8A93B0', lineHeight: 1 }}>✕</button>
                </div>

                {/* Search */}
                {!isImagePicker && items.length > 6 && (
                    <div style={{ padding: '12px 24px 4px' }}>
                        <input
                            type="text"
                            placeholder={isModelPicker ? t('creativeOs.createBar.searchModels') : t('creativeOs.createBar.searchProducts')}
                            value={search}
                            onChange={e => setSearch(e.target.value)}
                            style={{
                                width: '100%', padding: '10px 14px',
                                borderRadius: '10px', border: '1px solid rgba(51,122,255,0.15)',
                                background: 'rgba(51,122,255,0.03)', fontSize: '13px',
                                outline: 'none', color: '#0D1B3E', fontFamily: 'inherit',
                                transition: 'border-color 0.2s',
                            }}
                            onFocus={e => e.currentTarget.style.borderColor = 'rgba(51,122,255,0.4)'}
                            onBlur={e => e.currentTarget.style.borderColor = 'rgba(51,122,255,0.15)'}
                        />
                    </div>
                )}

                {/* Grid */}
                <div style={{ padding: '16px 20px', overflowY: 'auto', flex: 1 }}>
                    {filtered.length === 0
                        ? <div style={{ textAlign: 'center', padding: '48px 20px', color: '#8A93B0', fontSize: '14px' }}>
                            {items.length === 0
                                ? (isImagePicker ? t('creativeOs.createBar.noImages') : t('creativeOs.createBar.loading'))
                                : t('creativeOs.createBar.noResults')}
                          </div>
                        : <div style={{
                            display: 'grid',
                            gridTemplateColumns: isImagePicker
                                ? 'repeat(auto-fill, minmax(100px, 1fr))'
                                : 'repeat(3, 1fr)',
                            gap: '12px',
                          }}>
                            {filtered.map((item, i) => {
                                const displayName = item.name || item.product_name || item.shot_type || `Image ${i + 1}`;
                                return (
                                    <button key={item.id || i} onClick={() => onSelect(item)} style={{
                                        padding: '0', borderRadius: '14px',
                                        border: '2px solid transparent',
                                        background: 'rgba(51,122,255,0.03)',
                                        cursor: 'pointer', textAlign: 'center',
                                        transition: 'all 0.18s ease',
                                        overflow: 'hidden',
                                        display: 'flex', flexDirection: 'column',
                                    }}
                                    onMouseEnter={e => {
                                        e.currentTarget.style.borderColor = 'rgba(51,122,255,0.5)';
                                        e.currentTarget.style.boxShadow = '0 4px 16px rgba(51,122,255,0.15)';
                                        e.currentTarget.style.transform = 'translateY(-2px)';
                                    }}
                                    onMouseLeave={e => {
                                        e.currentTarget.style.borderColor = 'transparent';
                                        e.currentTarget.style.boxShadow = 'none';
                                        e.currentTarget.style.transform = 'none';
                                    }}
                                    >
                                        {item.image_url
                                            ? <img src={item.image_url} alt="" loading="lazy" style={{
                                                width: '100%',
                                                aspectRatio: isImagePicker ? '9/16' : (isModelPicker ? '3/4' : '1'),
                                                objectFit: 'cover', display: 'block',
                                              }} />
                                            : <div style={{
                                                width: '100%',
                                                aspectRatio: isImagePicker ? '9/16' : (isModelPicker ? '3/4' : '1'),
                                                background: 'linear-gradient(135deg, rgba(91,123,255,0.08), rgba(168,123,255,0.08))',
                                              }} />}
                                        <div style={{
                                            padding: '8px 6px 10px',
                                            fontSize: '12px', fontWeight: 600, color: '#0D1B3E',
                                            overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                                        }}>{displayName}</div>
                                    </button>
                                );
                            })}
                        </div>
                    }
                </div>
            </div>
        </div>
    );
}

function Spinner() {
    return <div style={{ width: '14px', height: '14px', border: '2px solid rgba(255,255,255,0.3)', borderTopColor: 'white', borderRadius: '50%', animation: 'coSpin 0.6s linear infinite' }} />;
}
