from html import escape

import pandas as pd
import plotly.express as px
import psycopg
import streamlit as st

from src.dashboard import data


COLORS = ["#2563A5", "#D59316", "#138A72", "#8E63AD", "#D45C4D"]
MONTHS = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
WEEKDAYS = ["Domingo", "Segunda-feira", "Terça-feira", "Quarta-feira", "Quinta-feira", "Sexta-feira", "Sábado"]
SECTIONS = ["Visão executiva", "Panorama", "Zonas e meses", "Dias e horários", "Perfil das viagens", "Cobertura e método"]


@st.cache_data(ttl=900, max_entries=1, show_spinner=False)
def load_cached_data(queries):
    # O texto SQL faz parte da chave do cache. Alterar uma consulta invalida a copia.
    return data.load_analytics(queries)


def number(value, decimals=0):
    if pd.isna(value):
        return "—"
    return f"{value:,.{decimals}f}".replace(",", "_").replace(".", ",").replace("_", ".")


def chart(figure):
    figure.update_layout(
        font=dict(family="Arial, sans-serif", color="#172B43"),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=12, r=12, t=30, b=20),
        legend_title_text="", hoverlabel=dict(bgcolor="white"),
    )
    st.plotly_chart(figure, width="stretch", config={"displaylogo": False})


def table(frame, columns, labels):
    st.dataframe(frame[columns].rename(columns=labels), hide_index=True, width="stretch")



