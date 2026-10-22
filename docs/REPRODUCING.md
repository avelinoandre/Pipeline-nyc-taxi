# Como reproduzir o projeto

Este guia reproduz a entrega local: Bronze -> Silver -> Gold -> PostgreSQL ->
consultas analiticas -> Streamlit, com orquestracao pelo Airflow.

## 1. Ambiente

Ambiente de referencia: Ubuntu 22.04 no WSL2, Python 3.10, OpenJDK 21, Docker Engine
com Compose e navegador no Windows. Execute os comandos no terminal Ubuntu, a
partir da raiz do repositorio clonado dentro do filesystem Linux. O Airflow e
executado no WSL; o PostgreSQL analitico fica no Docker. A memoria e compartilhada
com outros processos: execute as tarefas de dados sequencialmente.

Confirme as ferramentas:

```bash
python3.10 --version
java -version
docker --version
docker compose version
```

## 2. Ambiente Python da pipeline e credenciais

```bash
python3.10 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
cp .env.postgres.example .env.postgres
chmod 600 .env .env.postgres
```

Edite `.env` para preencher `KAGGLE_API_TOKEN` e `.env.postgres` para definir sua
senha local. Os exemplos nao sao credenciais prontas. Esses dois arquivos locais
sao ignorados pelo Git. O token e necessario para obter a Bronze quando ela ainda
nao existe; nao e exigido para reutilizar os arquivos locais ja disponiveis.

Inicie o banco deste projeto:

```bash
docker compose up -d --wait postgres
docker compose ps
```

O banco `nyc_taxi` e publicado em `127.0.0.1:5432`. O Compose usa o nome `nyc-taxi`
para separar seus recursos de outros projetos. Os dados persistem no volume
`nyc-taxi_postgres_data`. A estrutura sera criada por uma tarefa da DAG.

## 3. Instalar o Airflow separado

Nao instale Airflow dentro da `.venv` anterior. Suas constraints fixam versoes de
bibliotecas que podem ser diferentes das exigidas pela pipeline e pelo dashboard.

```bash
python3.10 -m venv .venv-airflow
.venv-airflow/bin/python -m pip install --upgrade pip
.venv-airflow/bin/python -m pip install -r requirements-airflow.txt
bash scripts/airflow.sh version
```

O arquivo de requisitos usa Airflow 3.3.1 e as constraints oficiais para Python
3.10. O script `scripts/airflow.sh` configura caminhos relativos ao checkout, uma
porta propria e as opcoes locais; nao depende de ativar `.venv-airflow` no shell.
As tarefas da DAG usam explicitamente o Python de `.venv`, que tem Spark e os
clientes de dados. Os ambientes desempenham papeis distintos.

## 4. Iniciar e disparar a DAG

No primeiro terminal, mantenha este processo em execucao:

```bash
bash scripts/airflow.sh standalone
```

