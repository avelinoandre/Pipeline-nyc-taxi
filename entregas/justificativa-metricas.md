# Proposta de métricas — Dashboard 2

Público-alvo proposto: equipe de planejamento operacional de uma operação de
táxis. O painel descreve o perfil das viagens registradas e apoia a escolha
de horários e perfis de viagem para investigação operacional.

Base: versão limitada a 200.000 viagens da Silver tratada já aprovada na Aula 1,
conforme escolha do aluno nesta etapa. As métricas representam viagens
presentes nessa amostra histórica, não contagens da Silver completa nem toda
a demanda da cidade. Médias são
calculadas diretamente nas linhas, ignorando valores nulos de cada medida.
Cada linha da Silver representa uma viagem.

Seleção aprovada pelo aluno: amostra aleatória sem reposição de 200.000 linhas,
usando Polars com `seed=42`, seguindo a abordagem da EDA. O CSV está em
`data/clean/dataset.csv`; os nove Parquets completos da Aula 1 permanecem
preservados. O intervalo inclusivo de `trip_distance`, em milhas, filtra as
duas abas. A multiseleção de variáveis afeta somente o Dashboard 1.

## 1. Viagens avaliadas — contagem

- **Variável:** registros de viagens.
- **O que mede:** quantidade de viagens no recorte exibido.
- **Por que foi escolhida:** identifica o tamanho da base que sustenta as outras métricas.
- **Público-alvo:** equipe de planejamento operacional.
- **Qual decisão pode ser apoiada:** decidir se o recorte tem volume suficiente para aprofundar a análise.
- **O que comunica ao público-alvo:** quantas viagens estão sendo comparadas.

```python
viagens = len(df)
st.metric("Viagens avaliadas", f"{viagens:,}")
```

## 2. Distância média — média

- **Variável:** `trip_distance`, em milhas.
- **O que mede:** distância média registrada por viagem com distância válida.
- **Por que foi escolhida:** resume o comprimento dos trajetos no recorte.
- **Público-alvo:** equipe de planejamento operacional.
- **Qual decisão pode ser apoiada:** escolher recortes de trajetos curtos ou longos para estudo operacional.
- **O que comunica ao público-alvo:** o tamanho médio dos percursos observados.

```python
distancia_media = df["trip_distance"].mean()
st.metric("Distância média (milhas)", f"{distancia_media:.2f}")
```

## 3. Duração média — média

- **Variável:** `trip_duration_minutes`, em minutos.
- **O que mede:** tempo médio registrado por viagem com duração válida.
- **Por que foi escolhida:** complementa a distância com o tempo das viagens.
- **Público-alvo:** equipe de planejamento operacional.
- **Qual decisão pode ser apoiada:** identificar perfis com maior tempo de viagem para investigação de alocação operacional.
- **O que comunica ao público-alvo:** o tempo médio consumido pelas viagens observadas; não mede espera nem tempo ocioso.

```python
duracao_media = df["trip_duration_minutes"].mean()
st.metric("Duração média (min)", f"{duracao_media:.2f}")
```

## 4. Valor total médio cobrado — média

- **Variável:** `total_amount`, em dólares (USD).
- **O que mede:** valor total médio registrado por viagem com total não nulo.
- **Por que foi escolhida:** relaciona o perfil operacional ao valor cobrado registrado.
- **Público-alvo:** equipe de planejamento operacional.
- **Qual decisão pode ser apoiada:** selecionar perfis de viagem para uma análise financeira posterior com dados de custos.
- **O que comunica ao público-alvo:** o total médio registrado, incluindo os componentes presentes na fonte; não representa lucro nem rendimento líquido do motorista.

```python
valor_medio = df["total_amount"].mean()
st.metric("Total médio cobrado (USD)", f"{valor_medio:.2f}")
```

## Visuais finais do Dashboard 2

**Variável agrupada:** hora do embarque, derivada de `pickup_datetime`.
**Visual:** barras com a quantidade de viagens por hora (0–23).
**Finalidade:** identificar horários com maior volume de viagens registradas
para aprofundar a investigação operacional. Não mede demanda não atendida.

```python
por_hora = (
    df.groupby(df["pickup_datetime"].dt.hour)
    .size()
    .reindex(range(24), fill_value=0)
)
```

O notebook `notebooks/03_metricas_streamlit.ipynb` contém os cálculos em pandas
e o gráfico prévio. O `app.py` calcula os mesmos indicadores para o recorte
apresentado. Se não houver viagens, as médias são exibidas como “—”.

Além das barras por hora, a versão final reutiliza as duas relações exploradas
na EDA: **distância × tarifa** e **distância × duração**. Os dois gráficos de
dispersão usam até 5.000 viagens do recorte, com `random_state=42`, seguindo
a abordagem de visualização da EDA; as barras e os KPIs continuam usando
todo o recorte da amostra de 200.000 viagens.

O clique em uma barra de horário seleciona as viagens exibidas nas duas
dispersões; duplo clique limpa a seleção. As seleções internas dos gráficos não alteram os KPIs,
que permanecem calculados para o intervalo da sidebar. Essa distinção é
informada no próprio app para que os denominadores não sejam confundidos.

As dispersões permitem investigar trajetos com tarifas ou durações distintas,
sem atribuir causa, corrigir registros ou excluir extremos automaticamente.
Zeros, valores negativos e extremos que permanecem na Silver são preservados.

Fontes de conteúdo: Aula 22, slides 9 e 13–17, e enunciado da atividade.
