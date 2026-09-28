"""
    Desc: extracts raw text, tables and images from source files for skeds
    Creator: Kirosha
"""

from __future__ import annotations

import csv
import json
import tempfile
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from based.utils.__console import log_err

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}
MIN_TEXT_CHARS_PER_PAGE = 200


@dataclass
class Extracted:
    text: str = ""
    tables: list[list[list[str]]] = field(default_factory=list)
    images: list[Path] = field(default_factory=list)
    temp_dirs: list[Path] = field(default_factory=list)


def extract(source: Path) -> Extracted:
    suffix = source.suffix.lower()
    try:
        if suffix in (".txt", ".md"):
            return _extract_plain_text(source)
        if suffix in (".csv", ".tsv"):
            return _extract_csv(source, suffix)
        if suffix in (".xlsx", ".xls"):
            return _extract_xlsx(source)
        if suffix == ".docx":
            return _extract_docx(source)
        if suffix == ".rtf":
            return _extract_rtf(source)
        if suffix == ".pdf":
            return _extract_pdf(source)
        if suffix == ".pptx":
            return _extract_pptx(source)
        if suffix in IMAGE_EXTENSIONS:
            return Extracted(images=[source])
        if suffix == ".ics":
            return _extract_ics(source)
        if suffix == ".json":
            return _extract_json(source)
        log_err(f"unsupported file extension: {suffix}")
        return Extracted()
    except ImportError as exc:
        log_err(f"missing dependency for {suffix}: {exc}. install based[skeds]")
        return Extracted()
    except Exception as exc:
        log_err(f"failed to extract {source}: {exc}")
        return Extracted()


def _temp_dir() -> Path:
    path = Path(tempfile.gettempdir()) / "based" / "skeds" / str(uuid.uuid4())
    path.mkdir(parents=True, exist_ok=True)
    return path


def _extract_plain_text(source: Path) -> Extracted:
    return Extracted(text=source.read_text(encoding="utf-8", errors="ignore"))


def _extract_csv(source: Path, suffix: str) -> Extracted:
    delimiter = "\t" if suffix == ".tsv" else ","
    with source.open(newline="", encoding="utf-8", errors="ignore") as handle:
        rows = list(csv.reader(handle, delimiter=delimiter))
    text = "\n".join(" | ".join(row) for row in rows)
    return Extracted(text=text, tables=[rows] if rows else [])


def _extract_xlsx(source: Path) -> Extracted:
    import openpyxl

    workbook = openpyxl.load_workbook(source, data_only=True)
    tables: list[list[list[str]]] = []
    text_parts: list[str] = []
    for sheet in workbook.worksheets:
        rows = [
            [str(cell) if cell is not None else "" for cell in row]
            for row in sheet.iter_rows(values_only=True)
        ]
        if not rows:
            continue
        tables.append(rows)
        text_parts.append(f"# {sheet.title}")
        text_parts.append("\n".join(" | ".join(row) for row in rows))
    return Extracted(text="\n\n".join(text_parts), tables=tables)


def _extract_docx(source: Path) -> Extracted:
    import docx

    document = docx.Document(str(source))
    text_parts = [paragraph.text for paragraph in document.paragraphs if paragraph.text]
    tables: list[list[list[str]]] = []
    for table in document.tables:
        rows = [[cell.text for cell in row.cells] for row in table.rows]
        tables.append(rows)
    return Extracted(text="\n".join(text_parts), tables=tables)


def _extract_rtf(source: Path) -> Extracted:
    from striprtf.striprtf import rtf_to_text

    raw = source.read_text(encoding="utf-8", errors="ignore")
    return Extracted(text=rtf_to_text(raw))


def _extract_pdf(source: Path) -> Extracted:
    import pdfplumber
    import pypdfium2 as pdfium

    text_parts: list[str] = []
    tables: list[list[list[str]]] = []
    page_count = 0
    with pdfplumber.open(source) as pdf:
        page_count = len(pdf.pages)
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)
            for table in page.extract_tables():
                tables.append(table)

    text = "\n".join(text_parts)
    images: list[Path] = []
    temp_dirs: list[Path] = []

    if len(text) < MIN_TEXT_CHARS_PER_PAGE * page_count:
        output_dir = _temp_dir()
        temp_dirs.append(output_dir)
        pdf_doc = pdfium.PdfDocument(source)
        for index, page in enumerate(pdf_doc):
            bitmap = page.render(scale=2.0)
            pil_image = bitmap.to_pil()
            image_path = output_dir / f"page_{index}.png"
            pil_image.save(image_path)
            images.append(image_path)

    return Extracted(text=text, tables=tables, images=images, temp_dirs=temp_dirs)


def _extract_pptx(source: Path) -> Extracted:
    from pptx import Presentation
    from pptx.enum.shapes import MSO_SHAPE_TYPE

    presentation = Presentation(str(source))
    text_parts: list[str] = []
    picture_candidates: list = []
    output_dir = _temp_dir()
    temp_dirs: list[Path] = [output_dir]

    for slide_index, slide in enumerate(presentation.slides):
        for shape_index, shape in enumerate(slide.shapes):
            if shape.has_text_frame:
                for paragraph in shape.text_frame.paragraphs:
                    text = "".join(run.text for run in paragraph.runs)
                    if text:
                        text_parts.append(text)
            if shape.shape_type == MSO_SHAPE_TYPE.PICTURE:
                picture_candidates.append((slide_index, shape_index, shape.image))

    images: list[Path] = []
    text = "\n".join(text_parts)
    if len(text) < MIN_TEXT_CHARS_PER_PAGE * max(1, len(presentation.slides)):
        for slide_index, shape_index, image in picture_candidates:
            image_path = output_dir / f"slide_{slide_index}_{shape_index}.{image.ext}"
            image_path.write_bytes(image.blob)
            images.append(image_path)
    else:
        temp_dirs.clear()

    return Extracted(text=text, images=images, temp_dirs=temp_dirs)


def _extract_ics(source: Path) -> Extracted:
    from icalendar import Calendar

    calendar = Calendar.from_ical(source.read_bytes())
    lines: list[str] = []
    for component in calendar.walk("VEVENT"):
        summary = component.get("summary")
        start = component.get("dtstart")
        end = component.get("dtend")
        location = component.get("location")
        lines.append(
            f"{summary} | {start.dt if start else ''} | {end.dt if end else ''} | {location or ''}"
        )
    return Extracted(text="\n".join(lines))


def _extract_json(source: Path) -> Extracted:
    data = json.loads(source.read_text(encoding="utf-8"))
    if isinstance(data, dict) and "lessons" in data and "group_name" in data:
        log_err("json already looks like a schedule, skipping llm")
    return Extracted(text=json.dumps(data, indent=2, ensure_ascii=False))
