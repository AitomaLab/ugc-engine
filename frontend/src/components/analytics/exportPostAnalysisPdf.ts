import { jsPDF } from 'jspdf';
import type { AnalyticsBreakdown, AnalyticsPost } from './analytics-types';
import { formatCount, resolvePostPosterUrl } from './analytics-types';

const PAGE_W = 210;
const PAGE_H = 297;
const MARGIN = 16;
const CONTENT_W = PAGE_W - MARGIN * 2;

const NAVY: [number, number, number] = [13, 27, 62];
const BLUE: [number, number, number] = [51, 122, 255];
const TEXT1: [number, number, number] = [13, 27, 62];
const TEXT2: [number, number, number] = [90, 100, 120];
const TEXT3: [number, number, number] = [140, 148, 165];
const BORDER: [number, number, number] = [232, 236, 244];
const BLUE_LIGHT: [number, number, number] = [240, 246, 255];

const PLATFORM_RGB: Record<string, [number, number, number]> = {
    instagram: [225, 48, 108],
    tiktok: [0, 0, 0],
    youtube: [255, 0, 0],
    facebook: [24, 119, 242],
};

export interface PostAnalysisPdfLabels {
    reportTitle: string;
    metrics: string;
    views: string;
    likes: string;
    comments: string;
    shares: string;
    engagement: string;
    duration: string;
    hidden: string;
    measuring: string;
    caption: string;
    aiBreakdown: string;
    hook: string;
    scenes: string;
    audio: string;
    visualDetails: string;
    keyMoments: string;
    takeaways: string;
    summary: string;
    onScreen: string;
    whyItWorks: string;
    noAudio: string;
    analysisPending: string;
    analysisRunning: string;
    analysisFailed: string;
    analysisNone: string;
    generatedOn: string;
    postUrl: string;
    posted: string;
    exporting: string;
}

export interface ExportPostAnalysisPdfInput {
    post: AnalyticsPost;
    breakdown: AnalyticsBreakdown | null;
    derivedDuration?: number;
    labels: PostAnalysisPdfLabels;
}

function formatPostedAt(iso: string | null | undefined): string {
    if (!iso) return '—';
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return '—';
    return d.toLocaleDateString(undefined, {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
    });
}

async function loadImageDataUrl(url: string): Promise<string | null> {
    try {
        const res = await fetch(url, { mode: 'cors' });
        if (!res.ok) return null;
        const blob = await res.blob();
        return await new Promise((resolve) => {
            const reader = new FileReader();
            reader.onloadend = () => resolve(typeof reader.result === 'string' ? reader.result : null);
            reader.onerror = () => resolve(null);
            reader.readAsDataURL(blob);
        });
    } catch {
        return null;
    }
}

function safeFilename(username: string, platform: string): string {
    const base = `${platform}-${username}`.replace(/[^a-zA-Z0-9._-]+/g, '-').slice(0, 80);
    const date = new Date().toISOString().slice(0, 10);
    return `post-analysis-${base}-${date}.pdf`;
}

class PdfBuilder {
    doc: jsPDF;
    y: number;
    labels: PostAnalysisPdfLabels;

    constructor(labels: PostAnalysisPdfLabels) {
        this.doc = new jsPDF({ unit: 'mm', format: 'a4' });
        this.y = MARGIN;
        this.labels = labels;
    }

    ensureSpace(needed: number) {
        if (this.y + needed > PAGE_H - MARGIN) {
            this.doc.addPage();
            this.y = MARGIN;
        }
    }

    sectionTitle(text: string) {
        this.ensureSpace(12);
        this.doc.setFont('helvetica', 'bold');
        this.doc.setFontSize(8);
        this.doc.setTextColor(...TEXT3);
        this.doc.text(text.toUpperCase(), MARGIN, this.y);
        this.y += 6;
    }