Interface: [http://127.0.0.1:8081](http://127.0.0.1:8081). Usuario: `andre`.
A senha e gerada uma unica vez em `.airflow/ui_passwords.json`. Consulte esse
arquivo local no editor quando precisar entrar; nao publique seu conteudo.
Os arquivos de controle, logs, senha e chaves ficam em `.airflow/`, ignorado pelo
Git e com diretorio privado. A interface escuta somente em localhost.

O modo standalone e uma instalacao de desenvolvimento: inicia scheduler,
dag processor, API/UI e triggerer. O executor e LocalExecutor com paralelismo 1. As transformacoes Spark usam
`SPARK_MASTER=local[2]` e driver de 1 GB na DAG; isso limita as tarefas concorrentes
que disputam memoria. Fora da DAG, os scripts aceitam `SPARK_MASTER`, mantendo
`local[*]` como padrao quando a variavel nao e definida.
O SQLite local `.airflow/airflow.db` registra somente o controle do Airflow; os
dados analiticos permanecem no PostgreSQL. Esse arranjo nao pretende oferecer
alta disponibilidade, isolamento multiusuario ou configuracao de producao.

No segundo terminal, tambem na raiz do projeto:

```bash
bash scripts/airflow.sh dags list-import-errors --output json
RUN_AIRFLOW_TESTS=1 AIRFLOW_HOME="$PWD/.airflow" .venv-airflow/bin/python -m unittest discover -s tests -p test_airflow_dag.py -v
bash scripts/airflow.sh dags unpause nyc_taxi_pipeline
bash scripts/airflow.sh dags trigger nyc_taxi_pipeline
```

Tambem e possivel habilitar e disparar a DAG pela interface. `schedule=None` torna
o disparo manual: nao ha uma carga diaria agendada para o mesmo extrato historico.
`catchup=False` evita agendar execucoes retroativas. Ha no maximo uma execucao
ativa e uma tarefa simultanea. Cada tarefa tem uma tentativa adicional apos dois
minutos; a duracao maxima e de duas horas por tarefa e quatro horas por DAG.

Um aviso do CLI sobre Graphviz se refere a exportacao opcional de grafos como
arquivos; o registro e a execucao da DAG nao dependem desse pacote.

Acompanhe as seis tarefas na ordem:

```text
prepare_bronze
  -> bronze_to_silver
  -> silver_to_gold
  -> create_postgres_schema
  -> gold_to_postgres
  -> validate_pipeline
```

A preparacao reutiliza os dois arquivos Bronze obrigatorios quando existem e nao
estao vazios. Para uma atualizacao deliberada da fonte, com a DAG parada:

```bash
.venv/bin/python src/ingestion/download_dataset.py --force-download
```

Depois dispare a DAG novamente. O teste de presenca da Bronze nao prova sua
completude: os scripts seguintes aplicam as validacoes de schema e de dados.
Uma falha de download gera erro de processo; as tarefas seguintes exigem sucesso
das anteriores. Nao execute os scripts de transformacao manualmente enquanto a
DAG estiver ativa, pois todos usam os mesmos diretorios de dados.

## 5. Conferir o resultado

A DAG so termina com sucesso depois de validar os Parquets, a carga PostgreSQL
e as seis consultas usadas pelo dashboard. A tarefa `validate_pipeline` salva
contagens e identificacao da execucao em `.airflow/validation/latest.json`.
Esse arquivo e local; o registro de entrega e documentado em `VALIDATION.md`.

No pgAdmin, abra `sql/validate_tables.sql` no banco `nyc_taxi`. As contagens devem
coincidir com os metadados dos Parquets da execucao. PKs, FKs e constraints ficam
ativas durante a carga. A fato deve ter a mesma quantidade de linhas da Silver.

A carga PostgreSQL e uma substituicao completa e transacional: uma falha antes
do COMMIT preserva a carga anterior. A DAG inteira nao e uma unica transacao:
Silver/Gold sao substituidas em disco; uma falha na ultima tarefa analitica nao
desfaz o COMMIT ja concluido pelo carregador. Verifique a causa antes de limpar
ou reexecutar tarefas. Para repetir apenas a tarefa que falhou, use Clear na
interface e mantenha as entradas inalteradas; uma nova carga completa pode ser
executada por outro disparo da DAG.

## 6. Abrir o dashboard

Apos concluir a carga, em outro terminal WSL:

```bash
source .venv/bin/activate
python -m streamlit run app.py
```

Abra [http://127.0.0.1:8501](http://127.0.0.1:8501). A Visao executiva e a entrada
para a apresentacao; as demais secoes permitem aprofundar perguntas. Use
**Atualizar dados** depois de uma nova carga. O botao invalida o cache das
consultas, sem iniciar a pipeline. A primeira consulta pode levar alguns minutos.

Os notebooks sao opcionais para executar o dashboard. Para explorar o raciocinio
da analise, abra `notebooks/02_pilot_business_analysis.ipynb` no VS Code conectado
ao WSL e selecione o kernel de `.venv`.

## 7. Testes e encerramento

Com o banco disponivel, as tabelas preparadas e sem uma DAG pesada em execucao:

```bash
RUN_POSTGRES_TESTS=1 .venv/bin/python -m unittest discover -s tests -v
RUN_AIRFLOW_TESTS=1 AIRFLOW_HOME="$PWD/.airflow" .venv-airflow/bin/python -m unittest discover -s tests -p test_airflow_dag.py -v
```

Os testes PostgreSQL usam schemas separados e rollback; nao apagam `public`.
A suite da pipeline ignora os testes exclusivos do Airflow, que rodam no outro
ambiente. Nao rode testes Spark simultaneamente com as transformacoes completas
se a memoria local estiver limitada.

Ctrl+C no terminal do Streamlit encerra o app. Ctrl+C no terminal do standalone
encerra os componentes desta instancia Airflow. Para parar apenas o PostgreSQL
deste projeto, use `docker compose stop postgres`. Nao use `down -v` para um
encerramento normal: o volume contem os dados persistentes.

## Limites da entrega

A entrega implementa um fluxo batch local para um snapshot historico, com
validacoes e apresentacao exploratoria. Carga incremental, atualizacao automatica
da fonte, usuarios de leitura dedicados, publicacao do Streamlit e deploy de
producao sao evolucoes possiveis, sem serem requisitos deste escopo.
