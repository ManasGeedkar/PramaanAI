import hashlib
import json
import math
import os
import random
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(__file__))
from world import *  # noqa
import render as R
import imaging as IM

OUT = sys.argv[1] if len(sys.argv) > 1 else "/home/claude/aicte_synthetic_dataset_v1"
if os.path.exists(OUT):
    shutil.rmtree(OUT)
os.makedirs(OUT)
TMP = tempfile.mkdtemp()
rng = random.Random(SEED)
I = {i["id"]: i for i in INSTITUTIONS}


def total_proposed(inst):
    """Total proposed intake as written on the application form / affidavit."""
    if inst.get("claimed_prev_intake"):
        return inst["claimed_prev_intake"]
    return sum(n for _, n in inst["programmes"].values())


def total_existing(inst):
    return sum(o for o, _ in inst["programmes"].values())


def sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


# ---------------------------------------------------------------- faculty
used = set()
shared_pool = make_people(3, rng, used)
trap_a = dict(faculty_id="FAC-418820", name="Rajesh Sharma", dob="1979-04-12", qualification="Ph.D. (CSE)",
              designation="Professor", department="CSE", joining="2014-07-01")
trap_b = dict(faculty_id="FAC-562391", name="Rajesh Sharma", dob="1988-11-03", qualification="M.Tech (Mech)",
              designation="Assistant Professor", department="ME", joining="2019-08-01")
used |= {trap_a["faculty_id"], trap_b["faculty_id"]}
faculty = {}
for inst in INSTITUTIONS:
    req = math.ceil(total_proposed(inst) / 20)
    n = inst.get("faculty_count", req + rng.randint(2, 4))
    people = []
    if inst.get("shared_faculty_with"):
        people += shared_pool
    if inst["id"] == "INST01":
        people.append(trap_a)
    if inst["id"] == "INST05":
        people.append(trap_b)
    people += make_people(n - len(people), rng, used)
    faculty[inst["id"]] = people

# ---------------------------------------------------------------- numbers
fire_issue = {"INST01": ("2025-04-10", "2028-03-31"), "INST02": ("2025-02-18", "2028-03-31"),
              "INST03": ("2023-04-01", "2026-03-31"), "INST04": ("2023-03-15", "2026-03-31"),
              "INST05": ("2025-06-02", "2028-06-30"), "INST06": ("2024-11-20", "2027-12-31"),
              "INST07": ("2025-01-09", "2028-01-31"), "INST08": ("2025-03-27", "2028-03-31"),
              "INST10": ("2025-05-14", "2028-05-31")}
noc_no = {k: f"SPFES/NOC/{v[0][:4]}/{rng.randint(1000, 9999)}" for k, v in fire_issue.items()}
noc_no["INST09"] = noc_no["INST01"]
deed = {}
for inst in INSTITUTIONS:
    yr = rng.randint(2006, 2016)
    deed[inst["id"]] = dict(
        deed_no=f"SPREG/{inst['district'][:3].upper()}/{yr}/{rng.randint(10000, 99999)}",
        survey_no=f"Khasra No. {rng.randint(100, 899)}/{rng.randint(1, 9)}",
        reg_date=f"{yr}-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}")
aff_no = {i["id"]: f"{ISSUERS[i['university']]['code']}/AFF/2027/{rng.randint(100, 999)}" for i in INSTITUTIONS}
aff_date = {i["id"]: f"2026-09-{rng.randint(1, 25):02d}" for i in INSTITUTIONS}
accr = {"INST01": ("B.Tech CSE", "2024-07-01", "2029-06-30"),
        "INST02": ("B.Tech CSE", "2025-07-01", "2028-06-30"),
        "INST10": ("B.Tech CSE", "2025-01-01", "2028-12-31")}
accr_no = {k: f"BPAC/ACC/{v[1][:4]}/{rng.randint(1000, 9999)}" for k, v in accr.items()}

# ---------------------------------------------------------------- build
fields_gt, manifest, verification_gt = {}, [], {}
registries = {"fire_noc": {}, "land": {}, "university": {"STU": {"name": ISSUERS["univ_stu"]["name"], "available": True, "letters": {}},
                                                         "KVU": {"name": ISSUERS["univ_kvu"]["name"], "available": False, "letters": {}}},
              "accreditation": {}}

