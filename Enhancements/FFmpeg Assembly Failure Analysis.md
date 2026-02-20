# FFmpeg Assembly Failure Analysis

## **Error Report**

```
🔧 Assembling final video...
   📐 Normalizing to 9:16...
❌ Job 5f57c123-c349-4afe-8812-60591dab7f44 failed: [WinError 2] The system cannot find the file specified
❌ In-process job 5f57c123-c349-4afe-8812-60591dab7f44 failed: [WinError 2] The system cannot find the file specified
WARNING:  StatReload detected changes in 'config.py'. Reloading...
```

---

## **Error Analysis**

### **Error Type:** `[WinError 2] The system cannot find the file specified`

This is a **Windows-specific error** that occurs when:
1. A file path is invalid or doesn't exist
2. FFmpeg executable is not found in PATH
3. A subprocess call is trying to execute a command that doesn't exist

### **Location:** The error occurs during `📐 Normalizing to 9:16...`

**File:** `assemble_video.py` (Lines 105-127)

```python
print("   📐 Normalizing to 9:16...")
normalized_paths = []

for i, scene_data in enumerate(video_paths):
    if isinstance(scene_data, dict):
        path = scene_data["path"]
        scene_type = scene_data.get("type", "veo")
    else:
        path = scene_data
        scene_type = "veo"

    if scene_type == "physical_product_scene":
        normalized = work_dir / f"normalized_{i}.mp4"
        normalize_video(path, normalized)  # ← ERROR LIKELY HERE
        normalized_paths.append(str(normalized))
        ...
```

---

## **ROOT CAUSE HYPOTHESES**

### **Hypothesis 1: FFmpeg Not in PATH (Most Likely)**

**Evidence:**
- Error occurs at the first FFmpeg call (`normalize_video`)
- `[WinError 2]` typically means "command not found"
- Windows systems require FFmpeg to be explicitly added to PATH

**Verification Needed:**
1. Check if FFmpeg is installed on the Windows system
2. Check if FFmpeg is in the system PATH
3. Check if the code is using absolute path to FFmpeg or relying on PATH

**Code Analysis:**

`assemble_video.py` Line 73-88:
```python
def normalize_video(input_path, output_path, target_width=1080, target_height=1920):
    cmd = [
        "ffmpeg", "-y",  # ← Assumes "ffmpeg" is in PATH
        "-i", str(input_path),
        ...
    ]
    subprocess.run(cmd, capture_output=True, check=True)
```

**Problem:** The code assumes `ffmpeg` is available in PATH. On Windows, this is often not the case unless explicitly configured.

### **Hypothesis 2: Input Video Path is Invalid**

**Evidence:**
- Error occurs when trying to normalize the first scene
- The `path` variable may be incorrect or the file may not exist

**Verification Needed:**
1. Check if the video files were successfully downloaded from Veo 3.1
2. Check if the `path` in `scene_data` is correct
3. Check if the path uses Windows backslashes vs. forward slashes

**Code Analysis:**

`core_engine.py` Line 126:
```python
generate_scenes.download_video(video_url, output_path)
```

**Question:** Did the download succeed? Is `output_path` valid?

### **Hypothesis 3: Working Directory Doesn't Exist**

**Evidence:**
- The error could occur if `work_dir` doesn't exist

**Code Analysis:**

`assemble_video.py` Line 99-100:
```python
work_dir = config.TEMP_DIR / "assembly"
work_dir.mkdir(parents=True, exist_ok=True)
```

**Verdict:** This should create the directory, so unlikely to be the issue.

### **Hypothesis 4: FFprobe Not in PATH**

**Evidence:**
- The code uses both `ffmpeg` and `ffprobe`
- If `ffprobe` is missing, it could cause issues

**Code Analysis:**

`assemble_video.py` Line 22-32:
```python
def get_video_duration(video_path):
    cmd = [
        "ffprobe", "-v", "quiet",  # ← Also assumes ffprobe is in PATH
        ...
    ]
```

---

## **MOST LIKELY ROOT CAUSE**

**FFmpeg is not installed or not in the Windows system PATH.**

### **Evidence:**

1. ✅ Error occurs at the first FFmpeg call
2. ✅ `[WinError 2]` is the standard Windows error for "command not found"
3. ✅ The code assumes `ffmpeg` and `ffprobe` are in PATH
4. ✅ Windows systems don't include FFmpeg by default

