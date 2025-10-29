import json
import logging
import os
from typing import Any, Dict, Optional
from .elasticsearch_formatter import ElasticsearchFormatter, format_documents_for_elasticsearch

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(module)s - %(message)s')
log = logging.getLogger(__name__)

def format_and_output_json(
    data: Optional[Dict[str, Any]],
    status: str = "Sucesso",
    message: str = "Operação concluída.",
    output_file: Optional[str] = None,
    elasticsearch_format: bool = False
) -> None:
    # Formata para Elasticsearch se solicitado
    if elasticsearch_format and data:
        try:
            from .elasticsearch_formatter import ElasticsearchFormatter
            formatter = ElasticsearchFormatter()
            
            # Detecta tipo de dados e formata adequadamente
            if isinstance(data, list):
                formatted_data = []
                for item in data:
                    if item.get('is_scraped_item'):
                        formatted_data.append(formatter.format_scraped_item(item))
                    else:
                        formatted_data.append(formatter.format_pdf_document(item))
                data = formatted_data
            elif isinstance(data, dict):
                if data.get('is_scraped_item'):
                    data = formatter.format_scraped_item(data)
                else:
                    data = formatter.format_pdf_document(data)
        except ImportError:
            log.warning("ElasticsearchFormatter não disponível. Usando formato padrão.")
        except Exception as e:
            log.error(f"Erro ao formatar para Elasticsearch: {e}. Usando formato padrão.")

    output_structure = {
        "status": status,
        "message": message,
        "results": data 
    }

    try:
        json_output_string = json.dumps(output_structure, indent=4, ensure_ascii=False)

        print("\n--- Saída JSON ---")
        print(json_output_string)
        print("------------------")

        if output_file:
            try:
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(json_output_string)
                log.info(f"Saída JSON salva com sucesso em '{output_file}'")
            except IOError as e:
                log.error(f"Erro ao salvar saída JSON em '{output_file}': {e}", exc_info=True)
            except Exception as e:
                log.error(f"Erro inesperado ao salvar JSON em '{output_file}': {e}", exc_info=True)

    except TypeError as e:
        log.error(f"Erro de tipo ao serializar para JSON: {e}. Verifique os tipos de dados em 'results'.", exc_info=True)
        
        print("\n--- Saída JSON (Erro de Serialização) ---")
        print(f'{{"status": "Erro", "message": "Falha ao serializar resultados para JSON: {e}", "results": null}}')
        print("----------------------------------------")
    except Exception as e:
        log.error(f"Erro inesperado ao formatar ou imprimir JSON: {e}", exc_info=True)
        print("\n--- Erro na Saída JSON ---")
        print(f'{{"status": "Erro", "message": "Falha inesperada ao gerar saída JSON: {e}", "results": null}}')
        print("--------------------------")

# No final da função export_to_elasticsearch_format

def export_to_elasticsearch_format(
    data: Optional[Dict[str, Any]],
    index_name: str = "oxossi_docs_index",
    output_file: Optional[str] = None,
    include_mapping: bool = True
) -> Optional[Dict[str, Any]]:
    """
    Exporta dados no formato otimizado para Elasticsearch
    """
    try:
        from .elasticsearch_formatter import (
            format_documents_for_elasticsearch,
            save_bulk_file,
            save_mapping_file
        )
        
        if not data:
            log.warning("Nenhum dado fornecido para exportação Elasticsearch")
            return None
        
        # Converte dados para lista se necessário
        documents = data if isinstance(data, list) else [data]
        
        # Formata documentos
        elasticsearch_output = format_documents_for_elasticsearch(documents, index_name)
        
        # Salva arquivos separados
        if output_file:
            # Arquivo bulk (.ndjson)
            bulk_file = output_file.replace('.json', '_bulk.ndjson')
            save_bulk_file(elasticsearch_output["bulk_file"], bulk_file)
            
            # Arquivo de mapeamento (.json)
            mapping_file = output_file.replace('.json', '_mapping.json')
            save_mapping_file(elasticsearch_output["index_mapping"], mapping_file)
            
            # Arquivo de resumo
            summary = {
                "elasticsearch_ready": True,
                "index_name": index_name,
                "total_documents": elasticsearch_output["total_documents"],
                "total_bulk_lines": elasticsearch_output["total_bulk_lines"],
                "formatted_at": elasticsearch_output["formatted_at"],
                "files": {
                    "bulk_data": bulk_file,
                    "mapping": mapping_file
                },
                "import_commands": {
                    "create_index": f"curl -X PUT 'localhost:9200/{index_name}' -H 'Content-Type: application/json' -d @{mapping_file}",
                    "bulk_import": f"curl -X POST 'localhost:9200/_bulk' -H 'Content-Type: application/x-ndjson' --data-binary @{bulk_file}"
                }
            }
            
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(summary, f, indent=2, ensure_ascii=False)
            
            log.info(f"Exportação Elasticsearch completa:")
            log.info(f"  - Resumo: {output_file}")
            log.info(f"  - Dados bulk: {bulk_file}")
            log.info(f"  - Mapeamento: {mapping_file}")
        
        return elasticsearch_output
        
    except ImportError:
        log.error("ElasticsearchFormatter não encontrado. Verifique se o módulo está instalado.")
        return None
    except Exception as e:
        log.error(f"Erro ao exportar para formato Elasticsearch: {e}", exc_info=True)
        return None

