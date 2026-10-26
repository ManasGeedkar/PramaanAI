"""Document renderers. Each returns field bounding boxes in PDF points,
top-left origin (x0, y0, x1, y1) on an A4 page (595.28 x 841.89)."""
import hashlib
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.graphics.shapes import Drawing
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics import renderPDF
from reportlab.lib.colors import HexColor, black, white

PW, PH = A4
LM = 56
DISCLAIMER = ("SYNTHETIC DOCUMENT - SIH 2026 PS 26261 PROTOTYPE TEST DATA - "
              "Fictional issuer, not a real certificate")


def fmt(d):
    """ISO yyyy-mm-dd -> dd-mm-yyyy as printed on documents."""
    y, m, dd = d.split("-")
    return f"{dd}-{m}-{y}"


class Doc:
    def __init__(self, path, title, producer, created):
        self.c = canvas.Canvas(path, pagesize=A4)
        self.c.setTitle(title)
        self.c.setProducer(producer)
        self.c.setCreator(producer)
        self.c.setAuthor(producer.split(" ")[0])
        self._created = created
        self.y = 60  # distance from top
        self.boxes = {}

    # -- primitives ---------------------------------------------------------
    def text(self, s, x, size=10, font="Helvetica", color=black):
        c = self.c
        c.setFont(font, size)
        c.setFillColor(color)
        c.drawString(x, PH - self.y, s)
        w = c.stringWidth(s, font, size)
        return (x, self.y - size * 0.8, x + w, self.y + size * 0.25)

    def center(self, s, size=12, font="Helvetica-Bold", color=black):
        c = self.c
        c.setFont(font, size)
        c.setFillColor(color)
        c.drawCentredString(PW / 2, PH - self.y, s)

    def gap(self, h):
        self.y += h

    def field(self, key, label, value, x_label=LM, x_val=LM + 170, size=10.5):
        self.text(label, x_label, size, "Helvetica-Bold")
        box = self.text(str(value), x_val, size, "Helvetica")
        self.boxes[key] = [round(v, 1) for v in box]
        self.gap(size * 1.9)
        return box

    def para(self, s, size=10, width=PW - 2 * LM, leading=14):
        c = self.c
        c.setFont("Helvetica", size)
        c.setFillColor(black)
        words, line = s.split(), ""
        for w in words:
            t = (line + " " + w).strip()
            if c.stringWidth(t, "Helvetica", size) > width:
                c.drawString(LM, PH - self.y, line)
                self.y += leading
                line = w
            else:
                line = t
        if line:
            c.drawString(LM, PH - self.y, line)
            self.y += leading

    def rule(self, color="#1F3A68", w=1.2):
        c = self.c
        c.setStrokeColor(HexColor(color))
        c.setLineWidth(w)
        c.line(LM, PH - self.y, PW - LM, PH - self.y)

    def header(self, org, office, sub, color="#1F3A68"):
        c = self.c
        c.setFillColor(HexColor(color))
        c.rect(0, PH - 92, PW, 92, stroke=0, fill=1)
        c.setFillColor(white)
        c.setFont("Helvetica-Bold", 15)
        c.drawCentredString(PW / 2, PH - 38, org)
        c.setFont("Helvetica", 10)
        c.drawCentredString(PW / 2, PH - 56, office)
        c.setFont("Helvetica-Oblique", 8.5)
        c.drawCentredString(PW / 2, PH - 72, sub)
        self.y = 122

    def qr(self, payload, x=PW - LM - 110, top=None, size=110):
        top = top if top is not None else PH - 150 - size
        w = QrCodeWidget(payload)
        b = w.getBounds()
        bw, bh = b[2] - b[0], b[3] - b[1]
        d = Drawing(size, size, transform=[size / bw, 0, 0, size / bh, 0, 0])
        d.add(w)
        renderPDF.draw(d, self.c, x, top)
        self.c.setFont("Helvetica", 6.5)
        self.c.drawCentredString(x + size / 2, top - 8, "Scan to verify (mock service)")
        self.boxes["qr"] = [round(x, 1), round(PH - top - size, 1), round(x + size, 1), round(PH - top, 1)]

    def stamp(self, x, y_top, label1, label2, color="#7A1F1F"):
        c = self.c
        c.setStrokeColor(HexColor(color))
        c.setFillColor(HexColor(color))
        c.setLineWidth(1.4)
        cx, cy = x, PH - y_top
        c.circle(cx, cy, 34, stroke=1, fill=0)
        c.circle(cx, cy, 29, stroke=1, fill=0)
        c.setFont("Helvetica-Bold", 6.5)
        c.drawCentredString(cx, cy + 6, label1)
        c.setFont("Helvetica", 6)
        c.drawCentredString(cx, cy - 4, label2)
        c.drawCentredString(cx, cy - 12, "SPECIMEN")

    def signature(self, name, role, y_top=None):
        c = self.c
        if y_top is not None:
            self.y = y_top
        c.setStrokeColor(black)
        c.setLineWidth(0.6)
        x = PW / 2 - 70
        # squiggle
        p = c.beginPath()
        p.moveTo(x + 10, PH - self.y + 8)
        for i in range(8):
            p.curveTo(x + 20 + i * 14, PH - self.y + 22, x + 26 + i * 14, PH - self.y - 2, x + 32 + i * 14, PH - self.y + 10)
        c.drawPath(p, stroke=1, fill=0)
        self.gap(16)
        c.line(x, PH - self.y, x + 170, PH - self.y)
        self.gap(12)
        self.text(name, x, 9.5, "Helvetica-Bold")
        self.gap(12)
        self.text(role, x, 9)

    def finish(self):
        c = self.c
        # watermark
        c.saveState()
        c.setFillColor(HexColor("#B0B0B0"))
        c.setFillAlpha(0.18)
        c.translate(PW / 2, PH / 2)
        c.rotate(35)
        c.setFont("Helvetica-Bold", 54)
        c.drawCentredString(0, 0, "SYNTHETIC TEST DATA")
        c.restoreState()
        # footer
        c.setFont("Helvetica", 7)
        c.setFillColor(HexColor("#666666"))
        c.drawCentredString(PW / 2, 26, DISCLAIMER)
        c.showPage()
        c.save()
        return self.boxes


