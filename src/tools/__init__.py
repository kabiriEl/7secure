"""Tools package for newsletter pipeline.

Convenience re-exports to help type checkers resolve submodules.
"""

# Re-export commonly used helpers (optional)
try:
    from .image_extractor import extract_best_image_url  # type: ignore
except ImportError:
    pass

try:
    from .ghost_media import download_image, upload_image_to_ghost  # type: ignore
except ImportError:
    pass
