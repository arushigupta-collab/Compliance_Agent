"""Generate a dummy passport PDF that PASSES both KYC checks.

The KYC screen checks two things:
  1) Face match — the passport must contain a face that matches your live selfie.
  2) Validity   — the passport expiry must be >= 6 months after REVIEW_DATE
                  (2026-01-15), i.e. >= 2026-07-15, and not expired.

This tool embeds a face image you supply and writes the passport fields in the
same label/value layout the extractor reads, so both checks pass.

Usage:
    python tools/make_dummy_passport.py --face /path/to/face.jpg \
        --name "Test Founder" --expiry 2032-01-01 --out dummy_passport.pdf

Then on the KYC page: upload dummy_passport.pdf as the passport, and take your
live selfie of the SAME face -> real OpenCV match + valid expiry -> Verified.

Notes:
  - The face must be a real, photo-realistic face so OpenCV (YuNet) can detect it.
    Use your OWN photo, or an AI-generated face (e.g. a "this-person-does-not-exist"
    style image). Never use a real third party's passport photo.
  - For the selfie to match, use the same person's face you embedded here.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import fitz  # PyMuPDF


def build(face_path: str, out_path: str, name: str, nationality: str,
          dob: str, expiry: str, passport_no: str) -> None:
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)  # A4

    page.insert_text((60, 70), "PASSPORT", fontsize=20, fontname="helv")
    page.insert_text((60, 92), "Machine-readable travel document (demo)", fontsize=9, fontname="helv")

    # Face photo (top-right box).
    if face_path and Path(face_path).exists():
        rect = fitz.Rect(400, 110, 540, 290)
        page.insert_image(rect, filename=face_path)
    else:
        page.insert_text((400, 150), "[no face image supplied]", fontsize=9, color=(1, 0, 0))

    # Fields as label / value lines (the extractor reads these).
    fields = [
        ("Full name", name),
        ("Nationality", nationality),
        ("Date of birth", dob),
        ("Place of birth", "Demo City"),
        ("Passport no. (synthetic)", passport_no),
        ("Date of issue", "2022-01-01"),
        ("Date of expiry", expiry),
        ("Issuing authority", "Demo Authority"),
    ]
    y = 150
    for label, value in fields:
        page.insert_text((60, y), label, fontsize=11, fontname="helv")
        page.insert_text((60, y + 16), value, fontsize=12, fontname="helv")
        y += 44

    doc.save(out_path)
    doc.close()
    print(f"Wrote {out_path}  (name={name}, expiry={expiry})")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--face", default="", help="path to a real/AI-generated face image")
    ap.add_argument("--name", default="Test Founder")
    ap.add_argument("--nationality", default="India")
    ap.add_argument("--dob", default="1990-05-01")
    ap.add_argument("--expiry", default="2032-01-01", help="must be >= 2026-07-15 to pass")
    ap.add_argument("--passport-no", default="D1234567")
    ap.add_argument("--out", default="dummy_passport.pdf")
    a = ap.parse_args()
    build(a.face, a.out, a.name, a.nationality, a.dob, a.expiry, a.passport_no)


if __name__ == "__main__":
    main()
