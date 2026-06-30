export interface InsufficientCreditsInfo {
  balance?: number;
  required?: number;
}

const INSUFFICIENT_RE =
  /insufficient\s+credits|insufficient_credits|402\s+payment\s+required/i;

const BALANCE_RE = /(?:current\s+)?balance[:\s]+(\d+)/i;
const REQUIRED_RE = /required[:\s]+(\d+)/i;

export function isInsufficientCreditsError(text: string): boolean {
  return INSUFFICIENT_RE.test(text || '');
}

export function parseInsufficientCredits(text: string): InsufficientCreditsInfo | null {
  if (!text || !isInsufficientCreditsError(text)) return null;

  const balanceMatch = text.match(BALANCE_RE);
  const requiredMatch = text.match(REQUIRED_RE);

  return {
    balance: balanceMatch ? Number(balanceMatch[1]) : undefined,
    required: requiredMatch ? Number(requiredMatch[1]) : undefined,
  };
}