def executive_view(results, selected_ids):
    st.html("""<style>
    .pitch-hero{border-left:5px solid #D59316;padding:4px 0 4px 22px;margin:12px 0 26px}
    .pitch-eyebrow{font-size:12px;font-weight:700;letter-spacing:1.8px;color:#52677e;text-transform:uppercase}
    .pitch-hero h1{font-size:clamp(28px,3.4vw,46px);line-height:1.12;color:#172b43;margin:12px 0}
    .pitch-hero p{font-size:16px;color:#52677e;max-width:780px;line-height:1.6;margin:0}
    .pitch-kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:14px;margin:22px 0}
    .pitch-kpi{background:#f1f4f8;border-radius:10px;padding:18px}
    .pitch-label{font-size:12px;color:#52677e;text-transform:uppercase;letter-spacing:.6px}
    .pitch-value{font-size:clamp(23px,2.2vw,32px);font-weight:700;color:#172b43;margin-top:8px}
    .pitch-cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:16px;margin:18px 0}
    .pitch-card{border:1px solid #dce3eb;border-top:4px solid #2563a5;border-radius:10px;padding:20px;background:white}
    .pitch-card h3{font-size:19px;line-height:1.3;margin:7px 0 16px;color:#172b43}
    .pitch-card .pitch-data{font-size:24px;font-weight:700;color:#2563a5;margin:4px 0}
    .pitch-card p{font-size:13px;line-height:1.6;color:#52677e;margin:10px 0}
    .pitch-card strong{color:#172b43}
    .pitch-actions{background:#172b43;color:white;border-radius:12px;padding:22px 26px;margin:24px 0}
    .pitch-actions h3{color:white;font-size:20px;margin:0 0 14px}
    .pitch-actions p{color:#e5edf6;font-size:14px;line-height:1.6;margin:10px 0}
    </style>""")
    st.html("""<div class="pitch-hero">
        <div class="pitch-eyebrow">NYC Taxi / Estratégia / Base histórica de 2018</div>
        <h1>Onde investigar primeiro um piloto em NYC?</h1>
        <p>Uma proposta para orientar a validação de campo antes de decidir sobre a operação.</p>
    </div>""")
    st.subheader("01 / Decisão em discussão")
    st.markdown("**Quais zonas e faixas de horário devem entrar no primeiro estudo de campo?** "
                "O objetivo desta reunião é definir o foco da investigação.")
    if not selected_ids:
        st.info("Selecione zonas na barra lateral para montar a hipótese do piloto.")
        return

    zones = results["zones"].loc[results["zones"]["zone_id"].isin(selected_ids)].sort_values("trip_count", ascending=False)
    total = results["monthly"]["trip_count"].sum()
    selected_count = int(zones["trip_count"].sum())
    monthly = results["zone_monthly"].loc[results["zone_monthly"]["zone_id"].isin(selected_ids)]
    stability = monthly.groupby("zone_id", as_index=False).agg(
        months_with_trips=("trip_count", lambda counts: int(counts.gt(0).sum())),
        min_share=("share_of_month_dataset_pct", "min"),
        max_share=("share_of_month_dataset_pct", "max"),
    )
    profile = results["profile"][["zone_id", "median_fare_usd", "median_duration_minutes", "median_distance_miles"]]
    hours = results["hourly"].loc[results["hourly"]["zone_id"].isin(selected_ids)]
    peaks = hours.loc[hours.groupby("zone_id")["trips_per_observed_weekday"].idxmax(),
                      ["zone_id", "day_of_week", "pickup_hour", "trips_per_observed_weekday"]]
    proposal = zones.merge(profile, on="zone_id", validate="one_to_one").merge(
        stability, on="zone_id", validate="one_to_one").merge(peaks, on="zone_id", validate="one_to_one")
    business = results["coverage"].loc[results["coverage"]["pickup_year"].eq(data.BUSINESS_YEAR)].iloc[0]
    unknown_pct = 100 * business["unknown_pickup_zone_trips"] / total

    st.subheader("02 / Proposta inicial")
    if set(selected_ids) == {138, 132, 230}:
        st.markdown("**Investigar LaGuardia e JFK, usando Times Square como contraponto urbano.** "
                    "A hipótese compara polos com alto volume registrado e perfis distintos de viagem.")
    else:
        names = ", ".join(zones["zone_name"])
        st.markdown(f"**Investigar as zonas selecionadas:** {names}. "
                    "Comparar seu movimento e perfil de viagem antes de definir o escopo do piloto.")
    st.caption("Lista inicial: três zonas mapeadas com mais embarques no extrato. A seleção pode ser alterada na barra lateral.")

    st.subheader("03 / Evidências que sustentam a investigação")
    min_months = int(proposal["months_with_trips"].min())
    kpis = [("Embarques nas zonas", number(selected_count)),
            ("Participação no extrato", number(100 * selected_count / total, 2) + "%"),
            ("Zonas em análise", number(len(zones))),
            ("Presença mínima no ano", f"{min_months}/12 meses")]
    st.html('<div class="pitch-kpis">' + ''.join(
        f'<div class="pitch-kpi"><div class="pitch-label">{escape(label)}</div>'
        f'<div class="pitch-value">{escape(value)}</div></div>' for label, value in kpis
    ) + '</div>')
    st.caption("Seleção atual · Embarques de 2018 · Percentuais sobre todas as viagens do extrato, incluindo zonas desconhecidas.")
    cards = []
    for row in proposal.itertuples(index=False):
        day = WEEKDAYS[int(row.day_of_week) - 1]
        cards.append(f"""<div class="pitch-card">
            <div class="pitch-label">{escape(row.borough)}</div>
            <h3>{escape(row.zone_name)}</h3>
            <div class="pitch-data">{number(100 * row.trip_count / total, 2)}% do extrato</div>
            <p>{number(row.trip_count)} embarques registrados</p>
            <p>Tarifa mediana <strong>USD {number(row.median_fare_usd, 2)}</strong><br>
            Viagem mediana: <strong>{number(row.median_duration_minutes, 1)} min</strong> · {number(row.median_distance_miles, 1)} milhas</p>
            <p>Pico registrado: <strong>{day}, {int(row.pickup_hour):02d}h</strong><br>
            {number(row.trips_per_observed_weekday, 1)} embarques / dia da semana observado</p>
            <p>Presença em <strong>{int(row.months_with_trips)}/12 meses</strong></p>
        </div>""")
    st.html('<div class="pitch-cards">' + ''.join(cards) + '</div>')
    st.markdown("**Acompanhar a participação mensal ajuda a avaliar se o destaque é pontual.**")
    figure = px.line(monthly, x="month", y="share_of_month_dataset_pct", color="zone_name", markers=True,
                     color_discrete_sequence=COLORS,
                     labels={"month": "Mês de 2018", "share_of_month_dataset_pct": "% do extrato mensal", "zone_name": "Zona"})
    figure.update_xaxes(tickvals=results["monthly"]["month"], ticktext=MONTHS)
    figure.update_layout(height=340, legend=dict(orientation="h", y=-0.25, x=0))
    chart(figure)
    st.caption("A série descreve este extrato; presença mensal não comprova estabilidade de demanda ou dos picos horários.")

    st.subheader("04 / Incertezas que afetam a decisão")
    st.markdown(
        "- **Dados históricos de 2018:** atualizar a evidência antes de uma decisão atual.\n"
        "- **Cobertura não comprovada:** a seleção do extrato pode influenciar o ranking; "
        f"{number(unknown_pct, 2)}% dos embarques não têm zona identificada.\n"
        "- **Viabilidade ainda aberta:** faltam custos, oferta e demanda não atendida. "
        "Tarifa não é lucro; os horários da fonte precisam ser confirmados antes de propor escalas."
    )
    st.subheader("05 / Próximo passo e resultado esperado")
    st.html("""<div class="pitch-actions">
        <h3>Encaminhamento proposto: validar a hipótese em campo</h3>
        <p><strong>Ação:</strong> observar oferta, filas e espera nas zonas e faixas destacadas; levantar dados recentes, custos e tempos sem passageiros.</p>
        <p><strong>Entrega esperada:</strong> comparar a viabilidade das zonas e definir critérios mensuráveis para um piloto operacional.</p>
        <p><strong>Decisão solicitada nesta etapa:</strong> aprovar o escopo do estudo de campo, antes de dimensionar frota ou iniciar a operação.</p>
    </div>""")
    with st.expander("Detalhes para perguntas da equipe"):
        st.write(f"Base tratada: {number(total)} viagens de 2018. Os percentuais da proposta usam essa base completa como denominador.")
        st.write("As medianas são calculadas por zona, sem reagregação. O pico exibido é a combinação de dia e hora "
                 "com maior média de embarques por dia da semana observado; em empates, a primeira na ordem do SQL. "
                 "Não mede viagens por táxi. A consistência mensal do pico exige uma análise adicional.")
        st.write("As áreas de exploração e de cobertura mantêm comparativos, denominadores e auditoria para sustentar a apresentação.")


