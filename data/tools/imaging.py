"""Scan simulation, tampering, blur and procedural photos."""
import io
import os
import subprocess
import tempfile
import random
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
import img2pdf
from pypdf import PdfReader, PdfWriter

DPI = 150
SCALE = DPI / 72.0
FONT_TAMPER = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


def pdf_to_image(pdf_path, dpi=DPI):
    with tempfile.TemporaryDirectory() as td:
        out = os.path.join(td, "p")
        subprocess.run(["pdftoppm", "-r", str(dpi), "-png", "-singlefile", pdf_path, out], check=True)
        return Image.open(out + ".png").convert("RGB")


def image_to_pdf(img, pdf_path, quality, producer, creation=None, mod=None, title=None):
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=quality)
    layout = img2pdf.get_fixed_dpi_layout_fun((DPI, DPI))
    pdf_bytes = img2pdf.convert(buf.getvalue(), layout_fun=layout)
    set_meta(pdf_bytes, pdf_path, producer, creation, mod, title)


def jpeg_bytes_to_pdf(jpeg_bytes, pdf_path, producer, creation=None, mod=None, title=None):
    layout = img2pdf.get_fixed_dpi_layout_fun((DPI, DPI))
    pdf_bytes = img2pdf.convert(jpeg_bytes, layout_fun=layout)
    set_meta(pdf_bytes, pdf_path, producer, creation, mod, title)


def pdf_date(iso, hh="10", mm="30"):
    y, m, d = iso.split("-")
    return f"D:{y}{m}{d}{hh}{mm}00+05'30'"


def set_meta(pdf_bytes, pdf_path, producer, creation=None, mod=None, title=None):
    r = PdfReader(io.BytesIO(pdf_bytes))
    w = PdfWriter()
    for p in r.pages:
        w.add_page(p)
    meta = {"/Producer": producer, "/Creator": producer}
    if creation:
        meta["/CreationDate"] = pdf_date(creation)
    if mod:
        meta["/ModDate"] = pdf_date(mod, "18", "05")
    if title:
        meta["/Title"] = title
    w.add_metadata(meta)
    with open(pdf_path, "wb") as f:
        w.write(f)


def restamp_pdf_meta(pdf_path, producer, creation, mod=None):
    with open(pdf_path, "rb") as f:
        b = f.read()
    set_meta(b, pdf_path, producer, creation, mod or creation)


def scanify(img, rng, angle=None, noise=6, blur=0.0):
    """Make a clean render look like a photocopy/scan."""
    angle = angle if angle is not None else rng.uniform(-0.9, 0.9)
    img = img.convert("L")
    img = img.rotate(angle, resample=Image.BICUBIC, expand=False, fillcolor=255)
    arr = np.asarray(img).astype(np.float32)
    nrng = np.random.default_rng(rng.randint(0, 10**6))
    arr = arr * 0.93 + 10 + nrng.normal(0, noise, arr.shape)
    # slight uneven illumination
    h, w = arr.shape
    grad = np.linspace(0, 12, w)[None, :]
    arr = np.clip(arr - grad, 0, 255).astype(np.uint8)
    img = Image.fromarray(arr).convert("RGB")
    if blur:
        img = img.filter(ImageFilter.GaussianBlur(blur))
    return img


def scan_pdf(src_pdf, dst_pdf, rng, producer="HP ScanJet Pro 3000 s4", created=None, blur=0.0,
             quality=78, downscale=None):
    img = pdf_to_image(src_pdf)
    img = scanify(img, rng, blur=blur)
    if downscale:
        w, h = img.size
        img = img.resize((int(w * downscale), int(h * downscale)), Image.BILINEAR).resize((w, h), Image.BILINEAR)
    image_to_pdf(img, dst_pdf, quality, producer, created, created)


def tamper_date(src_pdf, dst_pdf, rng, bbox_pt, new_text, created, modified,
                producer="Adobe Photoshop 25.1 (Windows)"):
    """Classic edited-scan: scan saved at low JPEG quality, region repainted, saved again at high
    quality. Untouched areas are double-compressed; the edited patch is single-compressed, which
    Error Level Analysis exposes. Returns the tampered region bbox in PDF points."""
    img = scanify(pdf_to_image(src_pdf), rng, angle=0.0, noise=5)
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=55)
    img = Image.open(io.BytesIO(buf.getvalue())).convert("RGB")
    x0, y0, x1, y1 = [v * SCALE for v in bbox_pt]
    pad = 4
    region = (int(x0 - pad), int(y0 - pad), int(x1 + 40), int(y1 + pad))
    # clone-stamp blank paper from the right margin over the old value, then type the new one
    w, h = region[2] - region[0], region[3] - region[1]
    patch = img.crop((region[0] + 260, region[1] - 60, region[0] + 260 + w, region[1] - 60 + h))
    img.paste(patch, region[:2])
    dr = ImageDraw.Draw(img)
    font = ImageFont.truetype(FONT_TAMPER, int(10.5 * SCALE))
    dr.text((x0, y0 - 1), new_text, fill=(18, 18, 18), font=font)
    out = io.BytesIO()
    img.save(out, "JPEG", quality=98)
    jpeg_bytes_to_pdf(out.getvalue(), dst_pdf, producer, created, modified)
    return [round(v / SCALE, 1) for v in region]