    bodyText(text: string, opts?: { bold?: boolean; color?: [number, number, number]; size?: number }) {
        const size = opts?.size ?? 10;
        const color = opts?.color ?? TEXT1;
        this.doc.setFont('helvetica', opts?.bold ? 'bold' : 'normal');
        this.doc.setFontSize(size);
        this.doc.setTextColor(...color);
        const lines = this.doc.splitTextToSize(text, CONTENT_W);
        const lineH = size * 0.42;
        for (const line of lines) {
            this.ensureSpace(lineH + 1);
            this.doc.text(line, MARGIN, this.y);
            this.y += lineH;
        }
        this.y += 2;
    }

    drawHeader(post: AnalyticsPost) {
        const platform = (post.platform || '').toLowerCase();
        const platformRgb = PLATFORM_RGB[platform] ?? TEXT2;

        this.doc.setFillColor(...NAVY);
        this.doc.rect(0, 0, PAGE_W, 28, 'F');

        this.doc.setFont('helvetica', 'bold');
        this.doc.setFontSize(14);
        this.doc.setTextColor(255, 255, 255);
        this.doc.text(this.labels.reportTitle, MARGIN, 12);

        this.doc.setFont('helvetica', 'normal');
        this.doc.setFontSize(9);
        this.doc.setTextColor(200, 210, 230);
        const generated = new Date().toLocaleString(undefined, {
            dateStyle: 'medium',
            timeStyle: 'short',
        });
        this.doc.text(`${this.labels.generatedOn}: ${generated}`, MARGIN, 20);

        this.y = 36;

        // Platform pill + username
        this.doc.setFillColor(...platformRgb);
        const pillW = 28;
        this.doc.roundedRect(MARGIN, this.y - 4, pillW, 7, 2, 2, 'F');
        this.doc.setFont('helvetica', 'bold');
        this.doc.setFontSize(7);
        this.doc.setTextColor(255, 255, 255);
        this.doc.text((post.platform || '—').toUpperCase(), MARGIN + 3, this.y);

        this.doc.setFont('helvetica', 'bold');
        this.doc.setFontSize(13);
        this.doc.setTextColor(...TEXT1);
        this.doc.text(`@${post.username || '—'}`, MARGIN + pillW + 6, this.y);

        this.doc.setFont('helvetica', 'normal');
        this.doc.setFontSize(9);
        this.doc.setTextColor(...TEXT3);
        const posted = formatPostedAt(post.posted_at || post.scraped_at);
        this.doc.text(`${this.labels.posted}: ${posted}`, PAGE_W - MARGIN, this.y, { align: 'right' });
        this.y += 10;

        if (post.post_url) {
            this.doc.setFontSize(8);
            this.doc.setTextColor(...BLUE);
            const urlLines = this.doc.splitTextToSize(`${this.labels.postUrl}: ${post.post_url}`, CONTENT_W);
            for (const line of urlLines) {
                this.ensureSpace(5);
                this.doc.text(line, MARGIN, this.y);
                this.y += 4;
            }
            this.y += 4;
        }
    }