def panorama(results):
    st.subheader("O movimento registrado ao longo do ano")
    st.caption("Base completa de 2018 · Esta visão não muda com a seleção de zonas.")
    monthly = results["monthly"].copy()
    metric = st.radio("Comparar meses por", ["Média por dia observado", "Total de viagens"], horizontal=True)
    field = "trips_per_observed_day" if metric == "Média por dia observado" else "trip_count"
    monthly["month_label"] = monthly["month"].dt.month.map(dict(enumerate(MONTHS, start=1)))
    figure = px.bar(monthly, x="month_label", y=field, color_discrete_sequence=[COLORS[0]],
                    labels={"month_label": "Mês de 2018", field: metric},
                    hover_data={"observed_days": True, "month_label": False})
    chart(figure)
    peak = monthly.loc[monthly[field].idxmax()]
    st.info(f"{MONTHS[peak['month'].month - 1]} tem o maior valor neste comparativo: "
            f"{number(peak[field], 2 if field != 'trip_count' else 0)}. "
            "Isso descreve o extrato; não comprova sazonalidade recorrente ou crescimento do mercado.")
    st.markdown("**Por que comparar a média diária?** Meses têm quantidades diferentes de dias. "
                "O denominador usa datas com algum embarque na base, sem comprovar cobertura completa.")
    table(monthly, ["month", "trip_count", "observed_days", "calendar_days", "trips_per_observed_day"],
          {"month": "Mês", "trip_count": "Viagens", "observed_days": "Dias observados",
           "calendar_days": "Dias do calendário", "trips_per_observed_day": "Viagens / dia observado"})


