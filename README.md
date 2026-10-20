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

Bronze, Silver e Gold estao implementadas. PostgreSQL, Docker e Airflow sao etapas
futuras. A orquestracao sera adicionada depois dos scripts individuais.

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
auditoria e, depois, introduzir Docker e Airflow.
