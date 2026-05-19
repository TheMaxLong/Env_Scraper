#!/usr/bin/env python3
"""
Sanitize demo screenshots for the hark.equipment OCR-tool Gumroad listing.

Source:  /Users/max/Downloads/PDF logger ocr tool/
Output:  /Users/max/Documents/GitHub/Env_Scraper/assets/demo/

Two kinds of inputs:
  1) BEFORE — phone photos of handwritten grow-room log sheets, stitched
     into tall composites. They expose real facility room codes
     (AB1-AB8, EF1-EF8, GH5-GH8), dates, and distinctive handwriting.
  2) AFTER  — screenshots of the structured web report the tool produces.
     These already contain the real room codes in clean text.

Strategy per image is declared in IMAGE_PLAN below. Adjust coordinates
there; the renderer is dumb on purpose.

PII redaction modes per region:
  - "blur"  : gaussian blur (good for handwriting / signature regions)
  - "fill"  : solid rectangle (good for room-code labels / dates)
  - "label" : solid rectangle + centered replacement text (good for
              room-code labels you want to relabel "Room A1" etc.)

Hero picks (chosen by Claude for clearest before/after story):
  BEFORE 1: 012715  (AB row, dense numeric grid — looks like real work)
  BEFORE 2: 012736  (GH row, similar density — pairs visually)
  AFTER  1: 013650  (Runoff report — same AB rooms; direct mirror of BEFORE 1)
  AFTER  2: 013745  (Environmental — grouped by building; mirrors BEFORE 2)

Run:
    python3 sanitize_demo.py --dry-run   # print plan, write nothing
    python3 sanitize_demo.py             # actually render

Dependencies: Pillow.
"""

from __future__ import annotations

import argparse
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from PIL import Image, ImageDraw, ImageFilter, ImageFont

SRC_DIR = Path("/Users/max/Downloads/PDF logger ocr tool")
OUT_DIR = Path("/Users/max/Documents/GitHub/Env_Scraper/assets/demo")

# Map of REAL room code -> generic public code. Used only in AFTER images
# where the codes appear as crisp digital text (we re-render them).
ROOM_CODE_MAP = {
    "AB1": "Room A1", "AB2": "Room A2", "AB3": "Room A3", "AB4": "Room A4",
    "AB5": "Room A5", "AB6": "Room A6", "AB7": "Room A7", "AB8": "Room A8",
    "EF1": "Room B1", "EF2": "Room B2", "EF3": "Room B3", "EF4": "Room B4",
    "EF5": "Room B5", "EF6": "Room B6", "EF7": "Room B7", "EF8": "Room B8",
    "GH5": "Room C5", "GH6": "Room C6", "GH7": "Room C7", "GH8": "Room C8",
    "AB Building": "Building A",
    "EF Building": "Building B",
    "GH Building": "Building C",
}

RedactMode = Literal["blur", "fill", "label"]


@dataclass
class Region:
    """A rectangular region to redact. Coords are (left, top, right, bottom)
    in pixels relative to the ORIGINAL (uncropped) image."""
    box: tuple[int, int, int, int]
    mode: RedactMode = "fill"
    text: str = ""           # used only when mode == "label"
    fill: tuple[int, int, int] = (245, 242, 235)  # parchment, matches AFTER bg
    blur_radius: int = 18


@dataclass
class ImagePlan:
    src_name: str
    out_name: str
    # Crop applied first (left, top, right, bottom). None = no crop.
    crop: tuple[int, int, int, int] | None = None
    # Regions are in ORIGINAL coordinates; we apply them before cropping.
    regions: list[Region] = field(default_factory=list)
    # Optional max width for the final saved PNG (keeps file size sane).
    max_width: int | None = 1400


# ---------------------------------------------------------------------------
# Per-image plan
# ---------------------------------------------------------------------------
# Notes on BEFORE images:
#   They're 1080-wide phone screenshots with no visible status bar or nav
#   bar in the captured region (the screenshots are pure stitched page
#   content). So we don't need to crop UI chrome.  We DO need to:
#     - blur the top-left corner of every stitched panel, which contains
#       a hand-written room-code label (e.g. "AB1", "EF2", "GH6")
#     - blur any handwritten date strings near those labels
#   Handwriting in the cells themselves is fine — that's the whole point
#   of the demo. We only redact the *labels* that identify Max's rooms.
#
# Notes on AFTER images:
#   These are clean web screenshots. The real room codes are crisp text.
#   We cover the room-code text with a small filled rectangle and stamp
#   the generic replacement on top.