    async drawThumbnail(post: AnalyticsPost) {
        const thumb = resolvePostPosterUrl(post);
        if (!thumb) return;

        const dataUrl = await loadImageDataUrl(thumb);
        const maxW = 72;
        const maxH = 96;
        let imgW = maxW;
        let imgH = maxH;

        if (dataUrl) {
            try {
                const dims = await new Promise<{ w: number; h: number }>((resolve, reject) => {
                    const img = new Image();
                    img.onload = () => resolve({ w: img.naturalWidth, h: img.naturalHeight });
                    img.onerror = reject;
                    img.src = dataUrl;
                });
                const ratio = dims.w / dims.h;
                if (ratio > maxW / maxH) {
                    imgH = maxW / ratio;
                } else {
                    imgW = maxH * ratio;
                }
                this.ensureSpace(imgH + 8);
                const x = (PAGE_W - imgW) / 2;
                this.doc.setDrawColor(...BORDER);
                this.doc.setLineWidth(0.3);
                this.doc.roundedRect(x - 1, this.y - 1, imgW + 2, imgH + 2, 3, 3, 'S');
                const fmt = dataUrl.startsWith('data:image/png') ? 'PNG' : 'JPEG';
                this.doc.addImage(dataUrl, fmt, x, this.y, imgW, imgH);
                this.y += imgH + 10;
                return;
            } catch {
                /* fall through to placeholder */
            }
        }

        this.ensureSpace(maxH + 8);
        const x = (PAGE_W - maxW) / 2;
        this.doc.setFillColor(...BLUE_LIGHT);
        this.doc.setDrawColor(...BORDER);
        this.doc.roundedRect(x, this.y, maxW, maxH, 3, 3, 'FD');
        this.doc.setFont('helvetica', 'normal');
        this.doc.setFontSize(9);
        this.doc.setTextColor(...TEXT3);
        this.doc.text('Preview unavailable', PAGE_W / 2, this.y + maxH / 2, { align: 'center' });
        this.y += maxH + 10;
    }

    drawMetrics(
        post: AnalyticsPost,
        labels: PostAnalysisPdfLabels,
        derivedDuration?: number,
    ) {
        const platformLc = (post.platform || '').toLowerCase();
        const sharesHidden =
            post.shares == null && (platformLc === 'instagram' || platformLc === 'youtube');
        const sharesValue = sharesHidden ? labels.hidden : formatCount(post.shares);

        const isStatic = post.media_type === 'image' || post.media_type === 'carousel';
        const effectiveDuration = post.duration_seconds ?? derivedDuration;
        const durationValue = effectiveDuration
            ? `${Math.round(effectiveDuration)}s`
            : labels.measuring;

        const items: { label: string; value: string; accent?: boolean }[] = [
            { label: labels.views, value: formatCount(post.views) },
            { label: labels.likes, value: formatCount(post.likes) },
            { label: labels.comments, value: formatCount(post.comments) },
            { label: labels.shares, value: sharesValue },
            { label: labels.engagement, value: formatCount(post.total_engagement), accent: true },
        ];
        if (!isStatic) {
            items.push({ label: labels.duration, value: durationValue });
        }

        this.sectionTitle(labels.metrics);

        const cols = 3;
        const gap = 4;
        const cellW = (CONTENT_W - gap * (cols - 1)) / cols;
        const cellH = 18;
        const rows = Math.ceil(items.length / cols);

        this.ensureSpace(rows * (cellH + gap) + 4);

        items.forEach((item, i) => {
            const col = i % cols;
            const row = Math.floor(i / cols);
            const x = MARGIN + col * (cellW + gap);
            const y = this.y + row * (cellH + gap);

            this.doc.setFillColor(255, 255, 255);
            this.doc.setDrawColor(...BORDER);
            this.doc.roundedRect(x, y, cellW, cellH, 2, 2, 'FD');

            this.doc.setFont('helvetica', 'bold');
            this.doc.setFontSize(12);
            if (item.accent) this.doc.setTextColor(...BLUE);
            else this.doc.setTextColor(...TEXT1);
            this.doc.text(item.value, x + 4, y + 9);

            this.doc.setFont('helvetica', 'normal');
            this.doc.setFontSize(7);
            this.doc.setTextColor(...TEXT3);
            this.doc.text(item.label.toUpperCase(), x + 4, y + 14);
        });

        this.y += rows * (cellH + gap) + 8;
    }

