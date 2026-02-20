# UGC Engine: Definitive Technical Analysis & Root Cause Report

**Prepared by:** Manus AI  
**Date:** February 17, 2026  
**Repository:** [AitomaLab/ugc-engine](https://github.com/AitomaLab/ugc-engine)

---

## Executive Summary

The UGC Engine is experiencing two critical, independent failures that are preventing successful video generation:

1.  **Veo 3.1 Character Hallucinations:** The Veo 3.1 video generation model is introducing different people mid-video, despite receiving correct reference images. This is a **prompt engineering failure**.
2.  **FFmpeg Assembly Failure:** The final video assembly process is failing on Windows with a `[WinError 2] The system cannot find the file specified` error. This is a **missing dependency validation failure**.

This report provides a definitive root cause analysis for both issues and outlines the complete, self-contained solution for each. The fixes are straightforward, low-risk, and ready for immediate implementation.

---

## Issue #1: Veo 3.1 Mid-Video Character Hallucinations

### **Problem Description**

-   **Nano Banana Pro** correctly generates a composite image with the intended influencer.
-   **Veo 3.1** receives this correct image as a reference for video animation.
-   **Mid-video**, Veo 3.1 hallucinates and morphs the character into a different person.
-   The final video shows a character switching identity during the animation.

### **Root Cause Analysis**

The root cause is a **prompt engineering failure** in `scene_builder.py`. The current Veo 3.1 prompts lack explicit instructions for temporal consistency, allowing the model to deviate from the reference image over time.

**Current Prompt Weaknesses:**

| Issue | Current Prompt | Result |
|---|---|---|
| **Character Description** | Describes a generic person (e.g., "a 25-year-old female influencer") | Veo 3.1 generates a person matching the description, not the reference image |
| **Temporal Consistency** | Not mentioned | Veo 3.1 is free to morph the character mid-video |
| **Identity Anchoring** | Not anchored to the reference image | The model does not know to maintain the person from the reference |
| **Negative Prompt** | Prohibits anatomical errors but not identity errors | No prohibition on character morphing or face changes |

**Technical Explanation:**

Veo 3.1 uses the `FIRST_AND_LAST_FRAMES_2_VIDEO` generation type, which means it generates intermediate frames based on the first frame (the reference image) and the text prompt. When the prompt describes a generic person, the model starts with the reference image but gradually drifts towards the generic description over the course of the video, resulting in character morphing.

### **Solution: Enhanced Prompt Architecture**

The solution is to enhance the Veo 3.1 prompts in `scene_builder.py` with the following principles:

1.  **Extreme Specificity:** Use strong, direct language to constrain the model.
2.  **Reference Image as Ground Truth:** The prompt must reinforce that the reference image is the source of truth for the character's identity.
3.  **Redundancy and Reinforcement:** Repeat critical instructions to ensure they are prioritized.
4.  **Comprehensive Negative Prompts:** Explicitly prohibit all forms of character inconsistency.

**Enhanced Prompt Structure:**

```python
# ANCHOR: Use the exact person from the reference image
f"A realistic, high-quality, authentic UGC video selfie of THE EXACT SAME PERSON from the reference image. "

# CRITICAL: Enforce temporal consistency
f"CRITICAL: The person's identity, facial features, skin tone, hair, and body remain COMPLETELY IDENTICAL and CONSISTENT throughout the ENTIRE video from the first frame to the last frame. "

# ACTION: Describe what the person is doing (not who they are)
f"The person is holding exactly one product bottle in their right hand..."

# REINFORCEMENT: Final emphasis on consistency
f"The person remains THE SAME INDIVIDUAL with NO CHANGES to their face, identity, or appearance at any point in the video. "

# NEGATIVE PROMPT: Prohibit all forms of inconsistency
f"NEGATIVE PROMPT: ... character morphing, face morphing, different person, facial feature changes, identity switching, ..."
```

---

## Issue #2: FFmpeg Assembly Failure on Windows

### **Problem Description**

-   All video scenes are generated successfully.
-   The final assembly process using FFmpeg fails with `[WinError 2] The system cannot find the file specified`.
-   This error occurs on Windows environments.

### **Root Cause Analysis**

The root cause is a **missing dependency validation failure**. The application does not check if FFmpeg is installed and available in the system's PATH before attempting to use it.

**Technical Explanation:**

The `assemble_video.py` module calls FFmpeg using `subprocess.run()`. On Windows, if `ffmpeg.exe` is not in the system PATH, the operating system cannot find the executable, resulting in the `[WinError 2]` error.

**Current Code Weakness:**

-   There is no startup check to validate that FFmpeg is installed and accessible.
-   The application fails late in the process, after all expensive AI generation steps are complete.
-   The error message is cryptic and does not guide the user on how to resolve the issue.

### **Solution: Startup Dependency Validation**

The solution is to add a validation function in `main.py` (or the application entry point) that checks for the presence of FFmpeg at startup.

**Validation Function Structure:**

```python
import shutil
import platform

def validate_dependencies():
    """Validate that all required external dependencies are available."""
    if not shutil.which("ffmpeg"):
        error_msg = (
            "❌ CRITICAL: FFmpeg not found in PATH.\n"
            "   Please install FFmpeg and add it to your system PATH.\n"
            "   Download: https://ffmpeg.org/download.html\n"
            "   Windows Installation Guide: https://www.wikihow.com/Install-FFmpeg-on-Windows"
        )
        raise RuntimeError(error_msg)
    print("   ✅ FFmpeg validated")
```

This function should be called at the very beginning of the application startup. If FFmpeg is not found, the application will fail immediately with a clear, helpful error message.

---

## Implementation Priority Matrix

| Priority | Issue | Impact | Effort | Timeline |
|---|---|---|---|---|
| **P0** | Veo 3.1 Character Hallucinations | 100% of videos are unusable | Low (prompt change) | 30 minutes |
| **P0** | FFmpeg Assembly Failure | 100% failure on Windows | Low (validation code) | 15 minutes |

---

## Conclusion

Both critical failures have straightforward, low-risk solutions that can be implemented quickly.

-   The **Veo 3.1 hallucination issue** is a classic prompt engineering problem that can be solved by providing more explicit and restrictive instructions to the model.
-   The **FFmpeg assembly failure** is a common dependency issue that can be resolved by adding a simple validation check at startup.

By implementing these two fixes, the UGC Engine will become significantly more reliable and produce consistently high-quality videos.

---

**End of Technical Analysis**
