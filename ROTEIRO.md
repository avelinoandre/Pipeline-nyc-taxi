# Roteiro da prática Streamlit

Roteiro local organizado a partir dos três slides fornecidos e do enunciado.

## Aula 1 — esqueleto

1. Copiar a EDA para `notebooks/`.
2. Atualizar o notebook para salvar os dados originais e tratados.
3. Desenhar o layout do Dashboard 1.
4. Criar o `app.py` com sidebar, seletor de variáveis, slider e espaços para correlação e distribuição.
5. Fazer commit e push da entrega da aula.

## Aula 2 — Dashboard 1 e rascunho do Dashboard 2

1. Organizar `entregas/`, `prompts/` e este roteiro.
2. Carregar os dados com `st.cache_data` e caminho relativo.
3. Aplicar identidade visual coerente aos temas e gráficos.
4. Completar correlação e distribuições, recalculadas conforme os filtros.
5. Testar zero variáveis, uma variável, duas ou mais e combinações dos widgets.
6. Propor de três a cinco métricas e registrar as justificativas.
7. Testar cálculos e fazer um gráfico prévio no notebook.
8. Criar as duas abas e rascunhar o Dashboard 2 com KPIs e um gráfico de barras agrupado.
9. Salvar `entregas/rascunho-dashboard2.jpg`.
10. Atualizar `prompts/declaracao-uso-ia.md`.
11. Mostrar a lista exata de arquivos e aguardar aprovação do aluno antes do commit.
12. Fazer commit com a mensagem `aula 2` e push na `main`.

## Aula 3 — conclusão e publicação

1. Finalizar o Dashboard 2 com três a cinco métricas e três visuais além delas.
2. Conferir execução local, dependências, caminhos relativos, dados tratados versionados e ausência de dados sensíveis.
3. Publicar no Streamlit Community Cloud e colocar o link no README.
4. Testar o app publicado em janela anônima, widgets e abas.
5. Conferir os rascunhos dos dois dashboards, justificativas e declaração de IA.

## Testes de widgets da Aula 2

- Zero variáveis: mostrar orientação; não tentar calcular uma correlação vazia.
- Uma variável: apresentar seu histograma e explicar que a correlação entre variáveis exige duas ou mais.
- Duas ou mais variáveis: apresentar a matriz de correlação e um histograma para cada variável selecionada.
- Alterar o intervalo: conferir que a base avaliada e os visuais correspondem ao novo recorte.
- Combinar seleção de variáveis e intervalo: conferir o recálculo sem erros.
- Intervalo sem viagens: apresentar orientação sem tentar desenhar gráficos vazios.
- Variável constante no recorte: explicar a correlação indefinida.

`data/raw/` e `secrets.toml` permanecem fora do commit.

## Executar a versão desta entrega

Na raiz do repositório, com as dependências de `requirements.txt` disponíveis:

```bash
streamlit run app.py
```

O app lê `data/clean/dataset.csv`: amostra aleatória de 200.000 linhas da Silver,
com `seed=42`, aprovada pelo aluno. O CSV é incluído na entrega. O notebook
`notebooks/03_metricas_streamlit.ipynb` documenta a geração a partir dos
Parquets completos, calcula os quatro KPIs e faz o gráfico prévio.

O slider de distância afeta as duas abas; o seletor de variáveis afeta somente
os gráficos de correlação e distribuição. Com duas ou mais variáveis e dados
válidos, o Dashboard 1 mostra um heatmap e um histograma por variável. Com uma
variável mostra o histograma e explica a necessidade de duas para correlação.

## Validação realizada nesta etapa

- CSV real: 200.000 linhas, duas abas, quatro KPIs reconciliados com pandas e sete gráficos (heatmap, cinco histogramas e barras).
- Seleção vazia: orientação no Dashboard 1 e KPIs do Dashboard 2 preservados.
- Uma variável: histograma, sem tentativa de correlação entre variáveis.
- Duas variáveis: heatmap e dois histogramas.
- Seleção de variáveis combinada com distância: recálculo da correlação e dos KPIs conferido.
- Intervalo inclusivo: valores nos limites entram na avaliação.
- Intervalo sem registros: orientações, contagem zero e médias “—”, sem gráficos vazios.
- Variáveis constantes: correlações indefinidas explicadas.
- Coluna inteiramente nula: aviso em vez de histograma vazio.
- Cache: uma leitura do CSV durante as interações de teste.
- Notebook de métricas: quatro células de código executadas sem erros.

