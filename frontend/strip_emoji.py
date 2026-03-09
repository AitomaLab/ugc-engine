"""Final pass: remove all remaining standard emoji from TSX files."""
import os
import re
import glob

SRC = r"C:\Users\dedam\.antigravity\UGC Engine SaaS\frontend\src\app"
files = glob.glob(os.path.join(SRC, "**", "*.tsx"), recursive=True)

# Unicode emoji range regex
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
    
    if emoji_pattern.search(content):
        # Remove emojis
        # Also handle cases where emoji is followed by a space (e.g., "🎬 Video" -> "Video")
        # To strictly do this, we can replace emoji + space with empty, then just emoji with empty
        
        # We'll just use the regex sub, and then clean up double spaces or leading spaces if within tags
        # A simpler way is to just replace the exact matches
        
        # Function to replace and strip trailing space if present
        def replacer(match):
            return ""

        # Remove emojis
        new_content = emoji_pattern.sub(replacer, content)
        
        # Clean up cases where we left a leading space inside a string or tag:
        # e.g., " Video" -> "Video", "' Video'" -> "'Video'", "> Video" -> ">Video"
        # We can just do a few common replacements safely
        new_content = new_content.replace(">  ", "> ")
        new_content = new_content.replace("'  ", "' ")
        new_content = new_content.replace('"  ', '" ')
        
        if new_content != content:
            with open(fpath, 'w', encoding='utf-8') as f:
                f.write(new_content)
            count += 1
            print(f"Removed emojis from: {os.path.basename(fpath)}")

print(f"\nTotal files updated: {count}")
