"""Sanity checks: the planted signals must be detectable with simple, standard techniques."""
import io, json, os, re, subprocess, sys, tempfile
import numpy as np
import cv2
from PIL import Image, ImageChops
from pypdf import PdfReader
import pytesseract

D = sys.argv[1]
A = os.path.join(D, "applications")


def page_img(pdf, dpi=150):
    with tempfile.TemporaryDirectory() as td:
        subprocess.run(["pdftoppm", "-r", str(dpi), "-png", "-singlefile", pdf, td + "/p"], check=True)
        return Image.open(td + "/p.png").convert("RGB")


def qr(pdf):
    """Robust decode: try several render resolutions (what the backend should do too)."""
    for dpi in (150, 200, 300, 120):
        img = np.array(page_img(pdf, dpi).convert("L"))
        txt, pts, _ = cv2.QRCodeDetector().detectAndDecode(img)
        if txt:
            return txt
    return None


def phash(path, size=32, keep=8):
    img = Image.open(path).convert("L").resize((size, size), Image.LANCZOS)
    dct = cv2.dct(np.asarray(img, dtype=np.float32))[:keep, :keep]
    med = np.median(dct.flatten()[1:])
    return (dct > med).flatten()


def ela_patch_score(pdf, bbox_pt, q=75):
    """Mean ELA error inside bbox vs. the rest of the page text area."""
    r = PdfReader(pdf)
    # embedded JPEG = the scan itself
    img = None
    for name, obj in r.pages[0].images.items() if hasattr(r.pages[0].images, "items") else []:
        pass
    imgs = r.pages[0].images
    raw = imgs[0].data
    orig = Image.open(io.BytesIO(raw)).convert("RGB")
    buf = io.BytesIO()
    orig.save(buf, "JPEG", quality=q)
    re_ = Image.open(io.BytesIO(buf.getvalue())).convert("RGB")
    diff = np.asarray(ImageChops.difference(orig, re_)).astype(np.float32).sum(axis=2)
    s = orig.size[0] / 595.28
    x0, y0, x1, y1 = [int(v * s) for v in bbox_pt]
    inside = diff[y0:y1, x0:x1].mean()
    return inside


ok = True
def check(cond, msg):
    global ok
    print(("PASS " if cond else "FAIL ") + msg)
    ok &= bool(cond)

# 1. text layer on digital docs
t = PdfReader(f"{A}/INST01/documents/fire_noc.pdf").pages[0].extract_text()
check("SPFES/NOC/" in t and "Valid Till" in t, "digital Fire NOC has extractable text layer")

# 2. OCR on scanned deed
ocr = pytesseract.image_to_string(page_img(f"{A}/INST05/documents/land_deed.pdf", 200))
check(re.search(r"2\.00\s*acres", ocr) is not None, f"Tesseract reads INST05 deed land area (found: {re.findall(r'[0-9.]+ ?acres', ocr)})")
ocr_aff = pytesseract.image_to_string(page_img(f"{A}/INST05/documents/affidavit.pdf", 200))
check("3.50 acres" in ocr_aff, "Tesseract reads INST05 affidavit land area 3.50")

# 3. QR decode
q1 = qr(f"{A}/INST01/documents/fire_noc.pdf")
check(q1 and "HOLDER=INST01" in q1, f"INST01 Fire NOC QR decodes: {q1}")
q9 = qr(f"{A}/INST09/documents/fire_noc.pdf")
check(q9 and "HOLDER=INST01" in q9, "INST09 Fire NOC QR points to INST01")
q4 = qr(f"{A}/INST04/documents/fire_noc.pdf")
check(q4 and "VALID_TILL=2026-03-31" in q4, f"INST04 tampered NOC QR still says 2026: {q4}")
q10 = qr(f"{A}/INST10/documents/accreditation_certificate.pdf")
check(not q10, f"INST10 blurry accreditation QR unreadable (got: {q10})")
q2 = qr(f"{A}/INST02/documents/accreditation_certificate.pdf")
check(q2 and "BPAC" in q2, "INST02 accreditation QR decodes")

# 4. ELA
gt = json.load(open(f"{D}/labels/fields_ground_truth.json"))
bb = gt["INST04"]["fire_noc"]["fields"]["valid_till"]["bbox"]
# compare the tampered field against an untouched text field of similar size on the same page
inside = ela_patch_score(f"{A}/INST04/documents/fire_noc.pdf", bb)
ref = ela_patch_score(f"{A}/INST04/documents/fire_noc.pdf", gt["INST04"]["fire_noc"]["fields"]["noc_no"]["bbox"])
check(inside > 1.6 * ref, f"ELA: tampered 'Valid Till' patch {inside:.1f} vs untouched 'NOC No.' patch {ref:.1f}")
f3 = gt["INST03"]["land_deed"]["fields"]
i3 = ela_patch_score(f"{A}/INST03/documents/land_deed.pdf", f3["land_area_acres"]["bbox"])
r3 = ela_patch_score(f"{A}/INST03/documents/land_deed.pdf", f3["deed_no"]["bbox"])
check(i3 < 1.5 * r3, f"ELA: clean scan fields look alike ({i3:.1f} vs {r3:.1f})")

# 5. metadata
m4 = PdfReader(f"{A}/INST04/documents/fire_noc.pdf").metadata
m1 = PdfReader(f"{A}/INST01/documents/fire_noc.pdf").metadata
check("Photoshop" in (m4.producer or ""), f"INST04 producer: {m4.producer}")
check("SPFES" in (m1.producer or ""), f"INST01 producer: {m1.producer}")

# 6. pHash
h = {i: phash(f"{A}/{i}/photos/computer_lab.jpg") for i in sorted(os.listdir(A))}
d27 = int((h["INST02"] != h["INST07"]).sum())
others = [int((h[a] != h[b]).sum()) for a in h for b in h if a < b and {a, b} != {"INST02", "INST07"}]
check(d27 <= 10 and min(others) >= 16, f"pHash: INST02~INST07 distance {d27}; min other pair {min(others)}")

# 7. labels / registries consistency
exp = json.load(open(f"{D}/labels/expected_findings.json"))
reg = json.load(open(f"{D}/mock_sources/fire_noc_registry.json"))
check(len(exp) == 10, "expected_findings covers 10 institutions")
apps = {i: json.load(open(f"{A}/{i}/application.json")) for i in sorted(os.listdir(A))}
check(not os.path.exists(f"{A}/INST06/documents/accreditation_certificate.pdf"), "INST06 accreditation missing")
f7 = {r["faculty_id"] for r in gt["INST07"]["faculty_list"]["rows"]}
f8 = {r["faculty_id"] for r in gt["INST08"]["faculty_list"]["rows"]}
check(len(f7 & f8) == 3, f"INST07/INST08 share {len(f7 & f8)} faculty IDs")
allf = {}
for i in gt:
    for r in gt[i]["faculty_list"]["rows"]:
        allf.setdefault(r["faculty_id"], set()).add(i)
check(sum(1 for v in allf.values() if len(v) > 1) == 3, "only the 3 planted faculty are shared")
print("\nALL PASS" if ok else "\nSOME CHECKS FAILED")
