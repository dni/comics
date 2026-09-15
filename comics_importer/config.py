FULL_MAX_DIMENSION = 2000  # px, longest edge, optimized full image
FULL_JPEG_QUALITY = 85

THUMB_MAX_DIMENSION = 1024  # px, longest edge, Claude-vision thumbnail
THUMB_JPEG_QUALITY = 85

# Locating an edge/corner needs far less resolution than reading cover text, so
# the crop-only estimate (comics_importer.vision.estimate_crop) gets its own much
# smaller, contrast-boosted thumbnail - cuts vision tokens roughly 4x vs
# THUMB_MAX_DIMENSION for that call, since Claude's image tokens scale with
# pixel area. Crop/rotation results are fractions of the image, so accuracy
# doesn't depend on the source resolution the way text legibility would.
CROP_THUMB_MAX_DIMENSION = 512
CROP_THUMB_JPEG_QUALITY = 80

CLAUDE_MODEL = "claude-sonnet-5"
CLAUDE_MAX_TOKENS = 1024

# Offered in the frontend's model picker for import/reclassify. Keep in sync
# with whatever's current in Anthropic's lineup - these are the vision-capable
# models worth trading off cost against accuracy for cover identification.
AVAILABLE_MODELS = [
    "claude-opus-4-8",
    "claude-sonnet-5",
    "claude-haiku-4-5",
]

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".heic", ".heif", ".tif", ".tiff", ".bmp", ".webp"}
