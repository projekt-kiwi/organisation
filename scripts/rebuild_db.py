#!/usr/bin/env python3
"""
Rebuild kiwi.db from schools.csv, partner_workshops.csv, and school_workshops.csv.
Preserves schema and relationships:
  - hosting_organisations (partners) ← workshops (hosting_organisation_id)
  - school_workshop (school_id, workshop_id)
  - school_contact (school_id, person_id)
"""
import csv
import os
import sqlite3

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILES = os.path.join(ROOT, "files")
DB_PATH = os.path.join(ROOT, "kiwi.db")
PUBLIC_DB = os.path.join(ROOT, "public", "kiwi.db")

SCHEMA = """
CREATE TABLE schools (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    school_type TEXT NOT NULL
);
CREATE TABLE persons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email_primary TEXT,
    email_secondary TEXT
);
CREATE TABLE hosting_organisations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);
CREATE TABLE workshops (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    hosting_organisation_id INTEGER NOT NULL REFERENCES hosting_organisations(id)
);
CREATE TABLE school_contact (
    school_id INTEGER NOT NULL REFERENCES schools(id),
    person_id INTEGER NOT NULL REFERENCES persons(id),
    PRIMARY KEY (school_id, person_id)
);
CREATE TABLE school_workshop (
    school_id INTEGER NOT NULL REFERENCES schools(id),
    workshop_id INTEGER NOT NULL REFERENCES workshops(id),
    PRIMARY KEY (school_id, workshop_id)
);
CREATE INDEX idx_schools_type ON schools(school_type);
CREATE INDEX idx_workshops_host ON workshops(hosting_organisation_id);
CREATE INDEX idx_school_workshop_school ON school_workshop(school_id);
CREATE INDEX idx_school_workshop_workshop ON school_workshop(workshop_id);
"""


def parse_emails(emails_str):
    """Split 'a@x.at, b@y.at' into (primary, secondary or None)."""
    parts = [s.strip() for s in (emails_str or "").split(",") if s.strip()]
    return (parts[0], parts[1] if len(parts) > 1 else None)


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.executescript("DROP TABLE IF EXISTS school_workshop; DROP TABLE IF EXISTS school_contact; DROP TABLE IF EXISTS workshops; DROP TABLE IF EXISTS hosting_organisations; DROP TABLE IF EXISTS persons; DROP TABLE IF EXISTS schools;")
    conn.executescript(SCHEMA)

    # Maps for resolving names to ids
    school_key_to_id = {}  # (name, school_type) -> id
    person_key_to_id = {}  # (name, email_primary) -> id
    host_name_to_id = {}   # name -> id
    workshop_name_to_id = {}  # name -> id

    # 1) schools.csv → schools, persons, school_contact
    with open(os.path.join(FILES, "schools.csv"), newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            school_name = (row["School"] or "").strip()
            school_type = (row["School_Type"] or "").strip()
            names_str = (row.get("Name(s)", "") or "").strip()
            emails_str = (row.get("Email(s)", "") or "").strip()
            if not school_name or not school_type:
                continue
            cur = conn.execute(
                "INSERT INTO schools (name, school_type) VALUES (?, ?)",
                (school_name, school_type),
            )
            school_id = cur.lastrowid
            school_key_to_id[(school_name, school_type)] = school_id

            if names_str or emails_str:
                email_primary, email_secondary = parse_emails(emails_str)
                name = names_str or "(Unbekannt)"
                person_key = (name, email_primary or "")
                if person_key not in person_key_to_id:
                    conn.execute(
                        "INSERT INTO persons (name, email_primary, email_secondary) VALUES (?, ?, ?)",
                        (name, email_primary, email_secondary),
                    )
                    person_key_to_id[person_key] = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
                person_id = person_key_to_id[person_key]
                conn.execute(
                    "INSERT OR IGNORE INTO school_contact (school_id, person_id) VALUES (?, ?)",
                    (school_id, person_id),
                )

    # 2) partner_workshops.csv → hosting_organisations, workshops (and optionally school_workshop)
    # Supports: "Company,Workshop" or "School,School_Type,Workshop,Hosting_Organisation"
    with open(os.path.join(FILES, "partner_workshops.csv"), newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        fieldnames = [k.strip() for k in (reader.fieldnames or [])]
        has_company = "Company" in fieldnames
        has_host_org = "Hosting_Organisation" in fieldnames
        has_school = "School" in fieldnames and "School_Type" in fieldnames
        for row in reader:
            row = {k.strip(): (v or "").strip() for k, v in row.items()}
            if has_company:
                company = row.get("Company", "")
                workshop_name = row.get("Workshop", "")
            elif has_host_org:
                company = row.get("Hosting_Organisation", "")
                workshop_name = row.get("Workshop", "")
            else:
                continue
            if not company or not workshop_name:
                continue
            if company not in host_name_to_id:
                conn.execute("INSERT INTO hosting_organisations (name) VALUES (?)", (company,))
                host_name_to_id[company] = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            host_id = host_name_to_id[company]
            conn.execute(
                "INSERT INTO workshops (name, hosting_organisation_id) VALUES (?, ?)",
                (workshop_name, host_id),
            )
            workshop_name_to_id[workshop_name] = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            if has_school:
                school_name = row.get("School", "")
                school_type = row.get("School_Type", "")
                if school_name and school_type:
                    school_id = school_key_to_id.get((school_name, school_type))
                    workshop_id = workshop_name_to_id.get(workshop_name)
                    if school_id and workshop_id:
                        conn.execute(
                            "INSERT OR IGNORE INTO school_workshop (school_id, workshop_id) VALUES (?, ?)",
                            (school_id, workshop_id),
                        )

    # 3) school_workshops.csv → school_workshop (link by school name+type and workshop name)
    with open(os.path.join(FILES, "school_workshops.csv"), newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            school_name = (row["School"] or "").strip()
            school_type = (row["School_Type"] or "").strip()
            workshop_name = (row["Workshop"] or "").strip()
            if not school_name or not school_type or not workshop_name:
                continue
            school_id = school_key_to_id.get((school_name, school_type))
            workshop_id = workshop_name_to_id.get(workshop_name)
            if school_id is None:
                print(f"Warning: school not found: {school_name!r} ({school_type})")
                continue
            if workshop_id is None:
                print(f"Warning: workshop not found: {workshop_name!r}")
                continue
            conn.execute(
                "INSERT OR IGNORE INTO school_workshop (school_id, workshop_id) VALUES (?, ?)",
                (school_id, workshop_id),
            )

    conn.commit()

    # Sanity checks
    n_schools = conn.execute("SELECT COUNT(*) FROM schools").fetchone()[0]
    n_persons = conn.execute("SELECT COUNT(*) FROM persons").fetchone()[0]
    n_hosts = conn.execute("SELECT COUNT(*) FROM hosting_organisations").fetchone()[0]
    n_workshops = conn.execute("SELECT COUNT(*) FROM workshops").fetchone()[0]
    n_contact = conn.execute("SELECT COUNT(*) FROM school_contact").fetchone()[0]
    n_school_workshop = conn.execute("SELECT COUNT(*) FROM school_workshop").fetchone()[0]
    print(f"schools: {n_schools}, persons: {n_persons}, hosting_organisations: {n_hosts}, workshops: {n_workshops}")
    print(f"school_contact: {n_contact}, school_workshop: {n_school_workshop}")

    conn.close()

    # Copy to public/ for the app
    import shutil
    shutil.copy2(DB_PATH, PUBLIC_DB)
    print(f"Copied {DB_PATH} -> {PUBLIC_DB}")


if __name__ == "__main__":
    main()
