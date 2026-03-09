"""Fix all corrupted emoji and encoding issues across TSX files."""
import os
import glob

SRC = r"C:\Users\dedam\.antigravity\UGC Engine SaaS\frontend\src\app"

# Collect all TSX files
files = glob.glob(os.path.join(SRC, "**", "*.tsx"), recursive=True)

REPLACEMENTS = [
    # Corrupted emoji → clean replacements
    (b'\xc3\xa2\xc2\x9c\xc2\x95', b'\xc3\x97'),              # ✕ → ×
    (b'\xc3\xa2\xc2\x9c\xc2\xa8', b''),                        # ✨ → remove
    (b'\xc3\xa2\xc2\x9c\xc2\x85', b''),                        # ✅ → remove (already replaced with SVG)
    (b'\xc3\xa2\xc2\x9c\x22', b''),                             # ✓ variant
    (b'\xc3\xa2\xc2\xac\xc2\x87', b''),                         # ⬇ → remove
    (b'\xc3\xa2\xc2\x84\xc2\xa2', b''),                         # ™ → remove
    (b'\xc3\xa2\xe2\x80\x9e\xc2\xa2', b''),                     # another ™
    (b'\xc3\xa2\xe2\x80\x93', b'\xe2\x80\x94'),                 # em-dash
    
    # Corrupted multi-byte emoji
    (b'\xc3\xb0\xc2\x9f\xc2\x93\xc2\x85', b''),                # 📅
    (b'\xc3\xb0\xc2\x9f\xc2\x94\xc2\x97', b''),                # 🔗
    (b'\xc3\xb0\xc2\x9f\xc2\x91\xc2\xa4', b''),                # 👤
    (b'\xc3\xb0\xc2\x9f\xc2\x8e\xc2\xac', b''),                # 🎬
    (b'\xc3\xb0\xc2\x9f\xc2\x93\xc2\xa6', b''),                # 📦
    (b'\xc3\xb0\xc2\x9f\xc2\x93\xc2\xb1', b''),                # 📱
    (b'\xc3\xb0\xc2\x9f\xc2\x93\xc2\x9d', b''),                # 📝
    (b'\xc3\xb0\xc2\x9f\xc2\x94', b''),                         # 🔍 (partial)
    
    # Corrupted gender symbols
    (b'\xc3\xa2\xc2\x99\xc2\x82\xc3\xaf\xc2\xb8\xc2\x8f', b''),  # ♂️
    (b'\xc3\xa2\xc2\x99\xc2\x80\xc3\xaf\xc2\xb8\xc2\x8f', b''),  # ♀️
    
    # Fix text-[#1A1A1F] on dark backgrounds (should be text-white)
    (b'bg-black/60 text-[#1A1A1F]', b'bg-black/60 text-white'),
    (b'bg-red-500/80 text-[#1A1A1F]', b'bg-red-500/80 text-white'),
    (b'bg-purple-500/80 text-[#1A1A1F]', b'bg-purple-500/80 text-white'),
    (b'bg-blue-500/80 text-[#1A1A1F]', b'bg-blue-500/80 text-white'),
    (b'bg-[#94A3B8]/80 text-[#1A1A1F]', b'bg-[#94A3B8]/80 text-white'),
    (b'bg-red-600 text-[#1A1A1F]', b'bg-red-600 text-white'),
    (b'bg-green-500 text-[#1A1A1F]', b'bg-green-500 text-white'),
    (b'bg-[#337AFF] text-[#1A1A1F]', b'bg-[#337AFF] text-white'),
    (b'bg-blue-600 text-[#1A1A1F]', b'bg-blue-600 text-white'),
    (b'bg-indigo-600 text-[#1A1A1F]', b'bg-indigo-600 text-white'),
    (b'bg-emerald-500 text-[#1A1A1F]', b'bg-emerald-500 text-white'),
    (b'gradient-cta text-[#1A1A1F]', b'gradient-cta text-white'),
    
    # Fix broken CSS class from slate-y replacement
    (b'-tranreveal-', b'-translate-'),
    
    # Fix InfluencerModal header: text-white on white bg should be dark
    (b'text-lg font-semibold text-white', b'text-lg font-semibold text-[#1A1A1F]'),
    
    # Fix border-white/5 → border-[#E8ECF4] in modal headers
    (b'border-b border-white/5 flex', b'border-b border-[#E8ECF4] flex'),
    (b'border-t border-white/5 bg-white/50', b'border-t border-[#E8ECF4] bg-[#F0F4FF]/30'),
    (b'bg-white/5">', b'">'),
    
    # Fix close/X button text-[#4A5568] should be text-[#1A1A1F] to be clearly visible
    (b'hover:text-white transition">\xc3\xa2\xc5\x93\xc2\x95', b'hover:text-[#1A1A1F] transition">\xc3\x97'),
]

count = 0
for fpath in files:
    with open(fpath, 'rb') as f:
        data = f.read()
    
    orig = data
    for old, new in REPLACEMENTS:
        data = data.replace(old, new)
    
    if data != orig:
        with open(fpath, 'wb') as f:
            f.write(data)
        count += 1
        print(f"Fixed: {os.path.basename(fpath)}")

print(f"\nTotal files fixed: {count}")