IMAGE_PLAN: list[ImagePlan] = [
    # ---------- BEFORE images ----------
    ImagePlan(
        src_name="Screenshot_20260515-012705.png",
        out_name="before-03-handwritten-log-ab.png",
        regions=[
            # Top panel "AB1" label + "Load in 5/13" date string
            Region(box=(20, 10, 470, 90), mode="blur", blur_radius=22),
            # Middle panel "AB2" label
            Region(box=(20, 690, 200, 760), mode="blur", blur_radius=22),
            # Bottom panel "AB3" label
            Region(box=(20, 1340, 280, 1410), mode="blur", blur_radius=22),
        ],
    ),
    ImagePlan(
        src_name="Screenshot_20260515-012715.png",
        out_name="before-01-handwritten-log-ab.png",  # HERO PICK
        regions=[
            # Top panel "AB4" label
            Region(box=(20, 10, 200, 80), mode="blur", blur_radius=22),
            # Middle panel "EF" label + date
            Region(box=(20, 605, 260, 680), mode="blur", blur_radius=22),
            # Bottom panel "EF2" label
            Region(box=(20, 1200, 200, 1275), mode="blur", blur_radius=22),
        ],
    ),
    ImagePlan(
        src_name="Screenshot_20260515-012727.png",
        out_name="before-04-handwritten-log-ef.png",
        regions=[
            # Top "EF3"
            Region(box=(20, 10, 200, 80), mode="blur", blur_radius=22),
            # Middle "EF4"
            Region(box=(20, 550, 200, 620), mode="blur", blur_radius=22),
            # Bottom "GH5"
            Region(box=(20, 1090, 200, 1160), mode="blur", blur_radius=22),
        ],
    ),
    ImagePlan(
        src_name="Screenshot_20260515-012736.png",
        out_name="before-02-handwritten-log-gh.png",  # HERO PICK
        regions=[
            # Top "GH6  4/29/26" — label + date
            Region(box=(20, 10, 470, 90), mode="blur", blur_radius=22),
            # Middle "GH7"
            Region(box=(20, 700, 200, 770), mode="blur", blur_radius=22),
            # Bottom "GH8  Load in 5/13"
            Region(box=(20, 1700, 470, 1780), mode="blur", blur_radius=22),
        ],
    ),

    # ---------- AFTER images ----------
    # The AFTER screenshots show real room codes (AB1, EF2, GH5, etc).
    # We stamp generic codes over each. Coordinates are conservative —
    # adjust if the labels shift after Max regenerates the report.
    ImagePlan(
        src_name="Screenshot_20260515-013650.png",
        out_name="after-01-runoff-report.png",  # HERO PICK (pairs w/ before-01)
        regions=[
            Region(box=(33, 220, 130, 270), mode="label", text="Room A1"),
            Region(box=(33, 430, 130, 480), mode="label", text="Room A2"),
            Region(box=(33, 700, 130, 750), mode="label", text="Room A3"),
            Region(box=(33, 1010, 130, 1060), mode="label", text="Room A4"),
        ],
    ),
    ImagePlan(
        src_name="Screenshot_20260515-013703.png",
        out_name="after-03-runoff-report-ef.png",
        regions=[
            Region(box=(20, 30, 175, 110), mode="label", text="Room B1"),
            Region(box=(20, 360, 175, 440), mode="label", text="Room B2"),
            Region(box=(20, 720, 175, 800), mode="label", text="Room B3"),
            Region(box=(20, 1090, 175, 1170), mode="label", text="Room B4"),
        ],
    ),
    ImagePlan(
        src_name="Screenshot_20260515-013717.png",
        out_name="after-04-runoff-report-gh.png",
        regions=[
            Region(box=(15, 15, 110, 55), mode="label", text="Room C5"),
            Region(box=(15, 195, 110, 235), mode="label", text="Room C6"),
            Region(box=(15, 380, 110, 420), mode="label", text="Room C7"),
            Region(box=(15, 565, 110, 605), mode="label", text="Room C8"),
        ],
    ),
    ImagePlan(
        src_name="Screenshot_20260515-013731.png",
        out_name="after-05-flags-summary.png",
        # The Flags page references room codes mid-sentence (AB3 — S2: ...).
        # Too many inline references to redact cleanly; we blur the body
        # and keep only the header crisp. Max can rerun OCR on a renamed
        # dataset if he wants a clean version of this view.
        regions=[
            Region(box=(0, 200, 895, 2142), mode="blur", blur_radius=6),
        ],
    ),
    ImagePlan(
        src_name="Screenshot_20260515-013745.png",
        out_name="after-02-environmental-summary.png",  # HERO PICK
        regions=[
            # Building headers
            Region(box=(20, 130, 360, 195), mode="label", text="Building A"),
            Region(box=(20, 455, 360, 520), mode="label", text="Building B"),
            Region(box=(20, 785, 360, 850), mode="label", text="Building C"),
            # AB rows
            Region(box=(35, 215, 145, 255), mode="label", text="Room A1"),
            Region(box=(35, 275, 145, 315), mode="label", text="Room A2"),
            Region(box=(35, 335, 145, 375), mode="label", text="Room A3"),
            Region(box=(35, 395, 145, 435), mode="label", text="Room A4"),
            # EF rows
            Region(box=(35, 540, 145, 580), mode="label", text="Room B1"),
            Region(box=(35, 600, 145, 640), mode="label", text="Room B2"),
            Region(box=(35, 660, 145, 700), mode="label", text="Room B3"),
            Region(box=(35, 720, 145, 760), mode="label", text="Room B4"),
            # GH rows
            Region(box=(35, 870, 145, 910), mode="label", text="Room C5"),
            Region(box=(35, 930, 145, 970), mode="label", text="Room C6"),
            Region(box=(35, 990, 145, 1030), mode="label", text="Room C7"),
            Region(box=(35, 1050, 145, 1090), mode="label", text="Room C8"),
        ],
    ),
]


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "/System/Library/Fonts/Supplemental/Georgia Bold.ttf",
        "/System/Library/Fonts/Supplemental/Georgia.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    return ImageFont.load_default()


