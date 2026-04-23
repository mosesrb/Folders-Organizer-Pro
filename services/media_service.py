import os
import miniaudio
import wave
from pathlib import Path
from pypdf import PdfReader, PdfWriter
from PIL import Image

def convert_mp3_to_wav(input_path: str, progress_callback):
    """Converts MP3 to WAV using miniaudio (no ffmpeg needed)."""
    src = Path(input_path)
    dst = src.with_suffix('.wav')
    
    if dst.exists():
        dst = src.parent / f"{src.stem}_{int(os.path.getmtime(input_path))}.wav"

    try:
        # Decode MP3
        decoded = miniaudio.decode_file(str(src))
        
        # Write WAV
        with wave.open(str(dst), 'wb') as wav_file:
            wav_file.setnchannels(decoded.nchannels)
            wav_file.setsampwidth(2) # miniaudio decode_file usually returns 16-bit PCM
            wav_file.setframerate(decoded.sample_rate)
            wav_file.writeframes(decoded.samples)
            
        return str(dst)
    except Exception as e:
        print(f"Failed to convert {src.name}: {e}")
        return None

def compress_pdf(input_path: str, progress_callback):
    """Compresses PDF by optimizing content streams and removing duplicates."""
    src = Path(input_path)
    dst = src.parent / f"{src.stem}_compressed.pdf"
    
    if dst.exists():
        dst = src.parent / f"{src.stem}_compressed_{int(os.path.getmtime(input_path))}.pdf"
    
    try:
        reader = PdfReader(str(src))
        writer = PdfWriter()
        
        for page in reader.pages:
            writer.add_page(page)
            
        # Apply compression
        for page in writer.pages:
            page.compress_content_streams() # This is where the magic happens
            
        with open(dst, "wb") as f:
            writer.write(f)
            
        return str(dst)
    except Exception as e:
        print(f"Failed to compress {src.name}: {e}")
        return None

def optimize_image(input_path: str, quality: int, progress_callback):
    """Optimizes image size using Pillow."""
    src = Path(input_path)
    # We create a copy to avoid overwriting original immediately
    dst = src.parent / f"{src.stem}_optimized{src.suffix}"
    
    if dst.exists():
        dst = src.parent / f"{src.stem}_optimized_{int(os.path.getmtime(input_path))}{src.suffix}"
    
    try:
        with Image.open(src) as img:
            # Convert to RGB if saving as JPEG to avoid transparency issues
            if src.suffix.lower() in ['.jpg', '.jpeg'] and img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
                
            img.save(dst, optimize=True, quality=quality)
            
        return str(dst)
    except Exception as e:
        print(f"Failed to optimize {src.name}: {e}")
        return None
