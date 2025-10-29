import json
import sys

def converter_para_ndjson(input_filename, output_filename, index_name):
    """
    Lê um arquivo contendo JSONs concatenados, separa-os,
    e os converte para o formato NDJSON válido para o Elasticsearch Bulk API.
    """
    print(f"--- Iniciando a conversão de '{input_filename}' para NDJSON ---")

    # Passo 1: Ler o arquivo de entrada e separar os JSONs concatenados.
    # Esta é a etapa crucial que corrige os documentos "grudados".
    try:
        with open(input_filename, 'r', encoding='utf-8') as f:
            # Lê o conteúdo inteiro (pode ser uma linha gigante)
            content = f.read()
            # Substitui '}{' por '}\n{', efetivamente colocando cada JSON em sua própria linha
            separated_docs_str = content.replace('}{', '}\n{')
            # Divide a string em uma lista de documentos individuais
            documents_str_list = separated_docs_str.split('\n')
        print(f"[PASSO 1/2] Sucesso: {len(documents_str_list)} documentos JSON foram separados.")
    except FileNotFoundError:
        print(f"ERRO: O arquivo de entrada '{input_filename}' não foi encontrado.")
        return
    except Exception as e:
        print(f"ERRO: Falha ao ler ou separar o arquivo de entrada. Detalhes: {e}")
        return

    # Passo 2: Iterar sobre cada documento, criar o par de ação/dados e salvar no arquivo de saída.
    success_count = 0
    error_count = 0

    with open(output_filename, 'w', encoding='utf-8') as outfile:
        for i, doc_str in enumerate(documents_str_list):
            line_num = i + 1
            # Ignora linhas vazias que podem ter sido criadas pela separação
            if not doc_str.strip():
                continue

            try:
                # Tenta carregar a string da linha como um objeto JSON
                data = json.loads(doc_str)

                # Pega o ID do documento. Usamos 'id_original' como você definiu.
                doc_id = data.get('id_original')
                if not doc_id:
                    print(f"  -> AVISO na linha {line_num}: Documento sem campo 'id_original'. Pulando.")
                    error_count += 1
                    continue

                # Cria o dicionário da "ação" para o NDJSON
                action = {
                    "index": {
                        "_index": index_name,
                        "_id": str(doc_id) # Garante que o ID seja uma string
                    }
                }

                # Escreve a linha de ação e a linha de dados no arquivo de saída
                outfile.write(json.dumps(action, ensure_ascii=False) + '\n')
                outfile.write(json.dumps(data, ensure_ascii=False) + '\n')

                success_count += 1

            except json.JSONDecodeError:
                print(f"  -> ERRO na linha {line_num}: A linha não é um JSON válido e será ignorada.")
                error_count += 1
            except Exception as e:
                print(f"  -> ERRO inesperado na linha {line_num}: {e}")
                error_count += 1

    print(f"[PASSO 2/2] Sucesso: Arquivo '{output_filename}' foi gerado.")
    print("--- Resumo da Conversão ---")
    print(f"Documentos convertidos com sucesso: {success_count}")
    print(f"Documentos com erro (ignorados): {error_count}")

# --- Ponto de Entrada do Script ---
if __name__ == "__main__":
    # Verifica se os argumentos de linha de comando foram passados
    if len(sys.argv) != 3:
        print("ERRO: Uso incorreto.")
        print("Como usar: python3 corrigir_json.py <arquivo_de_entrada> <arquivo_de_saida>")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2]
    INDEX_NAME = "oxossi_docs_index" # O nome do seu índice

    converter_para_ndjson(input_file, output_file, INDEX_NAME)