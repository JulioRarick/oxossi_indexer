import fitz
from packaging import version
import os
import logging
import re
from typing import Optional

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(module)s - %(message)s')
log = logging.getLogger(__name__)

PYMUPDF_VERSION = version.parse(fitz.version[0])
TEXT_EXTRACTION_METHOD = "get_text" if PYMUPDF_VERSION >= version.parse("1.18.0") else "getText"

def clean_extracted_text(text: str) -> str:
    """
    Remove caracteres de controle e tenta recompor a quebra de palavras.
    Aplica heurísticas para detectar e limpar texto corrompido.
    """
    if not isinstance(text, str):
        return ""
    
    # Remove caracteres NULL
    cleaned_text = text.replace('\u0000', '')
    
    # Remove caracteres de controle (0x01 a 0x1F, exceto \n, \r, \t)
    control_chars = ''.join([chr(i) for i in range(1, 32) if i not in [9, 10, 13]])
    for char in control_chars:
        cleaned_text = cleaned_text.replace(char, ' ')
    
    # Remove hífen de quebra de linha
    cleaned_text = cleaned_text.replace('-\n', '')
    
    # Substitui quebras de linha por espaço
    cleaned_text = cleaned_text.replace('\n', ' ')
    
    # Normaliza múltiplos espaços
    cleaned_text = ' '.join(cleaned_text.split())
    
    # NOVA LÓGICA: Detecta se o texto está muito corrompido
    if is_text_corrupted(cleaned_text):
        log.warning("Texto altamente corrompido detectado. Tentando OCR ou extração alternativa.")
        return "[TEXTO CORROMPIDO - REQUER OCR]"
    
    return cleaned_text

def is_text_corrupted(text: str, threshold: float = 0.3) -> bool:
    """
    Detecta se o texto está corrompido baseado em heurísticas.
    
    Args:
        text: Texto a ser analisado
        threshold: Proporção de caracteres inválidos tolerada (0.3 = 30%)
    
    Returns:
        True se o texto estiver corrompido
    """
    if not text or len(text) < 50:
        return False
    
    # Conta caracteres estranhos (não ASCII imprimíveis, não acentuados)
    strange_chars = sum(1 for c in text if ord(c) > 127 and c not in 'áéíóúàèìòùâêîôûãõçÁÉÍÓÚÀÈÌÒÙÂÊÎÔÛÃÕÇ')
    
    # Conta palavras muito curtas ou sem vogais
    words = text.split()
    invalid_words = sum(1 for w in words if len(w) < 2 or not any(v in w.lower() for v in 'aeiouáéíóúàèìòùâêîôûãõ'))
    
    # Calcula proporções
    char_ratio = strange_chars / len(text) if len(text) > 0 else 0
    word_ratio = invalid_words / len(words) if len(words) > 0 else 0
    
    # Texto corrompido se muitos caracteres estranhos OU muitas palavras inválidas
    return char_ratio > threshold or word_ratio > 0.5

def extract_text_from_pdf(pdf_path: str, use_ocr_fallback: bool = False) -> Optional[str]:
    """
    Extrai texto de um PDF usando estratégia robusta.
    
    Args:
        pdf_path: Caminho do arquivo PDF
        use_ocr_fallback: Se True, tenta OCR quando detecção de corrupção
    
    Returns:
        Texto extraído ou None em caso de erro
    """
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
                page_text = ""
                
                # Tenta extração por blocos (mais robusto)
                try:
                    blocks = getattr(page, TEXT_EXTRACTION_METHOD)("blocks")
                    if isinstance(blocks, list):
                        page_text = "\n".join([block[4] for block in blocks if len(block) > 4 and block[4].strip()])
                except Exception as e:
                    log.warning(f"Erro na extração por 'blocks' da página {page_num + 1}: {e}")
                
                # Fallback para modo "text"
                if not page_text or len(page_text.split()) < 5:
                    try:
                        page_text = getattr(page, TEXT_EXTRACTION_METHOD)("text")
                    except Exception as e:
                        log.warning(f"Erro na extração por 'text' da página {page_num + 1}: {e}")
                
                # NOVO: Tenta extração de imagens como último recurso
                if (not page_text or is_text_corrupted(page_text)) and use_ocr_fallback:
                    log.info(f"Tentando OCR na página {page_num + 1}")
                    page_text = extract_with_ocr(page)
                
                if page_text:
                    full_text += page_text + "\n"
            
            log.info(f"Texto extraído com sucesso do PDF ({len(full_text)} caracteres).")
            
    except fitz.FileDataError as e:
        log.error(f"Erro do PyMuPDF ao ler o arquivo PDF '{pdf_path}': {e}", exc_info=True)
        return None
    except Exception as e:
        log.error(f"Erro inesperado ao ler o PDF '{pdf_path}': {e}", exc_info=True)
        return None

    # Aplica limpeza
    cleaned = clean_extracted_text(full_text)
    
    # Se ainda estiver muito corrompido, retorna indicação
    if "[TEXTO CORROMPIDO" in cleaned:
        log.error(f"PDF '{pdf_path}' contém texto corrompido que requer OCR")
        return f"[ERRO: PDF com fontes corrompidas. Arquivo: {os.path.basename(pdf_path)}]"
    
    return cleaned

def extract_with_ocr(page) -> str:
    """
    Extrai texto usando OCR (requer pytesseract e Pillow).
    Esta é uma função placeholder - implementação real requer bibliotecas adicionais.
    """
    try:
        # Renderiza página como imagem
        pix = page.get_pixmap(dpi=300)
        
        # Aqui você precisaria usar pytesseract
        # from PIL import Image
        # import pytesseract
        # img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        # text = pytesseract.image_to_string(img, lang='por')
        # return text
        
        log.warning("OCR não implementado. Instale: pip install pytesseract pillow")
        return ""
    except Exception as e:
        log.error(f"Erro no OCR: {e}")
        return ""