def qr_payload(issuer_code, doc_type, number, holder_id, **kw):
    extra = "|".join(f"{k.upper()}={v}" for k, v in kw.items())
    sig = hashlib.sha256(f"{issuer_code}{number}{holder_id}".encode()).hexdigest()[:10]
    return f"MOCKVERIFY|{issuer_code}|{doc_type}|{number}|HOLDER={holder_id}|{extra}|SIG={sig}"


# ---------------------------------------------------------------------------
def fire_noc(path, iss, inst, noc_no, issue, valid_till, holder_id_for_qr, valid_till_qr=None,
             producer=None, address=None):
    d = Doc(path, "Fire Safety No Objection Certificate", producer or iss["producer"], issue)
    d.header(iss["name"], iss["office"], "Government of Sampurna Pradesh (fictional state)", "#8B1A1A")
    d.center("FIRE SAFETY NO OBJECTION CERTIFICATE", 14)
    d.gap(26)
    d.field("noc_no", "NOC No.:", noc_no)
    d.field("issue_date", "Date of Issue:", fmt(issue))
    d.gap(6)
    d.para("This is to certify that the building(s) described below have been inspected under the "
           "Sampurna Pradesh Fire Prevention and Fire Safety Rules (fictional) and are found to comply "
           "with fire safety requirements for the stated use, subject to the conditions overleaf.")
    d.gap(10)
    d.field("institution_name", "Name of Occupier:", inst["name"])
    d.field("address", "Premises Address:", address or f"Main Campus, {inst['district']}, {inst['district']} District")
    d.field("building_use", "Use of Building:", "Educational (Technical Institution)")
    d.field("built_up_area_sqm", "Built-up Area (sq. m):", f"{inst['built_up_sqm']:,}")
    d.field("floors", "No. of Floors:", "G + 3")
    d.field("valid_till", "Valid Till:", fmt(valid_till))
    d.gap(8)
    d.para("Conditions: fire extinguishers to be serviced annually; evacuation drills twice a year; "
           "any structural change requires fresh NOC. This certificate must be renewed before expiry.")
    d.qr(qr_payload(iss["code"], "FIRE_NOC", noc_no, holder_id_for_qr,
                    valid_till=(valid_till_qr or valid_till)), top=PH - 690)
    d.stamp(LM + 60, 660, "SPFES", "FIRE SAFETY WING")
    d.signature("Divisional Fire Officer", f"{iss['name'].split(' &')[0]}", y_top=700)
    return d.finish()