def apply_region(img: Image.Image, region: Region) -> None:
    """Mutates img in place."""
    if region.mode == "blur":
        crop = img.crop(region.box).filter(
            ImageFilter.GaussianBlur(radius=region.blur_radius)
        )
        img.paste(crop, region.box)
        return

    draw = ImageDraw.Draw(img)
    draw.rectangle(region.box, fill=region.fill)

    if region.mode == "label" and region.text:
        x0, y0, x1, y1 = region.box
        box_h = y1 - y0
        font_size = max(12, int(box_h * 0.55))
        font = _load_font(font_size)
        try:
            bbox = draw.textbbox((0, 0), region.text, font=font)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        except AttributeError:
            tw, th = draw.textsize(region.text, font=font)
        tx = x0 + ((x1 - x0) - tw) // 2
        ty = y0 + ((y1 - y0) - th) // 2
        draw.text((tx, ty), region.text, fill=(30, 30, 30), font=font)


def process(plan: ImagePlan, dry_run: bool) -> None:
    src = SRC_DIR / plan.src_name
    dst = OUT_DIR / plan.out_name
    if not src.exists():
        print(f"  ! missing source: {src}")
        return

    if dry_run:
        print(f"  PLAN {plan.src_name} -> {plan.out_name}")
        for r in plan.regions:
            extra = f' text="{r.text}"' if r.mode == "label" else ""
            print(f"      {r.mode:5s} box={r.box}{extra}")
        if plan.crop:
            print(f"      crop {plan.crop}")
        if plan.max_width:
            print(f"      max_width {plan.max_width}")
        return

    img = Image.open(src).convert("RGB")
    for region in plan.regions:
        apply_region(img, region)
    if plan.crop:
        img = img.crop(plan.crop)
    if plan.max_width and img.width > plan.max_width:
        new_h = int(img.height * plan.max_width / img.width)
        img = img.resize((plan.max_width, new_h), Image.LANCZOS)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    img.save(dst, "PNG", optimize=True)
    print(f"  wrote {dst}  ({img.size[0]}x{img.size[1]})")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true",
                    help="Print the plan without writing any files.")
    args = ap.parse_args()

    print(f"source: {SRC_DIR}")
    print(f"output: {OUT_DIR}")
    print(f"mode:   {'DRY RUN' if args.dry_run else 'WRITE'}")
    print()
    for plan in IMAGE_PLAN:
        process(plan, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