def zones_and_months(results, mapped, selected_ids):
    st.subheader("Onde investigar uma operação piloto?")
    st.caption("Ranking anual · O distrito limita o ranking. As participações continuam relativas à base completa de 2018.")
    limit = st.slider("Zonas no ranking", 5, 20, 10)
    ranking = mapped.nlargest(limit, "trip_count").sort_values("trip_count")
    figure = px.bar(ranking, x="trip_count", y="zone_name", orientation="h",
                    color_discrete_sequence=[COLORS[0]],
                    labels={"trip_count": "Viagens registradas", "zone_name": "Zona de embarque",
                            "share_of_dataset_pct": "% do extrato"},
                    hover_data=["borough", "share_of_dataset_pct"])
    figure.update_layout(height=max(350, len(ranking) * 28))
    chart(figure)
    st.markdown("**Volume não é oportunidade garantida.** A concentração pode refletir a seleção do extrato. "
                "Faltam oferta concorrente, espera e pedidos não atendidos.")
    st.divider()
    st.subheader("As zonas selecionadas mantêm presença nos meses?")
    if not selected_ids:
        st.info("Selecione pelo menos uma zona na barra lateral para comparar a evolução mensal.")
        return
    selected = results["zone_monthly"].loc[results["zone_monthly"]["zone_id"].isin(selected_ids)]
    metric = st.radio("Evolução das zonas", ["Participação no extrato mensal", "Média diária de viagens"], horizontal=True)
    field = "share_of_month_dataset_pct" if metric == "Participação no extrato mensal" else "trips_per_observed_day"
    figure = px.line(selected, x="month", y=field, color="zone_name", markers=True,
                     color_discrete_sequence=COLORS,
                     labels={"month": "Mês de 2018", field: "% das viagens do mês" if field.startswith("share") else "Viagens / dia observado",
                             "zone_name": "Zona"})
    chart(figure)
    st.caption("Os 12 meses permanecem visíveis. Zero significa ausência de registros nessa combinação, "
               "sem provar ausência de demanda. Uma única série anual não comprova sazonalidade.")


def days_and_hours(results, selected_ids):
    st.subheader("Quando ocorre o movimento nas zonas selecionadas?")
    st.caption("Ano inteiro de 2018 · Horários registrados na fonte, sem conversão adicional para o horário de NYC.")
    if not selected_ids:
        st.info("Selecione pelo menos uma zona na barra lateral para ver os horários.")
        return
    hours = results["hourly"].loc[results["hourly"]["zone_id"].isin(selected_ids)]
    # Uma escala comum permite comparar o volume entre todas as zonas selecionadas.
    color_max = hours["trips_per_observed_weekday"].max()
    for zone_id in selected_ids:
        zone = hours.loc[hours["zone_id"].eq(zone_id)]
        heatmap = zone.pivot(index="day_of_week", columns="pickup_hour", values="trips_per_observed_weekday")
        heatmap = heatmap.reindex(index=[2, 3, 4, 5, 6, 7, 1], columns=range(24))
        figure = px.imshow(heatmap.to_numpy(dtype=float), x=list(range(24)),
                           y=[WEEKDAYS[i - 1] for i in heatmap.index], aspect="auto",
                           color_continuous_scale="YlGnBu", zmin=0, zmax=color_max,
                           labels={"x": "Hora registrada do embarque", "y": "Dia da semana", "color": "Viagens / dia"})
        figure.update_layout(title=zone.iloc[0]["zone_name"], height=330)
        chart(figure)
    st.info("Cada célula divide o volume por todos os dias observados daquele dia da semana, inclusive dias "
            "sem viagens na zona/hora. Não mede viagens por táxi nem demanda não atendida.")
    st.caption("Antes de definir escalas reais, confirmar o significado temporal da fonte. "
               "A consistência mensal do volume não valida a consistência mensal destes picos horários.")


