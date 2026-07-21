/**
 * Small text helpers shared by the Markdown renderer and the account-report
 * parser. Kept framework-free so both the generic renderer and the parser can
 * import it without a wrong-direction dependency.
 */

/** A list item that is *only* a bold label, e.g. `**Format:**` or `**Format**`. */
const LABEL_ONLY = /^\*\*([^*]+?)\*\*\s*:?\s*$/;

/**
 * Merge a bare "**Label:**" list item with the description item that follows,
 * so a title and its description render as one `**Title:** description` row
 * instead of two separate cards.
 *
 * Left untouched:
 *   • items that already carry their own text (e.g. `**Views:** 1,648`),
 *   • a label followed by another label (kept standalone),
 *   • a trailing label with no following description.
 */
export function mergeLabelValuePairs(items: string[]): string[] {
    const out: string[] = [];
    for (let i = 0; i < items.length; i += 1) {
        const cur = (items[i] ?? '').trim();
        const label = LABEL_ONLY.exec(cur);
        const next = items[i + 1]?.trim();
        const nextIsLabel = next === undefined ? true : LABEL_ONLY.test(next);
        if (label && next !== undefined && !nextIsLabel) {
            out.push(`**${label[1].replace(/:\s*$/, '')}:** ${next}`);
            i += 1; // consume the description item
        } else {
            out.push(items[i]);
        }
    }
    return out;
}
