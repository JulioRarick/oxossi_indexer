import re
import os
import argparse
import logging
from collections import defaultdict
from typing import Dict, List, Tuple, Optional, DefaultDict, Set, Union, Any

from utils.pdf_utils import extract_text_from_pdf
from utils.output_utils import format_and_output_json

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')
log = logging.getLogger(__name__)

class PlaceExtractor:
    def __init__(self, data_path: str):
        self.data = self.load_place_captaincy_data(data_path)
        if not self.data:
            raise ValueError("Dados de locais/capitanias inválidos.")

    def load_place_captaincy_data(self, filepath: str) -> Optional[Dict[str, List[str]]]:
        if not os.path.exists(filepath):
            log.error(f"Arquivo de dados de locais/capitanias não encontrado em '{filepath}'")
            return None

        captaincy_data: DefaultDict[str, List[str]] = defaultdict(list)
        
        assigned_places: Set[str] = set()
        lines_processed = 0
        lines_ignored = 0
        places_loaded = 0
        captaincies_found = set()

        try:
            log.info(f"Carregando dados de locais/capitanias de: {filepath}")
            with open(filepath, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    lines_processed += 1

                    if not line or line.startswith('#'):
                        lines_ignored += 1
                        continue

                    parts = line.split(',', 1)
                    
                    if len(parts) == 2:
                        place = parts[0].strip()
                        captaincy = parts[1].strip()

                        if place and captaincy:
                            if place not in assigned_places:
                                captaincy_data[captaincy].append(place)
                                assigned_places.add(place)
                                captaincies_found.add(captaincy)
                                places_loaded += 1
                        else:
                            log.warning(f"Linha {line_num} ignorada por falta de nome de local ou capitania: '{line}'")
                            lines_ignored += 1
                    else:
                        log.warning(f"Linha {line_num} ignorada devido ao formato incorreto (Esperado 'Local,Capitania'): '{line}'")
                        lines_ignored += 1

            log.info(f"Carregamento concluído: {lines_processed} linhas lidas, {lines_ignored} ignoradas.")
            log.info(f"Carregados {places_loaded} locais únicos para {len(captaincies_found)} capitanias.")

        except IOError as e:
            log.error(f"Erro de I/O ao ler o arquivo {filepath}: {e}", exc_info=True)
            return None
        except Exception as e:
            log.error(f"Erro inesperado ao processar o arquivo {filepath}: {e}", exc_info=True)
            return None

        if not captaincy_data:
             log.warning(f"Nenhum dado válido de local/capitania carregado de '{filepath}'.")
             
             return {}

        return dict(captaincy_data)
    
    def extract_places(self, text: str) -> Dict[str, Any]:
        """ 
        Método wrapper para extração de locais, usando os dados internos.
        Este é o método que o run_indexer.py deve chamar.
        """
        if not self.data:
            log.warning("Chamada a extract_places, mas dados de local estão vazios.")
            return {
                "found_places_details": [],
                "top_captaincy": None,
                "all_captaincy_scores": {},
                "warning": "Dados de local não carregados na inicialização."
            }
            
        # Chama o método de análise principal, passando o texto e os dados internos
        return self.search_colonial_places(text, self.data)

    def search_colonial_places(self, text: str, captaincy_data: Dict[str, List[str]]) -> Dict[str, Any]:
        results_template: Dict[str, Any] = {
            "found_places_details": [],
            "top_captaincy": None,
            "all_captaincy_scores": {}
        }

        if not text:
            log.warning("Texto de entrada vazio para busca de locais.")
            return results_template
        if not captaincy_data:
            log.warning("Dados de capitania vazios para busca de locais.")
            return results_template

        captaincy_scores: Dict[str, int] = {cap: 0 for cap in captaincy_data}
        
        found_places_counts: DefaultDict[str, int] = defaultdict(int)

        place_to_captaincy: Dict[str, str] = {}
        all_places_canonical: Set[str] = set()
        
        lower_to_canonical_place: Dict[str, str] = {}

        log.info("Construindo tabelas de consulta de locais...")
        for captaincy, places in captaincy_data.items():
            for place in places:
                if place not in place_to_captaincy:
                    place_to_captaincy[place] = captaincy
                    all_places_canonical.add(place)
                    lower_to_canonical_place[place.lower()] = place

        if not all_places_canonical:
            log.warning("Nenhum local único encontrado nos dados de capitania para construir regex.")
            results_template["all_captaincy_scores"] = captaincy_scores 
            return results_template

        sorted_places = sorted(list(all_places_canonical), key=len, reverse=True)

        pattern_str = r'\b(' + '|'.join(re.escape(place) for place in sorted_places) + r')\b'
        log.info(f"Padrão regex criado com {len(sorted_places)} locais únicos.")

        try:
            regex_pattern = re.compile(pattern_str, re.IGNORECASE) 

            log.info("Buscando locais no texto...")
            matches_found = 0
            for match in regex_pattern.finditer(text):
                matched_text = match.group(1) 
                canonical_place = lower_to_canonical_place.get(matched_text.lower())
                
                if canonical_place:
                    found_places_counts[canonical_place] += 1
                    matches_found += 1
                else:
                    log.warning(f"Match encontrado '{matched_text}' mas não mapeado para nome canônico.")

            log.info(f"Busca concluída. {matches_found} matches encontrados para {len(found_places_counts)} locais distintos.")

        except re.error as e:
            log.error(f"Erro de Regex durante compilação ou busca: {e}", exc_info=True)
            results_template["all_captaincy_scores"] = captaincy_scores
            return results_template
        except Exception as e:
             log.error(f"Erro inesperado durante a busca regex: {e}", exc_info=True)
             results_template["all_captaincy_scores"] = captaincy_scores
             return results_template

        if not found_places_counts:
            log.info("Nenhum local conhecido foi encontrado no texto.")
            results_template["all_captaincy_scores"] = captaincy_scores
            return results_template

        log.info("Calculando pontuações das capitanias...")
        for place, count in found_places_counts.items():
            captaincy = place_to_captaincy.get(place)
            if captaincy:
                captaincy_scores[captaincy] += count
                
        top_captaincy: Optional[Union[str, List[str]]] = None
        max_score = 0
        
        positive_scores = {cap: score for cap, score in captaincy_scores.items() if score > 0}

        if positive_scores:
            max_score = max(positive_scores.values())
            
            tied_top_captaincies = [cap for cap, score in positive_scores.items() if score == max_score]

            if len(tied_top_captaincies) == 1:
                top_captaincy = tied_top_captaincies[0]
                log.info(f"Capitania principal: {top_captaincy} (Pontuação: {max_score})")
            else:
                top_captaincy = sorted(tied_top_captaincies)
                log.info(f"Empate para capitania principal: {', '.join(top_captaincy)} (Pontuação: {max_score})")
        else:
            log.info("Nenhuma capitania obteve pontuação maior que zero.")

        found_places_details_list = sorted(list(found_places_counts.items()))

        all_scores_dict = dict(captaincy_scores)

        return {
            "found_places_details": found_places_details_list,
            "top_captaincy": top_captaincy,
            "all_captaincy_scores": all_scores_dict
        }

def main():
    parser = argparse.ArgumentParser(
        description="Analisa arquivo TXT ou PDF para menções de locais coloniais, determina a capitania principal e gera saída JSON.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        "input_file",
        help="Caminho para o arquivo de entrada (.txt ou .pdf) a ser analisado."
    )
    parser.add_argument(
        "data_file",
        help="Caminho para o arquivo de dados contendo locais e suas capitanias.\nFormato esperado: Cada linha 'Nome do Lugar,Nome da Capitania'"
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="Caminho opcional para salvar a saída JSON."
    )
    args = parser.parse_args()

    log.info(f"Iniciando extração de locais para: {args.input_file}")
    log.info(f"Usando arquivo de dados: {args.data_file}")
    if args.output:
        log.info(f"Saída JSON será salva em: {args.output}")

    captaincy_place_map = None
    try:
        extractor = PlaceExtractor(args.data_file)
        captaincy_place_map = extractor.data
    except Exception as e:
        log.error(f"Erro ao inicializar PlaceExtractor: {e}", exc_info=True)
        format_and_output_json(None, status="Erro", message=str(e), output_file=args.output)
        sys.exit(1)

    if not captaincy_place_map: 
         format_and_output_json(None, status="Aviso", message=f"Nenhum dado válido de local/capitania carregado de {args.data_file}", output_file=args.output)

    file_text: Optional[str] = None
    input_path = args.input_file
    if not os.path.exists(input_path):
        error_msg = f"Erro: Arquivo de entrada não encontrado em '{input_path}'"
        log.error(error_msg)
        format_and_output_json(None, status="Erro", message=error_msg, output_file=args.output)
        sys.exit(1)
    elif input_path.lower().endswith(".pdf"):
        file_text = extract_text_from_pdf(input_path)
        if file_text is None:
            error_msg = f"Falha ao extrair texto do PDF '{input_path}'."
            format_and_output_json(None, status="Erro", message=error_msg, output_file=args.output)
            
            sys.exit(1)
    elif input_path.lower().endswith((".txt", ".csv")): 
        try:
            with open(input_path, 'r', encoding='utf-8') as f:
                file_text = f.read()
            log.info(f"Texto lido com sucesso de '{input_path}'")
        except Exception as e:
            error_msg = f"Erro ao ler arquivo de texto '{input_path}': {e}"
            log.error(error_msg, exc_info=True)
            format_and_output_json(None, status="Erro", message=error_msg, output_file=args.output)
            sys.exit(1)
    else:
        error_msg = f"Erro: Tipo de arquivo de entrada não suportado para '{input_path}'. Forneça .txt, .csv ou .pdf."
        log.error(error_msg)
        format_and_output_json(None, status="Erro", message=error_msg, output_file=args.output)
        sys.exit(1)

    analysis_results = None
    try:
        extractor = PlaceExtractor(args.data_file)
        analysis_results = extractor.search_colonial_places(file_text, captaincy_place_map or {})
    except Exception as e:
        log.error(f"Erro durante a análise de locais: {e}", exc_info=True)
        format_and_output_json(None, status="Erro", message=str(e), output_file=args.output)
        sys.exit(1)

    status = "Sucesso" if analysis_results.get("found_places_details") else "Aviso"
    message = "Análise de locais concluída." if status == "Sucesso" else "Nenhum local conhecido encontrado no texto."
    
    if not captaincy_place_map and status == "Aviso":
        message = "Nenhum local conhecido encontrado (dados de capitania estavam vazios)."

    format_and_output_json(analysis_results, status=status, message=message, output_file=args.output)

    log.info("Processo concluído.")

if __name__ == "__main__":
    import sys
    main()