def trip_profile(results, selected_ids):
    st.subheader("Tarifas maiores acompanham viagens mais longas?")
    st.caption("Perfil anual das zonas selecionadas · Valores históricos em USD · Distância em milhas.")
    if not selected_ids:
        st.info("Selecione pelo menos uma zona na barra lateral para comparar o perfil.")
        return
    selected = results["profile"].loc[results["profile"]["zone_id"].isin(selected_ids)]
    metric = st.radio("Medida para comparar", ["Tarifa (USD)", "Total cobrado (USD)", "Distância (milhas)", "Duração (minutos)"], horizontal=True, key="profile_metric")
    suffix = {"Tarifa (USD)": "fare_usd", "Total cobrado (USD)": "total_usd",
              "Distância (milhas)": "distance_miles", "Duração (minutos)": "duration_minutes"}[metric]
    values = selected.melt(id_vars="zone_name", value_vars=["avg_" + suffix, "median_" + suffix],
                           var_name="statistic", value_name="value")
    values["statistic"] = values["statistic"].map({"avg_" + suffix: "Média", "median_" + suffix: "Mediana"})
    figure = px.bar(values, x="zone_name", y="value", color="statistic", barmode="group",
                    color_discrete_sequence=COLORS, labels={"zone_name": "Zona", "value": metric, "statistic": "Estatística"})
    chart(figure)
    st.warning("Valor cobrado não é lucro. Faltam custos, oferta e identificação de veículos para estimar retorno ou tamanho de frota.")
    st.markdown("**Como ler as medidas:** zeros, negativos e extremos foram preservados. "
                "Nulos são ignorados pelos agregadores; os denominadores válidos estão na tabela. "
                "O total registrado não inclui gorjetas em dinheiro. Medianas não são somadas ou usadas para calcular uma mediana geral.")
    table(selected, ["zone_name", "trip_count", "trips_with_fare", "nonpositive_fare_trips", "trips_with_total", "nonpositive_total_trips"],
          {"zone_name": "Zona", "trip_count": "Viagens", "trips_with_fare": "Tarifas não nulas",
           "nonpositive_fare_trips": "Tarifas ≤ 0", "trips_with_total": "Totais não nulos", "nonpositive_total_trips": "Totais ≤ 0"})


def coverage_and_method(results):
    st.subheader("O que esta base permite concluir?")
    coverage = results["coverage"]
    outside = coverage.loc[coverage["pickup_year"].ne(data.BUSINESS_YEAR), "trip_count"].sum()
    st.info(f"{number(outside)} viagens com embarque fora de 2018 continuam na base e são exibidas nesta auditoria. "
            "As demais análises usam somente os embarques de 2018.")
    st.markdown("""
- **Fonte:** extrato histórico do Kaggle, tratado pela pipeline. Seu método de seleção e sua fração do universo TLC não foram comprovados.
- **Cobertura:** presença de registros nos dias não garante completude. A zona desconhecida entra nos totais, mas não identifica um local para o piloto.
- **Interpretação:** viagens realizadas mostram movimento atendido. Não medimos demanda reprimida, lucro, concorrência ou viabilidade atual.
- **Horários:** valores preservados da origem/Gold; validar a semântica temporal antes de definir escalas reais.
- **Valores extremos:** mantidos na base. Médias e medianas ajudam a comparar perfis, sem uma remoção adicional de outliers.
""")
    st.dataframe(coverage, hide_index=True, width="stretch")
    st.markdown("**Próxima decisão:** investigar em campo zonas e horários promissores, confirmar a composição "
                "do extrato e obter dados recentes, custos e informações sobre oferta. O dashboard apoia a investigação; "
                "não escolhe automaticamente onde operar.")
    st.download_button("Baixar auditoria por ano (CSV)", coverage.to_csv(index=False).encode("utf-8-sig"),
                       file_name="nyc_taxi_cobertura.csv", mime="text/csv")


