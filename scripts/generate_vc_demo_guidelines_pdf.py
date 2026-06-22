#!/usr/bin/env python3
"""Generate VC Demo Guidelines PDF from optimized slide copy."""

from __future__ import annotations

from pathlib import Path

from fpdf import FPDF

REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATHS = [
    REPO_ROOT / "docs" / "VC_DemoGuideline.pdf",
    Path.home() / "Downloads" / "VC_DemoGuideline.pdf",
]

SLIDES: list[tuple[str, str, str]] = [
    (
        "DASHBOARD",
        "How To Use:",
        (
            "Describe what you want in plain language — a UGC ad, product shots, or a "
            "multi-video campaign. Tap a suggestion chip below the composer for a proven "
            "starting prompt, or write your own brief. Each submission creates a project "
            "and hands off to the Creative Agent for scripting, casting, and generation."
        ),
    ),
    (
        "TAGGING",
        "How To Use:",
        (
            "Type @ in any prompt to search and tag influencers, products, images, or videos "
            "from your library. Tagged assets anchor the agent to real references — so output "
            "stays on-brand, on-product, and consistent across a campaign."
        ),
    ),
    (
        "PROJECTS",
        "How It Works:",
        (
            "Every Dashboard prompt opens a project — a persistent workspace for the agent "
            "thread, images, and videos. Return anytime from Projects to re-prompt, refine "
            "assets, or continue a campaign without losing context."
        ),
    ),
    (
        "INFLUENCERS",
        "How To Use:",
        (
            "Choose from ready-made AI Influencers, or click + New Influencer to upload a "
            "custom persona. For founder-led content, open My AI Clones to set up your face "
            "and voice — then @mention them in any brief."
        ),
    ),
    (
        "PRODUCTS",
        "How To Use:",
        (
            "Add physical or digital products here — upload images, run AI Vision analysis, "
            "or link app clips. Once saved, @mention any product in a prompt to generate "
            "UGC, cinematic shots, or full campaigns around it."
        ),
    ),
    (
        "PUBLISH",
        "How It Works:",
        (
            "Connect Instagram, TikTok, or YouTube via Manage Connections, then schedule "
            "finished videos from the Calendar or directly from any asset. Aitoma Studio "
            "publishes to your profiles — creation to distribution in one platform."
        ),
    ),
    (
        "ANALYTICS",
        "How It Works:",
        (
            "Open the Analytics tab to track performance across connected accounts — views, "
            "engagement, and post-level metrics. Run AI hook breakdowns on top performers, "
            "add competitor handles to benchmark trends, and reuse winning patterns in your "
            "next brief."
        ),
    ),
    (
        "EDITOR",
        "How To Use:",
        (
            "Generated videos sync to the Editor automatically. Trim clips, adjust captions, "
            "add music, or use the AI editor chat to refine by instruction — full "
            "post-production without leaving Aitoma Studio."
        ),
    ),
    (
        "CAMPAIGNS",
        "How It Works:",
        (
            'Ask the agent for scale — e.g. "Build a 5-video UGC campaign" or a multi-day '
            "content plan. The Creative Agent orchestrates batch scripting, generation, and "
            "scheduling so you move from one-off clips to full campaign production in a "
            "single workflow."
        ),
    ),
    (
        "FEEDBACK",
        "How To Use:",
        (
            "See something unexpected? Click the feedback bubble (bottom-right) to send "
            "notes, bugs, or ideas. During this MVP demo, your input goes directly to the "
            "team building what ships next."
        ),
    ),
    (
        "NOTE",
        "Please Note:",
        (
            "Aitoma Studio is in active MVP — you may hit rough edges or in-progress features. "
            "That's expected. Explore the full flow freely; we're optimizing daily ahead of "
            "public launch."
        ),
    ),
]


class VCDemoPDF(FPDF):
    def header(self) -> None:
        pass

    def footer(self) -> None:
        self.set_y(-15)
        self.set_font("Deck", "", 9)
        self.set_text_color(120, 120, 120)
        self.cell(0, 10, "VC Demo Guidelines", align="C")


def build_pdf(regular_font: Path, bold_font: Path) -> FPDF:
    pdf = VCDemoPDF(orientation="L", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_font("Deck", "", str(regular_font))
    pdf.add_font("Deck", "B", str(bold_font))

    for title, label, body in SLIDES:
        pdf.add_page()
        pdf.set_fill_color(248, 250, 252)
        pdf.rect(0, 0, 297, 210, style="F")

        pdf.set_xy(30, 35)
        pdf.set_font("Deck", "B", 28)
        pdf.set_text_color(15, 23, 42)
        pdf.cell(0, 14, title, ln=True)

        pdf.set_x(30)
        pdf.set_font("Deck", "B", 14)
        pdf.set_text_color(71, 85, 105)
        pdf.cell(0, 10, label, ln=True)

        pdf.ln(6)
        pdf.set_x(30)
        pdf.set_font("Deck", "", 13)
        pdf.set_text_color(30, 41, 59)
        pdf.multi_cell(237, 8, body)

    pdf.add_page()
    pdf.set_fill_color(248, 250, 252)
    pdf.rect(0, 0, 297, 210, style="F")
    pdf.set_xy(0, 85)
    pdf.set_font("Deck", "B", 32)
    pdf.set_text_color(15, 23, 42)
    pdf.cell(0, 14, "Thank You", align="C", ln=True)

    return pdf


def ensure_fonts() -> tuple[Path, Path]:
    font_dir = REPO_ROOT / "scripts" / "fonts"
    font_dir.mkdir(parents=True, exist_ok=True)
    regular = font_dir / "DejaVuSans.ttf"
    bold = font_dir / "DejaVuSans-Bold.ttf"

    if regular.exists() and bold.exists():
        return regular, bold

    windows_regular = Path(r"C:\Windows\Fonts\arial.ttf")
    windows_bold = Path(r"C:\Windows\Fonts\arialbd.ttf")
    if windows_regular.exists() and windows_bold.exists():
        return windows_regular, windows_bold

    raise FileNotFoundError(
        "No usable fonts found. Install DejaVu fonts under scripts/fonts/ or use Windows Arial."
    )


def main() -> None:
    import shutil

    regular, bold = ensure_fonts()
    pdf = build_pdf(regular, bold)
    primary = OUTPUT_PATHS[0]
    primary.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(primary))
    print(f"Wrote {primary}")

    for path in OUTPUT_PATHS[1:]:
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(primary, path)
        print(f"Wrote {path}")


if __name__ == "__main__":
    main()
