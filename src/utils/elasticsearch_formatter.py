import json
from datetime import datetime
from typing import Dict, List, Any, Optional
import logging

log = logging.getLogger(__name__)

class ElasticsearchFormatter:
    """Formata documentos para ingestão no Elasticsearch"""
    
    @staticmethod
    def get_index_mapping() -> Dict[str, Any]:
        """Retorna o mapeamento otimizado para o índice Elasticsearch"""
        return {
            "mappings": {
                "dynamic": "strict",  # Não permite campos não mapeados
                "properties": {
                    "document_id": {"type": "keyword"},
                    "filename": {"type": "keyword"},
                    "source_type": {"type": "keyword"},
                    "processed_at": {"type": "date"},
                    "has_extraction_error": {"type": "boolean"},
                    "extraction_error": {"type": "text"},
                    "file_path": {"type": "keyword"},
                    
                    "text": {
                        "type": "text",
                        "analyzer": "portuguese",
                        "fields": {
                            "keyword": {"type": "keyword", "ignore_above": 256}
                        }
                    },
                    "word_count": {"type": "integer"},
                    "character_count": {"type": "integer"},
                    
                    # Análise de nomes
                    "names_analysis": {
                        "properties": {
                            "potential_names_found": {"type": "keyword"},
                            "total_names": {"type": "integer"},
                            "error": {"type": "text"}
                        }
                    },
                    
                    # Análise de datas
                    "date_analysis": {
                        "properties": {
                            "total_dates": {"type": "integer"},
                            "centuries_found": {"type": "keyword"},
                            "error": {"type": "text"}
                        }
                    },
                    
                    # Análise temporal
                    "temporal_analysis": {
                        "properties": {
                            "temporal_markers": {"type": "keyword"},
                            "time_periods": {"type": "keyword"},
                            "error": {"type": "text"}
                        }
                    },
                    
                    # Análise de temas
                    "themes_analysis": {
                        "properties": {
                            "themes": {"type": "keyword"},
                            "primary_theme": {"type": "keyword"},
                            "total_themes": {"type": "integer"},
                            "error": {"type": "text"}
                        }
                    },
                    
                    # Análise de lugares - CORRIGIDO
                    "places_analysis": {
                        "properties": {
                            "places_found": {"type": "keyword"},
                            "total_places": {"type": "integer"},
                            "error": {"type": "text"}
                        }
                    },
                    
                    # Análise NER
                    "ner_analysis": {
                        "properties": {
                            "entities": {"type": "keyword"},
                            "entity_types": {"type": "keyword"},
                            "total_entities": {"type": "integer"},
                            "error": {"type": "text"}
                        }
                    },
                    
                    # Pessoas
                    "persons_analysis": {
                        "properties": {
                            "persons_found": {"type": "keyword"},
                            "total_persons": {"type": "integer"},
                            "error": {"type": "text"}
                        }
                    },
                    
                    # Referências
                    "references_analysis": {
                        "properties": {
                            "method": {"type": "keyword"},
                            "total_references": {"type": "integer"},
                            "extracted_authors": {"type": "keyword"},
                            "extracted_years": {"type": "keyword"},
                            "confidence": {"type": "keyword"},
                            "error": {"type": "text"}
                        }
                    },
                    
                    # Imagens
                    "image_analysis": {
                        "properties": {
                            "total_images": {"type": "integer"},
                            "image_types": {"type": "keyword"},
                            "error": {"type": "text"}
                        }
                    },
                    
                    # Campos para scraped items
                    "titulo": {"type": "text"},
                    "autor": {"type": "keyword"},
                    "tema": {"type": "keyword"},
                    "pdf_link": {"type": "keyword"},
                    "url": {"type": "keyword"},
                    "data_de_publicacao": {"type": "keyword"},
                    "nomes": {"type": "keyword"},
                    "capitania": {"type": "keyword"},
                    "localizacao": {"type": "keyword"},
                    "matches_seculos": {"type": "keyword"},
                    "matched": {"type": "boolean"}
                }
            },
            "settings": {
                "number_of_shards": 1,
                "number_of_replicas": 1,
                "index.mapping.total_fields.limit": 2000,
                "analysis": {
                    "analyzer": {
                        "portuguese": {
                            "type": "standard",
                            "stopwords": "_portuguese_"
                        }
                    }
                }
            }
        }
    
    def _normalize_places_analysis(self, places_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Normaliza estrutura de places_analysis para evitar conflitos de tipo"""
        if not isinstance(places_analysis, dict):
            return {}
        
        normalized = {}
        
        # Remove campos problemáticos e normaliza estrutura
        if 'place_counts' in places_analysis:
            # Extrai apenas os nomes dos lugares
            place_counts = places_analysis['place_counts']
            if isinstance(place_counts, dict):
                normalized['places_found'] = list(place_counts.keys())
                normalized['total_places'] = len(place_counts)
        
        if 'places_found' in places_analysis:
            places = places_analysis['places_found']
            if isinstance(places, list):
                normalized['places_found'] = places
                normalized['total_places'] = len(places)
            elif isinstance(places, dict):
                normalized['places_found'] = list(places.keys())
                normalized['total_places'] = len(places)
        
        if 'total_places' in places_analysis and isinstance(places_analysis['total_places'], int):
            normalized['total_places'] = places_analysis['total_places']
        
        if 'error' in places_analysis:
            normalized['error'] = str(places_analysis['error'])
        
        return normalized if normalized else {}
    
    def _normalize_themes_analysis(self, themes_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Normaliza estrutura de themes_analysis"""
        if not isinstance(themes_analysis, dict):
            return {}
        
        normalized = {}
        
        if 'themes' in themes_analysis:
            themes = themes_analysis['themes']
            if isinstance(themes, list):
                normalized['themes'] = themes
                normalized['total_themes'] = len(themes)
            elif isinstance(themes, dict):
                normalized['themes'] = list(themes.keys())
                normalized['total_themes'] = len(themes)
        
        if 'primary_theme' in themes_analysis:
            normalized['primary_theme'] = str(themes_analysis['primary_theme'])
        
        if 'error' in themes_analysis:
            normalized['error'] = str(themes_analysis['error'])
        
        return normalized if normalized else {}
    
    def _normalize_date_analysis(self, date_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Normaliza estrutura de date_analysis"""
        if not isinstance(date_analysis, dict):
            return {}
        
        normalized = {}
        
        # Remove century_counts (objeto complexo) e mantém apenas lista simples
        if 'century_counts' in date_analysis:
            century_counts = date_analysis['century_counts']
            if isinstance(century_counts, dict):
                normalized['centuries_found'] = list(century_counts.keys())
                normalized['total_dates'] = sum(century_counts.values()) if all(isinstance(v, int) for v in century_counts.values()) else len(century_counts)
        
        if 'centuries_found' in date_analysis:
            normalized['centuries_found'] = date_analysis['centuries_found']
        
        if 'total_dates' in date_analysis and isinstance(date_analysis['total_dates'], int):
            normalized['total_dates'] = date_analysis['total_dates']
        
        if 'error' in date_analysis:
            normalized['error'] = str(date_analysis['error'])
        
        return normalized if normalized else {}
    
    def _normalize_ner_analysis(self, ner_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Normaliza estrutura de ner_analysis"""
        if not isinstance(ner_analysis, dict):
            return {}
        
        normalized = {}
        
        if 'entities' in ner_analysis:
            entities = ner_analysis['entities']
            if isinstance(entities, list):
                normalized['entities'] = entities
                normalized['total_entities'] = len(entities)
            elif isinstance(entities, dict):
                normalized['entities'] = list(entities.keys())
                normalized['total_entities'] = len(entities)
        
        if 'entity_types' in ner_analysis:
            normalized['entity_types'] = ner_analysis['entity_types']
        
        if 'error' in ner_analysis:
            normalized['error'] = str(ner_analysis['error'])
        
        return normalized if normalized else {}
    
    def format_pdf_document(self, doc: Dict[str, Any]) -> Dict[str, Any]:
        """Formata documento PDF para Elasticsearch"""
        
        # Verifica se texto está corrompido
        text = doc.get("text", "")
        has_error = doc.get("has_extraction_error", False)
        
        source = {
            "document_id": str(doc.get("document_id", "")),
            "filename": doc.get("filename", ""),
            "source_type": doc.get("source_type", "pdf"),
            "file_path": doc.get("file_path", ""),
            "processed_at": doc.get("processed_at", datetime.now().isoformat()),
            "text": text if not has_error else "",
            "word_count": doc.get("word_count", 0),
            "character_count": doc.get("character_count", 0),
            "has_extraction_error": has_error
        }
        
        # Adiciona extraction_error se houver
        if has_error and "extraction_error" in doc:
            source["extraction_error"] = doc["extraction_error"]
        
        # Normaliza e adiciona análises
        if "names_analysis" in doc and not doc["names_analysis"].get("error"):
            cleaned = self._clean_analysis(doc["names_analysis"])
            if cleaned:
                source["names_analysis"] = cleaned
        
        if "date_analysis" in doc:
            normalized = self._normalize_date_analysis(doc["date_analysis"])
            if normalized:
                source["date_analysis"] = normalized
        
        if "temporal_analysis" in doc and not doc.get("temporal_analysis", {}).get("error"):
            cleaned = self._clean_analysis(doc["temporal_analysis"])
            if cleaned:
                source["temporal_analysis"] = cleaned
        
        if "themes_analysis" in doc:
            normalized = self._normalize_themes_analysis(doc["themes_analysis"])
            if normalized:
                source["themes_analysis"] = normalized
        
        if "places_analysis" in doc:
            normalized = self._normalize_places_analysis(doc["places_analysis"])
            if normalized:
                source["places_analysis"] = normalized
        
        if "ner_analysis" in doc:
            normalized = self._normalize_ner_analysis(doc["ner_analysis"])
            if normalized:
                source["ner_analysis"] = normalized
        
        if "persons_analysis" in doc and not doc.get("persons_analysis", {}).get("error"):
            cleaned = self._clean_analysis(doc["persons_analysis"])
            if cleaned:
                source["persons_analysis"] = cleaned
        
        if "references_analysis" in doc and not doc.get("references_analysis", {}).get("error"):
            cleaned = self._clean_analysis(doc["references_analysis"])
            if cleaned:
                source["references_analysis"] = cleaned
        
        if "image_analysis" in doc and not doc.get("image_analysis", {}).get("error"):
            cleaned = self._clean_analysis(doc["image_analysis"])
            if cleaned:
                source["image_analysis"] = cleaned
        
        return {
            "_index": "oxossi_documents",
            "_id": source["document_id"],
            "_source": source
        }
    
    def format_scraped_item(self, doc: Dict[str, Any]) -> Dict[str, Any]:
        """Formata item scraped para Elasticsearch"""
        original = doc.get("original_data", {})
        
        source = {
            "document_id": str(doc.get("_id", "")),
            "filename": doc.get("filename", ""),
            "source_type": "scraped",
            "processed_at": doc.get("processed_at", datetime.now().isoformat()),
            "text": original.get("texto_completo", ""),
            "titulo": original.get("titulo", original.get("title", "")),
            "autor": original.get("autor", original.get("author", "")),
            "tema": original.get("tema", original.get("theme", "")),
            "pdf_link": original.get("pdf_links", ""),
            "url": original.get("url", ""),
            "data_de_publicacao": original.get("data_de_publicacao", ""),
            "nomes": original.get("nomes", []),
            "capitania": original.get("capitania", ""),
            "localizacao": original.get("localizacao", ""),
            "matches_seculos": original.get("matches_seculos", []),
            "matched": original.get("matched", False),
            "has_extraction_error": False
        }
        
        return {
            "_index": "oxossi_documents",
            "_id": source["document_id"],
            "_source": source
        }
    
    def _clean_analysis(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Remove campos nulos e limpa estrutura de análise"""
        if not isinstance(analysis, dict):
            return {}
        
        cleaned = {}
        for key, value in analysis.items():
            # Pula valores nulos ou vazios
            if value is None or value == {} or value == []:
                continue
            
            # Para dicts, limpa recursivamente
            if isinstance(value, dict):
                # Não incluir dicts complexos que causam problemas
                if key in ['place_counts', 'century_counts', 'theme_scores']:
                    continue
                cleaned_dict = self._clean_analysis(value)
                if cleaned_dict:
                    cleaned[key] = cleaned_dict
            # Para listas, remove itens vazios
            elif isinstance(value, list):
                cleaned_list = [item for item in value if item not in (None, "", {})]
                if cleaned_list:
                    cleaned[key] = cleaned_list
            # Para strings, remove vazias
            elif isinstance(value, str):
                if value.strip():
                    cleaned[key] = value
            # Números e booleanos sempre adiciona
            elif isinstance(value, (int, float, bool)):
                cleaned[key] = value
        
        return cleaned


def format_documents_for_elasticsearch(
    documents: List[Dict[str, Any]],
    index_name: str = "oxossi_documents"
) -> Dict[str, Any]:
    """
    Formata lista de documentos para bulk API do Elasticsearch
    
    Returns:
        Dict contendo:
        - bulk_data: Lista de strings formatadas para bulk API (NDJSON)
        - bulk_file: String com todo o conteúdo NDJSON
        - index_mapping: Mapeamento do índice
        - total_documents: Total de documentos formatados
    """
    formatter = ElasticsearchFormatter()
    bulk_lines = []
    
    for doc in documents:
        try:
            # Determina tipo de documento
            is_scraped = doc.get("is_scraped_item", False) or doc.get("source_type") == "json_data"
            
            # Formata documento
            if is_scraped:
                formatted = formatter.format_scraped_item(doc)
            else:
                formatted = formatter.format_pdf_document(doc)
            
            # Cria action line (sem _source)
            action = {
                "index": {
                    "_index": formatted["_index"],
                    "_id": formatted["_id"]
                }
            }
            
            # Adiciona ao bulk (formato NDJSON - cada linha é um JSON completo)
            bulk_lines.append(json.dumps(action, ensure_ascii=False))
            bulk_lines.append(json.dumps(formatted["_source"], ensure_ascii=False))
            
        except Exception as e:
            log.error(f"Erro ao formatar documento {doc.get('document_id', 'unknown')}: {e}")
            continue
    
    # Junta todas as linhas com \n e adiciona \n no final
    bulk_content = '\n'.join(bulk_lines) + '\n'
    
    return {
        "bulk_data": bulk_lines,
        "bulk_file": bulk_content,  # Conteúdo completo para salvar em arquivo
        "index_mapping": formatter.get_index_mapping(),
        "total_documents": len(documents),
        "total_bulk_lines": len(bulk_lines),
        "formatted_at": datetime.now().isoformat()
    }


def save_bulk_file(bulk_data: str, output_path: str) -> bool:
    """
    Salva dados bulk em arquivo NDJSON
    
    Args:
        bulk_data: String com conteúdo NDJSON
        output_path: Caminho do arquivo de saída
        
    Returns:
        True se salvou com sucesso
    """
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(bulk_data)
        
        log.info(f"Arquivo bulk salvo: {output_path} ({len(bulk_data)} bytes)")
        return True
        
    except Exception as e:
        log.error(f"Erro ao salvar arquivo bulk: {e}")
        return False


def save_mapping_file(mapping: Dict[str, Any], output_path: str) -> bool:
    """
    Salva mapeamento do índice em arquivo JSON
    
    Args:
        mapping: Dicionário com o mapeamento
        output_path: Caminho do arquivo de saída
        
    Returns:
        True se salvou com sucesso
    """
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(mapping, f, indent=2, ensure_ascii=False)
        
        log.info(f"Mapeamento salvo: {output_path}")
        return True
        
    except Exception as e:
        log.error(f"Erro ao salvar mapeamento: {e}")
        return False
