# Oxossi Indexer - Versão 2.0

O Oxossi Indexer é uma ferramenta para processar documentos históricos (PDFs e dados JSON) e extrair informações estruturadas como datas, nomes, temas e lugares.

## ✨ Novas Funcionalidades v2.0

### 🔄 Processamento de JSON
- **Processa arquivos JSON** com dados históricos
- **Processa diretórios de PDFs** (requer PyMuPDF)
- **Suporte híbrido**: Funciona com ou sem dependências externas

### 💾 Sistema de Backup Automático
- **Backup incremental**: Salva progresso a cada 5 arquivos processados
- **Recuperação automática**: Resume processamento após falhas
- **Backup final**: Cria cópia completa dos resultados
- **Estrutura de backups**:
  ```
  backups/
  ├── progress_YYYYMMDD_HHMMSS.json      # Progresso atual
  ├── results_YYYYMMDD_HHMMSS.json       # Resultados parciais
  └── final_results_YYYYMMDD_HHMMSS.json # Backup final completo
  ```

### 📊 Saída JSON Estruturada
- **Relatório completo** com estatísticas de processamento
- **Metadata detalhada** por documento
- **Informações de sessão** para rastreamento
- **Compatibilidade Elasticsearch** opcional

### 🛡️ Tolerância a Falhas
- **Processamento resiliente**: Continua mesmo com erros individuais
- **Log detalhado**: Rastreia sucessos e falhas
- **Resumo de sessão**: Flag `--no-resume` para recomeçar do zero

## 🚀 Instalação e Uso

### Instalação Básica (apenas JSON)
```bash
# Funciona sem dependências externas para processamento JSON
python3 src/indexer/run_indexer.py dados.json
```

### Instalação Completa (PDFs + JSON)
```bash
# Para processamento de PDFs, instale:
pip install PyMuPDF

# Para análise completa, certifique-se que todos os extractors estão funcionando
```

### Uso Básico

```bash
# Processar arquivo JSON
python3 src/indexer/run_indexer.py dados.json --output resultados.json

# Processar diretório de PDFs
python3 src/indexer/run_indexer.py ./pdfs --output resultados.json

# Exportar para Elasticsearch
python3 src/indexer/run_indexer.py dados.json --elasticsearch-format --output resultados.json

# Recomeçar do zero (ignora progresso anterior)
python3 src/indexer/run_indexer.py ./pdfs --no-resume --output resultados.json
```

### Parâmetros da Linha de Comando

```
usage: run_indexer.py [-h] [--config-dir CONFIG_DIR] [--backup-dir BACKUP_DIR] 
                      [--output OUTPUT] [--elasticsearch-format] [--no-resume] input

Argumentos:
  input                        Diretório com PDFs ou arquivo JSON para processar

Opções:
  --config-dir, -c CONFIG_DIR  Diretório com arquivos de configuração (default: ./data)
  --backup-dir, -b BACKUP_DIR  Diretório para salvar backups (default: ./backups)
  --output, -o OUTPUT          Arquivo de saída JSON (opcional)
  --elasticsearch-format       Exporta formato otimizado para Elasticsearch
  --no-resume                  Não resume processamento anterior
```

## 📁 Estrutura de Configuração

### Diretório de Configuração (`./data/`)
```
data/
├── names.json          # Configuração de nomes
├── themes.json         # Configuração de temas
├── date_config.json    # Configuração de datas
└── places.txt          # Lista de lugares
```

### Exemplo de Configuração de Temas (`themes.json`)
```json
{
  "história": ["história", "histórico", "colonial", "período"],
  "economia": ["economia", "econômico", "comércio", "mineração"],
  "sociedade": ["sociedade", "social", "população", "família"],
  "política": ["política", "político", "governo", "administração"]
}
```

### Exemplo de Configuração de Datas (`date_config.json`)
```json
{
  "century_map": {
    "XVI": 1500, "XVII": 1600, "XVIII": 1700, "XIX": 1800
  },
  "part_map": {
    "início": [0, 33], "meio": [33, 66], "final": [66, 100]
  },
  "regex_patterns": {
    "year": "(?P<year>\\b(?:1[5-8]\\d{2})\\b)",
    "textual_phrase": "século\\s+(?P<century>XVI|XVII|XVIII|XIX)"
  }
}
```

## 📊 Estrutura de Saída JSON

### Relatório Principal
```json
{
  "status": "Sucesso",
  "message": "Processamento concluído. 3 documentos processados.",
  "results": {
    "indexing_session": {
      "session_id": "20251009_212605",
      "completed_at": "2025-10-09T21:26:05.253198",
      "total_processed": 3,
      "total_failed": 0,
      "total_results": 3,
      "success_rate": 100.0
    },
    "processed_files": ["doc1.pdf", "doc2.pdf"],
    "failed_files": [],
    "results": [...],  // Documentos processados
    "statistics": {
      "total_documents": 3,
      "total_word_count": 1450,
      "documents_with_dates": 2,
      "documents_with_names": 1,
      "documents_with_themes": 3
    }
  }
}
```

