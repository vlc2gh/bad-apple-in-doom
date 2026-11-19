"""Measure A/V sync of a DOSBox capture against the original badapple.mp4.

Audio: cross-correlate capture audio envelope with the original track (per window) to
get the capture-time of original t=0 and check that the chunk seams don't drift.
Video: mean brightness per captured frame vs the original video's brightness curve.
"""
import subprocess, sys, os, glob
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
cap = sys.argv[1] if len(sys.argv) > 1 else sorted(glob.glob(os.path.join(ROOT, "build", "capture", "*.avi")))[-1]
SR = 11025

def audio(path, extra=()):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, *extra, "-vn", "-ac", "1", "-ar", str(SR),
                          "-f", "f32le", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32)

def bright(path, w=32, h=20):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-vf", f"fps=70,scale={w}:{h},format=gray",
                          "-f", "rawvideo", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(-1, h * w).mean(1)

a_cap, a_org = audio(cap), audio(os.path.join(ROOT, "badapple.mp4"))
print(f"capture {cap}: {len(a_cap)/SR:.1f}s audio")

def env(x, hop=110):   # 100 Hz energy envelope
    n = len(x) // hop
    return np.sqrt((x[:n * hop].reshape(n, hop) ** 2).mean(1))

ec, eo = env(a_cap), env(a_org)
ec = (ec - ec.mean()) / (ec.std() + 1e-9)
def best_offset(seg_start_s, seg_len_s=8):
    """capture time where original second `seg_start_s` is heard"""
    s0 = int(seg_start_s * 100); seg = eo[s0:s0 + seg_len_s * 100]
    seg = (seg - seg.mean()) / (seg.std() + 1e-9)
    c = np.correlate(ec, seg, "valid") / len(seg)
    k = int(c.argmax())
    return k / 100 - seg_start_s, c[k]

print("audio: offset (capture_t - original_t) at several points:")
for t in [5, 20, 40, 55, 62, 70, 80, 95]:
    if t * 100 + 800 < len(eo):
        off, score = best_offset(t)
        if off + t + 8 < len(ec) / 100:
            print(f"  orig {t:3d}s -> offset {off:7.3f}s  (corr {score:.2f})")

# video brightness
bc = bright(cap)
bo = bright(os.path.join(ROOT, "badapple.mp4"))
def vnorm(x): return (x - x.mean()) / (x.std() + 1e-9)
print("video: offset (capture_t - original_t):")
for t in [10, 30, 50, 70, 90]:
    s0 = int(t * 70); seg = bo[s0:s0 + 8 * 70]
    if len(seg) < 8 * 70: continue
    seg = vnorm(seg)
    c = np.correlate(vnorm(bc), seg, "valid") / len(seg)
    if len(c) == 0: continue
    k = int(c.argmax())
    print(f"  orig {t:3d}s -> offset {k/70 - t:7.3f}s  (corr {c[k]:.2f})")
