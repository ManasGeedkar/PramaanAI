"""Fictional world definition for the PS 26261 synthetic dataset.

Every issuer, place and person here is invented. Documents carry a
SYNTHETIC TEST DATA watermark and footer so they can never pass as real.
"""
import random

SEED = 26261
ACADEMIC_YEAR = "2027-28"
SESSION_START = "2027-07-01"
STATE = "Sampurna Pradesh"

ISSUERS = {
    "fire": {
        "code": "SPFES",
        "name": "Sampurna Pradesh Fire & Emergency Services",
        "office": "Directorate of Fire Safety, Navgarh",
        "producer": "SPFES e-Certificate Portal v3.2",
    },
    "land": {
        "code": "SPREG",
        "name": "Department of Registration & Stamps, Sampurna Pradesh",
        "office": "Office of the Sub-Registrar",
        "producer": "SPREG Deed Registration System",
    },
    "univ_stu": {
        "code": "STU",
        "name": "Sampurna Technical University",
        "office": "Office of the Registrar, Navgarh",
        "producer": "STU Affiliation Module",
    },
    "univ_kvu": {
        "code": "KVU",
        "name": "Kaveri Valley University",
        "office": "Office of the Registrar, Dhanpur",
        "producer": "KVU Academic Portal",
    },
    "accr": {
        "code": "BPAC",
        "name": "Bharat Programme Accreditation Council",
        "office": "Accreditation Secretariat, Navgarh",
        "producer": "BPAC Certificate Engine",
    },
}

DISTRICTS = ["Navgarh", "Dhanpur", "Rajkot Kalan", "Sitapur Nagar", "Ambikapuri", "Devgarh"]

FIRST = ["Aarav", "Vivek", "Rajesh", "Sunita", "Priya", "Anil", "Kavita", "Manoj", "Neha", "Suresh",
         "Pooja", "Amit", "Deepa", "Rahul", "Meena", "Sanjay", "Anjali", "Vikram", "Rekha", "Arun",
         "Swati", "Nitin", "Geeta", "Harish", "Lata", "Pankaj", "Shweta", "Ramesh", "Asha", "Gaurav",
         "Divya", "Ajay", "Nisha", "Mahesh", "Sneha", "Kiran", "Rohit", "Usha", "Alok", "Bhavna"]
LAST = ["Sharma", "Verma", "Gupta", "Patel", "Singh", "Iyer", "Nair", "Reddy", "Joshi", "Mishra",
        "Kulkarni", "Deshmukh", "Yadav", "Pandey", "Chauhan", "Bose", "Das", "Menon", "Rao", "Tiwari"]
QUAL = ["Ph.D. (CSE)", "M.Tech (CSE)", "M.Tech (ECE)", "Ph.D. (Mech)", "M.Tech (Mech)",
        "M.E. (Civil)", "Ph.D. (Physics)", "M.Sc. (Maths), Ph.D.", "M.Tech (IT)", "MCA, Ph.D."]
DESIG = ["Professor", "Associate Professor", "Assistant Professor", "Assistant Professor",
         "Assistant Professor"]
DEPTS = ["CSE", "ECE", "ME", "CE", "IT", "Applied Sciences"]