### Documento Processado (PDF)
```json
{
  "document_id": "historia_colonial_001",
  "source_type": "pdf",
  "filename": "historia_colonial.pdf",
  "processed_at": "2025-10-09T21:26:05.253144",
  "text": "Texto extraído do PDF...",
  "word_count": 1250,
  "character_count": 8500,
  "names_analysis": {
    "potential_names_found": ["João Silva", "Maria Santos"],
    "total_names": 2
  },
  "date_analysis": {
    "combined_representative_years": [1650, 1687, 1725],
    "mean": 1687.3,
    "minimum": 1650,
    "maximum": 1725
  },
  "temporal_analysis": {
    "media_anos": 1687,
    "desvio_medio_absoluto": 25,
    "consistencia_temporal": 0.7,
    "seculos_mencionados": ["século XVII", "século XVIII"]
  },
  "themes_analysis": {
    "theme_counts": {"história": 8, "economia": 5},
    "top_theme": "história",
    "total_keywords_found": 13
  }
}
```

### Documento Processado (JSON)
```json
{
  "document_id": "doc_historico_001",
  "source_type": "json_data",
  "processed_at": "2025-10-09T21:26:05.253144",
  "original_data": {...},  // Dados originais preservados
  "analyzed_text": "Texto analisado...",
  "word_count": 145,
  // Análises aplicadas se configurações disponíveis
}
```

## 🔍 Compatibilidade Elasticsearch

### Export Automático
Quando usar `--elasticsearch-format`, o indexer cria:
- **Arquivo principal**: `results.json` (formato padrão)
- **Arquivo Elasticsearch**: `results_elasticsearch.json` (formato otimizado)

### Formato Elasticsearch Otimizado
```json
{
  "document_id": "historia_colonial_001",
  "document_type": "pdf",
  "title": "História Colonial Brasileira",
  "content": "Resumo do conteúdo...",
  "full_content": "Texto completo...",
  "names": ["João Silva", "Maria Santos"],
  "dates": {
    "years": [1650, 1687, 1725],
    "date_range": {"start": 1650, "end": 1725},
    "centuries": ["século XVII"]
  },
  "themes": {
    "primary_theme": "história",
    "all_themes": ["história", "economia"],
    "theme_scores": {"história": 8, "economia": 5}
  },
  "metadata": {
    "processed_at": "2025-10-09T21:26:05Z",
    "word_count": 1250,
    "has_dates": true,
    "has_names": true
  },
  "searchable_text": "Campo combinado para busca..."
}
```

### Comandos Elasticsearch
```bash
# Criar índice
curl -X PUT 'localhost:9200/oxossi_documents' \
  -H 'Content-Type: application/json' \
  -d @mapping.json

# Import bulk
curl -X POST 'localhost:9200/_bulk' \
  -H 'Content-Type: application/json' \
  --data-binary @results_elasticsearch.json

# Busca exemplo
curl -X GET 'localhost:9200/oxossi_documents/_search?pretty' \
  -d '{"query": {"match": {"searchable_text": "colonial"}}}'
```

## 🛠️ Desenvolvimento

### Estrutura do Projeto
```
src/
├── indexer/
│   └── run_indexer.py          # Script principal
├── extractors/                 # Módulos de extração
├── utils/
│   ├── output_utils.py         # Utilitários de saída
│   └── elasticsearch_formatter.py  # Formatador ES
└── data/                       # Configurações
```

### Classes Principais

#### `IndexerBackupManager`
- Gerencia backups e recuperação
- Salva progresso incremental
- Permite resumir processamento

#### `OxossiIndexer`
- Classe principal do indexer
- Processa PDFs e dados JSON
- Integra todos os extractors
- Gera relatórios estatísticos

### Extensibilidade
O indexer é modular - extractors individuais podem falhar sem quebrar o processamento geral. Cada extractor é verificado na inicialização e usado apenas se disponível.

## 📈 Monitoramento

### Logs
- **INFO**: Progresso normal e sucessos
- **WARNING**: Extractors não disponíveis, arquivos pulados
- **ERROR**: Falhas de processamento individual
- **CRITICAL**: Falhas que impedem continuação

### Arquivos de Backup
- Verificar `backups/` para progresso e recuperação
- Arquivos nomeados com timestamp para rastreamento
- Backup final sempre criado ao completar

### Estatísticas
Cada execução gera estatísticas completas:
- Taxa de sucesso
- Contagem de palavras total
- Documentos com cada tipo de análise
- Tempo de processamento

---

## 💡 Exemplos de Uso

### Cenário 1: Processamento de Arquivo JSON Simples
```bash
# Criar dados de teste
echo '[{"_id": "doc1", "title": "Teste", "content": "Brasil colonial século XVII"}]' > test.json

# Processar
python3 src/indexer/run_indexer.py test.json --output results.json
```

### Cenário 2: Processamento com Recovery
```bash
# Primeira execução (pode falhar)
python3 src/indexer/run_indexer.py ./pdfs --output results.json

# Resume automaticamente do ponto de parada
python3 src/indexer/run_indexer.py ./pdfs --output results.json
```

### Cenário 3: Export Completo para Elasticsearch
```bash
# Processamento completo com export ES
python3 src/indexer/run_indexer.py dados.json \
  --elasticsearch-format \
  --output results.json \
  --backup-dir ./meus_backups
```

O Oxossi Indexer v2.0 oferece uma solução robusta e flexível para processamento de documentos históricos com recuperação automática e compatibilidade com sistemas de busca modernos.