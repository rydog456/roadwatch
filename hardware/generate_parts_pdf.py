"""Build a printable capture PDF: python hardware/generate_parts_pdf.py"""

from __future__ import annotations

from pathlib import Path

from fpdf import FPDF

OUT = Path(__file__).resolve().parent / "InfraPulse_Parts_List.pdf"
DOWNLOADS = Path.home() / "Downloads" / "InfraPulse_Parts_List.pdf"

CORE = [
    (1, "iPhone 12 Pro or newer (Pro Max preferred)", "LiDAR + gyro + GPS + baro + ARKit", "owned"),
    (1, "3D Scanner App, Polycam, or ARKit export", "ASCII PLY per walk", "$0-40"),
    (1, "Second walker on the same block", "Densifies merged.ply", "$0"),
    (1, "Laptop", "Fusion, LLM, dashboard", "owned"),
]

RECOMMENDED = [
    (1, "Phone lanyard / two-hand grip", "Higher gyro pose quality", "$10"),
    (1, "Notes template (heat, trench, rut, tree)", "Feeds LA LLM priors", "$0"),
    (1, "USB-C cable + laptop folder", "Drop PLY into data/scenes", "$0"),
]

SKIP = [
    ("Raspberry Pi / MPU-6050 kit", "Hardware path retired"),
    ("HC-SR04 ultrasonic", "Not NDT"),
    ("GPR / professional ultrasound", "Later handoff, not this MVP"),
    ("Drones this weekend", "No safe flight + merge pipeline"),
]


class PartsPDF(FPDF):
    def header(self) -> None:
        self.set_fill_color(11, 18, 32)
        self.rect(0, 0, 216, 28, "F")
        self.set_text_color(232, 238, 247)
        self.set_font("Helvetica", "B", 16)
        self.set_xy(12, 8)
        self.cell(0, 8, "InfraPulse  |  iPhone Pro Max capture")
        self.set_font("Helvetica", "", 9)
        self.set_xy(12, 16)
        self.cell(0, 6, "LiDAR PLY merge  |  LA-weighted LLM  |  no Pi kit")
        self.ln(18)
        self.set_text_color(20, 20, 20)

    def footer(self) -> None:
        self.set_y(-12)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(120, 120, 120)
        self.cell(
            0,
            8,
            "Screening only. Do not claim structural capacity from a phone scan.  Page "
            + str(self.page_no()),
            align="C",
        )


def section(pdf: PartsPDF, title: str) -> None:
    pdf.ln(3)
    pdf.set_fill_color(47, 111, 237)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 8, "  " + title, fill=True, new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(20, 20, 20)
    pdf.ln(1)


def header_row(pdf: PartsPDF) -> None:
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_fill_color(230, 236, 247)
    pdf.cell(10, 7, "Got", border=1, fill=True, align="C")
    pdf.cell(12, 7, "Qty", border=1, fill=True, align="C")
    pdf.cell(78, 7, "Part", border=1, fill=True)
    pdf.cell(62, 7, "Why", border=1, fill=True)
    pdf.cell(22, 7, "Approx", border=1, fill=True, align="R", new_x="LMARGIN", new_y="NEXT")


def item_row(pdf: PartsPDF, qty: int, part: str, why: str, price: str, shade: bool) -> None:
    pdf.set_font("Helvetica", "", 8)
    pdf.set_fill_color(247, 249, 252 if shade else 255)
    if shade:
        pdf.set_fill_color(247, 249, 252)
    else:
        pdf.set_fill_color(255, 255, 255)
    pdf.cell(10, 8, "  [ ]", border=1, fill=True, align="C")
    pdf.cell(12, 8, str(qty), border=1, fill=True, align="C")
    pdf.cell(78, 8, part, border=1, fill=True)
    pdf.cell(62, 8, why, border=1, fill=True)
    pdf.cell(22, 8, price, border=1, fill=True, align="R", new_x="LMARGIN", new_y="NEXT")


def skip_row(pdf: PartsPDF, part: str, why: str) -> None:
    pdf.set_font("Helvetica", "", 8)
    pdf.set_fill_color(255, 244, 244)
    pdf.cell(100, 8, part, border=1, fill=True)
    pdf.cell(84, 8, why, border=1, fill=True, new_x="LMARGIN", new_y="NEXT")


def build() -> Path:
    pdf = PartsPDF(orientation="P", unit="mm", format="Letter")
    pdf.set_auto_page_break(auto=True, margin=16)
    pdf.add_page()
    pdf.set_font("Helvetica", "", 10)
    pdf.multi_cell(
        0,
        5,
        "Capture is iPhone Pro / Pro Max only. Export ASCII PLY. A second person "
        "scanning the same GPS cell densifies merged.ply. Gyro/compass align walks; "
        "the LLM is trained with Los Angeles distress priors.",
    )

    section(pdf, "1. CORE  (you already own this)")
    header_row(pdf)
    for i, row in enumerate(CORE):
        item_row(pdf, *row, shade=i % 2 == 1)

    section(pdf, "2. RECOMMENDED")
    header_row(pdf)
    for i, row in enumerate(RECOMMENDED):
        item_row(pdf, *row, shade=i % 2 == 1)

    section(pdf, "3. DO NOT BUY")
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_fill_color(90, 29, 42)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(100, 7, "Skip", border=1, fill=True)
    pdf.cell(84, 7, "Reason", border=1, fill=True, new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(20, 20, 20)
    for row in SKIP:
        skip_row(pdf, *row)

    pdf.ln(4)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 6, "On-device sensors used", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)
    pdf.multi_cell(
        0,
        5,
        "LiDAR mesh, camera, gyroscope, accelerometer, magnetometer, GPS, barometer, "
        "ARKit tracking state. Files: contrib_*.ply + merged.ply + scene.ipulse.json.",
    )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(OUT))
    try:
        DOWNLOADS.write_bytes(OUT.read_bytes())
    except OSError:
        pass
    return OUT


if __name__ == "__main__":
    path = build()
    print(path)
    if DOWNLOADS.exists():
        print(DOWNLOADS)
