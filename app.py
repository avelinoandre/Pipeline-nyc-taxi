import altair as alt
import matplotlib

# Renderização estática para Streamlit, sem abrir janelas do Matplotlib.
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
import pandas as pd
import seaborn as sns
import streamlit as st

st.set_page_config(page_title="NYC Taxi — Dashboards", layout="wide")

QUANTITATIVAS = [
    "trip_distance", "fare_amount", "trip_duration_minutes",
    "tip_amount", "total_amount",
]
ROTULOS = {
    "trip_distance": "Distância (milhas)",
    "fare_amount": "Tarifa (USD)",
    "trip_duration_minutes": "Duração (min)",
    "tip_amount": "Gorjeta (USD)",
    "total_amount": "Total cobrado (USD)",
}
AMARELO = "#B77900"
AZUL = "#172B43"
CINZA = "#E7EDF3"
PALETA_CORRELACAO = LinearSegmentedColormap.from_list(
    "taxi", [AZUL, CINZA, AMARELO]
)


@st.cache_data
def carregar_dados():
    # O cache evita reler o CSV a cada interação.
    return pd.read_csv(
        "data/clean/dataset.csv",
        usecols=QUANTITATIVAS + ["pickup_datetime"],
        parse_dates=["pickup_datetime"],
    )


def preparar_eixos(ax):
    ax.set_facecolor("white")
    ax.tick_params(colors=AZUL)
    ax.xaxis.label.set_color(AZUL)
    ax.yaxis.label.set_color(AZUL)
    ax.title.set_color(AZUL)


def visuais_operacionais(recorte):
    # A contagem usa todo o recorte; as dispersões seguem a amostra da EDA.
    por_hora = (
        recorte.groupby(recorte["pickup_datetime"].dt.hour)
        .size().reindex(range(24), fill_value=0)
        .rename_axis("hora_embarque").reset_index(name="viagens")
    )
    pontos = recorte[[
        "trip_distance", "fare_amount", "trip_duration_minutes", "pickup_datetime"
    ]].sample(n=min(5_000, len(recorte)), random_state=42)
    pontos = pontos.assign(hora_embarque=pontos["pickup_datetime"].dt.hour)
    pontos = pontos.drop(columns="pickup_datetime")
    # As duas fontes usam a mesma representação categórica na seleção.
    por_hora["hora_embarque"] = por_hora["hora_embarque"].astype(str)
    pontos["hora_embarque"] = pontos["hora_embarque"].astype(str)

    hora = alt.selection_point(
        name="hora_selecionada", fields=["hora_embarque"],
        toggle=False, clear="dblclick", empty=True,
    )
    barras = alt.Chart(por_hora).mark_bar().encode(
        x=alt.X("hora_embarque:O", title="Hora de embarque", sort=[str(h) for h in range(24)]),
        y=alt.Y("viagens:Q", title="Quantidade de viagens"),
        color=alt.condition(hora, alt.value(AMARELO), alt.value(CINZA)),
        tooltip=[
            alt.Tooltip("hora_embarque:O", title="Hora"),
            alt.Tooltip("viagens:Q", title="Viagens", format=","),
        ],
    ).add_params(hora).properties(
        title="1. Viagens por hora — recorte completo", width=740, height=140
    )

    base = alt.Chart(pontos).mark_circle(color=AMARELO, opacity=0.45, size=24).encode(
        x=alt.X("trip_distance:Q", title="Distância (milhas)", scale=alt.Scale(zero=False)),
        tooltip=[
            alt.Tooltip("hora_embarque:O", title="Hora"),
            alt.Tooltip("trip_distance:Q", title="Distância (milhas)", format=".2f"),
            alt.Tooltip("fare_amount:Q", title="Tarifa (USD)", format=".2f"),
            alt.Tooltip("trip_duration_minutes:Q", title="Duração (min)", format=".2f"),
        ],
    ).transform_filter(hora)
    tarifa = base.encode(
        y=alt.Y("fare_amount:Q", title="Tarifa (USD)", scale=alt.Scale(zero=False))
    ).properties(
        title="2. Distância × tarifa", width=350, height=200
    )
    duracao = base.encode(
        y=alt.Y("trip_duration_minutes:Q", title="Duração (min)", scale=alt.Scale(zero=False))
    ).properties(
        title="3. Distância × duração", width=350, height=200
    )
    return alt.vconcat(barras, alt.hconcat(tarifa, duracao)).resolve_scale(x="independent")


dados = carregar_dados()
st.title("NYC Taxi — Análise das viagens")
st.write("Amostra de 200 mil viagens históricas de táxi. Explore relações e o perfil operacional.")

