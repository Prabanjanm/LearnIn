"""
Seed the REAL GATE academic hierarchy: Exam -> Department (GATE paper /
discipline) -> Subject. Deliberately creates NOTHING below Subject - no
Paper/Question/Option/MockTest/Resource/Blog rows. Those are added later,
once real question content exists, through the normal admin CRUD.

Idempotent and repeatable: every row is looked up by its natural unique key
before being inserted (Exam.code, Department.(exam_id, code),
Subject.(department_id, slug)) - running this script any number of times
converges on the same set of rows instead of duplicating them. The whole run
is one transaction: either everything commits, or nothing does.

Data source: the official GATE 2026 organizing institute (IIT Guwahati,
gate2026.iitg.ac.in) paper list and syllabus PDFs, cross-checked against
established exam-prep aggregators where the raw PDF couldn't be parsed as
text. Two papers (Architecture and Planning / AR, Geology & Geophysics / GG)
have a Part A/B1/B2 syllabus structure that doesn't reduce to a clean flat
subject list from the sources available - they are seeded with ZERO subjects
rather than an invented breakdown; see GATE_PAPERS below and the run's final
report for exactly which papers/subjects were inserted.

Usage:
    cd backend
    python scripts/seed_gate_hierarchy.py
"""
import sys

sys.path.insert(0, ".")

import app.models  # noqa: E402, F401 - registers every model on Base.metadata before any query runs
from app.core.database import SessionLocal  # noqa: E402
from app.core.enums import StatusEnum  # noqa: E402
from app.common.utils.slug import generate_slug  # noqa: E402
from app.modules.department.model import Department  # noqa: E402
from app.modules.exam.model import Exam  # noqa: E402
from app.modules.subject.model import Subject  # noqa: E402

GATE_EXAM = {
    "code": "GATE",
    "name": "GATE",
    "description": (
        "Graduate Aptitude Test in Engineering - a national-level exam for "
        "admission to postgraduate engineering/science programs and PSU "
        "recruitment, conducted on a rotating basis by IISc and the IITs."
    ),
}

