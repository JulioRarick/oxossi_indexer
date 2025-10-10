import re
import json
import argparse
import logging
import os
import sys
import statistics
from typing import Optional, Dict, List, Tuple, Any, Union

from utils.pdf_utils import extract_text_from_pdf
from utils.data_utils import load_json_data
from utils.output_utils import format_and_output_json

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')
log = logging.getLogger(__name__)

class DateExtractor:
    def __init__(self, config: Optional[Union[str, Dict[str, Any]]]):

        if isinstance(config, str):
            self.config = load_date_config(config)
        elif isinstance(config, dict):
            self.config = config
        else:
            raise ValueError("Configuração inválida para DateExtractor. Deve ser um caminho de arquivo ou um dicionário.")

    def _load_date_config(self, config_path: str) -> Optional[Dict[str, Any]]:
        config = load_json_data(config_path)
        if not config:
            log.error(f"Falha ao carregar configuração de datas de '{config_path}'")
            return None
        required_keys = ["century_map", "part_map", "regex_patterns"]
        if not all(k in config for k in required_keys):
            log.error(f"Estrutura inválida no arquivo de configuração de datas '{config_path}'")
            return None
        return config

    def _calculate_interval_from_match(self, match_dict: Dict[str, Optional[str]], config: Dict[str, Any]) -> Optional[Tuple[int, int]]:
        century_str = match_dict.get('century')
        part_str = match_dict.get('part')
        century_map = config.get("century_map", {})
        part_map = config.get("part_map", {})

        if not century_str:
            return None

        century_norm = re.sub(r's[ée]culo\s+', '', century_str.lower().strip())
        base_year = century_map.get(century_norm)

        if base_year is None:
            log.warning(f"Normalização de século não reconhecida: '{century_norm}' (Original: '{century_str}')")
            return None
        
        if not part_str:
            return (base_year, base_year + 100)
        else:
            part_norm = part_str.lower().strip()
            part_norm = part_norm.replace('í', 'i').replace('ç', 'c').replace('finais', 'final')
            relative_interval = part_map.get(part_norm)

            if relative_interval and len(relative_interval) == 2:
                start_offset, end_offset = relative_interval
                
                start_offset = max(0, min(100, start_offset))
                end_offset = max(0, min(100, end_offset))
                
                if start_offset > end_offset:
                    start_offset, end_offset = end_offset, start_offset
                return (base_year + start_offset, base_year + end_offset)
            else:
                log.warning(f"Frase de parte não reconhecida ou inválida: '{part_str}' (Normalizada: '{part_norm}') - Usando século inteiro.")
                return (base_year, base_year + 100)

    def extract_and_analyze_dates(self, text: str) -> Dict[str, Any]:
        results_template = {
            'mean': None, 'median': None, 'minimum': None, 'maximum': None,
        }

        if not isinstance(text, str) or not text:
            log.warning("Texto de entrada inválido ou vazio para análise de datas.")
            return results_template
        if not self.config:
            log.error("Configuração de datas inválida ou vazia.")
            return results_template

        regex_patterns = self.config.get("regex_patterns", {})
        regex_year_str = regex_patterns.get("year")
        regex_textual_str = regex_patterns.get("textual_phrase")

        if not regex_year_str or not regex_textual_str:
            log.error("Padrões regex não encontrados na configuração.")
            return results_template

        combined_regex_str = f"({regex_year_str})|({regex_textual_str})"

        numeric_years_found = []
        textual_intervals_found = set() 

        try:
            compiled_regex = re.compile(combined_regex_str, flags=re.IGNORECASE | re.VERBOSE)

            log.info("Iniciando busca por datas no texto...")
            for match in compiled_regex.finditer(text):
                if match.group(1): 
                    try:
                        year_match = re.match(regex_year_str, match.group(1))
                        if year_match:
                            numeric_years_found.append(int(year_match.group('year')))
                    except (ValueError, IndexError, TypeError):
                         log.warning(f"Não foi possível converter ano numérico do match: {match.group(1)}")
                elif match.group(2):  
                    textual_match = re.match(regex_textual_str, match.group(2), flags=re.IGNORECASE | re.VERBOSE)
                    if textual_match:
                        interval = self._calculate_interval_from_match(textual_match.groupdict(), self.config)
                        if interval:
                            textual_intervals_found.add(interval)
                    else:
                        log.warning(f"Match textual encontrado ({match.group(2)}) mas falhou ao re-match para extrair partes.")

        except re.error as e:
            log.error(f"Erro de Regex durante a compilação ou busca: {e}", exc_info=True)
            return results_template 
        except Exception as e:
            log.error(f"Erro inesperado durante a busca por datas: {e}", exc_info=True)
            return results_template

        log.info(f"Encontrados {len(numeric_years_found)} anos numéricos e {len(textual_intervals_found)} intervalos textuais únicos.")

        representative_years_from_intervals = []
        for start, end in textual_intervals_found:
            representative_years_from_intervals.append(int(round((start + end) / 2)))

        combined_years = sorted(list(set(numeric_years_found + representative_years_from_intervals)))

        results = results_template.copy() 
        results['direct_numeric_years'] = sorted(list(set(numeric_years_found)))
        results['calculated_textual_intervals'] = sorted(list(textual_intervals_found))
        results['combined_representative_years'] = combined_years
        results['count'] = len(combined_years)

        if not combined_years:
            log.info("Nenhuma data representativa encontrada para análise estatística.")
            return results 

        try:
            results['mean'] = float(statistics.mean(combined_years))
            results['median'] = float(statistics.median(combined_years))
            results['minimum'] = int(min(combined_years))
            results['maximum'] = int(max(combined_years))
            
            # Calcula desvio padrão manualmente
            if len(combined_years) > 1:
                mean_val = results['mean']
                variance = sum((x - mean_val) ** 2 for x in combined_years) / len(combined_years)
                results['standard_deviation'] = float(variance ** 0.5)
            else:
                results['standard_deviation'] = 0.0
                
            results['full_range'] = f"{results['minimum']} - {results['maximum']}"

            if results['mean'] is not None and results['standard_deviation'] is not None:
                mean_val = results['mean']
                std_dev_val = results['standard_deviation']
                dense_start = int(round(mean_val - std_dev_val))
                dense_end = int(round(mean_val + std_dev_val))
                results['dense_range_stddev'] = (dense_start, dense_end)

            log.info("Análise estatística das datas concluída.")

        except Exception as e:
            log.error(f"Erro durante cálculos estatísticos: {e}", exc_info=True)
            
            results.update({
                'mean': None, 'median': None, 'standard_deviation': None,
                'full_range': None, 'dense_range_stddev': None
            })

        return results

    def extract_dates(self, text: str) -> List[Dict[str, Any]]:
        """
        Extrai datas do texto retornando informações detalhadas
        """
        results = self.extract_and_analyze_dates(text)
        
        date_infos = []
        
        # Adiciona anos numéricos diretos
        for year in results.get('direct_numeric_years', []):
            date_infos.append({
                'year': year,
                'type': 'numeric',
                'century': self._year_to_century(year)
            })
        
        # Adiciona intervalos textuais
        for start, end in results.get('calculated_textual_intervals', []):
            representative_year = int(round((start + end) / 2))
            date_infos.append({
                'year': representative_year,
                'year_start': start,
                'year_end': end,
                'type': 'textual',
                'century': self._year_to_century(representative_year)
            })
        
        return date_infos

    def _year_to_century(self, year: int) -> str:
        """Converte ano para século"""
        century_num = ((year - 1) // 100) + 1
        if century_num <= 20:
            century_romans = {
                1: 'I', 2: 'II', 3: 'III', 4: 'IV', 5: 'V',
                6: 'VI', 7: 'VII', 8: 'VIII', 9: 'IX', 10: 'X',
                11: 'XI', 12: 'XII', 13: 'XIII', 14: 'XIV', 15: 'XV',
                16: 'XVI', 17: 'XVII', 18: 'XVIII', 19: 'XIX', 20: 'XX'
            }
            return f"século {century_romans.get(century_num, str(century_num))}"
        return f"século {century_num}"

    def calcular_media_dma_temporal(self, text: str, ano_inicio: int = 1200, ano_fim: int = 2025) -> Tuple[Optional[int], Optional[int]]:
        """
        Calcula média e DMA dos anos encontrados no texto usando análise contextual avançada
        
        Args:
            text: Texto para análise
            ano_inicio: Ano mínimo do período
            ano_fim: Ano máximo do período
        
        Returns:
            Tuple com (media, dma) ou (None, None) se nenhum ano encontrado
        """
        try:
            # Extrai dados de datas
            dates_data = self.extract_dates(text)
            
            # Coleta anos válidos
            anos_encontrados = []
            for date_info in dates_data:
                if 'year' in date_info:
                    year = date_info['year']
                    if ano_inicio <= year <= ano_fim:
                        anos_encontrados.append(year)
                
                # Inclui ano inicial de intervalos textuais
                if 'year_start' in date_info and date_info.get('type') == 'textual':
                    year_start = date_info['year_start']
                    if ano_inicio <= year_start <= ano_fim:
                        anos_encontrados.append(year_start)
            
            if not anos_encontrados:
                return None, None
            
            # Remove duplicatas
            anos_unicos = list(set(anos_encontrados))
            
            # Calcula média
            media = sum(anos_unicos) / len(anos_unicos)
            
            # Calcula DMA (Desvio Médio Absoluto)
            desvios_absolutos = [abs(ano - media) for ano in anos_unicos]
            dma = sum(desvios_absolutos) / len(desvios_absolutos)
            
            return round(media), round(dma)
            
        except Exception as e:
            log.error(f"Erro no cálculo de média e DMA: {e}")
            return None, None

    def _analyze_temporal_context(self, text: str) -> Dict[str, Any]:
        """Análise temporal completa do documento"""
        try:
            # Calcula média e DMA
            media, dma = self.calcular_media_dma_temporal(text)
            
            # Extrai dados de datas
            dates_data = self.extract_dates(text)
            years = [d['year'] for d in dates_data if 'year' in d]
            
            # Calcula consistência
            consistencia = self._calculate_temporal_consistency(years)
            
            # Extrai séculos mencionados
            seculos = list(set(d.get('century') for d in dates_data if d.get('century')))
            
            return {
                'media_anos': media,
                'desvio_medio_absoluto': dma,
                'anos_encontrados': len(years),
                'periodo_principal': {
                    'inicio': min(years) if years else None,
                    'fim': max(years) if years else None
                },
                'seculos_mencionados': seculos,
                'consistencia_temporal': consistencia,
                'anos_listados': sorted(list(set(years))) if years else []
            }
            
        except Exception as e:
            log.error(f"Erro na análise temporal: {e}")
            return {
                'media_anos': None,
                'desvio_medio_absoluto': None,
                'anos_encontrados': 0,
                'periodo_principal': {'inicio': None, 'fim': None},
                'seculos_mencionados': [],
                'consistencia_temporal': 0.0,
                'anos_listados': []
            }

    def _calculate_temporal_consistency(self, years: List[int]) -> float:
        """
        Calcula consistência temporal do documento
        Documentos com anos próximos têm maior consistência
        """
        if len(years) < 2:
            return 1.0
        
        # Ordena anos e calcula gaps
        years_sorted = sorted(years)
        gaps = [years_sorted[i+1] - years_sorted[i] for i in range(len(years_sorted)-1)]
        
        # Se não há gaps, retorna 1.0
        if not gaps:
            return 1.0
        
        avg_gap = sum(gaps) / len(gaps)
        max_gap = max(gaps)
        
        # Classifica consistência baseada no gap máximo
        if max_gap <= 10:  # Anos muito próximos
            return 0.9
        elif max_gap <= 25:  # Anos relativamente próximos
            return 0.7
        elif max_gap <= 50:  # Anos moderadamente distantes
            return 0.5
        else:  # Anos muito distantes
            return 0.3

def load_date_config(config_path: str) -> Optional[Dict[str, Any]]:
    extractor = DateExtractor("")  
    return extractor._load_date_config(config_path)

def extract_dates(text: str, config: Dict[str, Any]) -> List[Dict[str, Any]]:
    extractor = DateExtractor(config)
    return extractor.extract_dates(text)

def main():
    parser = argparse.ArgumentParser(
        description="Extrai e analisa datas de um arquivo PDF, gerando um JSON com os resultados.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        "pdf_input_path",
        help="Caminho para o arquivo PDF de entrada."
    )
    parser.add_argument(
        "--config", "-c",
        default=os.path.join(os.path.dirname(__file__), "..", "..", "data", "date_config.json"),
        help="Caminho para o arquivo de configuração JSON (date_config.json)."
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="Caminho opcional para salvar a saída JSON."
    )
    args = parser.parse_args()

    log.info(f"Iniciando extração de datas para: {args.pdf_input_path}")
    log.info(f"Usando arquivo de configuração: {args.config}")
    if args.output:
        log.info(f"Saída JSON será salva em: {args.output}")

    date_extractor = DateExtractor(args.config)

    extracted_text = extract_text_from_pdf(args.pdf_input_path)
    if not extracted_text:
        format_and_output_json(None, status="Erro", message=f"Falha ao extrair texto de {args.pdf_input_path}", output_file=args.output)
        sys.exit(1)

    analysis_results = date_extractor.extract_and_analyze_dates(extracted_text)

    if analysis_results:
        status = "Sucesso" if analysis_results.get('count', 0) > 0 else "Aviso"
        message = f"{analysis_results.get('count', 0)} datas representativas analisadas." if status == "Sucesso" else "Nenhuma data relevante encontrada ou analisada."
        format_and_output_json(analysis_results, status=status, message=message, output_file=args.output)
    else:
        format_and_output_json(None, status="Erro", message="Falha inesperada durante a análise das datas.", output_file=args.output)
        sys.exit(1)

    log.info("Processo concluído.")

if __name__ == "__main__":
    main()
