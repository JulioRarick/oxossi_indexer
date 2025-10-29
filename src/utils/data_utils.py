# utils/data_utils.py

import json
import os
import logging
from typing import Any, Optional, Dict, List, Set, Union, Tuple
from collections import defaultdict
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(module)s - %(message)s')
log = logging.getLogger(__name__)

def load_json_data(file_path: str) -> Optional[Any]:
    """
    Carrega dados de arquivo JSON com tratamento robusto de erros
    
    Args:
        file_path: Caminho do arquivo JSON
        
    Returns:
        Dados carregados ou None se houver erro
    """
    # Valida se caminho foi fornecido
    if not file_path or not isinstance(file_path, str) or file_path.strip() == '':
        log.warning("Caminho de arquivo vazio ou inválido fornecido para load_json_data")
        return None
    
    # Remove espaços em branco
    file_path = file_path.strip()
    
    # Verifica se arquivo existe
    if not os.path.exists(file_path):
        log.error(f"Arquivo JSON não encontrado em '{file_path}'")
        return None
    
    # Verifica se é um arquivo (não diretório)
    if not os.path.isfile(file_path):
        log.error(f"'{file_path}' não é um arquivo")
        return None
    
    # Verifica tamanho do arquivo
    try:
        file_size = os.path.getsize(file_path)
        if file_size == 0:
            log.warning(f"Arquivo JSON vazio: '{file_path}'")
            return None
    except OSError as e:
        log.error(f"Erro ao obter tamanho do arquivo '{file_path}': {e}")
        return None
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Valida se retornou dados válidos
        if data is None:
            log.warning(f"Arquivo JSON contém apenas null: '{file_path}'")
            return None
            
        log.info(f"Dados JSON carregados com sucesso de '{file_path}'")
        return data
        
    except json.JSONDecodeError as e:
        log.error(f"Erro de decodificação JSON no arquivo '{file_path}': {e}", exc_info=True)
        log.debug(f"Linha {e.lineno}, coluna {e.colno}: {e.msg}")
        return None
        
    except UnicodeDecodeError as e:
        log.error(f"Erro de codificação ao ler '{file_path}': {e}")
        # Tenta com encoding alternativo
        try:
            log.info(f"Tentando ler com encoding 'latin-1'...")
            with open(file_path, 'r', encoding='latin-1') as f:
                data = json.load(f)
            log.info(f"JSON carregado com encoding alternativo")
            return data
        except Exception as e2:
            log.error(f"Falha também com encoding alternativo: {e2}")
            return None
            
    except IOError as e:
        log.error(f"Erro de I/O ao ler o arquivo JSON '{file_path}': {e}", exc_info=True)
        return None
        
    except Exception as e:
        log.error(f"Erro inesperado ao carregar JSON de '{file_path}': {e}", exc_info=True)
        return None


def load_names_config(file_path: str) -> Tuple[Set[str], Set[str], Set[str]]:
    """
    Carrega configuração de nomes
    
    Args:
        file_path: Caminho do arquivo de configuração
        
    Returns:
        Tupla com (first_names, second_names, prepositions)
    """
    data = load_json_data(file_path)
    if data is None:
        log.warning(f"Usando configuração vazia para nomes (arquivo não carregado)")
        return set(), set(), set()

    try:
        # Processa nomes
        first_names = set(
            name.strip().capitalize() 
            for name in data.get("first_names", []) 
            if name and isinstance(name, str) and name.strip()
        )
        
        # Processa sobrenomes
        second_names = set(
            name.strip().capitalize() 
            for name in data.get("second_names", []) 
            if name and isinstance(name, str) and name.strip()
        )
        
        # Processa preposições com fallback
        prepositions_list = data.get("prepositions")
        if not prepositions_list:
            log.info("Usando preposições padrão")
            prepositions_list = ["da", "das", "do", "dos", "de"]
        
        prepositions = set(
            prep.strip().lower() 
            for prep in prepositions_list 
            if prep and isinstance(prep, str) and prep.strip()
        )

        log.info(
            f"Carregados {len(first_names)} nomes, "
            f"{len(second_names)} sobrenomes, "
            f"{len(prepositions)} preposições de '{file_path}'"
        )
        
        return first_names, second_names, prepositions
        
    except Exception as e:
        log.error(f"Erro ao processar dados do arquivo de nomes '{file_path}': {e}", exc_info=True)
        return set(), set(), set()


def load_themes_config(file_path: str) -> Optional[Dict[str, List[str]]]:
    """
    Carrega configuração de temas
    
    Args:
        file_path: Caminho do arquivo de configuração
        
    Returns:
        Dicionário de temas ou None
    """
    data = load_json_data(file_path)
    if data is None:
        return None
        
    if not isinstance(data, dict):
        log.error(f"Formato inválido no arquivo de temas '{file_path}'. Esperado um dicionário.")
        return None

    valid_data = {}
    for theme, keywords in data.items():
        # Valida estrutura
        if not isinstance(theme, str):
            log.warning(f"Chave de tema inválida ignorada em '{file_path}': {theme}")
            continue
            
        if not isinstance(keywords, list):
            log.warning(f"Valor de tema inválido para '{theme}' em '{file_path}': {keywords}")
            continue
        
        # Valida e filtra keywords
        valid_keywords = [
            kw.strip() 
            for kw in keywords 
            if isinstance(kw, str) and kw.strip()
        ]
        
        if valid_keywords:
            valid_data[theme] = valid_keywords
        else:
            log.warning(f"Tema '{theme}' não possui palavras-chave válidas em '{file_path}'")

    if not valid_data:
        log.warning(f"Nenhum grupo de tema válido carregado de '{file_path}'.")
        return None

    log.info(f"Carregados {len(valid_data)} grupos de temas de '{file_path}'")
    return valid_data


