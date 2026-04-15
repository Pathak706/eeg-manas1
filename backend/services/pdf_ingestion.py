"""
PDF Ingestion Service.

Extracts raw text from a clinical report PDF and converts it to clean markdown.
Supports text-based PDFs natively via pdfplumber.
Scanned PDFs fall back to pytesseract (requires tesseract + poppler system binaries).
"""
import re
from pathlib import Path


class PdfIngestionService:

    def extract_text(self, path: Path) -> str:
        """Extract raw text from a PDF. Tries pdfplumber first, falls back to OCR."""
        try:
            import pdfplumber
        except ImportError:
            raise RuntimeError(
                "pdfplumber is not installed. Run: pip install pdfplumber"
            )

        text_parts = []
        with pdfplumber.open(str(path)) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text(x_tolerance=2, y_tolerance=4)
                if page_text:
                    text_parts.append(page_text)

        raw_text = "\n\n".join(text_parts).strip()

        # If pdfplumber got nothing (scanned PDF), try OCR
        if not raw_text:
            raw_text = self._ocr_fallback(path)

        return raw_text

    def _ocr_fallback(self, path: Path) -> str:
        """OCR fallback for scanned/image-only PDFs."""
        try:
            from pdf2image import convert_from_path
            import pytesseract
        except ImportError:
            raise RuntimeError(
                "This PDF appears to be scanned (no extractable text). "
                "Install OCR support with: pip install pdf2image pytesseract "
                "and install system packages: brew install tesseract poppler"
            )

        images = convert_from_path(str(path), dpi=200)
        parts = []
        for img in images:
            parts.append(pytesseract.image_to_string(img, lang="eng"))
        return "\n\n".join(parts).strip()

    def to_markdown(self, raw_text: str) -> str:
        """Convert raw extracted text to clean markdown."""
        lines = raw_text.splitlines()
        md_lines = []
        prev_blank = False

        for line in lines:
            stripped = line.strip()

            # Skip blank lines but avoid consecutive blanks
            if not stripped:
                if not prev_blank:
                    md_lines.append("")
                prev_blank = True
                continue
            prev_blank = False

            # Detect section headers: ALL CAPS lines of 4–80 chars, no digits only
            if (
                stripped.isupper()
                and 4 <= len(stripped) <= 80
                and not stripped.replace(" ", "").isdigit()
                and not re.match(r"^page\s+\d+", stripped, re.IGNORECASE)
            ):
                md_lines.append(f"\n## {stripped.title()}")
                continue

            # Strip page number artifacts (e.g. "- 3 -", "Page 3 of 10")
            if re.match(r"^[-–]?\s*\d+\s*[-–]?$", stripped):
                continue
            if re.match(r"^page\s+\d+\s*(of\s+\d+)?$", stripped, re.IGNORECASE):
                continue

            # Bullet-like lines starting with -, •, *, ·
            if re.match(r"^[-•*·]\s+", stripped):
                md_lines.append(f"- {stripped[2:].strip()}")
                continue

            md_lines.append(stripped)

        # Collapse triple+ blank lines to double
        result = "\n".join(md_lines)
        result = re.sub(r"\n{3,}", "\n\n", result)
        return result.strip()
