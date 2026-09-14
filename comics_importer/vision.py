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


def identify_metadata(
    thumb_path: Path,
    client: "anthropic.Anthropic",
    model: str = config.CLAUDE_MODEL,
) -> tuple[dict, str]:
    image_b64 = base64.standard_b64encode(thumb_path.read_bytes()).decode("utf-8")

    try:
        response = client.messages.create(
            model=model,
            max_tokens=config.CLAUDE_MAX_TOKENS,
            system=SYSTEM_PROMPT,
            output_config={
                "format": {"type": "json_schema", "schema": COMIC_METADATA_SCHEMA},
                "effort": "low",
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
                        {"type": "text", "text": "Identify this comic book from its cover photo."},
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
        metadata = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise VisionAPIError(f"Claude response was not valid JSON: {exc}") from exc

    return metadata, raw_text