with st.sidebar:
    st.write("### Filtros")
    variaveis = st.pills(
        "Variáveis quantitativas — Dashboard 1",
        options=QUANTITATIVAS,
        selection_mode="multi",
        default=QUANTITATIVAS,
    )
    intervalo = st.slider(
        "Distância da viagem (milhas)",
        min_value=float(dados["trip_distance"].min()),
        max_value=float(dados["trip_distance"].max()),
        value=(
            float(dados["trip_distance"].min()),
            float(dados["trip_distance"].max()),
        ),
    )
    st.write("A distância filtra as duas abas, incluindo os limites selecionados.")
    st.write("A seleção de variáveis altera somente a correlação e as distribuições.")

# Os filtros e os cálculos abaixo são refeitos a cada interação.
df = dados.loc[dados["trip_distance"].between(intervalo[0], intervalo[1])]
st.write(f"Viagens no intervalo: {len(df):,} de {len(dados):,}.")
aba1, aba2 = st.tabs(["Dashboard 1 — Correlação e distribuição", "Dashboard 2 — Perfil operacional"])

with aba1:
    if not variaveis:
        st.info("Selecione uma ou mais variáveis quantitativas na barra lateral.")
    elif df.empty:
        st.info("Nenhuma viagem no intervalo. Amplie o filtro de distância.")
    else:
        correlacao, distribuicao = st.columns(2)
        with correlacao:
            with st.container():
                st.write("### Correlação")
                if len(variaveis) < 2:
                    st.info("Selecione pelo menos duas variáveis para comparar correlações.")
                else:
                    # Mesma correlação de Pearson e heatmap usados na EDA.
                    matriz = df[variaveis].corr()
                    if matriz.isna().any().any():
                        st.write("Correlações sem variação ou sem pares válidos ficam indefinidas.")
                    if matriz.notna().any().any():
                        fig, ax = plt.subplots(figsize=(7, 6), facecolor="white")
                        sns.heatmap(
                            matriz.rename(index=ROTULOS, columns=ROTULOS),
                            annot=True, fmt=".2f", cmap=PALETA_CORRELACAO,
                            center=0, vmin=-1, vmax=1, ax=ax,
                        )
                        ax.set_title("Correlação de Pearson")
                        preparar_eixos(ax)
                        fig.tight_layout()
                        st.pyplot(fig)
                        plt.close(fig)
                    else:
                        st.info("O recorte não tem variação suficiente para calcular correlações.")
        with distribuicao:
            with st.container():
                st.write("### Distribuição")
                # Mantém as variáveis e as 100 classes dos histogramas da EDA.
                for variavel in variaveis:
                    valores = df[variavel].dropna()
                    if valores.empty:
                        st.info(f"Sem valores válidos para {ROTULOS[variavel]}.")
                    else:
                        fig, ax = plt.subplots(figsize=(7, 3), facecolor="white")
                        ax.hist(valores, bins=100, color=AMARELO, edgecolor=AZUL, linewidth=0.3)
                        ax.set_title(f"Distribuição de {ROTULOS[variavel]}")
                        ax.set_xlabel(ROTULOS[variavel])
                        ax.set_ylabel("Quantidade de viagens")
                        preparar_eixos(ax)
                        fig.tight_layout()
                        st.pyplot(fig)
                        plt.close(fig)
        with st.container():
            st.write("### Prévia do recorte — até 10 viagens")
            st.dataframe(df[variaveis].head(10))

with aba2:
    st.write("### Perfil operacional")
    st.write("Para a equipe de planejamento operacional. Os indicadores descrevem a amostra "
             "no intervalo de distância escolhido, sem representar os totais da Silver completa.")

    # Os mesmos cálculos são apresentados no notebook de métricas.
    viagens = len(df)
    distancia_media = df["trip_distance"].mean()
    duracao_media = df["trip_duration_minutes"].mean()
    valor_medio = df["total_amount"].mean()
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    with kpi1:
        st.metric("Viagens avaliadas", f"{viagens:,}")
    with kpi2:
        st.metric("Distância média (milhas)", "—" if pd.isna(distancia_media) else f"{distancia_media:.2f}")
    with kpi3:
        st.metric("Duração média (min)", "—" if pd.isna(duracao_media) else f"{duracao_media:.2f}")
    with kpi4:
        st.metric("Total médio cobrado (USD)", "—" if pd.isna(valor_medio) else f"{valor_medio:.2f}")
    st.write("O total cobrado não representa lucro. As médias ignoram nulos de cada medida.")

    if df.empty:
        st.info("Nenhuma viagem no intervalo. Amplie o filtro para visualizar os horários.")
    else:
        st.write("Clique em uma barra para filtrar as duas dispersões por hora. "
                 "Duplo clique limpa a seleção. Essa seleção afeta os visuais; "
                 "os KPIs seguem o filtro da barra lateral.")
        st.altair_chart(visuais_operacionais(df), width="stretch")
        st.write("Barras: todas as viagens do recorte. Dispersões: até 5.000 viagens "
                 "selecionadas com seed=42, como na EDA. Hora registrada na fonte. "
                 "A contagem não mede demanda não atendida.")
