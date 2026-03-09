"""Second pass: find and fix all remaining emoji in TSX files."""
import os
import re
import glob

SRC = r"C:\Users\dedam\.antigravity\UGC Engine SaaS\frontend\src\app"
files = glob.glob(os.path.join(SRC, "**", "*.tsx"), recursive=True)

# Unicode emoji range regex (catches most emoji)
emoji_pattern = re.compile(
    "["
    "\U0001F300-\U0001F9FF"  # Most emoji
    "\U00002702-\U000027B0"  # Dingbats
    "\U0000FE00-\U0000FE0F"  # Variation selectors
    "\U0000200D"             # Zero width joiner
    "\U000020E3"             # Combining enclosing keycap
    "\U00002600-\U000026FF"  # Misc symbols
    "\U00002B50"             # Star
    "\U0000231A-\U0000231B"
    "\U00002934-\U00002935"
    "\U000025AA-\U000025AB"
    "\U000025B6"
    "\U000025FB-\U000025FE"
    "\U00002614-\U00002615"
    "\U00002648-\U00002653"
    "\U0000267F"
    "\U00002693"
    "\U000026A1"
    "\U000026AA-\U000026AB"
    "\U000026BD-\U000026BE"
    "\U000026C4-\U000026C5"
    "\U000026CE"
    "\U000026D4"
    "\U000026EA"
    "\U000026F2-\U000026F3"
    "\U000026F5"
    "\U000026FA"
    "\U000026FD"
    "\U00002702"
    "\U00002705"
    "\U00002708-\U000027BF"
    "\U0000E000-\U0000F8FF"
    "]+", flags=re.UNICODE
)

count = 0
for fpath in files:
    with open(fpath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find emoji occurrences with context
    found = list(emoji_pattern.finditer(content))
    if found:
        fname = os.path.basename(fpath)
        print(f"\n{fname}: {len(found)} emoji occurrences")
        for m in found:
            line_num = content[:m.start()].count('\n') + 1
            start = max(0, m.start() - 30)
            end = min(len(content), m.end() + 30)
            ctx = content[start:end].replace('\n', ' ').replace('\r', '')
            emoji_chars = m.group()
            hex_codes = ' '.join(f'U+{ord(c):04X}' for c in emoji_chars)
            print(f"  L{line_num}: [{emoji_chars}] ({hex_codes}) ...{ctx}...")
        count += len(found)

print(f"\n--- Total emoji found: {count} ---")