def land_deed(path, iss, inst, deed_no, survey_no, reg_date, acres):
    d = Doc(path, "Registered Sale Deed (Extract)", iss["producer"], reg_date)
    d.header(iss["name"], f"{iss['office']}, {inst['district']}", "Government of Sampurna Pradesh (fictional state)", "#3B4A2A")
    d.center("CERTIFIED EXTRACT OF REGISTERED SALE DEED", 13.5)
    d.gap(26)
    d.field("deed_no", "Registration No.:", deed_no)
    d.field("registration_date", "Date of Registration:", fmt(reg_date))
    d.field("owner", "Purchaser / Owner:", inst["trust"])
    d.field("survey_no", "Khasra / Survey No.:", survey_no)
    d.field("village", "Village / Tehsil:", f"Ward 7, {inst['district']} Tehsil")
    d.field("district", "District:", inst["district"])
    d.field("land_area_acres", "Total Land Area:", f"{acres:.2f} acres")
    d.field("land_use", "Land Use:", "Institutional (converted)")
    d.gap(6)
    d.para("Certified that the above is a true extract of the deed registered in this office. "
           "Encumbrance: NIL as on date of registration.")
    d.stamp(LM + 60, 640, "SUB-REGISTRAR", inst["district"].upper())
    d.signature("Sub-Registrar", f"{inst['district']} (fictional office)", y_top=680)
    return d.finish()


def affiliation(path, iss, inst, letter_no, issue, holder_id):
    d = Doc(path, "Affiliation Letter", iss["producer"], issue)
    d.header(iss["name"], iss["office"], "A State University (fictional)", "#3C3489")
    d.center("GRANT OF AFFILIATION - ACADEMIC SESSION 2027-28", 13)
    d.gap(26)
    d.field("letter_no", "Letter No.:", letter_no)
    d.field("issue_date", "Date:", fmt(issue))
    d.field("institution_name", "Institution:", inst["name"])
    d.field("aicte_id", "AICTE Permanent ID:", inst["aicte_id"])
    d.field("session", "Session:", "2027-28")
    d.gap(4)
    d.text("Programmes and intake affiliated:", LM, 10.5, "Helvetica-Bold")
    d.gap(18)
    for prog, (old, new) in inst["programmes"].items():
        d.text(f"-  {prog}", LM + 14, 10.5)
        d.text(f"Intake: {old}", LM + 230, 10.5)
        d.gap(17)
    d.gap(6)
    d.para("Affiliation is granted subject to approval of the competent regulatory authority and "
           "continued compliance with university norms.")
    d.qr(qr_payload(iss["code"], "AFFILIATION", letter_no, holder_id, session="2027-28"), top=PH - 700)
    d.signature("Registrar", iss["name"], y_top=700)
    return d.finish()


def accreditation(path, iss, inst, cert_no, programme, vfrom, vtill, holder_id):
    d = Doc(path, "Accreditation Certificate", iss["producer"], vfrom)
    d.header(iss["name"], iss["office"], "An autonomous accreditation body (fictional)", "#0F6E56")
    d.center("CERTIFICATE OF PROGRAMME ACCREDITATION", 14)
    d.gap(26)
    d.field("cert_no", "Certificate No.:", cert_no)
    d.field("institution_name", "Institution:", inst["name"])
    d.field("programme", "Programme:", programme)
    d.field("valid_from", "Valid From:", fmt(vfrom))
    d.field("valid_till", "Valid Till:", fmt(vtill))
    d.field("grade", "Accreditation Status:", "Accredited (Tier II)")
    d.gap(6)
    d.para("The programme named above has been evaluated against the Council's outcome-based "
           "criteria and is accredited for the period stated.")
    d.qr(qr_payload(iss["code"], "ACCREDITATION", cert_no, holder_id, valid_till=vtill), top=PH - 690)
    d.stamp(LM + 60, 640, "BPAC", "ACCREDITATION")
    d.signature("Member Secretary", iss["name"], y_top=700)
    return d.finish()


