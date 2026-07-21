/**
 * Structured parsers for the two free-text LLM blobs shown on the account
 * detail page.
 *
 * Both the AI Strategy report and the AI Learnings ("creative guidelines")
 * arrive as a single Markdown string. The old renderer split them on *every*
 * heading level into a flat list, which surfaced the report's repeated child
 * headings ("Insights" / "Specific Posts") as duplicate side panels and
 * echoed posts as plain "Post 1 / Post 2" text.
 *
 * Instead we anchor on the report's three canonical sections by keyword
 * (language-agnostic across EN/ES, order-tolerant) and hand each section's
 * body back as Markdown for `StrategyReportMarkdown` to render. Real post
 * previews are shown separately by the Strategy tab, so the "Specific Posts"
 * text sub-section is stripped from the diagnosis prose.
 */

import { mergeLabelValuePairs } from '../markdownText';

const HEADING = /^(#{1,6})\s+(.*)$/;
const LIST_ITEM = /^\s*(?:[-*•]|\d+[.)])\s+(.*)$/;

interface HeadingRef {
    idx: number;
    text: string;
}

function splitLines(source: string): string[] {
    return source.replace(/\r\n/g, '\n').split('\n');
}

function collectHeadings(lines: string[]): HeadingRef[] {
    const out: HeadingRef[] = [];
    lines.forEach((raw, idx) => {
        const m = HEADING.exec(raw.trim());
        if (m) out.push({ idx, text: m[2].replace(/\*\*/g, '').trim() });
    });
    return out;
}

function firstHeadingMatching(headings: HeadingRef[], re: RegExp): number | null {
    const hit = headings.find((h) => re.test(h.text));
    return hit ? hit.idx : null;
}

/** Body lines from just after `startIdx` up to the next boundary (exclusive). */
function sliceBody(lines: string[], startIdx: number, boundaries: number[]): string {
    const next = boundaries.filter((b) => b > startIdx).sort((a, b) => a - b)[0] ?? lines.length;
    return lines.slice(startIdx + 1, next).join('\n').trim();
}

/**
 * A line that is ONLY a short label ending in a colon — `**Posts:**`,
 * `Posts:`, `- **Diagnosis:**` — with no content after it. LLM reports use
 * these as pseudo-headings whenever they skip real Markdown headings, so
 * section stripping must treat them as boundaries too.
 */
function pseudoHeadingText(line: string): string | null {
    const t = line.trim();
    if (!t || t.length > 48) return null;
    const unmarked = t
        .replace(/^(?:[-*•]|\d+[.)])\s+/, '')
        .replace(/\*\*/g, '')
        .trim();
    if (unmarked.length > 40) return null;
    const m = /^([A-Za-z0-9À-ÿ][^:]*):$/.exec(unmarked);
    return m ? m[1].trim() : null;
}

/** Heading text of a line — real `#` heading or bare-label pseudo-heading. */
function sectionLabel(line: string): string | null {
    const h = HEADING.exec(line.trim());
    if (h) return h[2].replace(/\*\*/g, '').trim();
    return pseudoHeadingText(line);
}

/** Drop a `#### Specific Posts` / `**Posts:**` sub-section — real cards replace it. */
function stripSubsection(body: string, re: RegExp): string {
    const lines = splitLines(body);
    const out: string[] = [];
    let skipping = false;
    for (const line of lines) {
        const label = sectionLabel(line);
        if (label !== null) {
            skipping = re.test(label);
            if (skipping) continue;
        }
        if (!skipping) out.push(line);
    }
    return out.join('\n').trim();
}

/**
 * Per-post metric dumps the report must never render as prose — the real
 * post cards sit right next to the panel. Anchored at line start (after an
 * optional bullet/number) so aggregate insights like `**High Engagement
 * Rates:** …` or `**Views Range:** …` survive. EN + ES labels.
 */
const METRIC_LINE = new RegExp(
    '^(?:[-*•]\\s*|\\d+[.)]\\s*)?(?:\\*\\*)?(?:'
    + 'post\\s*\\d+|date|posted(?:\\s*at)?|engagement\\s*rate|er|views?|likes?'
    + '|comments?|shares?|saves?|caption'
    + '|fecha|publicad[oa]|tasa\\s*de\\s*(?:engagement|interacci[oó]n)'
    + '|vistas?|reproducciones|me\\s*gusta|comentarios?|compartidos?|guardados?|leyenda'
    + ')(?:\\*\\*)?\\s*:',
    'i',
);

/** Belt-and-braces: drop residual per-post metric lines in any format. */
function stripMetricLines(body: string): string {
    return splitLines(body)
        .filter((l) => !METRIC_LINE.test(l.trim()))
        .join('\n')
        .replace(/\n{3,}/g, '\n\n')
        .trim();
}

/** Full cleanup for a diagnosis-prose body. */
function cleanSectionBody(body: string): string {
    return stripMetricLines(stripSubsection(body, SPECIFIC_POSTS_RE));
}

function extractItems(body: string): string[] {
    return splitLines(body)
        .map((l) => {
            const m = LIST_ITEM.exec(l);
            return m ? m[1].trim() : null;
        })
        .filter((x): x is string => Boolean(x));
}

