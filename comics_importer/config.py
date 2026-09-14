FULL_MAX_DIMENSION = 2000  # px, longest edge, optimized full image
FULL_JPEG_QUALITY = 85

THUMB_MAX_DIMENSION = 1024  # px, longest edge, Claude-vision thumbnail
THUMB_JPEG_QUALITY = 85

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
