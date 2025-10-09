# Oxossi PDF Search

Este projeto oferece uma API para busca em grandes coleções de PDFs (testado com 18.000+ arquivos) e dados scraped.

## Características Principais

- **Indexação massiva de PDFs**: processamento eficiente para grandes coleções
- **Análise de conteúdo**: extração de datas, nomes, lugares, referências e temas
- **Busca unificada**: recuperação de resultados tanto de PDFs quanto de dados scraped
- **API RESTful**: endpoints organizados para consulta e recuperação de documentos
- **Deploy automatizado**: script para inicialização completa do ambiente
- **MongoDB nativo**: sistema agora utiliza MongoDB sem dependências de Prisma

## Requisitos

- Docker e Docker Compose
- 8GB+ RAM para grandes coleções
- Espaço em disco para armazenar PDFs e dados MongoDB
- Python 3.8+ (para execução local)

## Deploy para SSH (Servidor Remoto)

Para implantar o sistema em um servidor via SSH, use o novo script `deploy_ssh.sh`:

```bash
chmod +x deploy_ssh.sh
./deploy_ssh.sh /caminho/absoluto/para/pdfs
```

O script irá:
1. Configurar os diretórios necessários
2. Verificar dependências (Docker, Docker Compose)
3. Criar arquivo de configuração .env
4. Testar a conexão com MongoDB
5. Inicializar todos os serviços via Docker Compose
6. Importar dados scraped (se disponíveis)
7. Iniciar o indexador e o servidor web

## Deploy Otimizado

Para evitar a duplicação dos arquivos PDF (29GB+) em múltiplos containers, utilize o script de deploy otimizado:

```bash
chmod +x deploy_optimized.sh
./deploy_optimized.sh
```

O script solicitará o caminho absoluto para o diretório que contém os PDFs e fará o deploy usando volumes Docker para compartilhar os arquivos sem duplicação.

## Logs e Resolução de Problemas

### Sistema de Logs

O sistema grava logs automaticamente em:
- `logs/oxossi_api.log` - Logs da API FastAPI
- `logs/pdf_indexer_debug.log` - Logs do indexador de PDFs

Se ocorrerem problemas de permissões com os logs:

```bash
# Dê permissões ao script e execute
chmod +x fix_permissions.sh
./fix_permissions.sh
```

Para testar se os logs estão funcionando corretamente:

```bash
python test_logging.py
```

### Diagnóstico de Problemas

Se encontrar problemas com permissões de arquivos ou logs, você pode receber erros como:

```
Could not set up file logging in any location. Logs will only be available on console output.
```

Isso geralmente indica problemas de permissão. Execute o script `fix_permissions.sh` e reinicie os containers se estiver usando Docker:

```bash
./fix_permissions.sh
docker-compose down
docker-compose up -d
```

## Testando a Conexão com MongoDB

Para verificar se o MongoDB está funcionando corretamente, execute:

```bash
python3 test_mongodb_connection.py --host localhost
```

Esse script irá testar:
- Conexão com o servidor MongoDB
- Acesso ao banco de dados e coleção
- Operações básicas (inserção, consulta e exclusão)
- Verificação de índices

```bash
chmod +x deploy_automatic.sh
./deploy_automatic.sh
```

O script realiza automaticamente:

1. Criação dos diretórios necessários
2. Configuração do ambiente
3. Inicialização de containers Docker
4. Indexação de PDFs e dados scraped
5. Verificação da API

## Estrutura do Projeto

## Diretórios Principais
- `src/`: Contém o código-fonte principal.
  - `indexer/`: Código relacionado ao indexador de PDFs.
  - `api/`: Código relacionado à API (FastAPI).
  - `utils/`: Funções utilitárias.
- `data/`: Arquivos de configuração e dados estáticos.
- `tests/`: Testes automatizados.
- `scripts/`: Scripts auxiliares (deploy, configuração, etc.).

## Como Usar
1. **Indexar PDFs:**
   ```bash
   python src/indexer/run_indexer.py
   ```
2. **Iniciar a API:**
   ```bash
   uvicorn src.api.app:app --reload
   ```

