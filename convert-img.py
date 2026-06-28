from PIL import Image, ImageFilter
from typing import List, Tuple, Optional
import os

# ===== Default tuning knobs (apply to all images unless overridden below) =====
DEFAULT_W            = 160   # canvas width in pixels
DEFAULT_MERGE_TOL    = 25    # Manhattan color distance for run-length merging
DEFAULT_PALETTE_SIZE = 32    # global palette colors

# ===== Per-image overrides =====
# Key = PNG filename without extension.
# Specify W or H (not both) — the other is computed from the aspect ratio.
# Omit either to use the defaults above.
IMAGE_CONFIG = {
    "example": {"H": 220, "MERGE_TOL": 30, "PALETTE_SIZE": 64},
    "Foresia2": {"H": 200, "MERGE_TOL": 20, "PALETTE_SIZE": 64}
}

# ============================================================
RESAMPLE = Image.LANCZOS
FLIP_Y   = True
CHARS    = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"

def to_base62(n: int, length: int = 5) -> str:
    s = ""
    for _ in range(length):
        s = CHARS[n % 62] + s
        n //= 62
    return s

def build_palette(img_rgb: Image.Image, palette_size: int) -> List[Tuple[int, int, int]]:
    pal_img = img_rgb.convert("P", palette=Image.ADAPTIVE, colors=palette_size)
    raw = pal_img.getpalette() or []
    raw = raw + [0] * max(0, palette_size * 3 - len(raw))
    return [(raw[i * 3], raw[i * 3 + 1], raw[i * 3 + 2]) for i in range(palette_size)]

def encode_image(
    img: Image.Image,
    target_w: Optional[int] = None,
    target_h: Optional[int] = None,
    merge_tol: int = DEFAULT_MERGE_TOL,
    palette_size: int = DEFAULT_PALETTE_SIZE,
) -> Tuple[str, int, int, int, List[Tuple[int, int, int]]]:
    img = img.convert("RGBA").filter(ImageFilter.SHARPEN)
    src_w, src_h = img.size

    # Compute canvas dimensions from whichever axis was pinned
    if target_h is not None:
        W = max(1, int(round(src_w * target_h / src_h)))
        h = target_h
    else:
        W = target_w if target_w is not None else DEFAULT_W
        h = max(1, int(round(src_h * W / src_w)))

    # n overflow guard: max encodable h for this W and palette_size
    max_h = int(62 ** 5 / (W ** 2 * palette_size))
    if h > max_h:
        ratio = src_h / src_w
        W = max(1, int((62 ** 5 / (ratio * palette_size)) ** (1 / 3)))
        h = max(1, int(round(src_h * W / src_w)))
        print(f"  WARNING: height exceeded limit; auto-reduced to W={W} H={h}")

    img = img.resize((W, h), RESAMPLE)
    palette = build_palette(img.convert("RGB"), palette_size)

    pal_cycle = (palette * ((256 // palette_size) + 1))[:256]
    pal_flat  = [v for rr, gg, bb in pal_cycle for v in (rr, gg, bb)]
    pal_ref   = Image.new("P", (1, 1))
    pal_ref.putpalette(pal_flat)
    quantized = img.convert("RGB").quantize(palette=pal_ref, dither=0)

    pix_a = img.load()
    pix_q = quantized.load()

    parts: List[str] = []
    run_count = 0
    for y in range(h):
        y_out = (h - 1 - y) if FLIP_Y else y
        x = 0
        while x < W:
            if pix_a[x, y][3] < 8:
                x += 1
                continue
            c0 = pix_q[x, y] % palette_size
            x1 = x
            x += 1
            while x < W:
                if pix_a[x, y][3] < 8:
                    break
                c2 = pix_q[x, y] % palette_size
                if c2 != c0:
                    r0, g0, b0 = palette[c0]
                    r2, g2, b2 = palette[c2]
                    if abs(r2 - r0) + abs(g2 - g0) + abs(b2 - b0) > merge_tol:
                        break
                x += 1
            n = ((x1 * h + y_out) * W + (x - x1 - 1)) * palette_size + c0
            parts.append(to_base62(n, 5))
            run_count += 1

    data = "".join(parts)

    # Decode verification — catches any encoding bugs before writing the loader
    BV = {ord(c): i for i, c in enumerate(CHARS)}
    bad = []
    for si, seg in enumerate(parts):
        nv = 0
        for c in seg:
            nv = nv * 62 + BV[ord(c)]
        c_dec   = nv % palette_size;  nv //= palette_size
        dx1_dec = nv % W;             nv //= W
        y1_dec  = nv % h;             x1_dec = nv // h
        x2_dec  = x1_dec + dx1_dec + 1
        if not (0 <= x1_dec < W and 0 < x2_dec <= W and
                0 <= y1_dec < h and 0 <= c_dec < palette_size):
            bad.append(f"seg[{si}]: x1={x1_dec} x2={x2_dec} y1={y1_dec} c={c_dec} "
                       f"(W={W} H={h} P={palette_size})")
        if len(bad) >= 5:
            bad.append("...(more errors suppressed)")
            break
    if bad:
        raise ValueError("Decode verification failed:\n  " + "\n  ".join(bad))

    return data, run_count, W, h, palette

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    pngs = [f for f in os.listdir(script_dir)
            if f.lower().endswith('.png') and not f.startswith('.')]
    if not pngs:
        print("No PNG files found."); return

    for name in sorted(pngs):
        base = os.path.splitext(name)[0]
        cfg  = IMAGE_CONFIG.get(base, {})

        target_w    = cfg.get("W")
        target_h    = cfg.get("H")
        merge_tol   = cfg.get("MERGE_TOL",    DEFAULT_MERGE_TOL)
        palette_size = cfg.get("PALETTE_SIZE", DEFAULT_PALETTE_SIZE)
        if target_w is None and target_h is None:
            target_w = DEFAULT_W

        with Image.open(os.path.join(script_dir, name)) as im:
            packed, runs, img_w, img_h, palette = encode_image(
                im, target_w, target_h, merge_tol, palette_size)

        out_lua = os.path.join(script_dir, base + "_loader2.lua")
        pal_lua = ", ".join(f"{v/255:.4f}" for color in palette for v in color)
        max_h   = int((62 ** 5 - 1) // (img_w ** 2 * palette_size))

        with open(out_lua, "w", encoding="utf-8") as f:
            f.write("-- Auto-generated by convert-img.py\n")
            f.write("local G = (args and args._G) or _G\n")
            f.write(f"G.img2CanvasW = {img_w}\n")
            f.write(f"G.img2CanvasH = {img_h}\n")
            f.write(f"G.img2PalSz   = {palette_size}\n")
            f.write(f"G.img2Palette = {{{pal_lua}}}\n")
            f.write(f'G.img2Data = "{packed}"\n')

        size_kb = len(packed) / 1024
        dim_src = "W" if target_h is None else "H"
        dim_val = img_w if target_h is None else img_h
        print(f"OK {name} | {img_w}x{img_h} (pinned {dim_src}={dim_val}) | "
              f"tol={merge_tol} | {runs:,} runs | {size_kb:.1f} KB -> {base}_loader2.lua")
        print(f"   verified | max safe H for W={img_w}/PALSZ={palette_size}: {max_h}px")
        if runs > 13000:
            print(f"   WARNING: {runs:,} segs may exceed WoW texture limit (~12,000). "
                  f"Raise MERGE_TOL to ~{merge_tol + 10}.")
        elif size_kb > 200:
            print("   WARNING: Too large -- raise MERGE_TOL or lower W/H")

if __name__ == "__main__":
    main()
