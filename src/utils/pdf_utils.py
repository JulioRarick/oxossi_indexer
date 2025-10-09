import fitz
from packaging import version
# FitzError is not directly importable; handle exceptions using fitz.fitz.FileDataError or Exception
import os
import logging
from typing import Optional

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(module)s - %(message)s')
log = logging.getLogger(__name__)

PYMUPDF_VERSION = version.parse(fitz.version[0])

TEXT_EXTRACTION_METHOD = "get_text" if PYMUPDF_VERSION >= version.parse("1.18.0") else "getText"

def extract_text_from_pdf(pdf_path: str) -> Optional[str]:
    if not isinstance(pdf_path, str) or not pdf_path:
        log.error("Caminho do PDF inválido fornecido.")
        return None
    if not os.path.exists(pdf_path):
        log.error(f"Arquivo PDF não encontrado em '{pdf_path}'")
        return None

    full_text = ""
    try:
        log.info(f"Abrindo PDF: {pdf_path}")
        with fitz.open(pdf_path) as doc:
            num_pages = len(doc)
            log.info(f"Lendo {num_pages} páginas...")
            for page_num in range(num_pages):
                page = doc.load_page(page_num)
                try:
                    page_text = getattr(page, TEXT_EXTRACTION_METHOD)("text")
                    if page_text:
                        full_text += page_text + "\n"
                except Exception as e:
                    log.warning(f"Erro ao extrair texto da página {page_num + 1}: {e}")
            log.info(f"Texto extraído com sucesso do PDF ({len(full_text)} caracteres).")
    except fitz.FileDataError as e:
        log.error(f"Erro do PyMuPDF ao ler o arquivo PDF '{pdf_path}': {e}", exc_info=True)
        return None
    except Exception as e:
        log.error(f"Erro inesperado ao ler o PDF '{pdf_path}': {e}", exc_info=True)
        return None

    return full_text

if __name__ == '__main__':
    test_pdf = "../pdfs/*.pdf" 
    if os.path.exists(test_pdf):
        text = extract_text_from_pdf(test_pdf)
        if text:
            print("\n--- Exemplo de Texto Extraído (primeiros 500 caracteres) ---")
            print(text[:500])
            print("...")
        else:
            print(f"Falha ao extrair texto de {test_pdf}")
    else:
        print(f"Arquivo de teste não encontrado: {test_pdf}")

