# Aula 3 — checagem anterior ao primeiro commit e ao deploy

Este registro descreve a preparação local. Não equivale a uma validação do
app publicado. A ordem solicitada exige aprovação do aluno antes do primeiro
commit `aula 3`; o deploy vem depois do push.

## Repositório

- [ ] **git status limpo e push da Aula 3:** ainda pendentes da aprovação do aluno. Há alterações locais prontas para revisão; o último push concluído é o da Aula 2.
- [x] **Repositório público:** a API do GitHub retornou `private: false` para `avelinoandre/Pipeline-nyc-taxi`, branch padrão `main`.
- [x] **app.py na raiz e execução local:** AppTest e Chrome executaram a aplicação em Python 3.12 sem erro na versão final.
- [x] **CSV tratado versionado:** `git ls-files data/clean` inclui `data/clean/dataset.csv` e os nove Parquets preservados da Aula 1.
- [x] **Caminhos portáveis:** o app usa `data/clean/dataset.csv`; novos testes derivam os caminhos da raiz do projeto. Não há caminho fixo de máquina no código do app ou nos notebooks de entrega.
- [x] **Dependências:** `requirements.txt` declara Streamlit, Altair, pandas, Matplotlib e Seaborn nas versões testadas; `pip check` não encontrou conflitos. As dependências da pipeline/EDA estão preservadas em `requirements-pipeline.txt`.
- [x] **Arquivos sensíveis fora do versionamento:** `.env`, `.env.postgres`, `data/raw/` e `secrets.toml` estão ignorados; a verificação de arquivos rastreados não encontrou esses arquivos.
- [x] **Identidade visual versionada:** `.streamlit/config.toml` já é rastreado e mantém os temas claro e escuro. A configuração de endereço/porta fixa foi retirada para permitir a configuração do ambiente de publicação.

## Conteúdo local

- [x] Dashboard 1: correlação quantitativa e um histograma por variável selecionada.
- [x] Dashboard 2: quatro `st.metric` e três visuais Altair concatenados.
- [x] Seleção cruzada: barra das 10 horas restringiu as duas dispersões a 153 viagens cada; duplo clique restaurou os 5.000 pontos em cada uma.
- [x] Filtros e casos extremos: seleção vazia, uma/duas variáveis, intervalo combinado, cache e recorte sem registros verificados em testes locais.
- [x] Prints reais: `rascunho-dashboard1.jpg` e `rascunho-dashboard2.jpg` em `entregas/`.
- [x] Justificativa das métricas e declaração de IA atualizadas.
- [x] README com descrição, relevância, stack e sugestão de gravação/GIF.

O CSV tem 21.677.815 bytes, aproximadamente 21,7 MB, e contém a amostra
aprovada de 200.000 viagens. O app lê somente as seis colunas necessárias.
As barras e os KPIs usam todo o recorte; as dispersões usam até 5.000 viagens.
Isso reduz a carga de visualização sem alterar os indicadores do recorte.

## Publicação e teste anônimo — ainda não executados

- [ ] Primeiro commit `aula 3` e push aprovados pelo aluno.
- [ ] Deploy público no Streamlit Community Cloud, com Python 3.12.
- [ ] Link real no README, substituindo `[LINK DO APP]`.
- [ ] Aprovação do commit do README, mensagem `aula 3` e push.
- [ ] Aplicação publicada abre em janela anônima.
- [ ] Todos os widgets respondem na aplicação publicada.
- [ ] Duas abas carregam na aplicação publicada.
- [ ] Interface publicada conferida quanto a secrets, dados brutos e informações pessoais.
- [ ] Link do app conferido no README público.

Os prints dessa futura validação pública ficarão fora do commit, salvo pedido
posterior do aluno. Nenhum item público acima foi marcado como feito antes
de sua execução real.