def inst_header(d, inst):
    d.header(inst["name"], f"Main Campus, {inst['district']}, {inst['district']} District, Sampurna Pradesh",
             f"Run by {inst['trust']}  |  AICTE Permanent ID: {inst['aicte_id']}", "#22364F")


def faculty_list(path, inst, people, date):
    d = Doc(path, "Faculty List", "Microsoft Excel 2019", date)
    inst_header(d, inst)
    d.center("LIST OF REGULAR TEACHING FACULTY - 2027-28", 13)
    d.gap(24)
    d.field("institution_name", "Institution:", inst["name"])
    d.field("faculty_count", "Total Regular Faculty:", str(len(people)))
    d.gap(4)
    cols = [("S.No", 30), ("Faculty ID", 70), ("Name", 110), ("DOB", 68), ("Qualification", 105),
            ("Designation", 105)]
    x = LM - 10
    c = d.c
    c.setFillColor(HexColor("#E8EEF7"))
    c.rect(x, PH - d.y - 5, sum(w for _, w in cols), 17, stroke=0, fill=1)
    xx = x + 3
    for name, w in cols:
        d.text(name, xx, 8.5, "Helvetica-Bold")
        xx += w
    d.gap(18)
    rows = []
    for i, p in enumerate(people, 1):
        xx = x + 3
        vals = [str(i), p["faculty_id"], p["name"], fmt(p["dob"]), p["qualification"], p["designation"]]
        row_boxes = []
        for (name, w), v in zip(cols, vals):
            row_boxes.append(d.text(v, xx, 8.5))
            xx += w
        rows.append({"faculty_id": p["faculty_id"], "bbox": [round(row_boxes[0][0], 1), round(row_boxes[0][1], 1),
                                                             round(row_boxes[-1][2], 1), round(row_boxes[-1][3], 1)]})
        d.gap(15.5)
    d.boxes["rows"] = rows
    d.signature("Principal / Director", inst["name"], y_top=max(d.y + 30, 720))
    return d.finish()


def affidavit(path, inst, date, land, bua, intake, faculty, noc_no):
    d = Doc(path, "Affidavit cum Undertaking", "Microsoft Word 2019", date)
    inst_header(d, inst)
    d.center("AFFIDAVIT CUM UNDERTAKING (ON NON-JUDICIAL STAMP PAPER)", 12)
    d.gap(24)
    d.para(f"I, the Secretary of {inst['trust']}, the society/trust running {inst['name']}, do hereby "
           f"solemnly affirm that the information furnished in the application for Extension of "
           f"Approval for the academic year 2027-28 is true and correct, and specifically declare:")
    d.gap(10)
    d.field("land_area_acres", "Land in possession:", f"{land:.2f} acres", x_val=LM + 200)
    d.field("built_up_area_sqm", "Built-up area:", f"{bua:,} sq. m", x_val=LM + 200)
    d.field("proposed_intake", "Total proposed intake:", str(intake), x_val=LM + 200)
    d.field("faculty_count", "Regular faculty on roll:", str(faculty), x_val=LM + 200)
    d.field("fire_noc_no", "Fire NOC reference:", noc_no, x_val=LM + 200)
    d.gap(6)
    d.para("I undertake that if any information is found false, the approval may be withdrawn and "
           "action may be taken as per applicable regulations.")
    d.stamp(LM + 60, 630, "NOTARY PUBLIC", inst["district"].upper())
    d.signature("Secretary (Deponent)", inst["trust"], y_top=670)
    return d.finish()
