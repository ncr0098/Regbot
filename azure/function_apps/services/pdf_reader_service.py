import pymupdf4llm
import logging

class PDFReaderService:
    def read_pdf(self, file_path):
        try:
            md_text = pymupdf4llm.to_markdown(file_path)
            return md_text
        except Exception as e:
            logging.error(f"Error reading PDF: {e}")
            raise