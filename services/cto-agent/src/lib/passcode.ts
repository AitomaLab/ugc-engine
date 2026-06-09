/**
 * Optional passcode gate. Configured via CTO_AGENT_PASSCODES env var:
 *   "VC Firm Name=passcode-here,Another Firm=other-pass"
 *
 * When the env var is empty, the gate is disabled (open access — appropriate
 * for local-first testing).
 */
interface ParsedPasscode {
  label: string;
  passcode: string;
}

let parsed: ParsedPasscode[] | null = null;

function parseEnv(): ParsedPasscode[] {
  if (parsed) return parsed;
  const raw = process.env.CTO_AGENT_PASSCODES || "";
  parsed = raw
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean)
    .map((pair) => {
      const [label, passcode] = pair.split("=").map((s) => s.trim());
      return { label: label || "Unknown", passcode: passcode || "" };
    })
    .filter((p) => p.passcode.length > 0);
  return parsed;
}

export function isGateEnabled(): boolean {
  return parseEnv().length > 0;
}

/** Returns the visitor label if the passcode is valid, otherwise null. */
export function validatePasscode(passcode: string | null): string | null {
  const entries = parseEnv();
  if (entries.length === 0) return "open-access";
  if (!passcode) return null;
  const match = entries.find(
    (e) => e.passcode.toLowerCase() === passcode.toLowerCase().trim(),
  );
  return match ? match.label : null;
}