# ---------------------------------------------------------------------------
# Institutions. "scenario" documents what is deliberately planted.
# intake values are first-year intake summed over programmes.
# ---------------------------------------------------------------------------
INSTITUTIONS = [
    dict(id="INST01", aicte_id="1-SP-0001001", name="Shri Ram Institute of Technology",
         district="Navgarh", trust="Shri Ram Shiksha Samiti", category="EoA",
         programmes={"B.Tech CSE": (60, 60), "B.Tech ME": (60, 60)},
         land_acres=6.2, built_up_sqm=14200, university="univ_stu",
         scenario="Clean application. Control case: everything valid and verifiable."),
    dict(id="INST02", aicte_id="1-SP-0001002", name="Navgarh College of Engineering",
         district="Navgarh", trust="Navgarh Vidya Trust", category="EoA_INTAKE_INCREASE",
         programmes={"B.Tech CSE": (60, 120), "B.Tech ECE": (60, 60)},
         land_acres=8.0, built_up_sqm=21000, university="univ_stu",
         scenario="Clean intake-increase application with valid accreditation. Control case."),
    dict(id="INST03", aicte_id="1-SP-0001003", name="Dhanpur Institute of Engineering & Management",
         district="Dhanpur", trust="Dhanpur Education Society", category="EoA",
         programmes={"B.Tech CSE": (120, 120), "MBA": (60, 60)},
         land_acres=5.5, built_up_sqm=16800, university="univ_stu",
         scenario="Fire NOC genuinely EXPIRED (valid till 2026-03-31). Registry confirms expiry."),
    dict(id="INST04", aicte_id="1-SP-0001004", name="Ambikapuri Engineering College",
         district="Ambikapuri", trust="Ambika Shiksha Prasar Mandal", category="EoA",
         programmes={"B.Tech CSE": (60, 60), "B.Tech CE": (60, 60)},
         land_acres=4.8, built_up_sqm=12500, university="univ_stu",
         scenario="Fire NOC TAMPERED: 'Valid till' edited 31-03-2026 -> 31-03-2028 on a scanned image "
                  "(ELA-detectable), PDF producer = Adobe Photoshop. QR + registry still say 2026."),
    dict(id="INST05", aicte_id="1-SP-0001005", name="Sitapur Nagar Polytechnic & Engineering College",
         district="Sitapur Nagar", trust="Sitapur Gramin Vikas Trust", category="EoA",
         programmes={"B.Tech ME": (60, 60), "B.Tech CE": (60, 60)},
         land_acres=2.0, built_up_sqm=9800, university="univ_stu", affidavit_land_acres=3.5,
         scenario="LAND MISMATCH: sale deed says 2.0 acres, affidavit claims 3.5 acres. 2.0 also fails "
                  "the minimum-land rule. Land registry verification returns PENDING."),
    dict(id="INST06", aicte_id="1-SP-0001006", name="Devgarh Institute of Technology",
         district="Devgarh", trust="Devgarh Takniki Shiksha Samiti", category="EoA_INTAKE_INCREASE",
         programmes={"B.Tech CSE": (60, 180), "B.Tech IT": (60, 60)},
         land_acres=5.0, built_up_sqm=15000, university="univ_stu", faculty_count=8,
         missing_docs=["accreditation"], no_prev_record=True,
         scenario="MISSING accreditation certificate for an intake increase; FACULTY SHORTAGE "
                  "(8 faculty for 240 intake); no previous-year record in AICTE system."),
    dict(id="INST07", aicte_id="1-SP-0001007", name="Rajkot Kalan College of Engineering",
         district="Rajkot Kalan", trust="Kalan Shiksha Nyas", category="EoA",
         programmes={"B.Tech CSE": (60, 60), "B.Tech ECE": (60, 60)},
         land_acres=4.0, built_up_sqm=11800, university="univ_stu",
         dup_photo_from="INST02", shared_faculty_with="INST08",
         scenario="DUPLICATE lab photo (INST02's photo, resized + brightened). 3 faculty members "
                  "(same Faculty ID, name, DOB) also claimed by INST08 in the same academic year."),
    dict(id="INST08", aicte_id="1-SP-0001008", name="Ambikapuri Institute of Information Technology",
         district="Ambikapuri", trust="Shree Vidya Bharati Trust", category="EoA",
         programmes={"B.Tech IT": (60, 60), "B.Tech CSE": (60, 60)},
         land_acres=3.6, built_up_sqm=10400, university="univ_stu",
         shared_faculty_with="INST07",
         scenario="Shares the same 3 faculty members with INST07 (entity-graph case)."),
    dict(id="INST09", aicte_id="1-SP-0001009", name="Navgarh Women's Engineering College",
         district="Navgarh", trust="Matrushakti Shiksha Trust", category="EoA",
         programmes={"B.Tech CSE": (60, 60), "B.Tech ECE": (60, 60)},
         land_acres=4.5, built_up_sqm=12000, university="univ_stu",
         reuse_noc_from="INST01",
         scenario="REUSED Fire NOC: carries INST01's NOC number with INST09's name typed in "
                  "(producer = Microsoft Word). QR + registry point to INST01 -> MISMATCH; "
                  "entity graph shows the NOC number in 2 applications."),
    dict(id="INST10", aicte_id="1-SP-0001010", name="Kaveri Valley School of Engineering",
         district="Dhanpur", trust="Kaveri Valley Education Foundation", category="EoA",
         programmes={"B.Tech CSE": (60, 60), "B.Tech ME": (60, 60)},
         land_acres=5.2, built_up_sqm=13900, university="univ_kvu",
         claimed_prev_intake=240, blurry_accr=True, faculty_count=14,
         scenario="RECORD MISMATCH: form claims existing intake 240, AICTE record says 120. "
                  "Affiliation from KVU whose verification API is UNAVAILABLE. Accreditation "
                  "certificate is a blurry scan with unreadable QR -> MANUAL REVIEW."),
]

rng = random.Random(SEED)


def make_people(n, rng, used_ids):
    people = []
    for _ in range(n):
        while True:
            fid = f"FAC-{rng.randint(100000, 999999)}"
            if fid not in used_ids:
                used_ids.add(fid)
                break
        y, m, d = rng.randint(1965, 1994), rng.randint(1, 12), rng.randint(1, 28)
        people.append(dict(
            faculty_id=fid,
            name=f"{rng.choice(FIRST)} {rng.choice(LAST)}",
            dob=f"{y:04d}-{m:02d}-{d:02d}",
            qualification=rng.choice(QUAL),
            designation=rng.choice(DESIG),
            department=rng.choice(DEPTS),
            joining=f"{rng.randint(2012, 2025)}-{rng.randint(1, 12):02d}-01",
        ))
    return people
