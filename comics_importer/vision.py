import base64
import json
from pathlib import Path

import anthropic

from . import config
from .errors import VisionAPIError

SYSTEM_PROMPT = """\
You are a comic-book cataloging assistant. You will be shown a photo of a single comic
book cover (possibly a raw or roughly-cropped photo, not a professional scan). Identify
the comic as precisely as you can from the cover art, logos, indicia, and any visible
text, and give a brief condition assessment based on visible physical wear (creases,
spine stress, corner wear, discoloration, tears) if the copy itself is visible in the
photo. If you cannot confidently determine a field, return null for it rather than
guessing, and explain why in `notes`. Respond only with the structured data described
by the schema — do not add commentary outside the schema fields.

In addition to the free-text `condition_grade`, estimate a `numeric_grade` on the
comic-industry's informal 0.5-10.0 condition scale (higher = better condition):
10.0 gem mint (flawless); 9.2-9.8 near mint (sharp corners, no creases, strong gloss);
8.5-9.0 very fine (minor wear, maybe one small spine tick); 7.0-8.0 fine/very fine
(light-to-moderate wear, a few small spine stress marks); 5.5-6.5 fine (noticeable wear,
small creases); 4.0-5.0 very good (well-read copy, multiple small defects); 2.5-3.5 good
(heavier wear, larger creases, maybe tape); 1.0-2.0 fair (major defects, tears, heavy
soiling); 0.5 poor (incomplete or falling apart). Base this only on what's visible in
the cover photo (corners, spine, gloss, creases, tears, staining, writing) - you can't
judge interior pages, so treat this as a rough estimate, not a certified grade. If the
photo doesn't show the physical copy clearly enough to judge, return null rather than
guessing.

You will also propose how to crop and straighten the photo down to just the comic
cover, since these are ordinary photos taken by hand and usually show background,
a tilt, or both around the actual comic. Determine `rotation_degrees`: the clockwise
rotation needed to make the comic's edges level (0 if already level). Then, imagining
the photo rotated by that amount, determine `crop_left`, `crop_top`, `crop_width`, and
`crop_height` as fractions (0.0-1.0) of that rotated image's width/height, forming a
tight bounding box around the comic cover only, excluding any visible background,
table, or other surface. If the comic already fills the frame edge-to-edge, use 0 for
rotation, 0 for crop_left/crop_top, and 1.0 for crop_width/crop_height rather than
leaving these null — always give your best estimate for these five fields.\
"""