# Each entry: GATE paper code, full paper name, and its official top-level
# syllabus subjects/sections. An empty "subjects" list means the paper's
# hierarchy exists (so content can be added later) but its subject
# breakdown could not be confidently verified this pass - see the module
# docstring and the seed run's final report.
GATE_PAPERS = [
    {"code": "AE", "name": "Aerospace Engineering", "subjects": [
        "Engineering Mathematics", "Flight Mechanics", "Space Dynamics", "Aerodynamics", "Structures", "Propulsion",
    ]},
    {"code": "AG", "name": "Agricultural Engineering", "subjects": [
        "Engineering Mathematics", "Farm Machinery", "Farm Power", "Soil and Water Conservation Engineering",
        "Irrigation and Drainage Engineering", "Agricultural Process Engineering", "Dairy and Food Engineering",
    ]},
    {"code": "AR", "name": "Architecture and Planning", "subjects": []},
    {"code": "BM", "name": "Biomedical Engineering", "subjects": [
        "Engineering Mathematics", "Electrical Circuits", "Signals and Systems", "Analog and Digital Electronics",
        "Measurements and Control Systems", "Sensors and Bioinstrumentation", "Human Anatomy and Physiology",
        "Medical Imaging Systems", "Biomechanics", "Biomaterials",
    ]},
    {"code": "BT", "name": "Biotechnology", "subjects": [
        "Engineering Mathematics", "General Biology", "Genetics", "Cellular and Molecular Biology",
        "Fundamentals of Biological Engineering", "Bioprocess Engineering and Process Biotechnology",
        "Plant, Animal and Microbial Biotechnology", "Recombinant DNA Technology and Other Tools",
    ]},
    {"code": "CE", "name": "Civil Engineering", "subjects": [
        "Engineering Mathematics", "Structural Engineering", "Geotechnical Engineering",
        "Water Resources Engineering", "Environmental Engineering", "Transportation Engineering",
        "Geomatics Engineering",
    ]},
    {"code": "CH", "name": "Chemical Engineering", "subjects": [
        "Engineering Mathematics", "Process Calculations and Thermodynamics",
        "Fluid Mechanics and Mechanical Operations", "Heat Transfer", "Mass Transfer",
        "Chemical Reaction Engineering", "Instrumentation and Process Control",
        "Plant Design and Economics", "Chemical Technology",
    ]},
    {"code": "CS", "name": "Computer Science & Information Technology", "subjects": [
        "Engineering Mathematics", "Digital Logic", "Computer Organization and Architecture",
        "Programming and Data Structures", "Algorithms", "Theory of Computation", "Compiler Design",
        "Operating Systems", "Databases", "Computer Networks",
    ]},
    {"code": "CY", "name": "Chemistry", "subjects": [
        "Physical Chemistry", "Inorganic Chemistry", "Organic Chemistry",
    ]},
    {"code": "DA", "name": "Data Science & Artificial Intelligence", "subjects": [
        "Probability and Statistics", "Linear Algebra", "Calculus and Optimization",
        "Programming, Data Structures and Algorithms", "Database Management and Warehousing",
        "Machine Learning", "Artificial Intelligence",
    ]},
    {"code": "EC", "name": "Electronics & Communication Engineering", "subjects": [
        "Engineering Mathematics", "Networks, Signals and Systems", "Electronic Devices", "Analog Circuits",
        "Digital Circuits", "Control Systems", "Communications", "Electromagnetics",
    ]},
    {"code": "EE", "name": "Electrical Engineering", "subjects": [
        "Engineering Mathematics", "Electric Circuits", "Electromagnetic Fields", "Signals and Systems",
        "Electrical Machines", "Power Systems", "Control Systems", "Electrical and Electronic Measurements",
        "Analog and Digital Electronics", "Power Electronics",
    ]},
    {"code": "ES", "name": "Environmental Science & Engineering", "subjects": [
        "Mathematics", "Environmental Chemistry", "Environmental Microbiology",
        "Water Resources and Environmental Hydraulics", "Water and Wastewater Treatment and Management",
        "Air and Noise Pollution", "Solid and Hazardous Waste Management",
        "Global and Regional Environmental Issues", "Environmental Management and Sustainable Development",
    ]},
    {"code": "EY", "name": "Ecology and Evolution", "subjects": [
        "Ecology", "Evolution", "Mathematics and Quantitative Ecology", "Behavioural Ecology",
        "Applied Ecology and Evolution",
    ]},
    {"code": "GE", "name": "Geomatics Engineering", "subjects": [
        "Engineering Mathematics", "GNSS", "Remote Sensing", "GIS", "Land Surveying", "Maps",
        "Aerial Photogrammetry", "Data Quantization and Processing", "Digital Image Processing",
        "Radiometric and Geometric Corrections",
    ]},
    {"code": "GG", "name": "Geology & Geophysics", "subjects": []},
    {"code": "XH", "name": "Humanities & Social Sciences", "subjects": [
        "Reasoning and Comprehension", "Economics", "English", "Linguistics", "Philosophy", "Psychology",
        "Sociology",
    ]},
    {"code": "IN", "name": "Instrumentation Engineering", "subjects": [
        "Engineering Mathematics", "Electricity and Magnetism", "Electrical Circuits and Machines",
        "Signals and Systems", "Control Systems", "Analog Electronics", "Digital Electronics", "Measurements",
        "Sensors and Industrial Instrumentation", "Communication and Optical Instrumentation",
    ]},
    {"code": "XL", "name": "Life Sciences", "subjects": [
        "Chemistry", "Biochemistry", "Botany", "Microbiology", "Zoology", "Food Technology",
    ]},
    {"code": "MA", "name": "Mathematics", "subjects": [
        "Calculus", "Linear Algebra", "Real Analysis", "Complex Analysis", "Ordinary Differential Equations",
        "Algebra", "Functional Analysis", "Numerical Analysis", "Partial Differential Equations", "Topology",
        "Linear Programming",
    ]},
    {"code": "ME", "name": "Mechanical Engineering", "subjects": [
        "Engineering Mathematics", "Applied Mechanics and Design", "Fluid Mechanics and Thermal Sciences",
        "Materials, Manufacturing and Industrial Engineering",
    ]},
    {"code": "MN", "name": "Mining Engineering", "subjects": [
        "Engineering Mathematics", "Mining Geology, Mine Development and Surveying",
        "Geomechanics and Ground Control", "Mining Methods and Machinery",
        "Mine Ventilation and Underground Hazards", "Mineral Economics, Mine Planning and Systems Engineering",
    ]},
    {"code": "MT", "name": "Metallurgical Engineering", "subjects": [
        "Engineering Mathematics", "Metallurgical Thermodynamics", "Transport Phenomena and Rate Processes",
        "Mineral Processing and Extractive Metallurgy", "Physical Metallurgy", "Mechanical Metallurgy",
        "Manufacturing Processes",
    ]},
    {"code": "NM", "name": "Naval Architecture & Marine Engineering", "subjects": [
        "Engineering Mathematics", "Applied Mechanics and Structures", "Fluid Mechanics and Marine Hydrodynamics",
        "Naval Architecture and Ocean Engineering", "Thermodynamics and Marine Engineering",
    ]},
    {"code": "PE", "name": "Petroleum Engineering", "subjects": [
        "Engineering Mathematics", "Petroleum Exploration", "Oil and Gas Well Drilling Technology",
        "Reservoir Engineering", "Petroleum Production Operations", "Offshore Drilling and Production Practices",
        "Petroleum Formation Evaluation", "Oil and Gas Well Testing",
        "Health, Safety and Environment in Petroleum Industry", "Enhanced Oil Recovery Techniques",
    ]},
    {"code": "PH", "name": "Physics", "subjects": [
        "Mathematical Physics", "Classical Mechanics", "Electromagnetic Theory", "Quantum Mechanics",
        "Thermodynamics and Statistical Physics", "Atomic and Molecular Physics", "Solid State Physics",
        "Electronics", "Nuclear and Particle Physics",
    ]},
    {"code": "PI", "name": "Production & Industrial Engineering", "subjects": [
        "Engineering Mathematics", "General Engineering", "Manufacturing Processes I", "Manufacturing Processes II",
        "Quality and Reliability", "Industrial Engineering", "Operations Research and Operations Management",
    ]},
    {"code": "ST", "name": "Statistics", "subjects": [
        "Calculus", "Linear Algebra", "Probability", "Multivariate Analysis", "Stochastic Processes",
        "Estimation", "Testing of Hypotheses", "Regression Analysis", "Non-parametric Statistics",
    ]},
    {"code": "TF", "name": "Textile Engineering & Fibre Science", "subjects": [
        "Textile Fibres", "Yarn Manufacture", "Fabric Manufacture", "Textile Testing", "Chemical Processing",
    ]},
    {"code": "XE", "name": "Engineering Sciences", "subjects": [
        "Engineering Mathematics", "Fluid Mechanics", "Materials Science", "Solid Mechanics", "Thermodynamics",
        "Polymer Science and Engineering", "Food Technology", "Atmospheric and Oceanic Sciences", "Energy Science",
    ]},
]

