import subprocess
import json
import argparse
import logging
import os
import sys
from typing import Optional, List, Dict, Any
from utils.output_utils import format_and_output_json

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')
log = logging.getLogger(__name__)


class ReferenceFormatter:
    def __init__(self):
        pass

    def format_reference(self, item: Dict[str, Any]) -> Optional[str]:
        authors = item.get("author", [])
        title_list = item.get("title", [])
        date_list = item.get("date", [])

        author_str = ""
        if authors and isinstance(authors, list) and len(authors) > 0:
            first_author = authors[0]
            if isinstance(first_author, dict):
                family = first_author.get("family")
                given = first_author.get("given")
                if family and given:
                    author_str = f"{family.strip()},{given.strip()[0:1]}"
                elif family:
                     author_str = f"{family.strip()}"

        title_str = title_list[0][:30] + "..." if title_list and isinstance(title_list, list) and title_list[0] else "-"
        title_str = title_str.strip()

        year_str = date_list[0][:4] if date_list and isinstance(date_list, list) and date_list[0] else "-"
        year_str = year_str.strip()

        if author_str:
            return f"{author_str}. ({year_str}) {title_str}"
        else:
            log.debug(f"Referência ignorada por falta de autor válido: {item}")
            return None


def extract_references_with_anystyle(pdf_path: str) -> Optional[List[Dict[str, Any]]]:
    """
    Extract references from PDF using anystyle tool.
    Falls back to an empty list if anystyle is not available.
    """
    if not os.path.exists(pdf_path):
        log.error(f"Arquivo PDF não encontrado para extração de referências: '{pdf_path}'")
        return None

    command = ["anystyle", "find", pdf_path]
    log.info(f"Executando comando: {' '.join(command)}")

    try:
        result = subprocess.run(command, capture_output=True, text=True, check=True, encoding='utf-8')
        log.info("Comando anystyle executado com sucesso.")
        try:
            references_raw = json.loads(result.stdout)
            if isinstance(references_raw, list):
                log.info(f"Encontradas {len(references_raw)} referências brutas pelo anystyle.")
                return references_raw
            else:
                log.error(f"Saída do anystyle não é uma lista JSON válida: {result.stdout[:200]}...")
                return None
        except json.JSONDecodeError as e:
            log.error(f"Falha ao decodificar a saída JSON do anystyle: {e}", exc_info=True)
            log.error(f"Saída recebida (stdout): {result.stdout[:500]}...") 
            return None

    except FileNotFoundError:
        log.warning("Comando 'anystyle' não encontrado. Usando fallback para extração de referências.")
        
        return []
    except subprocess.CalledProcessError as e:
        log.error(f"Comando anystyle falhou com código de erro {e.returncode}.")
        log.error(f"Stderr: {e.stderr}")
        log.error(f"Stdout: {e.stdout}")
        
        return []
    except Exception as e:
        log.error(f"Erro inesperado ao executar anystyle: {e}", exc_info=True)
        return None


def main():
    parser = argparse.ArgumentParser(
        description="Extrai referências bibliográficas de um arquivo PDF usando 'anystyle' e gera saída JSON.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        "pdf_input_path",
        help="Caminho para o arquivo PDF de entrada."
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="Caminho opcional para salvar a saída JSON."
    )
    parser.add_argument(
        "--raw", "-r",
        action="store_true", 
        help="Incluir a lista completa de referências brutas (JSON do anystyle) na saída."
    )

    args = parser.parse_args()

    log.info(f"Iniciando extração de referências para: {args.pdf_input_path}")
    if args.output:
        log.info(f"Saída JSON será salva em: {args.output}")

    references_raw = extract_references_with_anystyle(args.pdf_input_path)

    if references_raw is None:
        format_and_output_json(None, status="Erro", message="Falha ao executar ou processar a saída do anystyle.", output_file=args.output)
        sys.exit(1)

    formatted_references = []
    
    if references_raw:
        formatter = ReferenceFormatter()
        for item in references_raw:
            formatted = formatter.format_reference(item)
            if formatted:
                formatted_references.append(formatted)
        log.info(f"Formatadas {len(formatted_references)} referências válidas.")
    else:
        log.info("Nenhuma referência bruta encontrada pelo anystyle.")


    results_data = {
        "formatted_references": formatted_references,
        "count": len(formatted_references)
    }
    if args.raw:
        results_data["raw_anystyle_output"] = references_raw

    status = "Sucesso" if formatted_references else "Aviso"
    message = f"{len(formatted_references)} referências formatadas encontradas." if formatted_references else "Nenhuma referência válida encontrada ou formatada."
    if not references_raw and status == "Aviso": 
        message = "Nenhuma referência encontrada pelo anystyle."


    format_and_output_json(results_data, status=status, message=message, output_file=args.output)

    log.info("Processo concluído.")

if __name__ == "__main__":
    main()