Os testes funcionais foram executados localmente com AppTest do Streamlit.
Também foram usados dados controlados para conferir os casos extremos.
Não houve publicação nesta etapa.

## Conferência visual concluída no Chrome

Foi aberto o app local em `http://127.0.0.1:8502/`, com o CSV real de 200.000
viagens. Foram conferidos os temas Light e Dark pelo menu do Streamlit, as duas
abas, os gráficos, os quatro KPIs e a tabela. A rolagem permite ver os cinco
histogramas e o gráfico de barras completo. Os gráficos mantêm fundo branco
e a mesma paleta nos dois temas.

Também foram testadas na interface as seleções de zero, uma e duas variáveis.
O slider foi alterado para 0,01–24,99 milhas: o recorte passou a 198.400 viagens,
com distância média de 8,92 milhas, duração média de 32,89 minutos e total médio
cobrado de USD 39,85. Ao restaurar o intervalo, os KPIs voltaram a 200.000
viagens, 9,09 milhas, 33,13 minutos e USD 40,52. Ao final, as cinco variáveis e
o intervalo completo foram restaurados, assim como a preferência original de
tema System.

Capturas reais obtidas diretamente do navegador, sem geração de imagem:

- `entregas/dashboard1-tema-claro.jpg`
- `entregas/dashboard1-tema-escuro.jpg`
- `entregas/dashboard2-tema-claro.jpg`
- `entregas/dashboard2-tema-escuro.jpg`

`entregas/rascunho-dashboard2.jpg` foi substituído pela captura real do
Dashboard 2 no tema claro. A ilustração gerada anteriormente foi preservada
fora do repositório, em `../referencias/rascunho-dashboard2-gerado-anterior.jpg`.

## Aula 3 — versão final e publicação

O Dashboard 2 mantém os quatro KPIs e agora contém três visuais Altair
concatenados: viagens por hora, distância × tarifa e distância × duração.
Clique em uma barra para restringir as duas dispersões à mesma hora e dê
duplo clique para limpar a seleção. Os KPIs seguem o intervalo da sidebar.
As dispersões usam até 5.000 viagens do recorte, com `random_state=42`,
como na EDA; as barras e os KPIs usam todo o recorte da amostra de 200.000.

O app foi validado em Python 3.12 com as versões de `requirements.txt`. As
dependências anteriores da pipeline e dos notebooks foram preservadas em
`requirements-pipeline.txt`; o guia `docs/REPRODUCING.md` foi ajustado.

Execute os testes específicos da aplicação na raiz do projeto:

```bash
python -m unittest discover -s tests -p test_streamlit_aulas.py -v
```

Os testes verificam a base real, os quatro KPIs, os três visuais, a seleção de
zero/uma/duas variáveis, recálculo pelo intervalo, cache e recorte sem viagens.
No Chrome, a seleção das 10 horas restringiu as duas dispersões a 153 viagens
cada, e o duplo clique restaurou os pontos. O teste visual e os dois prints
foram feitos no app local com Python 3.12, na porta 8503.

- `entregas/rascunho-dashboard1.jpg`: print real com distância e tarifa selecionadas, heatmap e dois histogramas.
- `entregas/rascunho-dashboard2.jpg`: print real com quatro KPIs e três visuais.
- `entregas/checklist-aula3.md`: estado da checagem antes do primeiro commit e do deploy.

O primeiro commit precisa ser aprovado pelo aluno, usar a mensagem exata
`aula 3` e ser enviado à `main` antes do deploy. O README mantém `[LINK DO APP]`
até a publicação real. Depois do deploy, o link real deve ser preenchido,
novamente aprovado, commitado com `aula 3` e enviado à `main`. O teste anônimo
do app publicado será feito somente após essas etapas. Prints do teste
publicado não devem entrar no commit sem novo pedido do aluno.