    drawCaption(caption: string) {
        this.sectionTitle(this.labels.caption);
        this.ensureSpace(16);
        const pad = 4;
        this.doc.setFont('helvetica', 'normal');
        this.doc.setFontSize(9);
        const lines = this.doc.splitTextToSize(caption, CONTENT_W - pad * 2);
        const boxH = lines.length * 4.2 + pad * 2 + 4;
        this.ensureSpace(boxH);
        this.doc.setFillColor(...BLUE_LIGHT);
        this.doc.setDrawColor(...BORDER);
        this.doc.roundedRect(MARGIN, this.y, CONTENT_W, boxH, 2, 2, 'FD');
        this.doc.setTextColor(...TEXT2);
        let ty = this.y + pad + 4;
        for (const line of lines) {
            this.doc.text(line, MARGIN + pad, ty);
            ty += 4.2;
        }
        this.y += boxH + 8;
    }

    drawBreakdownStatus(message: string, tint: 'neutral' | 'warn' | 'error' = 'neutral') {
        const bg: [number, number, number] =
            tint === 'warn' ? [255, 248, 235] : tint === 'error' ? [255, 242, 242] : BLUE_LIGHT;
        const border: [number, number, number] =
            tint === 'warn' ? [255, 200, 120] : tint === 'error' ? [255, 180, 180] : BORDER;

        this.doc.setFont('helvetica', 'normal');
        this.doc.setFontSize(9);
        const lines = this.doc.splitTextToSize(message, CONTENT_W - 8);
        const boxH = lines.length * 4.2 + 12;
        this.ensureSpace(boxH);
        this.doc.setFillColor(...bg);
        this.doc.setDrawColor(...border);
        this.doc.roundedRect(MARGIN, this.y, CONTENT_W, boxH, 2, 2, 'FD');
        this.doc.setTextColor(...TEXT2);
        let ty = this.y + 8;
        for (const line of lines) {
            this.doc.text(line, MARGIN + 4, ty);
            ty += 4.2;
        }
        this.y += boxH + 8;
    }

    drawHookBox(breakdown: AnalyticsBreakdown) {
        const hook = breakdown.hook;
        if (!hook) return;

        this.ensureSpace(20);
        this.doc.setFillColor(240, 246, 255);
        this.doc.setDrawColor(51, 122, 255);
        this.doc.setLineWidth(0.4);

        const parts: string[] = [];
        if (hook.timestamp) parts.push(hook.timestamp);
        if (hook.on_screen_text) parts.push(`"${hook.on_screen_text}"`);
        if (hook.visual) parts.push(hook.visual);
        if (hook.why_it_works) parts.push(`${this.labels.whyItWorks}: ${hook.why_it_works}`);

        this.doc.setFont('helvetica', 'normal');
        this.doc.setFontSize(9);
        const innerW = CONTENT_W - 10;
        let totalLines = 1;
        for (const p of parts) {
            totalLines += this.doc.splitTextToSize(p, innerW).length;
        }
        const boxH = totalLines * 4.5 + 14;
        this.ensureSpace(boxH);
        this.doc.roundedRect(MARGIN, this.y, CONTENT_W, boxH, 2, 2, 'FD');

        let ty = this.y + 8;
        this.doc.setFont('helvetica', 'bold');
        this.doc.setFontSize(8);
        this.doc.setTextColor(...BLUE);
        this.doc.text(this.labels.hook.toUpperCase(), MARGIN + 5, ty);
        ty += 6;

        this.doc.setFont('helvetica', 'normal');
        this.doc.setFontSize(9);
        this.doc.setTextColor(...TEXT1);
        for (const p of parts) {
            const lines = this.doc.splitTextToSize(p, innerW);
            for (const line of lines) {
                this.doc.text(line, MARGIN + 5, ty);
                ty += 4.5;
            }
        }
        this.y += boxH + 6;
    }

    drawListSection(title: string, items: string[]) {
        if (!items.length) return;
        this.sectionTitle(title);
        for (let i = 0; i < items.length; i++) {
            this.bodyText(`${i + 1}. ${items[i]}`, { size: 9 });
        }
        this.y += 2;
    }

