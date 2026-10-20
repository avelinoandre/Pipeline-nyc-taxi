# NYC Taxi Data Engineering Pipeline

Projeto de portfolio de Engenharia de Dados com dados de viagens NYC Taxi do
[Kaggle](https://www.kaggle.com/datasets/neilclack/nyc-taxi-trip-data-google-public-data).
As transformacoes usam PySpark em modo local e persistem as camadas Silver e Gold
em Parquet.

## Arquitetura

```text
Kaggle -> Bronze (CSV) -> PySpark -> Silver (Parquet)
       -> PySpark -> Gold (Parquet) -> PostgreSQL -> BI/Analytics
```

Bronze, Silver e Gold estao implementadas. O PostgreSQL local ja pode ser
iniciado com Docker Compose, e a estrutura das quatro tabelas esta definida em
SQL. A carga da Gold no banco e a proxima etapa; o Airflow sera adicionado depois
dos scripts individuais.

## Preparacao e execucao

Execute os comandos a partir da raiz do repositorio. E necessario ter Python 3.10+
e Java compativel com a versao instalada do PySpark.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Para o download, configure `KAGGLE_API_TOKEN` no arquivo local `.env`. Credenciais,
ambiente virtual e arquivos das camadas de dados nao devem ser versionados.

```bash
python src/ingestion/download_dataset.py
python src/transformations/bronze_to_silver.py
python src/transformations/silver_to_gold.py
```

As escritas usam `overwrite` para permitir reexecucoes locais. Cada tabela e um
diretorio com arquivos `part-*.parquet`, e nao um arquivo unico. A Gold valida todas
as tabelas antes de escrever e valida novamente os Parquets relidos. A substituicao
das quatro tabelas e sequencial; se a execucao falhar durante a escrita, execute
novamente antes de consumir a camada.

## Bronze e Silver

Entradas em `data/bronze/`:

- `taxi_trip_data.csv`: fonte de viagens da pipeline.
- `taxi_zone_geo.csv`: referencia de zonas.
- `original_cleaned_nyc_taxi_data_2018.csv`: referencia para sanity checks, sem ser entrada das transformacoes.

A Silver em `data/silver/taxi_trips` converte os horarios para timestamps, remove
duplicatas de linha completa e filtra distancia e duracao menores ou iguais a zero.
A duracao em minutos e `(dropoff_em_segundos - pickup_em_segundos) / 60`.
A regra de rollover remove apenas a combinacao de diferenca de um dia entre as
datas com duracao entre 1.400 e 1.450 minutos. Outros casos longos sao preservados.
A validacao rejeita dataset vazio, distancia ou duracao nulas/nao positivas e
duracoes inconsistentes com os timestamps, antes da escrita e apos a releitura.

## Gold: modelo dimensional

O grao de `fact_trips` e **uma linha por viagem da Silver**. A Gold nao realiza uma
nova limpeza nem descarta viagens sem referencia em uma dimensao.

| Tabela | Chave | Conteudo |
| --- | --- | --- |
| `fact_trips` | `trip_id` | Medidas e atributos da Silver, chaves de pagamento, zonas e datas |
| `dim_payment_type` | `payment_type` | Descricao dos pagamentos e linha desconhecida |
| `dim_zone` | `zone_id` | Nome da zona, borough e linha desconhecida |
| `dim_date` | `date_id` | Data, ano, trimestre, mes, dia, dia da semana, semana e indicador de fim de semana |

Os diretorios sao `data/gold/fact_trips`, `data/gold/dim_payment_type`,
`data/gold/dim_zone` e `data/gold/dim_date`.

### Chaves e medidas

- `trip_id` e um hash SHA-256 da linha completa da Silver, com colunas ordenadas e serializacao de timestamps em UTC somente para gerar o hash. Nao depende da ordem das linhas ou das particoes. Alterar o conteudo ou o schema da Silver pode alterar o identificador.
- `payment_type` referencia `dim_payment_type`; `source_payment_type` preserva o codigo original, inclusive nulos.
- `pickup_zone_id` e `dropoff_zone_id` referenciam a mesma `dim_zone`. Os campos originais `pickup_location_id` e `dropoff_location_id` sao preservados.
- `pickup_date_id` e `dropoff_date_id` referenciam a mesma `dim_date`, no formato inteiro `yyyyMMdd`.
- As medidas, como `trip_distance`, `trip_duration_minutes`, `fare_amount`, `tip_amount` e `total_amount`, preservam os valores e tipos da Silver.
- `vendor_id`, `rate_code` e `store_and_fwd_flag` permanecem como atributos na fato, inclusive codigos ainda nao mapeados.

### Referencias desconhecidas e zonas repetidas

As dimensoes de pagamento e zona incluem a chave `-1`. Codigos sem correspondencia
e valores nulos sao associados a essa chave na fato, sem apagar os valores de origem.
O `left_anti` mostra os pagamentos da Silver sem correspondencia antes da conversao.

Os pagamentos 1 a 6 seguem o
[dicionario oficial da TLC](https://www.nyc.gov/assets/tlc/downloads/pdf/data_dictionary_trip_records_yellow.pdf):
Credit Card, Cash, No Charge, Dispute, Unknown e Voided Trip. O mapeamento local se
concentra nesses codigos; outros valores usam `-1`, preservando o codigo de origem.

Na referencia local, as repeticoes de `zone_id` 56 e 103 diferem nas geometrias,
mas compartilham nome e borough. A dimensao seleciona apenas os atributos
analiticos e remove linhas identicas dessa projecao. As geometrias continuam na
Bronze. Se um mesmo ID aparecer com nomes ou bairros conflitantes, a validacao
interrompe a pipeline, sem escolher uma linha arbitrariamente. IDs ausentes da
referencia, inclusive 57, 104 e 105, recebem a mesma politica de desconhecidos.

### Datas e validacoes

`dim_date` contem somente datas presentes no pickup ou dropoff da Silver, sem
preencher dias sem viagens. `day_of_week` segue o Spark: 1 = domingo, 7 = sabado.
A Gold mantem o fuso padrao da sessao, como a ingestao Silver; execute ambas no
mesmo ambiente para manter a interpretacao das datas. O fuso em uso e mostrado no
inicio da execucao. Nao ha conversao dos horarios de origem nem correcao de horario
de verao. Somente a serializacao usada pelo hash fixa UTC, sem mudar as colunas.

As validacoes verificam dimensoes nao vazias, chaves unicas e nao nulas, quantidade
de fatos igual a Silver, `trip_id` unico e nao nulo e integridade das cinco chaves
estrangeiras. A verificacao de unicidade da fato redistribui somente os IDs em
64 particoes para limitar a quantidade de valores distintos por tarefa no Spark
local. As mesmas verificacoes sao aplicadas aos Parquets gravados.

## PostgreSQL local com Docker Compose

O arquivo `docker-compose.yml` descreve somente o servico PostgreSQL deste projeto.
Ele usa a imagem oficial `postgres:16`, sem precisar criar um Dockerfile.
Essa imagem ja estava disponivel no Docker local; usa-la evitou alterar a rede
ou reiniciar o Docker de outros projetos apos uma falha de IPv6 no download.
O projeto Compose se chama `nyc-taxi`, separado de outros projetos Docker.

As credenciais ficam em `.env.postgres`, ignorado pelo Git. O `.env` usado pelo
Kaggle nao e passado para o container. Na configuracao inicial deste ambiente,
foi gerada uma senha local aleatoria, sem registra-la no README ou no terminal.
Em outro ambiente, crie sua configuracao e escolha uma senha antes de iniciar:

```bash
cp .env.postgres.example .env.postgres
chmod 600 .env.postgres
# Edite POSTGRES_PASSWORD em .env.postgres antes de iniciar.
```

Execute a partir da raiz do repositorio, no WSL com Docker disponivel:

```bash
docker compose config --quiet
docker compose up -d --wait postgres
docker compose ps
```

O Compose baixa a imagem quando necessario, cria a rede e o volume deste projeto,
e inicia o container. `-d` deixa o processo em segundo plano; `--wait` espera o
healthcheck indicar que o PostgreSQL esta pronto para receber conexoes.

| Configuracao | Valor |
| --- | --- |
| Host para programas executados no WSL | `127.0.0.1` |
| Porta publicada | `5432` |
| Banco inicial | `nyc_taxi` |
| Usuario local de desenvolvimento | `nyc_taxi` |
| Senha | Definida somente em `.env.postgres` |
| Volume persistente | `nyc-taxi_postgres_data` |

A porta e publicada somente no localhost. A imagem cria o usuario e o banco
indicados por `POSTGRES_USER` e `POSTGRES_DB` na primeira inicializacao.
Esse usuario e administrador para desenvolvimento local.

O volume e montado em `/var/lib/postgresql/data`, conforme o layout da imagem
PostgreSQL 16. Ele preserva os arquivos do banco se o container for recriado.
As variaveis de inicializacao nao alteram um banco ja existente: mudar a senha
no arquivo de ambiente, por si so, nao muda a senha armazenada no PostgreSQL.

Para entrar no cliente SQL dentro do container:

```bash
docker compose exec postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
```

Dentro do `psql`, execute `SELECT current_database(), current_user;` e use
`\q` para sair. O acesso local por socket dentro do container dispensa a senha;
as conexoes TCP de outros programas usam a senha de `.env.postgres`.

Comandos uteis:

```bash
docker compose logs --tail=50 postgres
docker compose stop postgres
docker compose start --wait postgres
docker compose down
```

`stop` para o servico; `start` retoma o container existente; `down` remove o
container e a rede do projeto, mas mantem o volume nomeado. Nao adicione `-v`
ao `down` se quiser preservar os dados.

O Compose prepara somente o servidor, sem executar SQL automaticamente na
inicializacao. A estrutura e criada separadamente pelo script SQL abaixo.

Referencias: [imagem oficial PostgreSQL](https://hub.docker.com/_/postgres),
[servicos Compose](https://docs.docker.com/reference/compose-file/services/) e
[volumes Compose](https://docs.docker.com/reference/compose-file/volumes/).

### Acesso grafico com pgAdmin desktop

O pgAdmin desktop pode ser instalado no Windows pelo instalador oficial:

```powershell
winget install --id PostgreSQL.pgAdmin --exact --source winget --scope user
```

O PostgreSQL continua no Docker/WSL; o pgAdmin apenas se conecta a ele.
O arquivo `pgadmin-servers.json` contem o cadastro do servidor NYC Taxi,
sem senhas. Pode ser importado pelo menu Tools > Import/Export Servers.
Mantenha os servidores existentes ao importar.

A conexao usa host `127.0.0.1`, porta `5432`, usuario `nyc_taxi` e banco
`nyc_taxi`. Informe a senha de `.env.postgres` quando solicitada.

Na arvore do pgAdmin, expanda o servidor NYC Taxi e depois Databases > nyc_taxi.
Clique com o botao direito no banco e abra Query Tool para escrever SQL.
As tabelas do projeto aparecem em Schemas > public > Tables depois da execucao
de `sql/create_tables.sql`. Elas permanecem vazias ate a carga da Gold.

Referencia: [importacao de servidores pgAdmin](https://www.pgadmin.org/docs/pgadmin4/latest/import_export_servers.html).

## Estrutura das tabelas no PostgreSQL

O arquivo `sql/create_tables.sql` cria as mesmas quatro tabelas da Gold no schema
`public`. Ele e a definicao versionada da estrutura do banco; o pgAdmin pode ser
usado para abrir, executar e inspecionar esse mesmo arquivo.

Para executar pelo terminal WSL, na raiz do projeto:

```bash
docker compose exec -T postgres sh -c 'psql -X -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1' < sql/create_tables.sql
```

No pgAdmin, abra o Query Tool do banco `nyc_taxi`, use Open File para abrir
`sql/create_tables.sql` e execute o script completo. Depois atualize
Schemas > public > Tables para visualizar as quatro tabelas.

Decisoes do modelo:

- As dimensoes sao criadas antes da fato, pois suas chaves sao referenciadas por ela.
- Os IDs da Gold sao preservados: nao ha `SERIAL` ou contador para substitui-los.
- A fato tem cinco chaves estrangeiras: pagamento, zona de pickup, zona de dropoff, data de pickup e data de dropoff.
- `PRIMARY KEY` impede IDs repetidos e nulos. `NOT NULL` exige os campos essenciais.
- `CHECK` protege distancia e duracao positivas, o tamanho do hash e intervalos dos atributos de calendario.
- Os codigos originais de pagamento e localizacao continuam opcionais, preservando os nulos da origem. As chaves analiticas usam a linha `-1` da Gold quando necessario; essa linha sera inserida na carga das dimensoes.
- Valores monetarios usam `NUMERIC` sem escala fixa para evitar arredondamento imposto pelo schema. A origem Parquet continua sendo double; a mudanca de tipo nao recupera precisao ja perdida na origem. Valores negativos nao sao excluidos.
- Distancia e duracao usam `DOUBLE PRECISION`. Os timestamps nao tem conversao de fuso nesta etapa; a interpretacao deles devera ser consistente na carga.

`BEGIN` e `COMMIT` agrupam a criacao em uma transacao. `IF NOT EXISTS` permite
reexecutar a criacao sem apagar tabelas ou registros. Ele nao compara nem atualiza
uma tabela existente: mudancas futuras de estrutura devem ser feitas em scripts
de migracao, sem usar `DROP TABLE` para recriar um banco com dados.

O arquivo `sql/validate_tables.sql` contem consultas para inspecionar tabelas,
colunas, constraints e contagens. Pode ser executado no pgAdmin ou pelo mesmo
comando anterior, trocando o arquivo de entrada.

Criar a estrutura nao carrega os Parquets: as quatro tabelas ficam vazias nesta
etapa. A proxima implementacao sera a carga automatizada, primeiro das dimensoes
e depois da fato, seguida da comparacao das contagens com a Gold.

## Testes

```bash
python -m unittest discover -s tests -v
```

Os testes cobrem o calculo da duracao, filtros e limites de rollover, validacoes da
Silver, zonas repetidas/conflitantes, codigos desconhecidos/nulos, estabilidade dos
IDs, integridade referencial e escrita/releitura com `overwrite`.

## EDA e proximas etapas

O notebook atual e `notebooks/01_exploratory_analysis.ipynb`. A EDA trabalha com
amostra de 100.000 linhas (`seed=42`); seus resultados nao representam contagens
do dataset completo. Limites estatisticos servem para monitoramento, sem remocao
automatica de outliers.

Proximas etapas: carregar as tabelas Gold no PostgreSQL, ampliar metricas de
auditoria e, depois, introduzir Airflow para orquestracao.
