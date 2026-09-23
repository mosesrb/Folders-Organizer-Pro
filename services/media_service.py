"""Media conversion and optimization services.

Handles audio (MP3->WAV), document (PDF compression), and image optimization.
Resolves FOP-AUD-005 by allocating collision-safe unique destinations and using
atomic temporary writes so existing outputs are never overwritten.
"""

import os
import uuid
import wave
from pathlib import Path
from typing import Optional, Tuple

import miniaudio
from PIL import Image
from pypdf import PdfReader, PdfWriter

from .file_service import allocate_unique_destination

# FOP-AUD-008: Bounded resource limits and explicit format restrictions
MAX_IMAGE_PIXELS = 100_000_000
MAX_IMAGE_DIMENSION = 16384
ALLOWED_IMAGE_FORMATS = ["JPEG", "PNG", "WEBP", "BMP", "TIFF", "GIF"]

Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS


def convert_mp3_to_wav(input_path: str, progress_callback) -> Tuple[Optional[str], Optional[str]]:
    """Converts MP3 to WAV using miniaudio (no ffmpeg needed).
    Returns (dst_path, error_message) — exactly one of which is None."""
    src = Path(input_path)
    intended_dst = src.with_suffix('.wav')
    dst = allocate_unique_destination(intended_dst)
    tmp_dst = dst.parent / f".tmp_{uuid.uuid4().hex[:8]}_{dst.name}"

    try:
        # Decode MP3
        decoded = miniaudio.decode_file(str(src))

        # Write WAV to temporary destination
        with wave.open(str(tmp_dst), 'wb') as wav_file:
            wav_file.setnchannels(decoded.nchannels)
            wav_file.setsampwidth(2)  # 16-bit PCM
            wav_file.setframerate(decoded.sample_rate)
            wav_file.writeframes(decoded.samples)

        # Atomically promote temporary file to final unique destination
        os.replace(str(tmp_dst), str(dst))
        return str(dst), None
    except Exception as e:
        if tmp_dst.exists():
            try:
                tmp_dst.unlink()
            except OSError:
                pass
        return None, f"{src.name}: {e}"


def compress_pdf(input_path: str, progress_callback) -> Tuple[Optional[str], Optional[str]]:
    """Compresses PDF by optimizing content streams and removing duplicates.
    Returns (dst_path, error_message) — exactly one of which is None."""
    src = Path(input_path)
    intended_dst = src.parent / f"{src.stem}_compressed.pdf"
    dst = allocate_unique_destination(intended_dst)
    tmp_dst = dst.parent / f".tmp_{uuid.uuid4().hex[:8]}_{dst.name}"

    try:
        reader = PdfReader(str(src))
        writer = PdfWriter()

        for page in reader.pages:
            writer.add_page(page)

        # Apply compression
        for page in writer.pages:
            page.compress_content_streams()

        with open(tmp_dst, "wb") as f:
            writer.write(f)

        # Atomically promote temporary file to final unique destination
        os.replace(str(tmp_dst), str(dst))
        return str(dst), None
    except Exception as e:
        if tmp_dst.exists():
            try:
                tmp_dst.unlink()
            except OSError:
                pass
        return None, f"{src.name}: {e}"


def optimize_image(input_path: str, quality: int, progress_callback) -> Tuple[Optional[str], Optional[str]]:
    """Optimizes image size using Pillow.
    Returns (dst_path, error_message) — exactly one of which is None."""
    src = Path(input_path)
    intended_dst = src.parent / f"{src.stem}_optimized{src.suffix}"
    dst = allocate_unique_destination(intended_dst)
    tmp_dst = dst.parent / f".tmp_{uuid.uuid4().hex[:8]}_{dst.name}"

    try:
        with Image.open(src, formats=ALLOWED_IMAGE_FORMATS) as img:
            width, height = img.size
            if width > MAX_IMAGE_DIMENSION or height > MAX_IMAGE_DIMENSION:
                raise ValueError(
                    f"Image dimensions ({width}x{height}) exceed maximum allowed dimension of {MAX_IMAGE_DIMENSION}px"
                )
            if width * height > MAX_IMAGE_PIXELS:
                raise ValueError(
                    f"Image pixel count ({width * height}) exceeds maximum allowed limit of {MAX_IMAGE_PIXELS} pixels"
                )

            # Convert to RGB if saving as JPEG to avoid transparency issues
            if src.suffix.lower() in ['.jpg', '.jpeg'] and img.mode in ("RGBA", "P"):
                img = img.convert("RGB")

            img.save(tmp_dst, optimize=True, quality=quality)

        # Atomically promote temporary file to final unique destination
        os.replace(str(tmp_dst), str(dst))
        return str(dst), None
    except Exception as e:
        if tmp_dst.exists():
            try:
                tmp_dst.unlink()
            except OSError:
                pass
        return None, f"{src.name}: {e}"