COMIC_METADATA_SCHEMA = {
    "type": "object",
    "properties": {
        "series": {
            "type": ["string", "null"],
            "description": "The comic series/title as printed on the cover, e.g. 'Amazing Spider-Man' or 'Micky Maus'. Null if illegible.",
        },
        "issue_number": {
            "type": ["string", "null"],
            "description": "The issue number as printed, e.g. '1', '42', 'Annual 3'. Kept as a string to allow non-numeric labels. Null if not visible.",
        },
        "year": {
            "type": ["integer", "null"],
            "description": "The 4-digit publication year, from the cover date or indicia if visible/inferable. Null if unknown.",
        },
        "publisher": {
            "type": ["string", "null"],
            "description": "Publisher name, e.g. 'Marvel Comics', 'Egmont Ehapa'. Null if unknown.",
        },
        "language": {
            "type": ["string", "null"],
            "description": "Language of the cover text, as an ISO 639-1 code where possible (e.g. 'en', 'de'), else a plain language name. Null if unknown.",
        },
        "condition_grade": {
            "type": ["string", "null"],
            "description": "A brief condition/grading assessment based on visible cover wear (e.g. 'Near Mint', 'Very Fine', 'Good - spine wear, corner crease'). Null if not assessable from this photo.",
        },
        "numeric_grade": {
            "type": ["number", "null"],
            "description": "Estimated condition on the comic-industry 0.5-10.0 scale (see system prompt for band definitions), e.g. 8.0, 9.2. Null if not assessable from this photo.",
        },
        "confidence": {
            "type": "string",
            "enum": ["high", "medium", "low"],
            "description": "Confidence in the series/issue/year identification above.",
        },
        "notes": {
            "type": ["string", "null"],
            "description": "Caveats, ambiguities, alternate readings, or anything that would help a human verify or correct this identification.",
        },
        "rotation_degrees": {
            "type": "number",
            "description": "Clockwise rotation in degrees needed to straighten the comic in this photo (correct for skew/tilt from how it was photographed). Typically between -45 and 45. Use 0 if the image is already straight.",
        },
        "crop_left": {
            "type": "number",
            "description": "Left edge of the comic book cover as a fraction of image width (0.0-1.0), measured after applying rotation_degrees. Use 0 if the comic already fills the frame edge-to-edge.",
        },
        "crop_top": {
            "type": "number",
            "description": "Top edge of the comic book cover as a fraction of image height (0.0-1.0), measured after applying rotation_degrees. Use 0 if already flush with the top.",
        },
        "crop_width": {
            "type": "number",
            "description": "Width of the comic book cover as a fraction of image width (0.0-1.0), measured after applying rotation_degrees. Use 1.0 if the comic fills the full width.",
        },
        "crop_height": {
            "type": "number",
            "description": "Height of the comic book cover as a fraction of image height (0.0-1.0), measured after applying rotation_degrees. Use 1.0 if the comic fills the full height.",
        },
    },
    "required": [
        "series",
        "issue_number",
        "year",
        "publisher",
        "language",
        "condition_grade",
        "numeric_grade",
        "confidence",
        "notes",
        "rotation_degrees",
        "crop_left",
        "crop_top",
        "crop_width",
        "crop_height",
    ],
    "additionalProperties": False,
}


def _call_vision(
    thumb_path: Path,
    client: "anthropic.Anthropic",
    model: str,
    system_prompt: str,
    schema: dict,
    user_text: str,
    effort: str = "low",
) -> tuple[dict, str]:
    image_b64 = base64.standard_b64encode(thumb_path.read_bytes()).decode("utf-8")

    try:
        response = client.messages.create(
            model=model,
            max_tokens=config.CLAUDE_MAX_TOKENS,
            system=system_prompt,
            output_config={
                "format": {"type": "json_schema", "schema": schema},
                "effort": effort,
            },
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/jpeg",
                                "data": image_b64,
                            },
                        },
                        {"type": "text", "text": user_text},
                    ],
                }
            ],
        )
    except anthropic.NotFoundError as exc:
        raise VisionAPIError(f"Model not found: {exc}") from exc
    except anthropic.RateLimitError as exc:
        raise VisionAPIError(f"Rate limited: {exc}") from exc
    except anthropic.APIStatusError as exc:
        raise VisionAPIError(f"API error ({exc.status_code}): {exc.message}") from exc
    except anthropic.APIConnectionError as exc:
        raise VisionAPIError(f"Connection error: {exc}") from exc

    if response.stop_reason == "refusal":
        raise VisionAPIError("Claude declined to process this image (refusal)")

    text_block = next((b for b in response.content if b.type == "text"), None)
    if text_block is None:
        raise VisionAPIError("Claude response contained no text block")

    raw_text = text_block.text
    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise VisionAPIError(f"Claude response was not valid JSON: {exc}") from exc

    return data, raw_text


def identify_metadata(
    thumb_path: Path,
    client: "anthropic.Anthropic",
    model: str = config.CLAUDE_MODEL,
) -> tuple[dict, str]:
    return _call_vision(
        thumb_path,
        client,
        model,
        SYSTEM_PROMPT,
        COMIC_METADATA_SCHEMA,
        "Identify this comic book from its cover photo.",
    )


