from __future__ import annotations

import io
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError

# Profile pictures, handled defensively:
#   * hard byte cap before decoding (helps against decompression bombs, with
#     Pillow's own MAX_IMAGE_PIXELS as the second layer);
#   * the upload must actually decode as an image;
#   * we NEVER store or serve the client's bytes — the image is re-encoded to a
#     fresh, fixed-size PNG (strips EXIF/GPS metadata and any smuggled payload);
#   * files live under data/avatars/<user_id>.png — the id comes from the session,
#     never from client input, so there's no path to traverse.

MAX_UPLOAD_BYTES = 2 * 1024 * 1024  # 2MB is plenty for a source selfie
AVATAR_SIZE = 256
BACKEND_ROOT = Path(__file__).resolve().parents[2]
AVATARS_DIR = BACKEND_ROOT / "data" / "avatars"

# Cap total decoded pixels (Pillow raises DecompressionBombError beyond this).
Image.MAX_IMAGE_PIXELS = 40_000_000


def avatar_path(user_id: int) -> Path:
    return AVATARS_DIR / f"{int(user_id)}.png"


def save_avatar(user_id: int, raw: bytes) -> Path:
    """Validate + re-encode an uploaded image into the user's avatar PNG."""
    if not raw:
        raise ValueError("Empty upload.")
    if len(raw) > MAX_UPLOAD_BYTES:
        raise ValueError("Image too large — keep it under 2MB.")

    try:
        with Image.open(io.BytesIO(raw)) as image:
            image.load()  # force a full decode; malformed files fail here
            # Honor camera rotation, drop alpha->RGB where needed, square-crop + resize.
            image = ImageOps.exif_transpose(image)
            image = image.convert("RGBA")
            image = ImageOps.fit(image, (AVATAR_SIZE, AVATAR_SIZE))
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, ValueError) as error:
        raise ValueError("That file doesn't look like a usable image.") from error

    AVATARS_DIR.mkdir(parents=True, exist_ok=True)
    destination = avatar_path(user_id)
    image.save(destination, format="PNG", optimize=True)
    return destination


def delete_avatar(user_id: int) -> bool:
    path = avatar_path(user_id)
    if path.is_file():
        path.unlink()
        return True
    return False