for inst in INSTITUTIONS:
    iid = inst["id"]
    base = os.path.join(OUT, "applications", iid)
    ddir, pdir = os.path.join(base, "documents"), os.path.join(base, "photos")
    os.makedirs(ddir)
    os.makedirs(pdir)
    fg, vg = {}, {}

    # --- Fire NOC
    p = os.path.join(ddir, "fire_noc.pdf")
    if iid == "INST09":
        src = I["INST01"]
        boxes = R.fire_noc(p, ISSUERS["fire"], inst, noc_no["INST01"], fire_issue["INST01"][0], fire_issue["INST01"][1],
                           holder_id_for_qr="INST01", producer="Microsoft Word 2019")
        IM.restamp_pdf_meta(p, "Microsoft Word 2019", "2026-09-22", "2026-09-22")
        printed_vt = fire_issue["INST01"][1]
        vg["fire_noc"] = dict(status="mismatch", reason="Registry: NOC number belongs to INST01 (Shri Ram Institute of Technology); QR HOLDER=INST01")
    elif iid == "INST04":
        tmp = os.path.join(TMP, "inst04_genuine.pdf")
        boxes = R.fire_noc(tmp, ISSUERS["fire"], inst, noc_no[iid], *fire_issue[iid], holder_id_for_qr=iid)
        region = IM.tamper_date(tmp, p, rng, boxes["valid_till"], "31-03-2028", created="2023-03-16", modified="2026-09-18")
        tamper_region = region
        printed_vt = "2028-03-31"
        vg["fire_noc"] = dict(status="mismatch", reason="Printed Valid Till 31-03-2028; QR and registry say 2026-03-31 (expired)")
    else:
        boxes = R.fire_noc(p, ISSUERS["fire"], inst, noc_no[iid], *fire_issue[iid], holder_id_for_qr=iid)
        IM.restamp_pdf_meta(p, ISSUERS["fire"]["producer"], fire_issue[iid][0])
        printed_vt = fire_issue[iid][1]
        vg["fire_noc"] = (dict(status="expired", reason="Registry status EXPIRED (valid till 2026-03-31)") if iid == "INST03"
                          else dict(status="verified", reason="Registry and QR match printed details"))
    if iid != "INST09":
        registries["fire_noc"][noc_no[iid]] = dict(
            holder_institution_id=iid, holder_name=inst["name"],
            address=f"Main Campus, {inst['district']}, {inst['district']} District",
            built_up_area_sqm=inst["built_up_sqm"], issue_date=fire_issue[iid][0], valid_till=fire_issue[iid][1],
            status="EXPIRED" if fire_issue[iid][1] < SESSION_START and fire_issue[iid][1] < "2026-10-25" else "ACTIVE")
    fg["fire_noc"] = dict(file="documents/fire_noc.pdf", scanned=(iid == "INST04"), fields={
        "noc_no": dict(value=noc_no[iid], bbox=boxes["noc_no"]),
        "issue_date": dict(value=fire_issue["INST01" if iid == "INST09" else iid][0], bbox=boxes["issue_date"]),
        "institution_name": dict(value=inst["name"], bbox=boxes["institution_name"]),
        "built_up_area_sqm": dict(value=inst["built_up_sqm"], bbox=boxes["built_up_area_sqm"]),
        "valid_till": dict(value=printed_vt, bbox=boxes["valid_till"]),
    }, qr_bbox=boxes.get("qr"))
    if iid == "INST04":
        fg["fire_noc"]["tampered_region"] = tamper_region

    # --- Land deed (scanned)
    dd = deed[iid]
    tmp = os.path.join(TMP, f"{iid}_deed.pdf")
    boxes = R.land_deed(tmp, ISSUERS["land"], inst, dd["deed_no"], dd["survey_no"], dd["reg_date"], inst["land_acres"])
    p = os.path.join(ddir, "land_deed.pdf")
    IM.scan_pdf(tmp, p, rng, producer="Canon iR-ADV C3530 Scanner", created="2026-09-10")
    registries["land"][dd["deed_no"]] = dict(owner=inst["trust"], survey_no=dd["survey_no"], district=inst["district"],
                                             land_area_acres=inst["land_acres"], registration_date=dd["reg_date"],
                                             response="PENDING" if iid == "INST05" else "OK")
    vg["land_deed"] = (dict(status="pending", reason="Land registry returned PENDING (async verification)") if iid == "INST05"
                       else dict(status="verified", reason="Registry record matches deed"))
    fg["land_deed"] = dict(file="documents/land_deed.pdf", scanned=True, bbox_note="approximate (scan rotation <= 0.9 deg)", fields={
        "deed_no": dict(value=dd["deed_no"], bbox=boxes["deed_no"]),
        "registration_date": dict(value=dd["reg_date"], bbox=boxes["registration_date"]),
        "owner": dict(value=inst["trust"], bbox=boxes["owner"]),
        "survey_no": dict(value=dd["survey_no"], bbox=boxes["survey_no"]),
        "land_area_acres": dict(value=inst["land_acres"], bbox=boxes["land_area_acres"]),
    })

    # --- Affiliation
    uni = ISSUERS[inst["university"]]
    p = os.path.join(ddir, "affiliation_letter.pdf")
    boxes = R.affiliation(p, uni, inst, aff_no[iid], aff_date[iid], iid)
    IM.restamp_pdf_meta(p, uni["producer"], aff_date[iid])
    registries["university"][uni["code"]]["letters"][aff_no[iid]] = dict(
        institution_id=iid, institution_name=inst["name"], session="2027-28",
        programmes={k: v[0] for k, v in inst["programmes"].items()}, issue_date=aff_date[iid])
    vg["affiliation_letter"] = (dict(status="source_unavailable", reason="KVU verification service unavailable")
                                if inst["university"] == "univ_kvu" else dict(status="verified", reason="University record matches"))
    fg["affiliation_letter"] = dict(file="documents/affiliation_letter.pdf", scanned=False, fields={
        "letter_no": dict(value=aff_no[iid], bbox=boxes["letter_no"]),
        "issue_date": dict(value=aff_date[iid], bbox=boxes["issue_date"]),
        "institution_name": dict(value=inst["name"], bbox=boxes["institution_name"]),
        "aicte_id": dict(value=inst["aicte_id"], bbox=boxes["aicte_id"]),
        "session": dict(value="2027-28", bbox=boxes["session"]),
    }, qr_bbox=boxes.get("qr"))

    # --- Accreditation
    if iid in accr:
        prog, vf, vt = accr[iid]
        p = os.path.join(ddir, "accreditation_certificate.pdf")
        if inst.get("blurry_accr"):
            tmp = os.path.join(TMP, f"{iid}_acc.pdf")
            boxes = R.accreditation(tmp, ISSUERS["accr"], inst, accr_no[iid], prog, vf, vt, iid)
            IM.scan_pdf(tmp, p, rng, producer="Mobile Scanner App", created="2026-09-28", blur=2.6, quality=45, downscale=0.33)
            vg["accreditation_certificate"] = dict(status="manual_review", reason="Blurry scan; QR unreadable and certificate number OCR low-confidence")
        else:
            boxes = R.accreditation(p, ISSUERS["accr"], inst, accr_no[iid], prog, vf, vt, iid)
            IM.restamp_pdf_meta(p, ISSUERS["accr"]["producer"], vf)
            vg["accreditation_certificate"] = dict(status="verified", reason="Accreditation registry matches")
        registries["accreditation"][accr_no[iid]] = dict(institution_id=iid, institution_name=inst["name"], programme=prog,
                                                         valid_from=vf, valid_till=vt, status="ACCREDITED")
        fg["accreditation_certificate"] = dict(file="documents/accreditation_certificate.pdf", scanned=bool(inst.get("blurry_accr")), fields={
            "cert_no": dict(value=accr_no[iid], bbox=boxes["cert_no"]),
            "programme": dict(value=prog, bbox=boxes["programme"]),
            "valid_from": dict(value=vf, bbox=boxes["valid_from"]),
            "valid_till": dict(value=vt, bbox=boxes["valid_till"]),
        }, qr_bbox=boxes.get("qr"))

    # --- Faculty list
    p = os.path.join(ddir, "faculty_list.pdf")
    boxes = R.faculty_list(p, inst, faculty[iid], "2026-09-30")
    IM.restamp_pdf_meta(p, "Microsoft Excel 2019", "2026-09-30")
    fg["faculty_list"] = dict(file="documents/faculty_list.pdf", scanned=False, fields={
        "faculty_count": dict(value=len(faculty[iid]), bbox=boxes["faculty_count"]),
    }, rows=[dict(**{k: v for k, v in f.items()}, bbox=r["bbox"]) for f, r in zip(faculty[iid], boxes["rows"])])

    # --- Affidavit (scanned)
    aff_land = inst.get("affidavit_land_acres", inst["land_acres"])
    tmp = os.path.join(TMP, f"{iid}_affidavit.pdf")
    boxes = R.affidavit(tmp, inst, "2026-10-01", aff_land, inst["built_up_sqm"], total_proposed(inst),
                        len(faculty[iid]), noc_no[iid])
    p = os.path.join(ddir, "affidavit.pdf")
    IM.scan_pdf(tmp, p, rng, producer="Epson WorkForce Scanner", created="2026-10-02")
    fg["affidavit"] = dict(file="documents/affidavit.pdf", scanned=True, bbox_note="approximate (scan rotation <= 0.9 deg)", fields={
        k: dict(value=v, bbox=boxes[k]) for k, v in [
            ("land_area_acres", aff_land), ("built_up_area_sqm", inst["built_up_sqm"]),
            ("proposed_intake", total_proposed(inst)), ("faculty_count", len(faculty[iid])), ("fire_noc_no", noc_no[iid])]})

    # --- Photos
    photos = []
    lab_p = os.path.join(pdir, "computer_lab.jpg")
    if inst.get("dup_photo_from"):
        IM.disguise_duplicate(os.path.join(OUT, "applications", inst["dup_photo_from"], "photos", "computer_lab.jpg"), lab_p)
        claimed = 24
    else:
        claimed = IM.lab_photo(lab_p, rng, rows=4, per_row=rng.choice([5, 6]))
    IM.classroom_photo(os.path.join(pdir, "classroom.jpg"), rng)
    photos = [dict(type="computer_lab", file="photos/computer_lab.jpg", claimed_computers=claimed),
              dict(type="classroom", file="photos/classroom.jpg", claimed_seats=60)]

    # --- Application form
    claimed_prev = inst.get("claimed_prev_intake")
    programmes = []
    for k, (old, new) in inst["programmes"].items():
        programmes.append(dict(name=k, existing_intake_claimed=(claimed_prev // len(inst["programmes"]) if claimed_prev else old),
                               proposed_intake=(new if not claimed_prev else claimed_prev // len(inst["programmes"]))))
    docs = [dict(doc_type=t, file=v["file"]) for t, v in fg.items()]
    app = dict(
        application_id=f"APP-2027-{int(iid[4:]):04d}",
        academic_year=ACADEMIC_YEAR, category=inst["category"],
        submitted_on=f"2026-10-{rng.randint(3, 20):02d}",
        institution=dict(id=iid, aicte_permanent_id=inst["aicte_id"], name=inst["name"], trust=inst["trust"],
                         district=inst["district"], state=STATE, university=uni["name"]),
        programmes=programmes,
        declared=dict(land_area_acres=aff_land, built_up_area_sqm=inst["built_up_sqm"],
                      faculty_count=len(faculty[iid]),
                      total_existing_intake=sum(p["existing_intake_claimed"] for p in programmes),
                      total_proposed_intake=sum(p["proposed_intake"] for p in programmes)),
        documents=docs, photos=photos)
    json.dump(app, open(os.path.join(base, "application.json"), "w"), indent=2)

    for t, v in fg.items():
        manifest.append(dict(institution_id=iid, doc_type=t, file=f"applications/{iid}/{v['file']}",
                             sha256=sha(os.path.join(base, v["file"])), scanned=v["scanned"]))
    for ph in photos:
        manifest.append(dict(institution_id=iid, doc_type="photo:" + ph["type"], file=f"applications/{iid}/{ph['file']}",
                             sha256=sha(os.path.join(base, ph["file"])), scanned=False))
    fields_gt[iid] = fg
    verification_gt[iid] = vg

# ---------------------------------------------------------------- mock sources
ms = os.path.join(OUT, "mock_sources")
os.makedirs(ms)
aicte = {}
for inst in INSTITUTIONS:
    prev = None if inst.get("no_prev_record") else dict(
        academic_year="2026-27", eoa_status="Approved",
        approved_intake={k: v[0] for k, v in inst["programmes"].items()},
        approval_letter_no=f"AICTE-MOCK/EoA/2026-27/{rng.randint(10000, 99999)}")
    aicte[inst["aicte_id"]] = dict(institution_id=inst["id"], name=inst["name"], trust=inst["trust"],
                                   district=inst["district"], state=STATE, previous_year=prev,
                                   ter_payment_2027_28=dict(status="PAID", amount_inr=rng.choice([150000, 180000, 210000]),
                                                            txn_ref=f"TER-MOCK-{rng.randint(100000, 999999)}"))
json.dump(aicte, open(os.path.join(ms, "aicte_records.json"), "w"), indent=2)
json.dump(registries["fire_noc"], open(os.path.join(ms, "fire_noc_registry.json"), "w"), indent=2)
json.dump(registries["land"], open(os.path.join(ms, "land_registry.json"), "w"), indent=2)
json.dump(registries["university"], open(os.path.join(ms, "university_registry.json"), "w"), indent=2)
json.dump(registries["accreditation"], open(os.path.join(ms, "accreditation_registry.json"), "w"), indent=2)

# ---------------------------------------------------------------- labels
lab = os.path.join(OUT, "labels")
os.makedirs(lab)
json.dump(fields_gt, open(os.path.join(lab, "fields_ground_truth.json"), "w"), indent=2)
json.dump(verification_gt, open(os.path.join(lab, "verification_ground_truth.json"), "w"), indent=2)
json.dump(manifest, open(os.path.join(lab, "manifest.json"), "w"), indent=2)

shared_ids = [p["faculty_id"] for p in shared_pool]
F = fields_gt
expected = {
    "INST01": dict(risk_band="Low", findings=[
        dict(code="ENTITY_REUSE", severity="info", doc_type="fire_noc", field="noc_no",
             detail=f"NOC number {noc_no['INST01']} also appears in INST09 (INST01 is the genuine holder per registry)",
             related=["INST09"])],
        must_not_flag=["ENTITY_REUSE on faculty 'Rajesh Sharma' (FAC-418820) - same name as INST05's FAC-562391 but different ID and DOB"]),
    "INST02": dict(risk_band="Low", findings=[
        dict(code="DUPLICATE_IMAGE", severity="info", doc_type="photo:computer_lab",
             detail="Lab photo reused by INST07 (INST02 appears to be the original)", related=["INST07"])]),
    "INST03": dict(risk_band="High", findings=[
        dict(code="EXPIRED_DOC", severity="critical", doc_type="fire_noc", field="valid_till",
             detail="Fire NOC valid till 31-03-2026, before session start 01-07-2027", bbox=F["INST03"]["fire_noc"]["fields"]["valid_till"]["bbox"]),
        dict(code="RULE_FAIL", severity="critical", rule_id="R-FIRE-001", detail="Fire NOC not valid on session start"),
        dict(code="SOURCE_EXPIRED", severity="critical", doc_type="fire_noc", detail="Registry status EXPIRED")]),
    "INST04": dict(risk_band="High", findings=[
        dict(code="TAMPER_SUSPECTED", severity="critical", doc_type="fire_noc", field="valid_till", method="ELA",
             detail="Edited region around 'Valid Till' value (single-compressed patch on double-compressed scan)",
             bbox=F["INST04"]["fire_noc"]["tampered_region"]),
        dict(code="METADATA_ANOMALY", severity="warning", doc_type="fire_noc",
             detail="PDF Producer 'Adobe Photoshop 25.1'; ModDate 2026-09-18 long after issue 2023-03-15"),
        dict(code="QR_MISMATCH", severity="critical", doc_type="fire_noc", field="valid_till",
             detail="QR VALID_TILL=2026-03-31 vs printed 31-03-2028"),
        dict(code="SOURCE_MISMATCH", severity="critical", doc_type="fire_noc",
             detail="Registry valid_till 2026-03-31 (EXPIRED) vs printed 31-03-2028")]),
    "INST05": dict(risk_band="High", findings=[
        dict(code="CROSS_DOC_MISMATCH", severity="critical", field="land_area_acres",
             detail="Land deed 2.00 acres vs affidavit / form 3.50 acres",
             evidence=[dict(doc_type="land_deed", bbox=F["INST05"]["land_deed"]["fields"]["land_area_acres"]["bbox"]),
                       dict(doc_type="affidavit", bbox=F["INST05"]["affidavit"]["fields"]["land_area_acres"]["bbox"])]),
        dict(code="RULE_FAIL", severity="critical", rule_id="R-LAND-001", detail="Deed land area 2.00 < 2.50 acres"),
        dict(code="VERIFICATION_PENDING", severity="info", doc_type="land_deed", detail="Land registry response PENDING")]),
    "INST06": dict(risk_band="High", findings=[
        dict(code="MISSING_DOC", severity="critical", doc_type="accreditation_certificate",
             detail="Required for EoA_INTAKE_INCREASE (B.Tech CSE 60 -> 180)"),
        dict(code="RULE_FAIL", severity="critical", rule_id="R-FAC-001",
             detail="Faculty 8 < required 12 for total proposed intake 240 (1:20)"),
        dict(code="RULE_FAIL", severity="critical", rule_id="R-ACC-001", detail="No valid accreditation for programme with intake increase"),
        dict(code="NO_PREVIOUS_RECORD", severity="warning", detail="AICTE records: previous_year is null")]),
    "INST07": dict(risk_band="Medium", findings=[
        dict(code="DUPLICATE_IMAGE", severity="warning", doc_type="photo:computer_lab", method="pHash",
             detail="Near-duplicate of INST02 computer_lab.jpg (cropped, resized, brightened)", related=["INST02"]),
        dict(code="ENTITY_REUSE", severity="warning", doc_type="faculty_list", entity_type="faculty",
             detail="3 faculty (same Faculty ID + name + DOB) also on INST08 list for 2027-28",
             entity_ids=shared_ids, related=["INST08"])]),
    "INST08": dict(risk_band="Medium", findings=[
        dict(code="ENTITY_REUSE", severity="warning", doc_type="faculty_list", entity_type="faculty",
             detail="3 faculty also claimed by INST07 for 2027-28", entity_ids=shared_ids, related=["INST07"])]),
    "INST09": dict(risk_band="High", findings=[
        dict(code="SOURCE_MISMATCH", severity="critical", doc_type="fire_noc",
             detail=f"Registry: {noc_no['INST01']} is held by INST01, not this institution"),
        dict(code="QR_MISMATCH", severity="critical", doc_type="fire_noc", detail="QR HOLDER=INST01"),
        dict(code="ENTITY_REUSE", severity="critical", doc_type="fire_noc", entity_type="fire_noc_no",
             detail="Same Fire NOC number in INST01 application", related=["INST01"]),
        dict(code="METADATA_ANOMALY", severity="warning", doc_type="fire_noc",
             detail="Issuer certificate produced with 'Microsoft Word 2019' (genuine SPFES certificates use 'SPFES e-Certificate Portal')")]),
    "INST10": dict(risk_band="Medium", findings=[
        dict(code="RECORD_MISMATCH", severity="critical", field="total_existing_intake",
             detail="Form claims existing intake 240; AICTE 2026-27 approved intake 120"),
        dict(code="SOURCE_UNAVAILABLE", severity="info", doc_type="affiliation_letter", detail="KVU verification API unavailable"),
        dict(code="MANUAL_REVIEW", severity="warning", doc_type="accreditation_certificate",
             detail="Unreadable QR / low-confidence OCR on blurry scan")]),
}
for k, v in expected.items():
    v["scenario"] = I[k]["scenario"]
    v["expected_verification"] = verification_gt[k]
json.dump(expected, open(os.path.join(lab, "expected_findings.json"), "w"), indent=2)

shutil.rmtree(TMP)
print("generated", OUT)