# ---------------------------------------------------------------------------
# Procedural placeholder photos (replace with real campus photos if you have them)
# ---------------------------------------------------------------------------
def _room(rng, W, H, wall, floor):
    img = Image.new("RGB", (W, H), wall)
    d = ImageDraw.Draw(img)
    horizon = int(H * rng.uniform(0.32, 0.58))
    tilt = rng.randint(-90, 90)
    d.polygon([(0, horizon + tilt), (W, horizon - tilt), (W, H), (0, H)], fill=floor)
    for i in range(-10, 30):
        x = i * W // rng.choice([10, 14, 18])
        d.line([(W // 2 + (x - W // 2) * 0.25, horizon), (x, H)], fill=tuple(max(0, c - 18) for c in floor), width=1)
    # windows / posters / cabinets with random placement
    for k in range(rng.randint(1, 4)):
        wx = rng.randint(10, W - 260)
        ww = rng.randint(120, 250)
        top = rng.randint(30, 90)
        d.rectangle([wx, top, wx + ww, max(top + 60, horizon - rng.randint(40, 110))],
                    fill=(rng.randint(170, 215), rng.randint(200, 235), rng.randint(220, 250)),
                    outline=(110, 110, 110), width=4)
    for k in range(rng.randint(1, 3)):
        px = rng.randint(10, W - 120)
        d.rectangle([px, rng.randint(120, 200), px + rng.randint(60, 110), rng.randint(220, 300)],
                    fill=(rng.randint(60, 230), rng.randint(60, 230), rng.randint(60, 230)))
    if rng.random() < 0.6:
        cx = rng.choice([0, W - 140])
        d.rectangle([cx, horizon - 160, cx + 140, horizon + 120], fill=(rng.randint(90, 160), rng.randint(90, 140), rng.randint(70, 120)))
    for k in range(rng.randint(2, 5)):
        lx = rng.randint(60, W - 60)
        d.rectangle([lx - 60, 8, lx + 60, 20], fill=(250, 250, 235))
    return img, d, horizon


def _finish(img, rng, path):
    if rng.random() < 0.5:
        img = img.transpose(Image.FLIP_LEFT_RIGHT)
    arr = np.asarray(img).astype(np.float32)
    # uneven lighting: smooth random field -> distinct low-frequency signature per photo
    nrng = np.random.default_rng(rng.randint(0, 10**6))
    field = Image.fromarray(((nrng.random((4, 4)) - 0.5) * 2 * 60 + 128).astype(np.uint8)).resize(
        (img.size[0], img.size[1]), Image.BICUBIC)
    arr = arr + (np.asarray(field).astype(np.float32) - 128)[:, :, None]
    arr += np.random.default_rng(rng.randint(0, 10**6)).normal(0, 7, arr.shape)
    img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.6))
    img.save(path, "JPEG", quality=88)


def lab_photo(path, rng, rows=4, per_row=6):
    W, H = 1280, 853
    wall = (rng.randint(150, 240), rng.randint(150, 235), rng.randint(140, 225))
    floor = (rng.randint(90, 190), rng.randint(80, 170), rng.randint(70, 150))
    img, d, hz = _room(rng, W, H, wall, floor)
    shift = rng.randint(-220, 220)
    desk = (rng.randint(90, 170), rng.randint(60, 120), rng.randint(40, 90))
    for r in range(rows):
        t = (r + 1) / rows
        y = int(hz + 30 + t * (H - hz - 80))
        scale = 0.45 + 0.6 * t
        dw, mw, mh = int(1000 * scale), int(70 * scale), int(52 * scale)
        x0 = (W - dw) // 2 + int(shift * t)
        d.rectangle([x0, y, x0 + dw, y + int(16 * scale)], fill=desk)
        for k in range(per_row):
            mx = x0 + int((k + 0.5) * dw / per_row) - mw // 2
            d.rectangle([mx, y - mh - int(8 * scale), mx + mw, y - int(8 * scale)], fill=(25, 25, 28))
            d.rectangle([mx + 3, y - mh - int(5 * scale), mx + mw - 3, y - int(11 * scale)],
                        fill=(rng.randint(40, 80), rng.randint(110, 160), rng.randint(190, 235)))
            d.rectangle([mx + mw // 2 - 3, y - int(8 * scale), mx + mw // 2 + 3, y], fill=(40, 40, 40))
    _finish(img, rng, path)
    return rows * per_row


def classroom_photo(path, rng):
    W, H = 1280, 853
    wall = (rng.randint(170, 245), rng.randint(170, 240), rng.randint(160, 225))
    floor = (rng.randint(110, 195), rng.randint(100, 180), rng.randint(90, 155))
    img, d, hz = _room(rng, W, H, wall, floor)
    bx = W // 2 + rng.randint(-250, 250)
    d.rectangle([bx - 260, 90, bx + 260, max(150, hz - 40)], fill=(30, 60, 45), outline=(90, 70, 50), width=8)
    shift = rng.randint(-200, 200)
    for r in range(5):
        t = (r + 1) / 5
        y = int(hz + 20 + t * (H - hz - 60))
        scale = 0.4 + 0.65 * t
        for k in range(4):
            bw = int(190 * scale)
            x = int(W / 2 + shift * t + (k - 1.5) * bw * 1.35) - bw // 2
            d.rectangle([x, y, x + bw, y + int(14 * scale)], fill=(140, 95, 60))
            d.rectangle([x + 6, y + int(14 * scale), x + 12, y + int(40 * scale)], fill=(70, 70, 70))
            d.rectangle([x + bw - 12, y + int(14 * scale), x + bw - 6, y + int(40 * scale)], fill=(70, 70, 70))
    _finish(img, rng, path)


def disguise_duplicate(src, dst):
    """Reuse another college's photo with light edits (resize, crop, brighten)."""
    img = Image.open(src).convert("RGB")
    w, h = img.size
    img = img.crop((int(w * 0.02), int(h * 0.015), int(w * 0.99), int(h * 0.985)))
    img = img.resize((1100, int(1100 * img.size[1] / img.size[0])), Image.LANCZOS)
    img = ImageEnhance.Brightness(img).enhance(1.12)
    img.save(dst, "JPEG", quality=84)