def format_scraped_item(doc: Dict[str, Any]) -> Dict[str, Any]:
    """
    Format a scraped item for API response, ensuring all requested fields are included.
    """
    original_data = doc.get("original_data", {})
    texto_completo = original_data.get("texto_completo", "")
    descricao = texto_completo[:300] + "..." if len(texto_completo) > 300 else texto_completo
    seculos = original_data.get("matches_seculos", [])
    data_seculos = ", ".join(seculos) if seculos else ""

    result = {
        # CORREÇÃO APLICADA: Garante que o _id nunca é vazio, usando um fallback único
        "_id": str(doc.get("_id", doc.get("document_id", f"missing_id_{os.getpid()}"))),
        "is_scraped_item": True,
        "score": doc.get("score", 1.0),
        "processed_at": doc.get("processed_at", ""),
        "filename": doc.get("filename", ""),
        "description": descricao,
        "data": data_seculos,
        "titulo": original_data.get("titulo", original_data.get("title", "")),
        "tema": original_data.get("tema", original_data.get("theme", "")),
        "pdf_link": original_data.get("pdf_links", ""),
        "autor": original_data.get("autor", original_data.get("author", "")),
        "capitania": original_data.get("capitania", original_data.get("captaincy", "")),
        "localizacao": original_data.get("localizacao", original_data.get("location", "")),
        "data_de_publicacao": original_data.get("data_de_publicacao", original_data.get("ano_publicacao", "")),
        "nomes": original_data.get("nomes", original_data.get("names", [])),
        "url": original_data.get("url", ""),
        "texto_completo": texto_completo,
        "matches": original_data.get("matches", []),
        "matches_seculos": seculos,
        "matched": original_data.get("matched", False),
        "matched_seculos": original_data.get("matched_seculos", False),
        "matched_nomes_completos": original_data.get("matched_nomes_completos", False),
        "matches_nomes_completos": original_data.get("matches_nomes_completos", []),
        "classified": original_data.get("classified", False)
    }
    return result

def format_pdf_document(doc: Dict[str, Any]) -> Dict[str, Any]:
    """
    Format a PDF document for API response.
    """
    return {
        # CORREÇÃO APLICADA: Garante que o _id nunca é vazio, usando um fallback único
        "_id": str(doc.get("_id", doc.get("document_id", f"missing_id_{os.getpid()}"))),
        "filename": doc.get("filename", ""),
        "text": doc.get("text", ""),
        "names": doc.get("names", []),
        "dates": doc.get("dates", []),
        "themes": doc.get("themes", []),
        "path": doc.get("path", "")
    }

def format_search_result(doc: Dict[str, Any]) -> Dict[str, Any]:
    """
    Format a MongoDB document for API response, supporting both scraped items and PDFs.
    """
    is_scraped = doc.get("is_scraped_item", False)
    result = {
        "id": str(doc.get("_id", "")),
        "score": doc.get("score", 1.0),
        "type": "PDF",
        "titulo": doc.get("title", doc.get("titulo", "Sem título")),
        "autor": doc.get("author", doc.get("autor", "Autor desconhecido")),
        "description": doc.get("description", ""),
        "data": doc.get("date", ""),
        "url": doc.get("url", ""),
        "tema": doc.get("theme", doc.get("tema", "")),
        "pdf_link": doc.get("pdf_url", doc.get("pdf_links", "")),
        "data_de_publicacao": doc.get("publication_date", ""),
        "nomes": doc.get("names", []),
        "capitania": doc.get("captaincy", ""),
        "localizacao": doc.get("location", ""),
        "texto_completo": doc.get("full_content", ""),
        "matched": doc.get("matched", False),
        "matches": doc.get("matches", []),
        "matched_seculos": doc.get("matched_seculos", False),
        "matches_seculos": doc.get("matches_seculos", []),
        "classified": doc.get("classified", False),
    }

    if not is_scraped:
        result.update({
            "dates": doc.get("date_analysis", {}).get("century_counts", {}).keys(),
            "places": doc.get("places_analysis", {}).get("place_counts", {}).keys(),
            "names": doc.get("names_analysis", {}).get("potential_names_found", []),
            "themes": doc.get("themes_analysis", {}).get("themes", []),
            "authors": [ref.get("author", "") for ref in doc.get("references_analysis", {}).get("raw_references", [])[:3]]
        })

    return result

if __name__ == '__main__':
    print("--- Exemplo 1: Sucesso ---")
    results_success = {"contagem": 10, "itens": ["a", "b"]}
    format_and_output_json(results_success, status="Sucesso", message="Itens processados.")

    print("\n--- Exemplo 2: Sucesso com Arquivo ---")
    output_path = "temp_output.json"
    format_and_output_json(results_success, output_file=output_path)
    if os.path.exists(output_path):
        print(f"Verifique o arquivo '{output_path}'")
        os.remove(output_path) 

    print("\n--- Exemplo 3: Aviso (sem dados) ---")
    format_and_output_json(None, status="Aviso", message="Nenhum item encontrado.")

    print("\n--- Exemplo 4: Erro (sem dados) ---")
    format_and_output_json(None, status="Erro", message="Falha ao ler arquivo de entrada.")

    print("\n--- Exemplo 5: Erro de Serialização ---")
    
    results_error = {"conjunto": {"a", "b"}}
    format_and_output_json(results_error)