def save_json_data(data: Union[Dict[str, Any], List[Any]], file_path: str, 
                   indent: int = 2, ensure_ascii: bool = False) -> bool:
    """
    Salva dados em arquivo JSON
    
    Args:
        data: Dados para salvar
        file_path: Caminho do arquivo de destino
        indent: Indentação (None para compacto)
        ensure_ascii: Se False, permite caracteres Unicode
        
    Returns:
        True se salvou com sucesso, False caso contrário
    """
    if not file_path or not isinstance(file_path, str) or file_path.strip() == '':
        log.error("Caminho de arquivo vazio fornecido para save_json_data")
        return False
    
    file_path = file_path.strip()
    
    try:
        # Cria diretório pai se não existir
        directory = os.path.dirname(file_path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        
        log.debug(f"Salvando JSON em: {file_path}")
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=indent, ensure_ascii=ensure_ascii)
        
        file_size = os.path.getsize(file_path)
        log.info(f"JSON salvo com sucesso em '{file_path}' ({file_size} bytes)")
        return True
        
    except Exception as e:
        log.error(f"Erro ao salvar JSON em '{file_path}': {e}", exc_info=True)
        return False


def load_text_file(file_path: str, encoding: str = 'utf-8') -> Optional[str]:
    """
    Carrega arquivo de texto
    
    Args:
        file_path: Caminho do arquivo
        encoding: Codificação do arquivo
        
    Returns:
        Conteúdo do arquivo ou None
    """
    if not file_path or not isinstance(file_path, str) or file_path.strip() == '':
        log.warning("Caminho de arquivo vazio fornecido para load_text_file")
        return None
    
    file_path = file_path.strip()
    
    if not os.path.exists(file_path):
        log.error(f"Arquivo de texto não encontrado: '{file_path}'")
        return None
    
    try:
        with open(file_path, 'r', encoding=encoding) as f:
            content = f.read()
        
        log.info(f"Arquivo de texto carregado: '{file_path}' ({len(content)} caracteres)")
        return content
        
    except UnicodeDecodeError as e:
        log.warning(f"Erro de encoding '{encoding}' em '{file_path}', tentando 'latin-1'")
        try:
            with open(file_path, 'r', encoding='latin-1') as f:
                content = f.read()
            log.info(f"Arquivo carregado com encoding alternativo")
            return content
        except Exception as e2:
            log.error(f"Erro ao ler arquivo com encoding alternativo: {e2}")
            return None
    
    except Exception as e:
        log.error(f"Erro ao carregar arquivo de texto '{file_path}': {e}")
        return None


def load_list_from_file(file_path: str, encoding: str = 'utf-8', 
                        strip: bool = True, skip_empty: bool = True) -> List[str]:
    """
    Carrega lista de strings de arquivo (uma por linha)
    
    Args:
        file_path: Caminho do arquivo
        encoding: Codificação
        strip: Remove espaços em branco
        skip_empty: Ignora linhas vazias
        
    Returns:
        Lista de strings
    """
    if not file_path or not isinstance(file_path, str) or file_path.strip() == '':
        log.warning("Caminho de arquivo vazio fornecido para load_list_from_file")
        return []
    
    file_path = file_path.strip()
    
    if not os.path.exists(file_path):
        log.error(f"Arquivo não encontrado: '{file_path}'")
        return []
    
    try:
        with open(file_path, 'r', encoding=encoding) as f:
            lines = f.readlines()
        
        if strip:
            lines = [line.strip() for line in lines]
        
        if skip_empty:
            lines = [line for line in lines if line]
        
        log.info(f"Carregadas {len(lines)} linhas de '{file_path}'")
        return lines
        
    except Exception as e:
        log.error(f"Erro ao carregar lista de '{file_path}': {e}")
        return []


def validate_config_files(config_dir: Union[str, Path]) -> Dict[str, bool]:
    """
    Valida existência e conteúdo dos arquivos de configuração
    
    Args:
        config_dir: Diretório de configurações
        
    Returns:
        Dict com status de cada arquivo
    """
    if isinstance(config_dir, str):
        config_dir = Path(config_dir)
    
    config_files = {
        'names.json': False,
        'themes.json': False,
        'date_config.json': False,
        'places.txt': False,
        'persons.json': False
    }
    
    for filename in config_files.keys():
        file_path = config_dir / filename
        
        if not file_path.exists():
            log.warning(f"Arquivo de configuração não encontrado: {filename}")
            continue
        
        try:
            if file_path.stat().st_size == 0:
                log.warning(f"Arquivo de configuração vazio: {filename}")
                continue
        except OSError:
            log.warning(f"Erro ao verificar tamanho de: {filename}")
            continue
        
        # Tenta carregar para validar
        if filename.endswith('.json'):
            data = load_json_data(str(file_path))
            config_files[filename] = data is not None and data != {} and data != []
        else:
            content = load_text_file(str(file_path))
            config_files[filename] = content is not None and content.strip() != ''
    
    return config_files


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
        
        print("\n--- Testando caminho vazio ---")
        result = load_json_data("")
        assert result is None
        print("✓ Caminho vazio tratado corretamente")
        
        print("\n--- Testando validate_config_files ---")
        status = validate_config_files("./data")
        print(f"Status dos arquivos: {status}")
        
        print("\n✅ Todos os testes passaram!")

    finally:
        if os.path.exists(test_names_path):
            os.remove(test_names_path)
        if os.path.exists(test_themes_path):
            os.remove(test_themes_path)
