# extractors/references.py

import os
import re
import subprocess
import logging
import json
import tempfile
import sys
from typing import List, Dict, Any, Optional
from pathlib import Path

log = logging.getLogger(__name__)

class ReferencesExtractor:
    """Extrator de referências bibliográficas com múltiplas estratégias"""
    
    def __init__(self):
        self.anystyle_available = self._check_anystyle()
        if self.anystyle_available:
            log.info("AnyStyle disponível e funcionando")
        else:
            log.warning("AnyStyle não disponível. Usando extração baseada em regex.")
    
    def _check_anystyle(self) -> bool:
        """Verifica se AnyStyle está instalado e funcionando"""
        try:
            result = subprocess.run(
                ['anystyle', '--version'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                log.debug(f"AnyStyle version: {result.stdout.strip()}")
                return True
            return False
        except (FileNotFoundError, subprocess.TimeoutExpired, Exception) as e:
            log.debug(f"AnyStyle não encontrado: {e}")
            return False
    
    def extract_references(self, pdf_path: str, text: Optional[str] = None) -> Dict[str, Any]:
        """
        Extrai referências usando AnyStyle ou fallback
        
        Args:
            pdf_path: Caminho do PDF
            text: Texto já extraído (opcional)
        
        Returns:
            Dict com referências extraídas
        """
        if self.anystyle_available:
            result = self._extract_with_anystyle(pdf_path, text)
            # Se AnyStyle falhar, tenta fallback
            if result.get("method") == "error" or result.get("total_references", 0) == 0:
                log.info(f"AnyStyle falhou para {pdf_path}, tentando fallback")
                if text is None:
                    text = self._extract_text_for_references(pdf_path)
                return self._extract_with_regex(text)
            return result
        else:
            # Extrai texto se não foi fornecido
            if text is None:
                text = self._extract_text_for_references(pdf_path)
            return self._extract_with_regex(text)
    
    def _extract_text_for_references(self, pdf_path: str) -> str:
        """Extrai texto do PDF especificamente para referências"""
        try:
            # Tenta importar de diferentes locais
            try:
                # Primeiro tenta importação relativa (quando executado como módulo)
                from utils.pdf_utils import extract_text_from_pdf
            except (ImportError, ValueError):
                # Se falhar, tenta importação absoluta
                # Adiciona o diretório pai ao path se necessário
                current_dir = Path(__file__).resolve().parent
                src_dir = current_dir.parent
                if str(src_dir) not in sys.path:
                    sys.path.insert(0, str(src_dir))
                
                from utils.pdf_utils import extract_text_from_pdf
            
            text = extract_text_from_pdf(pdf_path)
            return text if text else ""
            
        except ImportError as e:
            log.error(f"Não foi possível importar extract_text_from_pdf: {e}")
            log.info("Tentando extrair texto diretamente com PyMuPDF...")
            return self._extract_text_direct(pdf_path)
        except Exception as e:
            log.error(f"Erro ao extrair texto para referências: {e}")
            return ""
    
    def _extract_text_direct(self, pdf_path: str) -> str:
        """Extração direta de texto usando PyMuPDF (fallback)"""
        try:
            import fitz
            
            full_text = ""
            with fitz.open(pdf_path) as doc:
                for page_num in range(len(doc)):
                    page = doc.load_page(page_num)
                    try:
                        blocks = page.get_text("blocks")
                        page_text = "\n".join([block[4] for block in blocks if len(block) > 4 and block[4].strip()])
                    except:
                        page_text = page.get_text("text")
                    
                    if page_text:
                        full_text += page_text + "\n"
            
            return full_text
            
        except ImportError:
            log.error("PyMuPDF (fitz) não está instalado. Instale com: pip install PyMuPDF")
            return ""
        except Exception as e:
            log.error(f"Erro na extração direta de texto: {e}")
            return ""
    
    # ... resto do código permanece igual ...
    
    def _extract_with_anystyle(self, pdf_path: str, text: Optional[str] = None) -> Dict[str, Any]:
        """Extrai referências usando AnyStyle com múltiplas tentativas"""
        
        # Estratégia 1: Tentar com PDF diretamente
        result = self._try_anystyle_parse(pdf_path, source_type="pdf")
        if result and result.get("total_references", 0) > 0:
            return result
        
        # Estratégia 2: Tentar com texto extraído
        if text or os.path.exists(pdf_path):
            if not text:
                text = self._extract_text_for_references(pdf_path)
            
            if text:
                # Salva texto em arquivo temporário
                result = self._try_anystyle_with_text(text)
                if result and result.get("total_references", 0) > 0:
                    return result
        
        # Se ambas estratégias falharam
        log.warning(f"AnyStyle não conseguiu extrair referências de {pdf_path}")
        return self._empty_result("anystyle_failed")
    
    def _try_anystyle_parse(self, pdf_path: str, source_type: str = "pdf") -> Optional[Dict[str, Any]]:
        """Tenta executar AnyStyle parse"""
        try:
            # Verifica se arquivo existe
            if not os.path.exists(pdf_path):
                log.error(f"Arquivo não encontrado: {pdf_path}")
                return None
            
            # Executa AnyStyle
            cmd = ['anystyle', '-f', 'json', 'parse', pdf_path]
            
            log.debug(f"Executando: {' '.join(cmd)}")
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
                cwd=os.path.dirname(pdf_path) or '.'
            )
            
            if result.stderr:
                log.debug(f"AnyStyle stderr: {result.stderr}")
            
            if result.returncode != 0:
                log.warning(f"AnyStyle retornou código {result.returncode}")
                return None
            
            if not result.stdout or result.stdout.strip() == "":
                log.warning(f"AnyStyle retornou saída vazia para {pdf_path}")
                return None
            
            try:
                references = json.loads(result.stdout)
            except json.JSONDecodeError as e:
                log.error(f"Falha ao decodificar JSON do AnyStyle: {e}")
                log.debug(f"Stdout recebido: {result.stdout[:500]}")
                return None
            
            if not isinstance(references, list):
                log.warning(f"AnyStyle retornou formato inesperado: {type(references)}")
                return None
            
            valid_refs = [ref for ref in references if isinstance(ref, dict) and ref]
            
            if not valid_refs:
                log.info(f"AnyStyle não encontrou referências em {pdf_path}")
                return None
            
            return {
                "method": "anystyle",
                "source_type": source_type,
                "raw_references": valid_refs,
                "total_references": len(valid_refs),
                "extracted_authors": self._extract_authors_from_anystyle(valid_refs),
                "extracted_years": self._extract_years_from_anystyle(valid_refs),
                "confidence": "high"
            }
                
        except subprocess.TimeoutExpired:
            log.error(f"AnyStyle timeout ao processar {pdf_path}")
            return None
        except Exception as e:
            log.error(f"Erro inesperado no AnyStyle: {e}", exc_info=True)
            return None
    
    def _try_anystyle_with_text(self, text: str) -> Optional[Dict[str, Any]]:
        """Tenta AnyStyle com texto em arquivo temporário"""
        try:
            refs_section = self._find_references_section(text)
            if not refs_section:
                log.debug("Seção de referências não encontrada no texto")
                return None
            
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
                f.write(refs_section)
                temp_path = f.name
            
            try:
                result = subprocess.run(
                    ['anystyle', '-f', 'json', 'parse', temp_path],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                
                if result.returncode == 0 and result.stdout.strip():
                    try:
                        references = json.loads(result.stdout)
                        if isinstance(references, list) and references:
                            valid_refs = [ref for ref in references if isinstance(ref, dict) and ref]
                            
                            return {
                                "method": "anystyle",
                                "source_type": "text",
                                "raw_references": valid_refs,
                                "total_references": len(valid_refs),
                                "extracted_authors": self._extract_authors_from_anystyle(valid_refs),
                                "extracted_years": self._extract_years_from_anystyle(valid_refs),
                                "confidence": "medium"
                            }
                    except json.JSONDecodeError:
                        pass
                
                return None
                
            finally:
                try:
                    os.unlink(temp_path)
                except:
                    pass
                    
        except Exception as e:
            log.error(f"Erro ao processar texto com AnyStyle: {e}")
            return None
    
    def _extract_authors_from_anystyle(self, references: List[Dict[str, Any]]) -> List[str]:
        """Extrai autores de referências do AnyStyle"""
        authors = set()
        for ref in references:
            author_field = ref.get('author', [])
            
            if isinstance(author_field, list):
                for author in author_field:
                    if isinstance(author, dict):
                        family = author.get('family', '')
                        given = author.get('given', '')
                        if family:
                            authors.add(f"{family}, {given}" if given else family)
                    elif isinstance(author, str):
                        authors.add(author.strip())
            elif isinstance(author_field, str):
                authors.add(author_field.strip())
        
        return sorted(list(authors))
    
    def _extract_years_from_anystyle(self, references: List[Dict[str, Any]]) -> List[str]:
        """Extrai anos de referências do AnyStyle"""
        years = set()
        for ref in references:
            date_field = ref.get('date', ref.get('year', ''))
            
            if date_field:
                year_match = re.search(r'\b(19|20)\d{2}\b', str(date_field))
                if year_match:
                    years.add(year_match.group(0))
        
        return sorted(list(years))
    
    def _extract_with_regex(self, text: str) -> Dict[str, Any]:
        """Extrai referências usando regex (fallback)"""
        if not text or len(text) < 100:
            return self._empty_result("no_text")
        
        references_section = self._find_references_section(text)
        
        if not references_section:
            log.debug("Seção de referências não encontrada")
            return self._empty_result("no_section_found")
        
        references = self._parse_references(references_section)
        
        if not references:
            return self._empty_result("no_references_parsed")
        
        return {
            "method": "regex_fallback",
            "raw_references": references,
            "total_references": len(references),
            "extracted_authors": [ref.get("author", "") for ref in references if ref.get("author")],
            "extracted_years": [ref.get("year", "") for ref in references if ref.get("year")],
            "confidence": "low"
        }
    
    def _find_references_section(self, text: str) -> Optional[str]:
        """Localiza a seção de referências no texto"""
        patterns = [
            r'(?:REFERÊNCIAS|REFERENCIAS)\s+(?:BIBLIOGRÁFICAS?|BIBLIOGRAFICAS?)?\s*\n(.*?)(?=\n\s*\n[A-Z]{4,}|\n\s*APÊNDICE|\n\s*ANEXO|\Z)',
            r'BIBLIOGRAFIA\s*\n(.*?)(?=\n\s*\n[A-Z]{4,}|\n\s*APÊNDICE|\n\s*ANEXO|\Z)',
            r'REFERENCES\s*\n(.*?)(?=\n\s*\n[A-Z]{4,}|\n\s*APPENDIX|\Z)',
            r'WORKS\s+CITED\s*\n(.*?)(?=\n\s*\n[A-Z]{4,}|\Z)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                section = match.group(1).strip()
                if len(section) > 100:
                    log.debug(f"Seção de referências encontrada com {len(section)} caracteres")
                    return section
        
        return None
    
    def _parse_references(self, references_text: str) -> List[Dict[str, Any]]:
        """Parseia referências individuais"""
        references = []
        references_text = re.sub(r'\n+', '\n', references_text)
        lines = references_text.split('\n')
        current_ref = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            if (re.match(r'^[A-ZÀÁÂÃÄÅÇÈÉÊËÌÍÎÏÑÒÓÔÕÖÙÚÛÜ]{2,}', line) or 
                re.match(r'^\[\d+\]', line) or
                re.match(r'^\d+\.', line)):
                
                if current_ref:
                    ref_text = ' '.join(current_ref)
                    parsed = self._parse_single_reference(ref_text)
                    if parsed:
                        references.append(parsed)
                
                current_ref = [line]
            else:
                if current_ref:
                    current_ref.append(line)
        
        if current_ref:
            ref_text = ' '.join(current_ref)
            parsed = self._parse_single_reference(ref_text)
            if parsed:
                references.append(parsed)
        
        log.debug(f"Parseadas {len(references)} referências")
        return references
    
    def _parse_single_reference(self, ref_text: str) -> Optional[Dict[str, Any]]:
        """Parseia uma única referência"""
        if len(ref_text) < 20:
            return None
        
        try:
            parsed = {
                "raw": ref_text,
                "author": self._extract_author(ref_text),
                "year": self._extract_year(ref_text),
                "title": self._extract_title(ref_text),
                "publication": self._extract_publication(ref_text)
            }
            
            if parsed["author"] and (parsed["year"] or parsed["title"]):
                return parsed
            
            return None
            
        except Exception as e:
            log.debug(f"Erro ao parsear referência: {e}")
            return None
    
    def _extract_author(self, ref: str) -> str:
        """Extrai autor da referência"""
        patterns = [
            r'^([A-ZÀÁÂÃÄÅÇÈÉÊËÌÍÎÏÑÒÓÔÕÖÙÚÛÜ][A-ZÀÁÂÃÄÅÇÈÉÊËÌÍÎÏÑÒÓÔÕÖÙÚÛÜ\s\-\']+),\s*([A-Z]\.?\s*)+',
            r'^([A-ZÀÁÂÃÄÅÇÈÉÊËÌÍÎÏÑÒÓÔÕÖÙÚÛÜ][A-ZÀÁÂÃÄÅÇÈÉÊËÌÍÎÏÑÒÓÔÕÖÙÚÛÜ]+(?:\s+[A-ZÀÁÂÃÄÅÇÈÉÊËÌÍÎÏÑÒÓÔÕÖÙÚÛÜ]+)*)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, ref)
            if match:
                author = match.group(0).strip()
                author = re.sub(r'^\[\d+\]\s*', '', author)
                author = re.sub(r'^\d+\.\s*', '', author)
                return author.strip()
        
        return ""
    
    def _extract_year(self, ref: str) -> str:
        """Extrai ano da referência"""
        patterns = [
            r'\((\d{4}[a-z]?)\)',
            r'\b(\d{4})\.',
            r',\s*(\d{4})\b'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, ref)
            if match:
                year_str = match.group(1)
                year = int(re.search(r'\d{4}', year_str).group(0))
                if 1500 <= year <= 2030:
                    return year_str
        
        return ""
    
    def _extract_title(self, ref: str) -> str:
        """Extrai título da referência"""
        temp = re.sub(r'^[^.]+\.\s*\(?[\d]{4}[a-z]?\)?\.\s*', '', ref)
        
        patterns = [
            r'["\']([^"\']{10,})["\']',
            r'<i>([^<]+)</i>',
            r'<b>([^<]+)</b>',
            r'^([^.]{10,}?)\.',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, temp)
            if match:
                title = match.group(1).strip()
                if 10 < len(title) < 500:
                    return title
        
        words = re.split(r'[.,]', temp)[0].strip()
        if 10 < len(words) < 500:
            return words
        
        return ""
    
    def _extract_publication(self, ref: str) -> str:
        """Extrai informação de publicação"""
        patterns = [
            r'In:\s*([^,\.]{5,})',
            r'(?:Revista|Journal|Anais|Conference|Proceedings)\s+([^,\.]+)',
            r'(?:v\.|vol\.)\s*\d+',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, ref, re.IGNORECASE)
            if match:
                return match.group(0 if 'v.' in pattern else 1).strip()
        
        return ""
    
    def _empty_result(self, reason: str) -> Dict[str, Any]:
        """Retorna resultado vazio"""
        return {
            "method": "none",
            "reason": reason,
            "raw_references": [],
            "total_references": 0,
            "extracted_authors": [],
            "extracted_years": [],
            "confidence": "none"
        }


# Função de compatibilidade
def extract_references_with_anystyle(pdf_path: str, text: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Função wrapper para compatibilidade
    
    DEPRECATED: Use ReferencesExtractor().extract_references() diretamente
    """
    try:
        extractor = ReferencesExtractor()
        result = extractor.extract_references(pdf_path, text)
        
        if result.get("total_references", 0) == 0:
            return None
        
        return result
        
    except Exception as e:
        log.error(f"Erro ao extrair referências de {pdf_path}: {e}")
        return None