const TOP_RE = /top\s*perform|best\s*perform|what\s*worked|winners?|mejor|top\b/i;
const BOTTOM_RE = /bottom|worst|under[-\s]*perform|lowest|needs?\s*work|weak|peor|bajo/i;
const DIAGNOSIS_RE = /diagnos[ií]s|diagn[óo]stico/i;
const ACTIONS_RE = /do\s*next|what\s*to\s*do|next\s*step|action|recommend|priorit|hacer|acci[oó]n|pr[oó]xim|prioridad|siguiente/i;
/**
 * Sub-headings that just re-list the posts the report was built from
 * ("Specific Posts", "Bottom Posts", "Specifics"). Real preview cards
 * replace them, so they're stripped from the diagnosis prose.
 */
const SPECIFIC_POSTS_RE = /\bposts?\b|\bspecifics?\b|example\s*post|publicacion|ejemplos?|espec[ií]fic/i;

export interface StrategySections {
    /** Diagnosis prose for the top performers (specific-post listing stripped). */
    top: string | null;
    /** Diagnosis prose for the underperformers. */
    bottom: string | null;
    /** Standalone "Diagnosis" section (What Worked / What Went Wrong). */
    diagnosis: string | null;
    /** Ranked action items ("What to Do Next"), bold markers preserved. */
    actionItems: string[];
    /** Raw actions body, used when no discrete items could be parsed. */
    actionsBody: string | null;
    /** False → caller should fall back to the generic renderer. */
    recognized: boolean;
}

export function parseStrategyReport(source: string): StrategySections {
    const lines = splitLines(source);
    const headings = collectHeadings(lines);

    const topIdx = firstHeadingMatching(headings, TOP_RE);
    const bottomIdx = firstHeadingMatching(headings, BOTTOM_RE);
    const diagnosisIdx = firstHeadingMatching(headings, DIAGNOSIS_RE);
    const actionsIdx = firstHeadingMatching(headings, ACTIONS_RE);

    const anchors = [topIdx, bottomIdx, diagnosisIdx, actionsIdx]
        .filter((x): x is number => x !== null);
    // Need at least two canonical sections to trust the structure.
    if (anchors.length < 2) {
        return {
            top: null, bottom: null, diagnosis: null,
            actionItems: [], actionsBody: null, recognized: false,
        };
    }

    const topBody = topIdx !== null
        ? cleanSectionBody(sliceBody(lines, topIdx, anchors)) : '';
    const bottomBody = bottomIdx !== null
        ? cleanSectionBody(sliceBody(lines, bottomIdx, anchors)) : '';
    const diagnosisBody = diagnosisIdx !== null
        ? cleanSectionBody(sliceBody(lines, diagnosisIdx, anchors)) : '';
    const actionsBody = actionsIdx !== null ? sliceBody(lines, actionsIdx, anchors) : '';

    return {
        top: topBody || null,
        bottom: bottomBody || null,
        diagnosis: diagnosisBody || null,
        actionItems: mergeLabelValuePairs(extractItems(actionsBody)),
        actionsBody: actionsBody || null,
        recognized: true,
    };
}

const SUMMARY_RE = /summary|resumen|overview|snapshot/i;
const CONFIRMED_RE = /confirm|proven|establish|known|confirmad|comprobad/i;
const HYPO_RE = /hypothes|testing|experiment|exploring|hip[oó]tesis|probando|prueba/i;

export interface LearningsSections {
    /** Summary / preamble prose. */
    summary: string | null;
    /** Rules the AI has confirmed work. */
    confirmed: string[];
    /** Things the AI is still testing. */
    hypotheses: string[];
    /** False → caller should fall back to the generic renderer. */
    recognized: boolean;
}

export function parseLearnings(source: string): LearningsSections {
    const lines = splitLines(source);
    const headings = collectHeadings(lines);

    const summaryIdx = firstHeadingMatching(headings, SUMMARY_RE);
    const confirmedIdx = firstHeadingMatching(headings, CONFIRMED_RE);
    const hypoIdx = firstHeadingMatching(headings, HYPO_RE);

    const anchors = [summaryIdx, confirmedIdx, hypoIdx].filter((x): x is number => x !== null);
    if (confirmedIdx === null && hypoIdx === null) {
        return { summary: null, confirmed: [], hypotheses: [], recognized: false };
    }

    // Summary body, or the preamble before the first heading when no summary head.
    let summary: string | null = null;
    if (summaryIdx !== null) {
        summary = sliceBody(lines, summaryIdx, anchors) || null;
    } else if (headings.length) {
        const preamble = lines.slice(0, headings[0].idx).join('\n').trim();
        summary = preamble || null;
    }

    const confirmed = confirmedIdx !== null
        ? mergeLabelValuePairs(extractItems(sliceBody(lines, confirmedIdx, anchors))) : [];
    const hypotheses = hypoIdx !== null
        ? mergeLabelValuePairs(extractItems(sliceBody(lines, hypoIdx, anchors))) : [];

    return { summary, confirmed, hypotheses, recognized: true };
}
