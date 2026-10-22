"""Validation shared by cover images and CKEditor inline uploads.

Both paths accept real images only. The browser-supplied content type is
treated as a hint, never as proof: Pillow has to decode the file, and the
extension, detected format, pixel count and byte size all have to agree with
our allow-list.
"""

from __future__ import annotations

from pathlib import Path

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from PIL import Image, UnidentifiedImageError

MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_IMAGE_DIMENSION = 6000
MAX_IMAGE_PIXELS = 24_000_000
ALLOWED_IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp", ".gif")
ALLOWED_IMAGE_FORMATS = {"JPEG", "PNG", "WEBP", "GIF"}
ALLOWED_CONTENT_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/gif",
}


def validate_cover_image(file):
    """Reject oversized, mislabelled or undecodable image uploads."""

    if not file:
        return

    if getattr(file, "size", 0) > MAX_IMAGE_BYTES:
        raise ValidationError(
            _("Images must be 5 MB or smaller."),
            code="image_too_large",
        )

    suffix = Path(getattr(file, "name", "")).suffix.lower()
    if suffix not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValidationError(
            _("Use a JPG, PNG, WEBP or GIF image."),
            code="image_extension",
        )

    content_type = (getattr(file, "content_type", "") or "").lower()
    if content_type and content_type not in ALLOWED_CONTENT_TYPES:
        raise ValidationError(
            _("That file does not look like an image."),
            code="image_content_type",
        )

    try:
        file.seek(0)
        with Image.open(file) as image:
            image.verify()
    except (
        UnidentifiedImageError,
        OSError,
        ValueError,
        SyntaxError,
        Image.DecompressionBombError,
    ):
        raise ValidationError(
            _("That file could not be read as an image."),
            code="invalid_image",
        ) from None
    finally:
        file.seek(0)

    try:
        file.seek(0)
        with Image.open(file) as image:
            image_format = (image.format or "").upper()
            width, height = image.size
    except (
        UnidentifiedImageError,
        OSError,
        ValueError,
        SyntaxError,
        Image.DecompressionBombError,
    ):
        raise ValidationError(
            _("That file could not be read as an image."),
            code="invalid_image",
        ) from None
    finally:
        file.seek(0)

    if image_format not in ALLOWED_IMAGE_FORMATS:
        raise ValidationError(
            _("Use a JPG, PNG, WEBP or GIF image."),
            code="image_format",
        )

    if width > MAX_IMAGE_DIMENSION or height > MAX_IMAGE_DIMENSION:
        raise ValidationError(
            _("Images must be %(max)s pixels or smaller on each side."),
            code="image_dimensions",
            params={"max": MAX_IMAGE_DIMENSION},
        )

    if width * height > MAX_IMAGE_PIXELS:
        raise ValidationError(
            _("That image has too many pixels. Please resize it first."),
            code="image_pixel_count",
        )
