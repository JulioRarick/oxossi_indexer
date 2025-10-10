"""
Elasticsearch Output Formatter
Converte dados do indexer para formato otimizado para Elasticsearch
"""

import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

log = logging.getLogger(__name__)

class ElasticsearchFormatter:
    """
    Formata dados do oxossi_indexer para compatibilidade otimizada com Elasticsearch
    """
    
    def __init__(self):
        self.field_mappings = {
            # Mapeamento de campos em português para inglês
            'titulo': 'title',
            'autor': 'author', 
            'tema': 'theme',
            'data_de_publicacao': 'publication_date',
            'texto_completo': 'full_content',
            'localizacao': 'location',
            'capitania': 'captaincy'
        }
    
    def format_pdf_document(self, doc: Dict[str, Any]) -> Dict[str, Any]:
        """
        Formata documento PDF para Elasticsearch
        """
        # Extrai texto e calcula estatísticas
        text = doc.get('text', '')
        word_count = len(text.split()) if text else 0
        
        # Processa datas
        dates_data = self._process_dates(doc.get('dates', []))
        
        # Processa temas
        themes_data = self._process_themes(doc.get('themes', {}))
        
        # Processa nomes
        names = doc.get('names', [])
        
        # Cria conteúdo resumido (primeiros 500 caracteres)
        content_preview = text[:500] + "..." if len(text) > 500 else text
        
        formatted_doc = {
            # Identificação
            "document_id": str(doc.get('_id', '')),
            "document_type": "pdf",
            "filename": doc.get('filename', ''),
            
            # Conteúdo
            "title": self._extract_title_from_filename(doc.get('filename', '')),
            "content": content_preview,
            "full_content": text,
            
            # Entidades extraídas
            "names": names,
            "dates": dates_data,
            "themes": themes_data,
            
            # Metadados
            "metadata": {
                "file_path": doc.get('path', ''),
                "processed_at": datetime.now().isoformat(),
                "word_count": word_count,
                "character_count": len(text),
                "has_dates": len(dates_data.get('years', [])) > 0,
                "has_names": len(names) > 0,
                "has_themes": len(themes_data.get('all_themes', [])) > 0
            },
            
            # Campos para busca e filtros
            "searchable_text": self._create_searchable_text(text, names, themes_data),
            "date_range_years": dates_data.get('date_range', {}),
            "primary_theme": themes_data.get('primary_theme'),
            "all_themes": themes_data.get('all_themes', []),
            "centuries": dates_data.get('centuries', [])
        }
        
        return formatted_doc
    
    def format_scraped_item(self, doc: Dict[str, Any]) -> Dict[str, Any]:
        """
        Formata item scraped para Elasticsearch
        """
        original_data = doc.get("original_data", {})
        
        # Normaliza campos usando mapeamento
        normalized_fields = self._normalize_field_names(doc, original_data)
        
        # Processa texto completo
        full_text = normalized_fields.get('full_content', '')
        content_preview = full_text[:500] + "..." if len(full_text) > 500 else full_text
        
        # Processa matches e classificações
        matches_data = self._process_matches(doc)
        
        formatted_doc = {
            # Identificação
            "document_id": str(doc.get('_id', '')),
            "document_type": "scraped_item",
            "source_url": normalized_fields.get('url', ''),
            
            # Conteúdo
            "title": normalized_fields.get('title', ''),
            "author": normalized_fields.get('author', ''),
            "content": content_preview,
            "full_content": full_text,
            
            # Classificação e matching
            "theme": normalized_fields.get('theme', ''),
            "publication_date": normalized_fields.get('publication_date', ''),
            "location": normalized_fields.get('location', ''),
            "captaincy": normalized_fields.get('captaincy', ''),
            
            # Entidades e matches
            "names": normalized_fields.get('names', []),
            "matches": matches_data,
            
            # Status e scores
            "classification_status": {
                "is_matched": doc.get('matched', False),
                "is_classified": doc.get('classified', False),
                "has_century_matches": doc.get('matched_seculos', False),
                "has_name_matches": doc.get('matched_nomes_completos', False)
            },
            
            "score": doc.get('score', 0.0),
            
            # Metadados
            "metadata": {
                "processed_at": doc.get('processed_at', datetime.now().isoformat()),
                "is_scraped_item": True,
                "word_count": len(full_text.split()) if full_text else 0,
                "has_pdf_link": bool(normalized_fields.get('pdf_link')),
                "filename": doc.get('filename', '')
            },
            
            # Campos para busca
            "searchable_text": self._create_searchable_text(
                full_text, 
                normalized_fields.get('names', []), 
                {'all_themes': [normalized_fields.get('theme', '')]}
            ),
            
            # Links e recursos
            "pdf_link": normalized_fields.get('pdf_link', ''),
            "external_url": normalized_fields.get('url', '')
        }
        
        return formatted_doc
    
    def _process_dates(self, dates: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Processa informações de datas"""
        if not dates:
            return {
                "years": [],
                "date_range": {},
                "centuries": [],
                "date_types": []
            }
        
        years = [d.get('year') for d in dates if d.get('year')]
        centuries = list(set(d.get('century', '') for d in dates if d.get('century')))
        date_types = list(set(d.get('type', '') for d in dates if d.get('type')))
        
        date_range = {}
        if years:
            date_range = {
                "start": min(years),
                "end": max(years),
                "span": max(years) - min(years) if len(years) > 1 else 0
            }
        
        return {
            "years": sorted(years),
            "date_range": date_range,
            "centuries": centuries,
            "date_types": date_types,
            "total_dates": len(dates)
        }
    
    def _process_themes(self, themes: Dict[str, Any]) -> Dict[str, Any]:
        """Processa informações de temas"""
        if not themes:
            return {
                "primary_theme": None,
                "all_themes": [],
                "theme_scores": {},
                "total_keywords": 0
            }
        
        theme_counts = themes.get('theme_counts', {})
        
        return {
            "primary_theme": themes.get('top_theme'),
            "all_themes": list(theme_counts.keys()),
            "theme_scores": theme_counts,
            "total_keywords": themes.get('total_keywords_found', 0),
            "theme_percentages": themes.get('theme_percentages', {})
        }
    
    def _process_matches(self, doc: Dict[str, Any]) -> Dict[str, Any]:
        """Processa informações de matches"""
        return {
            "text_matches": doc.get('matches', []),
            "century_matches": doc.get('matches_seculos', []),
            "name_matches": doc.get('matches_nomes_completos', []),
            "total_matches": len(doc.get('matches', []))
        }
    
    def _normalize_field_names(self, doc: Dict[str, Any], original_data: Dict[str, Any]) -> Dict[str, Any]:
        """Normaliza nomes de campos usando mapeamento"""
        normalized = {}
        
        # Combina dados do documento principal e dados originais
        all_data = {**doc, **original_data}
        
        for key, value in all_data.items():
            # Usa mapeamento se disponível, senão mantém o nome original
            normalized_key = self.field_mappings.get(key, key)
            normalized[normalized_key] = value
        
        return normalized
    
    def _extract_title_from_filename(self, filename: str) -> str:
        """Extrai título do nome do arquivo"""
        if not filename:
            return "Documento sem título"
        
        # Remove extensão e substitui underscores/hífens por espaços
        title = filename.replace('.pdf', '').replace('_', ' ').replace('-', ' ')
        # Capitaliza palavras
        return ' '.join(word.capitalize() for word in title.split())
    
    def _create_searchable_text(self, text: str, names: List[str], themes_data: Dict[str, Any]) -> str:
        """Cria campo combinado para busca textual"""
        searchable_parts = []
        
        if text:
            searchable_parts.append(text)
        
        if names:
            searchable_parts.extend(names)
        
        if themes_data.get('all_themes'):
            searchable_parts.extend(themes_data['all_themes'])
        
        return ' '.join(searchable_parts)
    
    def format_for_bulk_index(self, documents: List[Dict[str, Any]], index_name: str) -> List[str]:
        """
        Formata documentos para bulk indexing no Elasticsearch
        """
        bulk_data = []
        
        for doc in documents:
            # Determina o tipo de documento e formata adequadamente
            if doc.get('is_scraped_item'):
                formatted_doc = self.format_scraped_item(doc)
            else:
                formatted_doc = self.format_pdf_document(doc)
            
            # Header para o bulk API
            header = {
                "index": {
                    "_index": index_name,
                    "_id": formatted_doc["document_id"]
                }
            }
            
            bulk_data.append(json.dumps(header))
            bulk_data.append(json.dumps(formatted_doc, ensure_ascii=False))
        
        return bulk_data
    
    def create_index_mapping(self) -> Dict[str, Any]:
        """
        Cria mapeamento otimizado para o índice Elasticsearch
        """
        mapping = {
            "mappings": {
                "properties": {
                    "document_id": {"type": "keyword"},
                    "document_type": {"type": "keyword"},
                    "filename": {"type": "keyword"},
                    "title": {
                        "type": "text",
                        "analyzer": "portuguese",
                        "fields": {
                            "keyword": {"type": "keyword"}
                        }
                    },
                    "author": {
                        "type": "text",
                        "analyzer": "portuguese",
                        "fields": {
                            "keyword": {"type": "keyword"}
                        }
                    },
                    "content": {
                        "type": "text",
                        "analyzer": "portuguese"
                    },
                    "full_content": {
                        "type": "text",
                        "analyzer": "portuguese",
                        "index": False  # Não indexa para economizar espaço
                    },
                    "searchable_text": {
                        "type": "text",
                        "analyzer": "portuguese"
                    },
                    "names": {
                        "type": "text",
                        "analyzer": "portuguese",
                        "fields": {
                            "keyword": {"type": "keyword"}
                        }
                    },
                    "dates": {
                        "properties": {
                            "years": {"type": "integer"},
                            "date_range": {
                                "properties": {
                                    "start": {"type": "integer"},
                                    "end": {"type": "integer"},
                                    "span": {"type": "integer"}
                                }
                            },
                            "centuries": {"type": "keyword"},
                            "date_types": {"type": "keyword"}
                        }
                    },
                    "themes": {
                        "properties": {
                            "primary_theme": {"type": "keyword"},
                            "all_themes": {"type": "keyword"},
                            "theme_scores": {"type": "object"},
                            "total_keywords": {"type": "integer"}
                        }
                    },
                    "metadata": {
                        "properties": {
                            "processed_at": {"type": "date"},
                            "word_count": {"type": "integer"},
                            "character_count": {"type": "integer"},
                            "has_dates": {"type": "boolean"},
                            "has_names": {"type": "boolean"},
                            "has_themes": {"type": "boolean"}
                        }
                    },
                    "score": {"type": "float"},
                    "classification_status": {
                        "properties": {
                            "is_matched": {"type": "boolean"},
                            "is_classified": {"type": "boolean"},
                            "has_century_matches": {"type": "boolean"},
                            "has_name_matches": {"type": "boolean"}
                        }
                    }
                }
            },
            "settings": {
                "number_of_shards": 1,
                "number_of_replicas": 0,
                "analysis": {
                    "analyzer": {
                        "portuguese": {
                            "type": "portuguese"
                        }
                    }
                }
            }
        }
        
        return mapping


def format_documents_for_elasticsearch(documents: List[Dict[str, Any]], 
                                     index_name: str = "oxossi_documents") -> Dict[str, Any]:
    """
    Função utilitária para formatar documentos para Elasticsearch
    """
    formatter = ElasticsearchFormatter()
    
    result = {
        "index_mapping": formatter.create_index_mapping(),
        "bulk_data": formatter.format_for_bulk_index(documents, index_name),
        "total_documents": len(documents),
        "formatted_at": datetime.now().isoformat()
    }
    
    return result


# Exemplo de uso
if __name__ == "__main__":
    # Exemplo de documento de teste
    sample_pdf_doc = {
        "_id": "doc_001",
        "filename": "historia_brasil_colonial.pdf",
        "text": "Este documento trata da história do Brasil colonial...",
        "names": ["Dom Pedro I", "José Bonifácio"],
        "dates": [
            {"year": 1822, "type": "numeric", "century": "século XIX"},
            {"year": 1850, "type": "numeric", "century": "século XIX"}
        ],
        "themes": {
            "theme_counts": {"história": 5, "política": 3},
            "top_theme": "história",
            "total_keywords_found": 8
        },
        "path": "/app/pdfs/historia_brasil_colonial.pdf"
    }
    
    formatter = ElasticsearchFormatter()
    
    print("=== Documento Formatado para Elasticsearch ===")
    formatted = formatter.format_pdf_document(sample_pdf_doc)
    print(json.dumps(formatted, indent=2, ensure_ascii=False))
    
    print("\n=== Mapeamento do Índice ===")
    mapping = formatter.create_index_mapping()
    print(json.dumps(mapping, indent=2, ensure_ascii=False))