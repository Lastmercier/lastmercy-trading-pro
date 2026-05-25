from typing import Optional
import io


def extract_text(file_obj, max_chars: int = 8000) -> str:
    try:
        import pdfplumber
        if hasattr(file_obj, "read"):
            raw = file_obj.read()
            file_obj = io.BytesIO(raw)
        with pdfplumber.open(file_obj) as pdf:
            pages_text = []
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    pages_text.append(text)
            full = "\n\n".join(pages_text)
            return full[:max_chars]
    except Exception as e:
        return f"[PDF extraction error: {e}]"