UNVERIFIED_PAPER_CODES = {"AR", "GG"}


def get_or_create_exam(db) -> Exam:
    exam = db.query(Exam).filter(Exam.code == GATE_EXAM["code"]).first()
    if exam is not None:
        return exam

    exam = Exam(
        name=GATE_EXAM["name"],
        code=GATE_EXAM["code"],
        description=GATE_EXAM["description"],
        slug=generate_slug(GATE_EXAM["name"]),
        status=StatusEnum.PUBLISHED,
    )
    db.add(exam)
    db.flush()
    return exam


def get_or_create_department(db, exam: Exam, code: str, name: str) -> tuple[Department, bool]:
    department = (
        db.query(Department)
        .filter(Department.exam_id == exam.id, Department.code == code)
        .first()
    )
    if department is not None:
        return department, False

    department = Department(
        exam_id=exam.id,
        name=name,
        code=code,
        slug=generate_slug(name),
        status=StatusEnum.PUBLISHED,
    )
    db.add(department)
    db.flush()
    return department, True


def get_or_create_subject(db, department: Department, name: str) -> tuple[Subject, bool]:
    slug = generate_slug(name)
    subject = (
        db.query(Subject)
        .filter(Subject.department_id == department.id, Subject.slug == slug)
        .first()
    )
    if subject is not None:
        return subject, False

    subject = Subject(
        department_id=department.id,
        name=name,
        slug=slug,
        status=StatusEnum.PUBLISHED,
    )
    db.add(subject)
    db.flush()
    return subject, True


def main() -> None:
    db = SessionLocal()
    report: list[tuple[str, str, list[str], list[str]]] = []  # (code, name, subjects_created, subjects_existing)

    try:
        exam = get_or_create_exam(db)

        for paper in GATE_PAPERS:
            department, _ = get_or_create_department(db, exam, paper["code"], paper["name"])

            created, existing = [], []
            for subject_name in paper["subjects"]:
                subject, was_created = get_or_create_subject(db, department, subject_name)
                (created if was_created else existing).append(subject.name)

            report.append((paper["code"], paper["name"], created, existing))

        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    total_departments = len(GATE_PAPERS)
    total_new_subjects = sum(len(created) for _, _, created, _ in report)
    total_existing_subjects = sum(len(existing) for _, _, _, existing in report)

    print(f"GATE exam: {GATE_EXAM['name']} (code={GATE_EXAM['code']})")
    print(f"Departments (GATE papers): {total_departments}")
    print(f"Subjects newly created this run: {total_new_subjects}")
    print(f"Subjects already present (skipped, idempotent): {total_existing_subjects}")
    print()

    for code, name, created, existing in report:
        subject_count = len(created) + len(existing)
        flag = "  [UNVERIFIED SUBJECT LIST - hierarchy only, see script docstring]" if code in UNVERIFIED_PAPER_CODES else ""
        print(f"- {name} ({code}) - {subject_count} subject(s){flag}")
        for s in created:
            print(f"    + {s} (created)")
        for s in existing:
            print(f"    = {s} (already existed)")


if __name__ == "__main__":
    main()
