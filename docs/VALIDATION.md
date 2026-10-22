# Registro de validacao da entrega local

Data de verificacao: 22/10/2026. Este registro descreve execucoes reais neste
ambiente, nao somente a definicao da DAG. O snapshot analitico e historico, de 2018.

## Execucao completa pelo Airflow

- DAG: `nyc_taxi_pipeline`.
- Execucao: `portfolio_validation_20261022_limited`.
- Disparo: manual pelo CLI, processado pelo scheduler e pelo LocalExecutor.
- Inicio: 22/10/2026 10:31:08 (America/Sao_Paulo).
- Fim: 22/10/2026 10:52:37 (America/Sao_Paulo).
- Estado final: **success**.

| Tarefa | Estado | Tentativa | Duracao (min) |
| --- | --- | ---: | ---: |
| `prepare_bronze` | success | 1 | 0.02 |
| `bronze_to_silver` | success | 1 | 4.92 |
| `silver_to_gold` | success | 1 | 3.46 |
| `create_postgres_schema` | success | 1 | 0.02 |
| `gold_to_postgres` | success | 1 | 11.45 |
| `validate_pipeline` | success | 1 | 1.53 |

O campo tentativa se refere a esta execucao. As tarefas foram sequenciais e
usaram os scripts da pipeline com o Python de `.venv`. A Bronze local foi
reutilizada, sem novo download do mesmo snapshot.

## Contagens e integridade

| Tabela Gold/PostgreSQL | Registros validados |
| --- | ---: |
| dim_payment_type | 7 |
| dim_zone | 261 |
| dim_date | 389 |
| fact_trips | 9.100.887 |

A Silver e a fato Gold possuem 9.100.887 viagens. As validacoes antes da escrita
e na releitura dos Parquets passaram. Foram verificadas chaves unicas e nao
nulas, igualdade com a Silver e as cinco referencias dimensionais. A carga COPY
confirmou a transacao depois de conferir contagens e datas.

A verificacao posterior ao COMMIT reconfirmou contagens Gold/PostgreSQL,
timestamps contra dim_date e as consultas analiticas. O catalogo do PostgreSQL
registrou quatro PKs e cinco FKs validadas. Nenhum teste foi usado para desabilitar
essas constraints durante a carga real.

| Recorte analitico de 2018 | Resultado |
| --- | ---: |
| Viagens | 9.100.757 |
| Dias com embarques | 365 |
| Embarques com zona desconhecida | 140.537 |
| Consultas analiticas executadas e reconciliadas | 6 |

O relatorio automatico desta execucao foi escrito em
`.airflow/validation/latest.json`, que permanece local e ignorado pelo Git.
Os horarios acima sao da execucao; nao indicam atualizacao da fonte externa.

## Ajuste encontrado no teste completo

A primeira execucao, `portfolio_validation_20261022`, falhou na Silver com
`java.lang.OutOfMemoryError: Java heap space`. O Spark estava usando todos os
nucleos locais com driver de 1 GB. A tentativa automatica seguinte foi encerrada
para aplicar o ajuste, sem iniciar as etapas seguintes.

As duas transformacoes passaram a aceitar `SPARK_MASTER`, mantendo o padrao
anterior quando a variavel nao e definida. A DAG fixa `local[2]`, driver de 1 GB
e `America/Sao_Paulo`. A API do Spark confirmou esses valores na reexecucao.
Nenhuma regra de limpeza, chave ou medida foi alterada por esse ajuste de recursos.
A execucao bem-sucedida documentada acima validou todo o fluxo com a configuracao
limitada. O historico de falha permanece no Airflow.

## Testes automatizados

```bash
RUN_POSTGRES_TESTS=1 SPARK_MASTER=local[1] .venv/bin/python -m unittest discover -s tests -v
RUN_AIRFLOW_TESTS=1 AIRFLOW_HOME="$PWD/.airflow" .venv-airflow/bin/python -m unittest discover -s tests -p test_airflow_dag.py -v
```

A suite principal descobriu 38 testes: **36 executados com sucesso e 2 ignorados**,
exclusivos do ambiente Airflow. Os **2 testes da DAG passaram** no ambiente
separado. Portanto, foram aprovados 38 testes distintos entre os dois ambientes.
Os logs locais estao em `.airflow/validation/tests-main.log` e `tests-airflow.log`.

A verificacao cobriu Silver, Gold, carga/reexecucao/rollback, consultas SQL,
interface Streamlit, cache, filtros, falhas de conexao, ingestao e dependencias da
DAG. Os testes PostgreSQL usam schemas isolados; nao substituem os dados `public`.
`pip check` passou nos dois ambientes, e o script de inicializacao passou por
`bash -n`. O diff foi conferido com `git diff --check`.

## Ambiente de referencia

- Ubuntu 22.04 no WSL2; Python 3.10; OpenJDK 21.
- PySpark 4.2.0 e Streamlit 1.65.0 no ambiente da pipeline.
- Airflow 3.3.1 com constraints oficiais, em `.venv-airflow`.
- PostgreSQL 16.15 (Debian 16.15-1.pgdg13+2) em Docker; volume persistente deste projeto.
- Airflow standalone local, com SQLite para metadados, LocalExecutor e uma tarefa por vez.

A imagem Docker e o servico PostgreSQL de outro projeto, assim como seus
componentes Airflow, nao foram reiniciados ou modificados para esta entrega.
Esta configuracao valida o escopo local, sem declarar prontidao para producao.

## Identificacao dos arquivos de entrada

```text
taxi_trip_data.csv
SHA-256: c47ff7c18cf229a3e99771373a1a55cd4d1c267fbcbf3b6dc609db93658de658
taxi_zone_geo.csv
SHA-256: 74dc2b6c1694657783a6ce9a714b565500f9d82cdd51aeffc81184edb0392d52
```

Os hashes identificam a Bronze desta verificacao. Um download futuro de uma
versao diferente da fonte pode gerar outras contagens. Nesse caso, comparar o
snapshot e reexecutar as validacoes, sem tratar os numeros deste documento como
uma garantia para qualquer versao do dataset. Os arquivos de dados nao sao
versionados no repositorio.

## Conferencia do consumidor Streamlit

Depois do sucesso da DAG, o dashboard executou uma nova consulta, concluida em
22/10/2026 as 10:56:25 (America/Sao_Paulo). A interface mostrou 3.151.748 embarques
nas tres zonas iniciais, 34,63% do extrato e presenca em 12/12 meses em cada uma.
A proposta, os perfis por zona, a serie mensal e os limites da decisao foram
conferidos na interface. As duas imagens no README foram capturadas depois dessa
leitura, sem publicar credenciais ou arquivos locais de controle do Airflow.

## Apresentacao e reproducao

A analise e os motivos das escolhas visuais estao no [README](../README.md).
O procedimento completo esta em [REPRODUCING.md](REPRODUCING.md). As capturas da
interface ficam em `images/`, sem credenciais, dados de autenticacao ou logs privados.
