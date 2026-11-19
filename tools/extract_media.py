"""Turn badapple.mp4 into the raw inputs for build_wad.py.

  build/frames_64x82.gray   64x82 8-bit gray frames at 35 fps (one per DOOM tic)
  build/audio_11025_u8.raw  mono 11025 Hz unsigned 8-bit PCM (DMX sound format)
"""
import os, subprocess
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "badapple.mp4")
BUILD = os.path.join(ROOT, "build")
os.makedirs(BUILD, exist_ok=True)

# video: area downscale straight to the wall resolution, one frame per tic
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", SRC,
                "-vf", "fps=35,scale=64:82:flags=area,format=gray",
                "-f", "rawvideo", os.path.join(BUILD, "frames_64x82.gray")], check=True)

# audio: mono 11025 Hz float, normalised so only the very loudest peaks clip, then 8-bit
raw = subprocess.run(["ffmpeg", "-v", "error", "-i", SRC, "-vn", "-ac", "1", "-ar", "11025",
                      "-f", "f32le", "-"], capture_output=True, check=True).stdout
pcm = np.frombuffer(raw, np.float32).astype(np.float64)
gain = 127 / np.percentile(np.abs(pcm), 99.999)
u8 = np.clip(np.rint(pcm * gain) + 128, 0, 255).astype(np.uint8)
u8.tofile(os.path.join(BUILD, "audio_11025_u8.raw"))
print(f"frames + {len(u8) / 11025:.2f}s of audio written to {BUILD}")