    drawTimestampedRows(
        title: string,
        rows: Array<{ ts?: string; primary: string; secondary?: string }>,
    ) {
        if (!rows.length) return;
        this.sectionTitle(title);
        for (const row of rows) {
            const ts = row.ts ? `[${row.ts}] ` : '';
            const main = `${ts}${row.primary}`;
            this.bodyText(main, { size: 9 });
            if (row.secondary) {
                this.bodyText(`"${row.secondary}"`, { size: 8, color: TEXT3 });
            }
        }
        this.y += 2;
    }

    drawCompletedBreakdown(breakdown: AnalyticsBreakdown) {
        if (breakdown.summary) {
            this.sectionTitle(this.labels.summary);
            this.bodyText(breakdown.summary);
        }

        this.drawHookBox(breakdown);

        if (breakdown.scenes?.length) {
            this.drawTimestampedRows(
                `${this.labels.scenes} (${breakdown.scenes.length})`,
                breakdown.scenes.map((s) => ({
                    ts: s.start,
                    primary: s.description || '—',
                    secondary: s.on_screen_text,
                })),
            );
        }

        if (breakdown.audio) {
            if (breakdown.audio.has_audio && breakdown.audio.transcript?.length) {
                this.drawTimestampedRows(
                    this.labels.audio,
                    breakdown.audio.transcript.map((line) => ({
                        ts: line.ts,
                        primary: line.text || '',
                    })),
                );
            } else {
                this.sectionTitle(this.labels.audio);
                this.bodyText(breakdown.audio.notes || this.labels.noAudio, { color: TEXT3, size: 9 });
            }
        }

        if (breakdown.visual_details?.length) {
            this.drawListSection(this.labels.visualDetails, breakdown.visual_details);
        }

        if (breakdown.key_moments?.length) {
            this.drawTimestampedRows(
                this.labels.keyMoments,
                breakdown.key_moments.map((m) => ({
                    ts: m.ts,
                    primary: m.description || '',
                })),
            );
        }

        if (breakdown.takeaways?.length) {
            this.sectionTitle(this.labels.takeaways);
            breakdown.takeaways.forEach((line, i) => {
                this.bodyText(`${i + 1}. ${line}`, { size: 9 });
            });
        }
    }

    save(post: AnalyticsPost) {
        this.doc.save(safeFilename(post.username || 'post', post.platform || 'social'));
    }
}

export async function exportPostAnalysisPdf(input: ExportPostAnalysisPdfInput): Promise<void> {
    const { post, breakdown, derivedDuration, labels } = input;
    const pdf = new PdfBuilder(labels);

    pdf.drawHeader(post);
    await pdf.drawThumbnail(post);
    pdf.drawMetrics(post, labels, derivedDuration);

    if (post.caption) {
        pdf.drawCaption(post.caption);
    }

    pdf.sectionTitle(labels.aiBreakdown);

    const status = breakdown?.status;
    if (!breakdown) {
        pdf.drawBreakdownStatus(labels.analysisNone);
    } else if (status === 'pending' || status === 'running') {
        pdf.drawBreakdownStatus(labels.analysisRunning, 'warn');
    } else if (status === 'failed') {
        pdf.drawBreakdownStatus(
            breakdown.error_message || labels.analysisFailed,
            'error',
        );
    } else if (status === 'completed') {
        pdf.drawCompletedBreakdown(breakdown);
    } else {
        pdf.drawBreakdownStatus(labels.analysisPending);
    }

    // Footer on last page
    const pageCount = pdf.doc.getNumberOfPages();
    for (let p = 1; p <= pageCount; p++) {
        pdf.doc.setPage(p);
        pdf.doc.setFont('helvetica', 'normal');
        pdf.doc.setFontSize(7);
        pdf.doc.setTextColor(...TEXT3);
        pdf.doc.text(
            `Aitoma Studio · ${labels.reportTitle} · Page ${p} of ${pageCount}`,
            PAGE_W / 2,
            PAGE_H - 8,
            { align: 'center' },
        );
    }

    pdf.save(post);
}
