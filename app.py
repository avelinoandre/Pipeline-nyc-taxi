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
    st.write("### Perfil operacional — rascunho")
    st.write("Público proposto: equipe de planejamento operacional de táxis.")
    st.write("Os indicadores descrevem a amostra; não representam os totais da Silver completa.")
    st.write("Os quatro indicadores usam o mesmo intervalo de distância do Dashboard 1.")

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
        por_hora = (
            df.groupby(df["pickup_datetime"].dt.hour)
            .size()
            .reindex(range(24), fill_value=0)
        )
        fig, ax = plt.subplots(figsize=(12, 4), facecolor="white")
        ax.bar(por_hora.index, por_hora.values, color=AMARELO, edgecolor=AZUL, linewidth=0.4)
        ax.set_title("Viagens por hora de embarque")
        ax.set_xlabel("Hora de embarque (horário registrado na fonte)")
        ax.set_ylabel("Quantidade de viagens")
        ax.set_xticks(range(24))
        preparar_eixos(ax)
        fig.tight_layout()
        st.pyplot(fig)
        plt.close(fig)
        st.write("A contagem descreve viagens registradas; não mede demanda não atendida.")