def main():
    st.set_page_config(page_title="NYC Taxi | Estudo de operação piloto", page_icon="🚕", layout="wide")

    with st.sidebar:
        st.title("NYC Taxi")
        section = st.radio("Análises", SECTIONS, key="section")
        st.divider()
        refresh = st.button("Atualizar dados", width="stretch")
        st.caption("A primeira consulta pode levar alguns minutos. Os filtros reutilizam os resultados por até 15 minutos.")
    if refresh:
        load_cached_data.clear()

    try:
        queries = data.read_queries()
        with st.spinner("Consultando e validando os indicadores no PostgreSQL…"):
            results = load_cached_data(queries)
    except (psycopg.Error, OSError, ValueError):
        st.error("Não foi possível carregar indicadores consistentes do PostgreSQL.")
        st.info("Confira se o PostgreSQL está ativo, se a Gold foi carregada e se .env.postgres está configurado. "
                "Após corrigir, clique em Atualizar dados. Nenhuma credencial é exibida neste painel.")
        st.stop()

    business = results["coverage"].loc[results["coverage"]["pickup_year"].eq(data.BUSINESS_YEAR)].iloc[0]
    mapped = results["zones"].loc[results["zones"]["is_mapped_zone"]].copy()
    all_count = int(business["trip_count"])
    # Duas colunas preservam os numeros completos em janelas menores.
    if section != "Visão executiva":
        st.markdown("**NYC TAXI / EXPLORAR INDICADORES**")
        st.title(section)
        st.caption("Ano de embarque: 2018 · Base completa nos indicadores gerais.")
        first_row = st.columns(2)
        first_row[0].metric("Viagens registradas", number(all_count))
        first_row[1].metric("Dias observados", number(business["observed_days"]))
        second_row = st.columns(2)
        second_row[0].metric("Zonas identificadas", number(len(mapped)))
        second_row[1].metric("Embarques sem zona", number(100 * business["unknown_pickup_zone_trips"] / all_count, 2) + "%")
        st.caption("Indicadores acima: base completa de 2018, incluindo zonas desconhecidas. Não representam todo o mercado de NYC.")
        st.divider()

    with st.sidebar:
        st.divider()
        st.subheader("Explorar zonas")
        borough = st.selectbox("Distrito para explorar", ["Todos"] + sorted(mapped["borough"].unique()), key="borough")
        if borough != "Todos":
            mapped = mapped.loc[mapped["borough"].eq(borough)]
        names = mapped.set_index("zone_id").apply(lambda row: row["zone_name"] + " · " + row["borough"], axis=1).to_dict()
        options = mapped.sort_values(["trip_count", "zone_id"], ascending=[False, True])["zone_id"].tolist()
        selected_ids = st.multiselect("Zonas para comparar (até 5)", options, default=options[:3],
                                      format_func=lambda zone_id: names[zone_id], max_selections=5,
                                      key="zones_" + borough)
        st.caption("A seleção altera os comparativos. O distrito também limita o ranking de zonas. "
                   "O panorama e os indicadores gerais permanecem sobre a base completa.")
        st.divider()
        st.caption("Consulta concluída: " + results["loaded_at"].strftime("%d/%m/%Y às %H:%M:%S") + " (Brasília). "
                   "Este é o horário da consulta, não da atualização da fonte.")

    if section == "Visão executiva":
        executive_view(results,selected_ids)
    elif section == "Panorama":
        panorama(results)
    elif section == "Zonas e meses":
        zones_and_months(results, mapped, selected_ids)
    elif section == "Dias e horários":
        days_and_hours(results, selected_ids)
    elif section == "Perfil das viagens":
        trip_profile(results, selected_ids)
    else:
        coverage_and_method(results)
    st.divider()
    st.caption("Estudo de operação piloto · 2018 · Fonte: extrato NYC Taxi do Kaggle · Valores cobrados não representam lucro.")


if __name__ == "__main__":
    main()