# Condensed from ~/.claude/skills/comic-grading/SKILL.md - see that file for the
# full reference notes. Kept in sync manually; this is the detailed version used
# when the user asks to *only* re-grade a comic (as opposed to identify_metadata's
# abbreviated grading blurb, which runs alongside full identification).
GRADING_SYSTEM_PROMPT = """\
You are assessing the physical condition of a comic book from a cover photo, using the
comic-industry's informal 0.5-10.0 grading scale (popularized by third-party graders
like CGC, CBCS, and PGX; this is a paraphrased general-knowledge summary, not any
company's proprietary standard). Higher = better condition. Treat the bands below as
fuzzy, not hard cutoffs - interpolate between them (e.g. 7.5, 8.5) based on how many
defects stack up and how severe each one is:

10.0 Gem Mint - flawless. Perfect centering, razor corners, no defects even up close.
9.8-9.9 Mint/Near Mint+ - nearly perfect; at most one tiny, hard-to-spot flaw.
9.2-9.6 Near Mint - sharp corners, no creases, minimal handling wear, strong gloss.
8.5-9.0 Very Fine/Near Mint- - minor wear, maybe one small spine tick, still glossy.
7.0-8.0 Fine/Very Fine - light-to-moderate handling wear, a few small spine stress marks.
5.5-6.5 Fine - noticeable wear, small creases, possibly a tiny tear, less gloss.
4.0-5.0 Very Good/Fine - well-read copy: multiple small defects, creasing, some soiling.
2.5-3.5 Good/Very Good - heavier wear, larger creases, maybe tape or a small piece missing.
1.0-2.0 Fair/Good - major defects: significant tears, heavy soiling, writing, discoloration.
0.5 Poor - incomplete or falling apart, barely holds together.

What to look for, in rough order of impact: corners (sharp/square vs. blunted, rounded,
or creased); spine (stress lines/ticks, spine roll, splits); cover gloss and color
(bright/reflective vs. faded or dull); creases and folds (especially diagonal "stress"
creases); tears and missing pieces (edge tears, cut-out coupons or pages); staples (rust,
popped/detached, migration through the spine); staining or damage (water damage, foxing,
mold); writing, stamps, or price stickers (owner names, library stamps - all reduce
grade); centerfold condition (usually not visible from a cover photo alone).

Be honest about the limits of grading from a single cover photo: only the visible
surface can be assessed (front cover, and spine/corners if in frame) - interior page
condition, centerfold detachment, odor, and back-cover condition usually can't be judged
this way. Treat your result as a rough estimate, not a certified grade equivalent to
in-hand or professional (CGC/CBCS) inspection. When evidence is ambiguous or photo
quality is poor, prefer a wider/lower estimate over false precision, and say so in
`grading_notes`. If the copy isn't visible clearly enough to judge at all, return null
for numeric_grade and condition_grade rather than guessing. Respond only with the
structured data described by the schema - do not add commentary outside the schema.\
"""

GRADE_SCHEMA = {
    "type": "object",
    "properties": {
        "condition_grade": {
            "type": ["string", "null"],
            "description": "Brief condition assessment, e.g. 'Near Mint', 'Very Fine', 'Good - spine wear, corner crease'. Null if not assessable from this photo.",
        },
        "numeric_grade": {
            "type": ["number", "null"],
            "description": "Estimated condition on the comic-industry 0.5-10.0 scale. Null if not assessable from this photo.",
        },
        "grading_notes": {
            "type": ["string", "null"],
            "description": "The specific wear observed that informed this grade (corners, spine, gloss, creases, tears, staining, etc.), or why grading wasn't possible. Null if nothing notable.",
        },
    },
    "required": ["condition_grade", "numeric_grade", "grading_notes"],
    "additionalProperties": False,
}


def assess_grade(
    thumb_path: Path,
    client: "anthropic.Anthropic",
    model: str = config.CLAUDE_MODEL,
) -> tuple[dict, str]:
    """Re-grade a comic's condition only, leaving series/issue/year/etc untouched."""
    return _call_vision(
        thumb_path,
        client,
        model,
        GRADING_SYSTEM_PROMPT,
        GRADE_SCHEMA,
        "Assess this comic book's condition from its cover photo.",
        # this is a manual, one-off action (not run on every import), so it's
        # worth spending more reasoning effort for a better-calibrated grade
        effort="medium",
    )


