"""Render a few carrier freight bills as PDFs for the Gemini document-audit demo.

    python -m tms_data.sample_invoices --csv data/generated --out data/sample_invoices

Produces: a clean invoice, one billed above the contract rate, and a scanned-style invoice with an
illegible fuel surcharge plus detention that the stop records do not support.
Requires: pip install reportlab
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


def _rows(path: Path) -> list[dict]:
    with path.open() as fh:
        return list(csv.DictReader(fh))


def render(inv: dict, carrier: dict, out: Path, smudge_fuel: bool = False) -> None:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas

    c = canvas.Canvas(str(out), pagesize=letter)
    w, h = letter
    c.setFont("Helvetica-Bold", 18)
    c.drawString(50, h - 60, carrier["carrier_name"].upper())
    c.setFont("Helvetica", 10)
    c.drawString(50, h - 76, f"SCAC: {carrier['scac']}   MC# {sum(map(ord, carrier['scac'])) * 1373 % 900000 + 100000}")
    c.setFont("Helvetica-Bold", 14)
    c.drawRightString(w - 50, h - 60, "FREIGHT INVOICE")
    c.setFont("Helvetica", 10)
    c.drawRightString(w - 50, h - 76, f"Invoice #: {inv['carrier_invoice_id']}")
    c.drawRightString(w - 50, h - 90, f"Invoice date: {inv['invoice_date']}")
    c.drawString(50, h - 120, "Bill to: Grocery & Foodservice Distribution (synthetic), Freight Payables")
    c.drawString(50, h - 134, f"Shipper reference / Load #: {inv['load_id']}")
    y = h - 180
    c.setFont("Helvetica-Bold", 11)
    c.drawString(50, y, "Description")
    c.drawRightString(w - 50, y, "Amount (USD)")
    c.line(50, y - 4, w - 50, y - 4)
    c.setFont("Helvetica", 11)
    lines = [
        (f"Linehaul  {float(inv['billed_miles']):.1f} mi @ ${float(inv['billed_rate_per_mile'] or 0):.3f}/mi",
         float(inv["billed_linehaul"])),
        ("Fuel surcharge (DOE)", None if smudge_fuel else float(inv["billed_fuel_surcharge"] or 0)),
        ("Detention", float(inv["billed_detention"])),
        (f"Lumper{' (receipt attached)' if inv['lumper_receipt_attached'] == 'true' else ''}", float(inv["billed_lumper"])),
        ("Other accessorials", float(inv["billed_other"])),
    ]
    total = 0.0
    for desc, amt in lines:
        y -= 22
        c.drawString(50, y, desc)
        if amt is None:
            c.setFillColor(colors.Color(0.55, 0.55, 0.55))
            c.rect(w - 130, y - 3, 80, 14, fill=1, stroke=0)
            c.setFillColor(colors.black)
        else:
            c.drawRightString(w - 50, y, f"{amt:,.2f}")
            total += amt
    y -= 30
    c.line(50, y + 14, w - 50, y + 14)
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y, "TOTAL DUE")
    c.drawRightString(w - 50, y, f"{float(inv['billed_total']):,.2f}")
    c.setFont("Helvetica-Oblique", 9)
    c.drawString(50, 60, "Remit within 30 days. Synthetic document generated for the TMS Intelligence hackathon demo.")
    c.save()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default="data/generated", type=Path)
    ap.add_argument("--out", default="data/sample_invoices", type=Path)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    invoices = {r["carrier_invoice_id"]: r for r in _rows(a.csv / "carrier_invoices.csv")}
    carriers = {r["carrier_id"]: r for r in _rows(a.csv / "carriers.csv")}
    truth = {r["carrier_invoice_id"]: r["error_code"] for r in _rows(a.csv / "_truth_invoice_errors.csv")}
    clean = next(i for i, r in invoices.items() if i not in truth and r["billed_fuel_surcharge"] and float(r["billed_lumper"]) == 0)
    rate = next(i for i, c in truth.items() if c == "RATE_ABOVE_CONTRACT")
    det = next(i for i, c in truth.items() if c == "DETENTION_NO_EVIDENCE")
    picks = [(clean, "01_clean", False), (rate, "02_rate_above_contract", False), (det, "03_scanned_detention_illegible_fuel", True)]
    for inv_id, label, smudge in picks:
        inv = invoices[inv_id]
        path = a.out / f"{label}_{inv_id}.pdf"
        render(inv, carriers[inv["carrier_id"]], path, smudge_fuel=smudge)
        print(path)


if __name__ == "__main__":
    main()
