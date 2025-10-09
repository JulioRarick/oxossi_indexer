import json
import os
import logging
from typing import Any, Optional, Dict, List, Set
from collections import defaultdict

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(module)s - %(message)s')
log = logging.getLogger(__name__)

def load_json_data(file_path: str) -> Optional[Any]:
    if not os.path.exists(file_path):
        log.error(f"Arquivo JSON não encontrado em '{file_path}'")
        return None
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            log.info(f"Dados JSON carregados com sucesso de '{file_path}'")
            return data
    except json.JSONDecodeError as e:
        log.error(f"Erro de decodificação JSON no arquivo '{file_path}': {e}", exc_info=True)
        return None
    except IOError as e:
        log.error(f"Erro de I/O ao ler o arquivo JSON '{file_path}': {e}", exc_info=True)
        return None
    except Exception as e:
        log.error(f"Erro inesperado ao carregar JSON de '{file_path}': {e}", exc_info=True)
        return None

def load_names_config(file_path: str) -> tuple[set[str], set[str], set[str]]:
    data = load_json_data(file_path)
    if data is None:
        return set(), set(), set()

    try:
        first_names = set(name.strip().capitalize() for name in data.get("first_names", []) if name.strip())
        second_names = set(name.strip().capitalize() for name in data.get("second_names", []) if name.strip())
        
        prepositions_list = data.get("prepositions")
        
        if not prepositions_list:
             prepositions_list = ["da", "das", "do", "dos", "de"] 
        prepositions = set(prep.strip().lower() for prep in prepositions_list if prep.strip())

        log.info(f"Carregados {len(first_names)} nomes, {len(second_names)} sobrenomes, {len(prepositions)} preposições de {file_path}")
        return first_names, second_names, prepositions
    except Exception as e:
        log.error(f"Erro ao processar dados do arquivo de nomes '{file_path}': {e}", exc_info=True)
        return set(), set(), set()

def load_themes_config(file_path: str) -> Optional[Dict[str, List[str]]]:
    data = load_json_data(file_path)
    if data is None:
        return None
    if not isinstance(data, dict):
        log.error(f"Formato inválido no arquivo de temas '{file_path}'. Esperado um dicionário.")
        return None

    valid_data = {}
    for theme, keywords in data.items():
        if isinstance(theme, str) and isinstance(keywords, list) and all(isinstance(kw, str) for kw in keywords):
            valid_data[theme] = keywords
        else:
            log.warning(f"Entrada de tema inválida ignorada em '{file_path}': Chave='{theme}', Valor='{keywords}'")

    if not valid_data:
        log.warning(f"Nenhum grupo de tema válido carregado de '{file_path}'.")
        return None

    log.info(f"Carregados {len(valid_data)} grupos de temas de {file_path}")
    return valid_data


if __name__ == '__main__':
    test_names_path = "temp_names.json"
    test_themes_path = "temp_themes.json"

    names_content = {
        "first_names": [" João ", "Maria", " pedro"],
        "second_names": ["Silva", " santos ", "Silva"], 
        "prepositions": [" de ", "da", ""] 
    }
    themes_content = {
        "Economia": ["gado", "comércio", "troca"],
        "Política": ["poder", "rei", "câmara"],
        "Inválido": ["ok", 123] 
    }

    try:
        with open(test_names_path, 'w', encoding='utf-8') as f:
            json.dump(names_content, f, ensure_ascii=False, indent=4)
        with open(test_themes_path, 'w', encoding='utf-8') as f:
            json.dump(themes_content, f, ensure_ascii=False, indent=4)

        print("\n--- Testando load_names_config ---")
        f_names, s_names, preps = load_names_config(test_names_path)
        print(f"Nomes: {f_names}")
        print(f"Sobrenomes: {s_names}")
        print(f"Preposições: {preps}")
        assert f_names == {"João", "Maria", "Pedro"}
        assert s_names == {"Silva", "Santos"}
        assert preps == {"de", "da"}

        print("\n--- Testando load_themes_config ---")
        themes = load_themes_config(test_themes_path)
        print(f"Temas: {themes}")
        assert themes is not None
        assert "Economia" in themes
        assert "Política" in themes
        assert "Inválido" not in themes 
        
        print("\n--- Testando arquivo inexistente ---")
        load_json_data("nao_existe.json")
        load_names_config("nao_existe.json")
        load_themes_config("nao_existe.json")

    finally:
        if os.path.exists(test_names_path):
            os.remove(test_names_path)
        if os.path.exists(test_themes_path):
            os.remove(test_themes_path)