CROP_SYSTEM_PROMPT = """\
You are precisely locating a comic book cover within a photo so it can be cropped and
straightened. The photo is an ordinary hand-taken picture - it usually shows background
(a table, hand, other comics, etc.) around the comic, and is rarely perfectly level.

Work through this in order:

1. Find the comic's front cover in the photo. If more than one comic is visible (e.g. a
   stack or pile), focus on whichever one is most prominent/fully in frame - the one that
   was clearly intended to be scanned - and ignore the others entirely.
2. Identify the cover's four edges. Use the comic's own physical edges (the paper's cut
   edges), not the printed border/artwork inside the page, and not a hand, finger, table
   edge, glare, or shadow that might be mistaken for an edge.
3. Determine `rotation_degrees`: the clockwise rotation needed so the cover's edges are
   perfectly horizontal/vertical (0 if already level). Typically small, between -45 and
   45 degrees for a hand-held photo, but can occasionally be larger - trust what you see
   over what's "typical".
4. Now imagine the photo rotated by that amount. In *that rotated frame*, the image's
   width and height change from the original (rotating a rectangle grows its bounding
   box) - do not reuse the original photo's width/height. Within this rotated frame,
   express `crop_left`, `crop_top`, `crop_width`, and `crop_height` as fractions (0.0-1.0)
   of the *rotated* frame's own width/height, forming the tightest possible box that
   contains the entire cover and nothing else.
5. Double-check before answering: does the box touch or clip any edge of the comic
   itself? Widen it slightly. Does it include a visible sliver of background, a finger,
   or another object? Tighten it. Precision here matters more than speed - a box that's
   off by a few percent produces a visibly crooked or clipped crop.

If the comic already fills the frame edge-to-edge and is already level, use rotation 0,
crop_left 0, crop_top 0, crop_width 1.0, crop_height 1.0 rather than leaving fields null -
always give your best estimate for all five fields, even a rough one.\
"""

CROP_SCHEMA = {
    "type": "object",
    "properties": {
        "rotation_degrees": {
            "type": "number",
            "description": "Clockwise rotation in degrees needed to straighten the comic in this photo. Typically between -45 and 45. Use 0 if already straight.",
        },
        "crop_left": {
            "type": "number",
            "description": "Left edge of the comic book cover as a fraction (0.0-1.0) of the image's width AFTER applying rotation_degrees - i.e. of the rotated frame, not the original photo.",
        },
        "crop_top": {
            "type": "number",
            "description": "Top edge of the comic book cover as a fraction (0.0-1.0) of the image's height AFTER applying rotation_degrees.",
        },
        "crop_width": {
            "type": "number",
            "description": "Width of the comic book cover as a fraction (0.0-1.0) of the rotated frame's width. Use 1.0 if it fills the full width.",
        },
        "crop_height": {
            "type": "number",
            "description": "Height of the comic book cover as a fraction (0.0-1.0) of the rotated frame's height. Use 1.0 if it fills the full height.",
        },
    },
    "required": ["rotation_degrees", "crop_left", "crop_top", "crop_width", "crop_height"],
    "additionalProperties": False,
}


def estimate_crop(
    thumb_path: Path,
    client: "anthropic.Anthropic",
    model: str = config.CLAUDE_MODEL,
) -> tuple[dict, str]:
    """Re-estimate crop/rotation only, leaving identification and grading untouched."""
    return _call_vision(
        thumb_path,
        client,
        model,
        CROP_SYSTEM_PROMPT,
        CROP_SCHEMA,
        "Locate this comic book's cover in the photo for cropping and straightening.",
        # manual, one-off action - worth the extra reasoning for a tighter crop
        effort="medium",
    )
