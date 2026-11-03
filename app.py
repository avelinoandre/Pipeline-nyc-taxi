import streamlit as st

st.set_page_config(page_title="Dashboard 1 — NYC Taxi", layout="wide")

st.title("Dashboard 1 — NYC Taxi")
st.write("Esqueleto de análise de correlação e distribuição das variáveis quantitativas.")

# Cada interação executa novamente o script inteiro, do topo.
with st.sidebar:
    st.write("Filtros")
    variaveis = st.pills(
        "Variáveis para a correlação",
        options=[
            "trip_distance",
            "fare_amount",
            "trip_duration_minutes",
            "tip_amount",
            "total_amount",
        ],
        selection_mode="multi",
        default=[
            "trip_distance",
            "fare_amount",
            "trip_duration_minutes",
            "tip_amount",
            "total_amount",
        ],
    )
    intervalo = st.slider(
        "Intervalo de avaliação — escala provisória",
        min_value=0,
        max_value=100,
        value=(0, 100),
    )
    st.write("O intervalo é ilustrativo; ainda não está ligado aos valores de uma variável.")

# Os widgets apenas registram escolhas nesta etapa.
with st.container():
    st.write("Variáveis selecionadas:", variaveis)
    st.write("Intervalo selecionado:", intervalo)

correlacao, distribuicao = st.columns(2)

with correlacao:
    with st.container():
        st.write("### Correlação")
        st.write("Espaço reservado para a matriz de correlação na próxima aula.")

with distribuicao:
    with st.container():
        st.write("### Distribuição")
        st.write("Espaço reservado para os histogramas na próxima aula.")

with st.container():
    st.write("### Prévia dos dados")
    st.write("Tabela vazia: o carregamento e o tratamento de dados serão conectados depois.")
    st.dataframe([])
