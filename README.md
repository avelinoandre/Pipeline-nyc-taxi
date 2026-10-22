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
iniciado com Docker Compose. A estrutura das tabelas esta definida em SQL e a
carga dos Parquets no banco esta implementada. O Airflow sera adicionado depois
da validacao dos scripts individuais.

### Por que Gold em Parquet e PostgreSQL

A Gold em Parquet e o resultado persistido das transformacoes analiticas. O
PostgreSQL publica esse mesmo modelo para consultas SQL e BI. Essa separacao
permite reutilizar a Gold ou recarregar o banco sem refazer Bronze -> Silver -> Gold.
O custo e manter duas copias, coordenar sua atualizacao e operar o script de carga.

Parquet e um formato de arquivo; DW e lakehouse descrevem arquiteturas e servicos
de dados. Nossos diretorios Parquet nao oferecem, sozinhos, snapshots de tabelas,
controle de escritores concorrentes ou transacao envolvendo as quatro tabelas.
Um lakehouse pode usar arquivos Parquet sob um formato de tabela gerenciado,
como Iceberg ou Delta. Uma Gold tambem pode residir diretamente em um DW.
A escolha local atual prioriza entender e testar o fluxo batch completo.

Referencias: [Apache Parquet](https://parquet.apache.org/docs/overview/) e
[Apache Iceberg](https://iceberg.apache.org/docs/latest/).

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

Criar a estrutura nao carrega os Parquets. Depois da criacao das tabelas, execute
a carga abaixo para disponibilizar os dados no PostgreSQL.

## Carga Gold -> PostgreSQL

O script `src/loading/gold_to_postgres.py` transfere os quatro Parquets da Gold
para as tabelas existentes. As dimensoes e a fato ja foram construidas pelo Spark;
a carga nao refaz os mapeamentos nem gera novos IDs.

Com o banco ativo e o schema criado, execute na raiz do projeto:

```bash
source .venv/bin/activate
pip install -r requirements.txt
python src/loading/gold_to_postgres.py
```

Fluxo:

1. Ler metadados dos Parquets, conferir que todos existem e nao estao vazios.
2. Conectar ao PostgreSQL com Psycopg usando apenas `.env.postgres`.
3. Conferir as colunas das tabelas antes de modificar seus registros.
4. Iniciar a transacao e limpar somente as quatro tabelas do modelo com um unico `TRUNCATE`, sem `CASCADE`.
5. Carregar `dim_payment_type`, `dim_zone`, `dim_date` e, por ultimo, `fact_trips`.
6. Comparar as contagens do PostgreSQL com as dos Parquets e conferir datas das viagens contra `dim_date`.
7. Confirmar a transacao somente se todas as verificacoes passarem e atualizar as estatisticas com `ANALYZE`.

### Lotes e consumo de memoria

O PyArrow le os Parquets em lotes de ate 50.000 linhas. Cada lote e convertido em
CSV em memoria e enviado com `COPY FROM STDIN`, sem criar arquivos CSV extras e
sem usar `collect()` ou carregar toda a fato em Pandas. Um COPY por lote limita os
eventos de verificacao das chaves estrangeiras; todos os lotes pertencem a mesma
transacao. Nulos e strings vazias permanecem distintos. Virgulas, aspas e quebras
de linha nos textos sao escapadas pelo escritor CSV.

### Reexecucao e rollback

A estrategia atual e **carga completa**, apropriada ao snapshot local deste
projeto. Reexecutar substitui os dados das quatro tabelas pelo conteudo atual da
Gold, sem acrescentar copias das mesmas viagens. Nao e uma carga incremental.
Dados inseridos manualmente nessas quatro tabelas sao substituidos na reexecucao.

O `TRUNCATE` e as cargas estao na mesma transacao. Uma falha no COPY, nas chaves ou
nas validacoes desfaz a tentativa inteira e preserva a versao anterior. Durante
essa transacao, consultas concorrentes podem aguardar a liberacao dos locks.
O script espera ate 10 segundos para adquirir locks, em vez de aguardar
indefinidamente uma transacao aberta no pgAdmin.

As chaves e constraints do banco permanecem ativas durante a carga. Os Parquets
Gold devem permanecer inalterados enquanto a carga esta em execucao: execute
Silver -> Gold e Gold -> PostgreSQL sequencialmente.

### Horarios e valores monetarios

A Gold atual foi escrita pelo Spark com sessao `America/Sao_Paulo`, como mostrado
nos logs de sua geracao. O Arrow le seus timestamps INT96 sem informar o fuso.
A carga usa `GOLD_TIME_ZONE` para reproduzir os mesmos horarios de parede usados
na geracao de `pickup_date_id` e `dropoff_date_id`, inclusive nas transicoes
historicas de horario de verao. Isso evita deslocar viagens para outra data.
Nao estamos reinterpretando os horarios de origem como horarios de Nova York.
Se o contrato de fuso da Gold mudar, a carga deve ser ajustada junto; a validacao
com `dim_date` interrompe a carga quando encontra divergencias de datas.

O CSV envia a representacao decimal dos doubles da Gold para as colunas NUMERIC,
sem impor duas casas decimais nem remover valores negativos. Isso nao recupera
precisao que ja tenha sido perdida na origem.

### Conferencia no pgAdmin e testes

Abra `sql/validate_tables.sql` no Query Tool para conferir as contagens depois da
carga. Para ver uma amostra da fato, use um limite em vez de pedir todos os registros:

```sql
SELECT trip_id, pickup_datetime, trip_distance, total_amount
FROM public.fact_trips
LIMIT 20;
```

Os testes de carga usam schemas temporarios separados, sem modificar `public`.
Eles exigem o PostgreSQL ativo, `.env.postgres`, os Parquets Gold e permissao de
criar schemas. Execute:

```bash
RUN_POSTGRES_TESTS=1 python -m unittest discover -s tests -p test_gold_to_postgres.py -v
```

A suite cobre horarios na virada de data, preservacao de valores e nulos, textos
com caracteres especiais, reexecucao sem duplicatas e preservacao da carga
anterior apos falha de FK, data inconsistente ou fonte vazia. Os testes de
integracao sao ignorados na suite comum se `RUN_POSTGRES_TESTS` nao estiver ativo.

Referencias: [Psycopg COPY](https://www.psycopg.org/psycopg3/docs/basic/copy.html),
[transacoes](https://www.psycopg.org/psycopg3/docs/basic/transactions.html) e
[PostgreSQL TRUNCATE](https://www.postgresql.org/docs/16/sql-truncate.html).

## Analytics: estudo historico para uma operacao piloto em NYC

### Cenario e motivo da escolha

Uma empresa de taxi esta avaliando uma operacao piloto em NYC e solicitou uma
analise historica das viagens disponiveis para selecionar zonas e faixas de
horario que merecem investigacao comercial. O dashboard sera uma entrega de
analise exploratoria para orientar esse estudo inicial.

Esse cenario conecta o trabalho de engenharia a uma decisao de negocio sem
prometer o que o dataset nao mede. A entrega identifica padroes de embarques
registrados e o perfil das viagens. Nao define tamanho de frota, nao estima lucro
e nao garante que uma zona tenha passageiros sem atendimento. Por serem dados
historicos, os resultados nao constituem uma recomendacao atual de entrada no
mercado; um piloto real exigiria dados recentes e validacao em campo.

### Cobertura verificada e recorte de analise

Na verificacao local de 20/10/2026, a fato carregada possui 9.100.887 viagens.
A consulta `sql/analytics/00_data_coverage.sql` audita todos os anos e encontrou
130 viagens com embarques fora de 2018, com datas entre 2001 e 2032. O intervalo
minimo/maximo, sozinho, portanto nao representa um periodo continuo de operacao.

As consultas de negocio usam embarques de **01/01/2018 inclusive a 01/01/2019
exclusive**: 9.100.757 viagens, distribuidas pelos 12 meses e pelos 365 dias de
2018. Esse e um recorte analitico explicito, sem apagar ou corrigir as 130 viagens
na Silver, na Gold ou no PostgreSQL. A auditoria continua exibindo esses registros.
Se o periodo mudar, atualize o CTE `parameters` nas cinco consultas de negocio,
mantenha as datas no primeiro dia do mes e execute novamente a auditoria.

Ter pelo menos um embarque em cada dia nao comprova completude nem amostragem
representativa. A fonte e o dataset do Kaggle indicado no inicio deste README;
a pipeline local nao comprova o metodo de selecao desse extrato nem sua fracao
do universo TLC. Nao extrapolar os totais para todo o mercado de NYC. O nome de
um arquivo de referencia de 2018 nao substitui a verificacao das datas da fato.
Nao confundir esta base tratada com a amostra de 100.000 linhas usada no notebook.

### Perguntas, consultas e graos

Todos os arquivos em `sql/analytics/` sao consultas `SELECT`, sem criar views,
modificar tabelas ou recarregar os Parquets. Foram mantidos SQL, joins e CTEs
explicitos para permitir a leitura e a execucao de cada analise separadamente.

| Arquivo | Pergunta / finalidade | Uma linha representa | Uso futuro no dashboard |
| --- | --- | --- | --- |
| `00_data_coverage.sql` | Qual e a cobertura e quais pontos exigem cuidado? | Ano de embarque, sem recorte | Painel de qualidade e contexto |
| `01_monthly_activity.sql` | Como o movimento registrado varia no ano? | Mes de embarque | Serie mensal e media por dia observado |
| `02_pickup_zones.sql` | Onde se concentram os embarques da base? | Zona de embarque no periodo | Barras por zona e borough |
| `03_zone_weekday_hour.sql` | Em quais dias e horarios ocorre o movimento em cada zona? | Zona x dia da semana x hora | Mapa de calor com filtro de zona |
| `04_zone_trip_profile.sql` | Como tarifa, total, distancia e duracao variam entre zonas? | Zona de embarque no periodo | Comparacao de medias, medianas e volume |
| `05_zone_monthly_activity.sql` | O movimento relativo de uma zona se mantem ao longo dos meses? | Zona de embarque x mes | Serie mensal por zona e participacao na base |

O foco espacial e o **embarque**: local onde a viagem comeca, adequado a pergunta
sobre posicionamento inicial. Zonas TLC sao unidades analiticas; nao equivalem
necessariamente a bairros administrativos. `borough` identifica os grandes
distritos. Nao interpretar o ranking como um ranking de rentabilidade.

### Definicao dos indicadores

- `trip_count`: numero de viagens tratadas no recorte, apos as regras da Silver.
- Participacao: viagens da zona divididas por todas as viagens do recorte (ou do mes), multiplicado por 100. O denominador inclui a zona desconhecida. E participacao no **dataset**, nao market share.
- Media por dia observado: viagens divididas pela quantidade de datas com algum embarque na base inteira do recorte ou mes. Dias sem viagens naquela zona tambem entram no denominador. `calendar_days` e `observed_days` permitem conferir a cobertura mensal.
- Media por dia da semana/hora: viagens daquela zona e hora divididas por todos os dias observados daquele dia da semana. Por exemplo, os embarques de segunda-feira as 08h sao divididos pelo numero de segundas observadas, nao somente pelas segundas com viagens na zona.
- Tarifa (`fare_amount`): componente de tarifa do taximetro. `total_amount` representa o total registrado cobrado do passageiro, com outros componentes; nao inclui gorjetas em dinheiro e nao representa receita liquida ou lucro.
- Distancia em milhas e duracao em minutos: medidas preservadas da Gold. Medias e medianas sao apresentadas juntas porque valores extremos ainda existem; nao ha remocao adicional de outliers nesta etapa.
- Somas e medias monetarias preservam zero e valores negativos. Nulos sao ignorados por `SUM`, `AVG` e `PERCENTILE_CONT`; `trips_with_fare` e `trips_with_total` informam os denominadores validos. A auditoria e o perfil exibem as contagens nao positivas. Um grupo so com nulos continua com medida nula, em vez de um zero artificial.

As consultas mensais completam os 12 meses. A consulta de zona/mes completa os
meses para cada zona com embarques no periodo. A de horarios completa as 24 horas
para cada zona e dia da semana observado no recorte. Um zero representa ausencia
de registros naquela combinacao, sem provar ausencia de demanda real. Uma media
sem dias observados retorna `NULL`, evitando divisao por zero e falsa cobertura.

A zona `-1` permanece em todas as agregacoes para reconciliar os totais, marcada
com `is_mapped_zone = false`. Exiba sua participacao como limitacao e filtre
`is_mapped_zone = true` ao escolher locais para investigar. Nao descarte essa
categoria silenciosamente ou altere o denominador ao apresentar os percentuais.
Zonas com poucas viagens exigem cautela; os arquivos nao impoem um corte de volume
arbitrario nem uma pontuacao automatica de oportunidade.

### Limites para a interpretacao empresarial

- As viagens realizadas mostram movimento atendido. Faltam pedidos nao atendidos, oferta concorrente e tempo de espera para medir demanda reprimida.
- Faltam custos e identificadores de motorista/veiculo para estimar lucro, utilizacao, receita por taxi ou necessidade de frota. `vendor_id` identifica o fornecedor tecnologico do registro, nao uma empresa de taxi a ser comparada.
- O extrato nao possui um campo explicito de tipo de servico para comparar frotas yellow, green e FHV. O uso do dicionario TLC para interpretar medidas nao comprova a cobertura dessas categorias na fonte.
- Datas e horas seguem os valores preservados na Gold e na carga, sem novo deslocamento de fuso. O fuso da sessao Spark descrito acima e um contrato tecnico, nao uma comprovacao independente do fuso da fonte. Apresente os resultados como horarios registrados; confirmar a semantica temporal da origem e necessario antes de definir escalas reais em NYC.
- Comparacoes entre meses descrevem variacao observada em um unico ano. Nao comprovam sazonalidade recorrente nem crescimento do mercado; mudancas na composicao do extrato tambem podem afetar os resultados.

Referencias para a interpretacao dos campos: [dicionario TLC de viagens yellow](https://www.nyc.gov/assets/tlc/downloads/pdf/data_dictionary_trip_records_yellow.pdf)
e [origem e limites dos registros TLC](https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page).
O dicionario atual e usado para as definicoes das medidas, sem aplicar tarifas ou
novos codigos de anos posteriores aos registros de 2018.

### Como executar e validar

No pgAdmin, conecte ao banco `nyc_taxi`, abra o Query Tool e use Open File para
abrir os arquivos de `sql/analytics/`, comecando por `00_data_coverage.sql`.
Execute cada arquivo completo: o CTE pertence ao SELECT que vem em seguida.
Depois siga a numeracao para inspecionar os resultados. A consulta com medianas
pode levar mais tempo porque precisa ordenar os valores dentro de cada zona.

Tambem e possivel executar um arquivo pelo WSL, a partir da raiz do projeto:

```bash
docker compose exec -T postgres sh -c 'psql -X -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1' < sql/analytics/01_monthly_activity.sql
```

A soma de `trip_count` em cada consulta de negocio deve coincidir com a contagem
de 2018 da auditoria. Em zona/mes, a soma das zonas de cada mes tambem deve
coincidir com a consulta mensal. Percentuais arredondados podem nao somar
exatamente 100. O arredondamento e somente de apresentacao, sem mudar os fatos.

Validacao na base completa em 20/10/2026: as seis consultas foram executadas
em uma transacao somente de leitura com snapshot consistente. As cinco consultas
de negocio reconciliaram 9.100.757 viagens, e zona/mes reconciliou cada total
mensal. A base de 2018 possui 140.537 embarques com zona desconhecida (cerca de
1,54%), mantidos nos totais. A execucao produziu:

| Consulta | Linhas de resultado |
| --- | ---: |
| Auditoria por ano | 11 |
| Movimento mensal | 12 |
| Zonas de embarque | 259, incluindo a desconhecida |
| Zona x dia da semana x hora | 43.512 |
| Perfil das viagens por zona | 259 |
| Zona x mes | 3.108 |

As maiores contagens de embarques na base foram LaGuardia Airport (1.981.984),
JFK Airport (869.812) e Times Sq/Theatre District (299.952). Sao resultados
descritivos do extrato; a concentracao reforca a necessidade de investigar sua
composicao antes de generalizar para NYC ou recomendar a operacao em aeroportos.

Os testes usam um schema isolado dentro de uma transacao desfeita ao terminar;
nao modificam `public`. Com PostgreSQL ativo e `.env.postgres` configurado:

```bash
RUN_POSTGRES_TESTS=1 python -m unittest discover -s tests -p test_analytics.py -v
```

Cobrem fronteiras do periodo, reconciliacao de contagens, zona desconhecida,
meses/horas sem registros, denominadores dos dias observados e preservacao de
nulos, valores negativos e extremos nas medidas. Esses testes nao exigem os
Parquets Gold: usam uma pequena massa controlada com resultados conhecidos.

### Uso dos indicadores no Streamlit

As consultas definem e validam as metricas antes dos graficos. O app Python
consulta o PostgreSQL usando os mesmos arquivos SQL do notebook. Nao juntar
resultados agregados de graos diferentes como se fossem fatos individuais:
isso pode multiplicar totais. A consulta de perfil e a de zona/hora agregam o
periodo inteiro e nao respondem automaticamente a filtros mensais do BI.

Contagens e somas podem ser reagrupadas em graos compativeis. Medias devem ser
recalculadas com seus denominadores, percentuais com seus totais, e medianas
sobre as viagens do novo grupo. Nao tirar media simples das medias nem somar
medianas, percentuais ou totais mensais repetidos em cada linha de zona.

A conclusao empresarial esperada e uma lista de zonas e horarios que merecem
estudo de campo para o piloto, acompanhada de volume, perfil das viagens e
estabilidade mensal. A recomendacao sera formulada depois da leitura dos
resultados, sem definir antecipadamente que maior volume significa melhor local.

## Notebook de analise de negocio

O notebook `notebooks/02_pilot_business_analysis.ipynb` investiga o cenario da
operacao piloto com os dados tratados do PostgreSQL. O notebook 01 continua
voltado a exploracao e qualidade da origem; o 02 conecta os resultados a
perguntas empresariais, sem refazer as transformacoes Silver/Gold.

Estrutura: contexto e objetivo, conexao, auditoria/reconciliacao, movimento mensal,
zonas de embarque, dias/horarios, perfil das viagens, consistencia mensal e
sintese exploratoria. Cada analise combina tabelas, graficos e interpretacao,
explicando a implicacao para o estudo e os limites da conclusao.

Use o VS Code conectado ao WSL e selecione o kernel da `.venv` do projeto.
Abra o notebook e execute Restart Kernel -> Run All. Pode ser iniciado na raiz
ou em `notebooks/`. O PostgreSQL deve estar ativo, as tabelas carregadas e as
credenciais configuradas em `.env.postgres`. As bibliotecas ja estao em
`requirements.txt`; nao e necessario instalar Streamlit para executar a analise.

O notebook le os seis arquivos de `sql/analytics/` em uma transacao somente de
leitura com snapshot consistente e encerra a conexao ao terminar. Somente os
resultados agregados vao para pandas; os nove milhoes de fatos ficam no banco.
As contagens por grao e por mes sao reconciliadas antes dos graficos. Os valores
NUMERIC retornados sao convertidos para float apenas no pandas para facilitar
analise e graficos, sem modificar a precisao armazenada no PostgreSQL.

A selecao das tres zonas com maior volume e um criterio exploratorio explicito,
sem criar uma pontuacao de oportunidade. Medias e medianas sao comparadas e os
horarios de pico sao contextualizados. A consistencia mensal de volume nao
comprova a consistencia mensal de cada pico de horario: essa pergunta exigiria
um SQL com grao zona/mes/dia/hora, ainda fora desta etapa.

Validacao local: nove celulas de codigo executadas em ordem, sem erros, com
cinco graficos revisados e reconciliacao das contagens agregadas.

O notebook e entregue com saidas executadas. Elas representam um snapshot da
analise e precisam ser atualizadas apos uma nova carga. As credenciais nao sao
exibidas; os resultados salvos sao agregados historicos e devem ser revisados
antes de uma eventual publicacao. A primeira versao do Streamlit usa esta analise
para definir suas secoes e indicadores. A investigacao permanece no notebook;
o dashboard executa os SQLs diretamente, sem depender das saidas salvas.

## Dashboard local em Streamlit

A primeira versao do dashboard esta em `app.py`. Ela transforma as perguntas e
as interpretacoes do notebook 02 em uma interface interativa para explorar o
estudo historico da operacao piloto. Usa Streamlit para a interface, Plotly para
os graficos e o PostgreSQL para as agregacoes. Nao exige executar o notebook.

### Executar

No terminal WSL, na raiz do projeto, com as tabelas ja carregadas:

```bash
source .venv/bin/activate
pip install -r requirements.txt
docker compose up -d --wait postgres
python -m streamlit run app.py
```

Abra [http://127.0.0.1:8501](http://127.0.0.1:8501) no navegador Windows.
O servidor e local e pode ser encerrado com Ctrl+C no terminal. A primeira
consulta pode levar alguns minutos: ela agrega a base completa antes de exibir
os indicadores. A porta, o endereco local, o tema e a desativacao de estatisticas
de uso estao em `.streamlit/config.toml`. Se a porta 8501 estiver ocupada, use
`python -m streamlit run app.py --server.port 8502` e acesse a porta correspondente.
O Python instalado no Windows nao substitui a `.venv` do WSL.

| Secao | O que permite investigar |
| --- | --- |
| Visao executiva | Decisao, proposta, evidencias, incertezas e encaminhamento para o estudo de campo |
| Panorama | Volume mensal ou media por dia observado na base completa de 2018 |
| Zonas e meses | Ranking por distrito e evolucao mensal de ate cinco zonas selecionadas |
| Dias e horarios | Mapas de calor por zona, com escala de cores comum |
| Perfil das viagens | Media e mediana de tarifa, total cobrado, distancia ou duracao |
| Cobertura e metodo | Registros fora de 2018, limitacoes e exportacao da auditoria em CSV |

### Por que a entrada e uma visao executiva

O publico da apresentacao e a equipe de estrategia de uma empresa de taxi.
Por isso, a tela inicial organiza a conversa em torno de uma decisao empresarial,
com o roteiro: **decisao -> proposta -> evidencias -> incertezas -> proximo passo**.
O notebook continua documentando a investigacao; as demais secoes do Streamlit
permitem aprofundar perguntas durante a apresentacao.

A decisao nesta etapa e escolher o foco de uma investigacao de campo. A selecao
inicial usa as tres zonas mapeadas com mais embarques: LaGuardia, JFK e Times
Square. Elas formam uma hipotese de comparacao entre aeroportos e um polo urbano,
sem assumir que os aeroportos sejam a melhor oportunidade de entrada. Ao mudar
as zonas na barra lateral, os textos e indicadores se referem a nova selecao.

A proposta aparece antes dos numeros. As evidencias incluem volume e participacao
das zonas no extrato completo, medianas por zona, picos registrados e presenca
mensal. Os indicadores da visao executiva se referem a selecao, enquanto os
indicadores gerais das demais secoes continuam sobre toda a base de 2018.
Nao se somam medianas nem se troca o denominador dos percentuais ao selecionar
zonas ou distritos. A presenca minima mensal e o menor numero de meses com
embarques entre as zonas selecionadas, sem afirmar estabilidade de demanda.

As incertezas relevantes ficam visiveis antes do encaminhamento: dados de 2018,
selecao do extrato nao comprovada, zonas desconhecidas e ausencia de custos/oferta.
Nao ficam escondidas somente em um expansor. Detalhes de calculo e auditoria
continuam disponiveis nas areas de apoio.

O encaminhamento proposto e aprovar o escopo de um estudo de campo para levantar
oferta, espera, custos e dados recentes. A entrega esperada desse estudo e definir
criterios para avaliar um piloto operacional, sem aprovar automaticamente frota
ou inicio de operacao. Esse roteiro permite usar o dashboard como apoio visual
para um pitch, sem exigir a leitura de todo o texto explicativo na reuniao.

A versao executiva foi conferida no navegador com os dados reais. Na selecao
inicial, as tres zonas reunem 3.151.748 embarques e 34,63% das viagens do recorte.
O teste de interface verifica a ordem dos cinco blocos e a atualizacao dos
percentuais quando a selecao muda, preservando a base completa no denominador.

### Resultados: insights e resumo da visao executiva

Os resultados abaixo correspondem ao snapshot analisado nas execucoes documentadas
em 20 e 21/10/2026. O periodo dos dados e **2018**, nao 2026. As cinco consultas
de negocio usam 9.100.757 viagens tratadas; os resultados representam o extrato
local e nao uma estimativa de todo o mercado de NYC. As tabelas abaixo registram
a selecao inicial do dashboard, sem os filtros que o usuario possa aplicar depois.

#### Resumo para a equipe de estrategia

> A proposta e investigar LaGuardia e JFK, usando Times Square como contraponto
> urbano, antes de decidir sobre uma operacao piloto. Essas tres zonas concentram
> 3.151.748 embarques, ou 34,63% das viagens do extrato de 2018, e possuem registros
> em todos os 12 meses. Seus perfis de viagem e horarios de maior movimento sao
> diferentes. O encaminhamento e definir um estudo de campo para avaliar oferta,
> espera, custos e dados recentes; ainda nao ha evidencia para aprovar frota ou
> concluir que operar nessas zonas sera rentavel.

Essa sintese segue o roteiro do pitch: decisao sobre onde investigar, proposta
inicial de zonas, evidencias, incertezas e proximo passo. A selecao das tres zonas
foi feita pelo maior volume de embarques mapeados; nao e uma classificacao de
viabilidade, lucro ou demanda nao atendida.

#### Insight 1: o movimento registrado se concentra em poucos polos

| Zona de embarque | Viagens em 2018 | Participacao no extrato |
| --- | ---: | ---: |
| LaGuardia Airport | 1.981.984 | 21,78% |
| JFK Airport | 869.812 | 9,56% |
| Times Sq/Theatre District | 299.952 | 3,30% |

LaGuardia e o maior polo de embarques dessa base, seguido por JFK e Times Square.
A concentracao fornece um criterio explicito para priorizar a investigacao.
Comparar os dois aeroportos com um polo urbano permite investigar contextos
operacionais diferentes, sem presumir que aeroportos sejam a melhor entrada.

A participacao conjunta de 34,63% e calculada sobre as contagens originais, antes
do arredondamento; nao e a soma dos percentuais individuais ja arredondados.
Os denominadores incluem os embarques com zona desconhecida. Todos esses
percentuais sao participacoes no extrato, nao market share da cidade.

#### Insight 2: uma tarifa maior acompanha um perfil diferente de viagem

| Zona | Tarifa mediana (USD) | Distancia mediana (milhas) | Duracao mediana (minutos) |
| --- | ---: | ---: | ---: |
| LaGuardia Airport | 32,50 | 10,00 | 31,38 |
| JFK Airport | 50,50 | 16,59 | 37,58 |
| Times Sq/Theatre District | 30,50 | 8,87 | 32,40 |

JFK combina as maiores medianas de tarifa, distancia e duracao entre as tres
zonas. Isso indica um perfil de viagem diferente, que deve entrar na comparacao
operacional. Nao demonstra que JFK tenha melhor margem, nem prova uma relacao
causal entre essas medidas: faltam custos, deslocamentos sem passageiros e oferta.
Cada mediana descreve sua propria distribuicao; esses valores nao caracterizam
necessariamente uma mesma viagem e nao devem ser somados ou divididos para
calcular uma margem ou uma taxa tipica por hora.

As medias e medianas sao apresentadas juntas nas analises de apoio porque ainda
existem valores extremos. Em LaGuardia, por exemplo, a duracao media e 35,78 min
e a mediana e 31,38 min. A diferenca ajuda a avaliar o perfil da distribuicao,
sem identificar sozinha a causa ou justificar a exclusao de registros.

#### Insight 3: os picos registrados variam entre as zonas

| Zona | Dia e hora do pico registrado | Media de embarques nessa combinacao |
| --- | --- | ---: |
| LaGuardia Airport | Domingo, 21h | 453,27 |
| JFK Airport | Domingo, 22h | 211,19 |
| Times Sq/Theatre District | Quarta-feira, 22h | 63,19 |

O pico e a combinacao de dia da semana e hora com maior media de embarques por
dia da semana observado no ano. O denominador inclui todos os dias observados
daquele dia da semana, inclusive quando nao houve viagem na zona/hora. Em
empates, o dashboard mostra a primeira combinacao na ordem do SQL.

Essas combinacoes ajudam a escolher faixas para observacao em campo. Nao sao
escalas de motoristas, volume por taxi ou horarios locais de NYC comprovados:
a semantica temporal da fonte ainda precisa ser confirmada. Tambem nao foi
verificado se o mesmo pico se repete em cada mes.

#### Insight 4: existe presenca anual, com variacao de participacao mensal

| Zona | Meses com registros | Menor participacao mensal | Maior participacao mensal |
| --- | ---: | ---: | ---: |
| LaGuardia Airport | 12 de 12 | 19,18% | 23,80% |
| JFK Airport | 12 de 12 | 8,53% | 11,13% |
| Times Sq/Theatre District | 12 de 12 | 3,19% | 3,40% |

As tres zonas aparecem ao longo do ano, portanto seu destaque nao depende apenas
de um unico mes com registros. Times Square tem a menor amplitude de participacao
mensal entre as tres. Isso descreve participacao relativa na base, sem demonstrar
volume constante ou demanda estavel. Variacoes nas demais zonas e na composicao
do extrato tambem afetam esses percentuais.

No panorama geral, marco apresenta a maior media diaria observada, com
30.143,10 viagens por dia; agosto apresenta a menor, com 21.152,32. A media diaria
ajuda a comparar meses com quantidades diferentes de dias. Um unico ano e uma
cobertura nao comprovada impedem interpretar essa diferenca como sazonalidade
recorrente ou crescimento/retracao do mercado.

#### Limites que acompanham os insights

Ha 140.537 embarques sem zona identificada em 2018, aproximadamente 1,54% do
recorte. Eles permanecem nos totais. Outras 130 viagens da fato possuem embarques
fora de 2018 e ficam visiveis na auditoria, sem entrar nas consultas de negocio.
Os 365 dias com registros nao comprovam cobertura completa; a selecao do extrato
nao foi verificada. Valores cobrados nao representam lucro e viagens realizadas
nao medem demanda nao atendida.

O resultado pratico desta etapa e uma **hipotese de investigacao**, com zonas e
faixas de horario para validar, e nao uma recomendacao de iniciar a operacao.
Fontes internas: `sql/analytics/00_data_coverage.sql` a `05_zone_monthly_activity.sql`,
saidas executadas de `notebooks/02_pilot_business_analysis.ipynb` e visao executiva
de `app.py`. Apos nova carga ou mudanca de regra, reexecutar as consultas e revisar
esta sintese: os numeros do README sao um registro estatico, nao dados atualizados
automaticamente pelo Streamlit.

### Por que cada grafico foi escolhido

Os graficos foram escolhidos pela pergunta de negocio e pelo grao de cada
consulta. A visao executiva destaca a proposta e poucas evidencias; as demais
secoes permitem investigar os resultados e responder perguntas da equipe.

| Visual / local no dashboard | Pergunta que apoia | Motivo da escolha | Cuidados de leitura |
| --- | --- | --- | --- |
| Cartoes de indicadores e de zonas / Visao executiva | Qual e a dimensao da selecao e o perfil de cada zona? | Reunem poucos numeros, unidades e horarios para leitura rapida durante o pitch. Os cartoes sao resumos numericos, nao uma nova agregacao dos fatos. | A participacao usa todas as viagens do recorte no denominador; as medianas continuam por zona. O volume alto nao representa lucro ou demanda reprimida. |
| Linhas de participacao mensal / Visao executiva | O destaque das zonas aparece durante o ano ou se concentra em meses especificos? | O eixo temporal ordenado permite acompanhar trajetorias e comparar a participacao relativa das zonas. Marcadores deixam explicitos os meses observados e as cores identificam as zonas. | Presenca e participacao nao comprovam estabilidade de demanda. Nao somar percentuais de meses diferentes nem extrapolar a serie para outros anos. |
| Barras verticais por mes / Panorama | Em quais meses o extrato tem maior volume ou maior media diaria? | Meses sao categorias ordenadas; a altura das barras facilita comparar suas magnitudes. A opcao de media diaria considera a quantidade de dias observados em cada mes. | A media usa dias com registros na base, sem comprovar completude. Total e media diaria sao alternativas de leitura, com unidades diferentes. |
| Barras horizontais ordenadas / Zonas e meses | Quais zonas concentram os embarques registrados? | O comprimento das barras facilita comparar volumes e a orientacao horizontal acomoda nomes longos de zonas. A ordenacao torna as maiores concentracoes visiveis. | O ranking e descritivo e pode ser limitado por distrito; os percentuais continuam sobre a base completa, sem trocar o denominador para o distrito. |
| Linhas de participacao ou media diaria por zona / Zonas e meses | Como evoluem as zonas selecionadas nos 12 meses? | Uma linha por zona permite comparar trajetorias. A participacao mostra o peso relativo na base mensal; a media diaria mostra movimento ajustado pelos dias observados. | As duas medidas respondem a perguntas diferentes. Uma participacao pode mudar porque outras zonas mudaram, mesmo sem a mesma variacao no volume da zona analisada. |
| Mapas de calor de dia da semana x hora / Dias e horarios | Quais combinacoes concentram o movimento em cada zona? | A grade 7 x 24 revela padroes e concentracoes em duas dimensoes temporais. A cor representa a media por dia da semana observado, permitindo enxergar faixas vizinhas ao pico. | As zonas da mesma selecao usam a mesma escala de cores. Ao mudar a selecao, o limite da escala pode mudar; comparar valores e legenda. A media nao e produtividade por taxi e o fuso da fonte precisa ser confirmado. |
| Barras agrupadas de media e mediana / Perfil das viagens | Como tarifa, total cobrado, distancia e duracao variam entre as zonas? | As duas barras por zona permitem comparar nivel e diferenca entre media e mediana. Cada medida tem seu proprio grafico/unidade, conforme a escolha do usuario. | Nulos sao ignorados pelos agregadores; zeros, negativos e extremos sao preservados. A diferenca entre media e mediana nao identifica sua causa. Nao reagrupar medianas nem interpretar valores cobrados como lucro. |
| Tabelas de denominadores e cobertura / Panorama, Perfil e Cobertura e metodo | Qual e a base de calculo e quais limitacoes afetam a interpretacao? | Tabelas preservam valores exatos, contagens validas, dias observados e referencias desconhecidas para conferencia. Sustentam os graficos quando a equipe pede detalhes. | Sao materiais de apoio, com possibilidade de exportacao. Devem ser lidos no mesmo periodo e grao do indicador que explicam. |

A escolha visual faz parte da interpretacao: cores consistentes, unidades
explicitas e denominadores identificados evitam que diferencas de apresentacao
sejam confundidas com diferencas reais de negocio. Os graficos sustentam a
hipotese do pitch; nao substituem a verificacao das limitacoes da fonte.

### Escopo dos filtros e das medidas

O recorte desta versao e fixo: embarques de 2018. O distrito limita as opcoes de
zonas e o ranking; as zonas selecionadas alteram os comparativos de evolucao,
horarios e perfil. Os cartoes gerais e o Panorama permanecem sobre toda a base
de 2018, como identificado na interface. A zona desconhecida participa desses
totais e dos denominadores, mas nao aparece como local para selecionar.

Nao existe filtro mensal global: os SQLs de horarios e perfil estao agregados
para o ano inteiro e nao permitem recalcular essas medidas corretamente por mes.
A serie por zona/mes usa o SQL especifico desse grao. Nao fazemos media das
medianas, nao somamos percentuais e nao somamos totais mensais repetidos por zona.
Ao filtrar distritos, o percentual continua representando a participacao da zona
na base completa, sem trocar silenciosamente o denominador para o distrito.

### Consulta, cache e falhas

`src/dashboard/data.py` le os mesmos seis SQLs versionados em `sql/analytics/`,
consulta o PostgreSQL em uma transacao somente de leitura com snapshot consistente
e fecha a conexao. As credenciais sao lidas de `.env.postgres` com caminho absoluto
a partir do projeto e nao sao exibidas. As tabelas nao sao alteradas. Os resultados
sao reconciliados por grao e por mes antes de renderizar a interface.

O app armazena somente agregados em memoria com `st.cache_data`, TTL de 15 minutos
e uma entrada de cache. Navegar ou filtrar nao repete os SQLs durante esse periodo.
O texto dos arquivos SQL faz parte da chave do cache: alterar uma consulta provoca
nova leitura no proximo rerun. O cache e compartilhado entre sessoes deste servidor
local, sem persistencia em disco. Nao e um mecanismo de isolamento entre usuarios
ou bancos diferentes; esta versao usa uma unica base local de desenvolvimento.

Depois de uma nova carga, use **Atualizar dados** para invalidar o cache e obter
outro snapshot. O botao apenas consulta; nao executa ingestao, Spark ou carga da
Gold. A data exibida e o horario da consulta (Brasilia), nao a data de atualizacao
da fonte. Expirar o TTL nao agenda consultas em segundo plano: a proxima interacao
com o app inicia a consulta. Depois de alterar credenciais, reinicie o app ou
atualize os dados para abandonar os agregados anteriores.

Conexao: timeout de 10 segundos. Espera por locks: 10 segundos. Cada SQL tem limite
de cinco minutos. Se houver indisponibilidade, falta de configuracao ou resultados
inconsistentes, o app interrompe a exibicao com uma mensagem generica, sem mostrar
senhas ou traceback. O usuario local ainda e administrador de desenvolvimento;
a transacao somente de leitura nao substitui um usuario de banco com permissoes
restritas quando houver publicacao ou outros usuarios.

Se a tela indicar falha, confira `docker compose ps`, as contagens de
`sql/validate_tables.sql` e a configuracao local de `.env.postgres`, sem publicar
seu conteudo. Corrija a causa e clique em Atualizar dados. Esta versao nao inclui
autenticacao ou publicacao na internet; o servidor escuta somente em localhost.

### Testes do dashboard

```bash
python -m unittest discover -s tests -p test_dashboard.py -v
```

Validacao local em 21/10/2026: a interface foi conferida no navegador com a
base real (9.100.757 viagens de 2018, 365 dias observados, 258 zonas identificadas
e 1,54% de embarques sem zona). As seis consultas reconciliaram e as secoes de exploracao
foram percorridas, incluindo mapas de calor e comparacoes de medias/medianas.
Os cartoes foram ajustados para preservar os numeros completos em janelas menores.

Nove testes verificam reconciliacao, deslocamento de contagens entre meses,
navegacao, roteiro executivo, participacao da selecao sobre a base completa,
comparacao das medidas, filtro de distrito, selecao vazia, uso do cache,
atualizacao explicita e falha de conexao sem expor credenciais. Usam AppTest para
executar o app real com agregados controlados, sem depender do PostgreSQL.

Referencias: [cache Streamlit](https://docs.streamlit.io/develop/concepts/architecture/caching),
[testes com AppTest](https://docs.streamlit.io/develop/api-reference/app-testing/st.testing.v1.apptest)
e [graficos Plotly no Streamlit](https://docs.streamlit.io/develop/api-reference/charts/st.plotly_chart).

## Papel do Airflow na evolucao do projeto

O Airflow coordenara a execucao dos scripts Bronze -> Silver -> Gold -> PostgreSQL:
ordem das tarefas, dependencias, logs e tratamento de falhas. Ele nao substitui
Spark, PostgreSQL ou Streamlit. O notebook continua sendo o ambiente de
investigacao; nao precisa ser executado inteiro a cada carga. As validacoes
obrigatorias de uma rotina automatica devem estar nos scripts e testes.

O Streamlit consulta a ultima carga confirmada no PostgreSQL. Como a carga
atual substitui os dados em uma transacao, consultas podem aguardar locks durante
a atualizacao. O app limita a espera por locks e permite atualizar seu cache.

A analise e a primeira versao do dashboard estao implementadas. A proxima
etapa de automacao e criar uma DAG inicialmente manual (`schedule=None`), sem agendar uma
recarga diaria do mesmo extrato historico. Um agendamento sera definido quando
houver uma fonte atualizada e uma politica de ingestao. A ingestao atual usa
`force_download=True`; antes de automatizar, revisar esse comportamento para
evitar downloads repetidos desnecessarios. Reexecucoes, tentativas e falhas entre
as camadas tambem precisam ser consideradas, especialmente a escrita sequencial
dos quatro diretorios Gold. O Airflow, sozinho, nao torna essa escrita atomica.

## Testes

```bash
python -m unittest discover -s tests -v
```

Os testes cobrem o calculo da duracao, filtros e limites de rollover, validacoes da
Silver, zonas repetidas/conflitantes, codigos desconhecidos/nulos, estabilidade dos
IDs, integridade referencial e escrita/releitura com `overwrite`.

## EDA e proximas etapas

O notebook `notebooks/01_exploratory_analysis.ipynb` explora a origem e trabalha com
amostra de 100.000 linhas (`seed=42`); seus resultados nao representam contagens
do dataset completo. Limites estatisticos servem para monitoramento, sem remocao
automatica de outliers.

Proximas etapas: revisar os achados e a usabilidade do dashboard com o contexto
empresarial e introduzir Airflow para orquestrar o fluxo validado. Filtros mensais
para horarios e perfil exigirao novas consultas com grao adequado, caso sejam
necessarios. A entrada real no mercado depende de dados atuais e estudo de campo.