## Uso da API

A API estará disponível em `http://localhost:8000/back-end-oxossi-py/`

### Endpoints Principais

#### Busca Simples
```
GET /back-end-oxossi-py/search/simple?query=sua_busca&include_scraped=true&include_pdfs=true
```

#### Busca Avançada
```
GET /back-end-oxossi-py/search?termo=sua_busca&autor=nome_autor&data=periodo&tema=assunto
```

#### Documentação Completa
```
http://localhost:8000/back-end-oxossi-py/docs
```

## Adicionando Dados

### PDFs
Coloque seus arquivos PDF no diretório `/pdfs/` e execute o script de deploy novamente.

### Dados Scraped
Coloque um arquivo chamado `scraped_items.json` no diretório raiz, contendo um array de objetos com pelo menos os campos:
- `title`: Título do item
- `content` ou `description`: Conteúdo textual
- `author`: Autor (opcional)
- `date`: Data (opcional)
- `url`: URL de origem (opcional)

## Monitoramento

- **Logs da API**: `docker logs -f oxossi_api_web`
- **MongoDB Express**: http://localhost:8081/mongo-express
- **Logs de Indexação**: `docker logs -f oxossi_indexer`

## Resolução de Problemas

1. **Erro de conexão com MongoDB**:
   - Verifique se o container está rodando: `docker ps`
   - Reinicie o sistema: `docker compose down && docker compose up -d`
   
2. **Problemas com volumes de PDFs**:
   - Verifique se o diretório de PDFs está corretamente configurado: `echo $PDF_DIR`
   - Reconfigure o volume: `export PDF_DIR=/caminho/absoluto/pdfs && docker compose down && docker compose up -d`

2. **PDFs não aparecem nos resultados**:
   - Verifique os logs do indexador: `docker logs oxossi_indexer`
   - Execute manualmente a indexação: `docker-compose run --rm indexer python massive_pdf_indexer.py /app/pdfs --verbose`

3. **API lenta ou travando**:
   - Aumente os recursos do Docker (RAM/CPU)
   - Otimize os índices MongoDB: `docker-compose exec mongo mongo -u lhs -p batata123 --authenticationDatabase admin oxossi_db --eval "db.pdf_documents.reIndex()"`

4. **Scraped items não aparecem na busca**:
   - Verifique se o arquivo `scraped_items.json` está corretamente formado
   - Execute apenas a importação de scraped items: 
     ```
     docker-compose run --rm indexer python -c "from massive_pdf_indexer import MongoDBIndexer, import_scraped_items; indexer = MongoDBIndexer(host='mongo'); indexer.connect(); import_scraped_items(indexer)"
     ```

## Solução de Problemas

### Problemas de Permissão de Logs

Se você encontrar erros de permissão ao gravar logs:
```
Could not set up file logging: [Errno 13] Permission denied: '/tmp/pdf_indexer_debug.log'
```

Solução:
```bash
# No host
mkdir -p logs
chmod 777 logs
# No docker-compose.yaml, confirme que há um volume mapeando /tmp para ./logs
```

### Falha na Conexão com MongoDB

Se o MongoDB não estiver acessível:
1. Verifique se o serviço está rodando: `docker-compose ps`
2. Verifique os logs: `docker-compose logs mongo`
3. Teste a conexão: `python test_mongodb_connection.py --host mongo`
4. Verifique as credenciais no arquivo .env

### Performance de Indexação Lenta

Para melhorar a performance da indexação:
1. Aumente o número de workers: `--parallel 12`
2. Reduza o batch size para economizar memória: `--batch-size 50`
3. Ative a otimização de memória: `--memory-optimization`
4. Use `--skip-existing` para pular documentos já indexados

## Notas Importantes

- Os PDFs são processados diretamente do servidor, sem necessidade de download.
- O sistema foi otimizado para lidar com coleções muito grandes (18.000+ PDFs).
- A API usa o padrão Clean Architecture, separando rotas, serviços e modelos.
- Todas as buscas são unificadas, retornando tanto PDFs quanto scraped_items.

## Licença

Este projeto é licenciado sob MIT License.