### **Why This Wasn't Caught Earlier:**

- The error only occurs during the **assembly phase**
- Veo 3.1 and Nano Banana Pro generation succeeded (no FFmpeg needed)
- The download step succeeded (no FFmpeg needed)
- FFmpeg is only needed for:
  - Normalizing videos
  - Concatenating scenes
  - Burning subtitles
  - Adding music

---

## **SOLUTION**

### **Option 1: Install FFmpeg and Add to PATH (Recommended)**

**Steps:**
1. Download FFmpeg for Windows from https://ffmpeg.org/download.html
2. Extract to `C:\ffmpeg\`
3. Add `C:\ffmpeg\bin\` to Windows PATH
4. Restart the terminal/IDE
5. Verify with `ffmpeg -version`

### **Option 2: Use Absolute Path in Code**

**Modify:** `assemble_video.py` and all files that call FFmpeg

```python
# At the top of the file
FFMPEG_PATH = r"C:\ffmpeg\bin\ffmpeg.exe"
FFPROBE_PATH = r"C:\ffmpeg\bin\ffprobe.exe"

# In functions
def normalize_video(...):
    cmd = [
        FFMPEG_PATH, "-y",  # Use absolute path
        ...
    ]
```

### **Option 3: Add FFmpeg Check at Startup**

**Add to:** `config.py` or `main.py`

```python
import shutil

def check_ffmpeg():
    if not shutil.which("ffmpeg"):
        raise RuntimeError(
            "FFmpeg not found in PATH. Please install FFmpeg and add it to your system PATH.\n"
            "Download: https://ffmpeg.org/download.html"
        )
    if not shutil.which("ffprobe"):
        raise RuntimeError("FFprobe not found in PATH.")
    print("✅ FFmpeg and FFprobe found")

# Call at startup
check_ffmpeg()
```

---

## **SECONDARY ISSUE: Path Handling on Windows**

### **Problem:**

Windows uses backslashes (`\`) in file paths, but FFmpeg expects forward slashes (`/`) or escaped backslashes.

**Evidence:**

`assemble_video.py` Line 142:
```python
safe_path = str(Path(path).resolve()).replace("\\", "/")
f.write(f"file '{safe_path}'\n")
```

**Verdict:** The code already handles this correctly for the concat list.

`assemble_video.py` Line 169:
```python
sub_path_safe = str(Path(subtitle_path).resolve()).replace("\\", "/").replace(":", "\\:")
```

**Verdict:** The code also handles this for subtitle paths.

**Conclusion:** Path handling appears correct.

---

## **VERIFICATION STEPS**

1. **Check FFmpeg Installation:**
   ```bash
   ffmpeg -version
   ffprobe -version
   ```

2. **Check if Video Files Exist:**
   ```python
   print(f"Video path: {path}")
   print(f"File exists: {Path(path).exists()}")
   ```

3. **Add Debug Logging:**
   ```python
   print(f"   Normalizing scene {i+1}: {path}")
   print(f"   Output: {normalized}")
   print(f"   FFmpeg command: {' '.join(cmd)}")
   ```

---

## **RECOMMENDED FIX**

### **Immediate Fix (For User):**

1. Install FFmpeg on Windows
2. Add to PATH
3. Restart the application

### **Code Fix (For Antigravity):**

Add FFmpeg validation at startup:

```python
# In config.py or main.py
import shutil

def validate_dependencies():
    """Validate that all required external dependencies are available."""
    if not shutil.which("ffmpeg"):
        raise RuntimeError(
            "❌ FFmpeg not found in PATH.\n"
            "Please install FFmpeg and add it to your system PATH.\n"
            "Download: https://ffmpeg.org/download.html\n"
            "Installation guide: https://www.wikihow.com/Install-FFmpeg-on-Windows"
        )
    if not shutil.which("ffprobe"):
        raise RuntimeError("❌ FFprobe not found in PATH.")
    
    print("✅ FFmpeg and FFprobe validated")

# Call at application startup
validate_dependencies()
```

---

## **CONCLUSION**

The FFmpeg assembly failure is caused by **FFmpeg not being installed or not in the Windows system PATH**. This is a **configuration issue**, not a code bug.

**Priority:** Add dependency validation at startup to catch this issue early with a helpful error message.
