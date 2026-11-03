# Declaração de uso de IA

## Ferramenta e escopo

Foi utilizado o Codex nesta conversa para apoiar a implementação da prática
Streamlit. Os conteúdos de referência foram os slides das Aulas 21, 22 e 23
(Streamlit partes 1, 2 e 3), o print do enunciado e a EDA própria fornecida pelo
aluno para determinar o dataset e as variáveis. Não foram usadas fontes web
externas para definir os requisitos da atividade.

## Aula 1

A IA ajudou a clonar o repositório, guardar os materiais, executar a EDA e
preparar o esqueleto com sidebar, multiseleção, slider, containers e placeholders.
O aluno escolheu reutilizar a Silver da pipeline. O notebook foi ajustado para
exportar os dados, e o app foi testado funcionalmente. O commit e o push foram
realizados após aprovação explícita do aluno.

## Aula 2

A IA apoiou as seguintes tarefas:

- Completar o Dashboard 1 com carregamento em cache, filtro de distância, correlação de Pearson e histogramas das cinco variáveis quantitativas da EDA.
- Reutilizar a matriz de correlação e a estrutura de distribuição da EDA, mantendo as 100 classes dos histogramas e utilizando Matplotlib/Seaborn com `st.pyplot`.
- Criar os temas claro e escuro e propor a paleta amarelo `#B77900`, azul escuro `#172B43` e cinza claro `#E7EDF3`.
- Propor quatro métricas próprias para planejamento operacional e registrar suas justificativas.
- Criar o notebook com a preparação do CSV, os cálculos em pandas e um gráfico prévio de viagens por hora.
- Criar duas abas e o rascunho do Dashboard 2, com quatro KPIs e um gráfico de barras.
- Preparar inicialmente uma imagem ilustrativa do layout e, após a orientação do aluno, substituí-la por uma captura real do app em `entregas/rascunho-dashboard2.jpg`.
- Organizar o roteiro e executar os testes funcionais locais.

## Decisões do aluno

- Usar CSV no app.
- Limitar o CSV a 200.000 viagens da Silver, em vez de carregar a Silver completa.
- Usar amostra aleatória sem reposição, com `seed=42`, seguindo a abordagem da EDA.
- Aplicar o filtro de distância às duas abas.
- Exigir a apresentação da lista exata de arquivos e aprovação antes de commit e push; mensagem prevista para esta etapa: `aula 2`.

## Rascunho e capturas da tela

Inicialmente, foi gerada uma ilustração do layout com a ferramenta integrada,
sem uso de API por CLI. O aluno depois solicitou que as imagens da entrega
fossem capturas diretas da tela. A ilustração foi preservada fora do
repositório, em `../referencias/rascunho-dashboard2-gerado-anterior.jpg`.

O arquivo entregue `entregas/rascunho-dashboard2.jpg` agora é uma captura
real do Dashboard 2 no Chrome, no tema claro, com os dados da amostra. Foram
salvas também quatro capturas reais das duas abas nos temas claro e escuro.
Esses arquivos não foram gerados nem redesenhados por IA.

## Validação e responsabilidade

O app foi executado com o CSV real de 200.000 linhas. Os quatro KPIs foram
comparados com pandas. Testes funcionais com AppTest verificaram seleção de
zero, uma e duas ou mais variáveis, combinações com o slider, intervalo vazio,
correlações indefinidas, valores nulos e reutilização do cache. O notebook de
métricas foi executado sem erros.

A conferência visual no Chrome e a alternância dos temas Light e Dark foram
concluídas com autorização do aluno. Foram conferidos os gráficos e os KPIs,
as seleções de zero, uma e duas variáveis e o slider afetando ambas as abas.
O intervalo de até 24,99 milhas resultou em 198.400 viagens e KPIs recalculados.
As cinco variáveis, o intervalo completo e a preferência original de tema
System foram restaurados ao final.

O público-alvo e as métricas são propostas para revisão do aluno. O total
cobrado não deve ser interpretado como lucro. O aluno aprovou explicitamente
a lista de 12 arquivos antes do commit da Aula 2 e do push na branch main.

## Aula 3

Nesta etapa, a IA apoiou a finalização do Dashboard 2 com quatro métricas e
três visuais Altair concatenados. Foram mantidos os indicadores já propostos,
o CSV de 200.000 viagens, o carregamento em cache e a identidade visual.
As relações distância × tarifa e distância × duração foram reaproveitadas
da EDA, incluindo a seleção de até 5.000 viagens para as dispersões.

Foi implementada e verificada no Chrome a seleção cruzada por horário:
clicar em uma barra restringe as duas dispersões, e duplo clique limpa a
seleção. As seleções internas dos visuais não alteram os KPIs. Os filtros
da sidebar continuam afetando as duas abas, conforme a decisão do aluno.

A IA preparou um ambiente Python 3.12 para validar o app na versão de Python
escolhida para o deploy. As bibliotecas do app foram declaradas em
`requirements.txt`; as dependências anteriores de pipeline/EDA foram
preservadas em `requirements-pipeline.txt`. O README e o guia de reprodução
foram ajustados para distinguir esses ambientes.

Foram executados os testes de `tests/test_streamlit_aulas.py`, a checagem de
dependências e a conferência visual local. Na seleção das 10 horas, cada
dispersão exibiu 153 viagens, e o duplo clique restaurou os pontos. Os arquivos
`entregas/rascunho-dashboard1.jpg` e `entregas/rascunho-dashboard2.jpg` são
capturas reais do Chrome, sem geração ou redesenho por IA.

Também foram preparados o README com descrição, stack, sugestão de GIF e o
placeholder `[LINK DO APP]`, além do checklist de repositório. O app não inclui
autenticação. Na preparação anterior ao primeiro commit desta aula, deploy,
link real no README e teste anônimo público ainda não foram executados:
devem ocorrer após o commit e push aprovados pelo aluno, na ordem solicitada.
