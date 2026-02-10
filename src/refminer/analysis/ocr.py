"""OCR engine for extracting text from PDF pages via image rendering."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Render DPI for page-to-image conversion
_DEFAULT_DPI = 200
_ZOOM = _DEFAULT_DPI / 72  # fitz uses 72 DPI base


class OcrEngine:
    """Wraps RapidOCR to perform OCR on PDF pages rendered as images."""

    def __init__(self, model_dir: Optional[Path] = None) -> None:
        try:
            from rapidocr_onnxruntime import RapidOCR
        except ImportError:
            raise ImportError(
                "rapidocr-onnxruntime is required for OCR. "
                "Install it with: pip install rapidocr-onnxruntime"
            )

        kwargs: dict = {}
        if model_dir and model_dir.is_dir():
            # Check for PaddleOCR model files inside model_dir
            rec_model = _find_model(model_dir, "rec")
            det_model = _find_model(model_dir, "det")
            if rec_model:
                kwargs["rec_model_path"] = str(rec_model)
            if det_model:
                kwargs["det_model_path"] = str(det_model)

        self._ocr = RapidOCR(**kwargs)

    def recognize_pdf_pages(
        self,
        pdf_path: Path,
        pages: Optional[list[int]] = None,
    ) -> list[str]:
        """Render PDF pages to images and run OCR.

        Args:
            pdf_path: Path to the PDF file.
            pages: 0-based page indices to process. ``None`` = all pages.

        Returns:
            List of extracted text strings, one per requested page.
        """
        import fitz  # PyMuPDF

        doc = fitz.open(pdf_path)
        try:
            page_indices = pages if pages is not None else list(range(len(doc)))
            results: list[str] = []
            mat = fitz.Matrix(_ZOOM, _ZOOM)

            for idx in page_indices:
                page = doc.load_page(idx)
                pix = page.get_pixmap(matrix=mat, alpha=False)
                img_bytes = pix.tobytes("png")

                # RapidOCR accepts image bytes directly
                ocr_result, _ = self._ocr(img_bytes)
                if ocr_result:
                    # Each item is [bbox, text, confidence]
                    lines = [item[1] for item in ocr_result]
                    results.append("\n".join(lines))
                else:
                    results.append("")

            return results
        finally:
            doc.close()

    def recognize_image(self, image_bytes: bytes) -> str:
        """Run OCR on a single image.

        Args:
            image_bytes: PNG/JPEG image bytes.

        Returns:
            Extracted text.
        """
        ocr_result, _ = self._ocr(image_bytes)
        if ocr_result:
            return "\n".join(item[1] for item in ocr_result)
        return ""


def _find_model(model_dir: Path, kind: str) -> Optional[Path]:
    """Find an ONNX model file for detection or recognition inside a directory tree."""
    for pattern in (f"*{kind}*.onnx", f"**/*{kind}*.onnx"):
        matches = list(model_dir.glob(pattern))
        if matches:
            return matches[0]
    return None
