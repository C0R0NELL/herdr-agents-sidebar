# herdr-agents-sidebar

Especificação para outro agente implementar. Atualizada em 11/10/2026.

**Estado:** implementação local, com provas isoladas em Herdr 0.9.3. Ativado no ambiente principal por solicitação posterior do usuário em 10/10/2026, usando o checkout e a identidade oficial. Primeira versão `0.1.0` aprovada e publicação pública no GitHub autorizada em 11/10/2026. Os resultados e limites estão em `docs/viabilidade.md`.

## 1. Objetivo e decisões do usuário

Organizar visualmente a seção nativa de agentes, oferecendo **Grouped**
(Máquina → Projeto → Agente por padrão) e **Priority** (duas linhas por agente
por padrão), com contexto configurável, sem alterar
o código ou fazer fork do Herdr.

Formato escolhido:

```text
machine01
  projeto01
     · ○ agente01
     · ○ agente02
  projeto02
     · ○ agente03
machine02
  projeto01
     · ○ agente01
  projeto02
     · ○ agente03
```

Regras visuais:

- Máquina: sem marcador, amarelo (`#f1fa8c`) e negrito por padrão; aparece uma vez por bloco.
- Projeto: sem marcador, azul (`#89b4fa`) e negrito por padrão; aparece uma vez por projeto dentro da máquina, com duas células de recuo em relação à máquina.
- Agente: nome sem marcador `>`, roxo (`#bd93f9`) por padrão e indicador de estado nativo antes do nome, sem copiar estados para tokens próprios. Compensar o recuo antes do ícone para que ele e os nomes fiquem alinhados mesmo nas entradas sem cabeçalhos. O Herdr acrescenta um ponto inline antes do ícone, formando `· ○ nome`; em 11/10/2026 o usuário aceitou esse ponto para corrigir o desalinhamento.
- Quando Show separator está ligada, uma linha contendo somente `·` entre máquinas, na mesma cor do cabeçalho da máquina imediatamente acima. A opção começa desligada; escolhas já salvas são preservadas. Não inserir linhas em branco nem separadores entre projetos/agentes. Em 10/10/2026, o usuário aceitou que o ponto permaneça ao final quando outro cliente mostra menos máquinas: os tokens são compartilhados no servidor, enquanto o catálogo é do cliente.
- Não acrescentar um nível para tabs, controles de expansão ou ícones que exijam
  fontes especiais. A aba (Tab) pode aparecer como contexto inline quando
  selecionada em View, conforme pedido posterior do usuário em 11/10/2026.
- Em 11/10/2026, o usuário pediu remover todos os `>` e inicialmente o ponto inline antes do ícone. Após reproduzir o desalinhamento dos ícones sem esse ponto, aprovou manter o ponto inline para alinhá-los. Todos os `>` continuam removidos. O ponto opcional entre máquinas continua separado dessa decisão.
- Em 11/10/2026, após experimentar as cores em Settings, o usuário definiu Default como Machine = Yellow, Project = Blue e Agent = Purple, nos tons já oferecidos pelo menu. Isso substitui as propostas intermediárias. Não alterar o tema global nem as cores de status do Herdr; escolhas explícitas em Settings continuam preservadas.
- Em 11/10/2026, o usuário pediu Mode como primeira opção de Settings, com
  Grouped/Priority. Grouped mantém a árvore já aprovada. Priority inicialmente
  colocou status/projeto acima e IA abaixo. Um snapshot posterior usou Project
  na primeira linha e Status/Agent/Tab na segunda; o mais recente substitui esse
  default por Project/Machine na primeira e Status/Agent na segunda.
  Preservar as cores de projeto e agente e o status nativo. Esse formato foi
  escolhido pelo usuário em 11/10/2026. Não renderizar cabeçalhos separados,
  recuos de árvore ou separadores entre máquinas nesse modo. Show separator
  continua salva e volta a valer ao retornar para Grouped.
- Em 11/10/2026, o usuário pediu View por modo e inicialmente propôs presets
  cumulativos. O pedido mais recente substitui esses presets: **Grouped** oferece
  somente Agent ou Agent / Tab, mantendo sempre a árvore Máquina → Projeto → Agente.
  Tab aparece após o nome do agente, na mesma linha e sem um nível novo.
- **Priority** permite montar as duas linhas de cada agente com os campos Status,
  Agent, Tab, Machine e Project. O usuário decide quais mostrar, em qual linha e
  em qual ordem; cada campo pode aparecer uma vez. O indicador Status é o token
  nativo, incluindo suas cores e estados, e pode ser movido ou escondido. Exigir
  pelo menos um campo no conjunto; uma linha vazia é omitida. Manter o layout
  padrão do snapshot mais recente (Project/Machine acima, Status/Agent abaixo), sem impor presets.
- As quatro cores (Machine, Project, Agent e Tab) são independentes por modo.
  Tab começa em Dark blue (`#6272a4`), conforme pedido posterior do usuário;
  os três defaults anteriores continuam iguais.
  Usar o token nativo `tab`, sem copiar o título da aba ou criar agrupamentos.
- Em pedido posterior em 11/10/2026, o usuário substituiu o seletor Mode por
  duas abas **Grouped | Priority** dentro de Settings. Cada aba tem **Active**,
  View e suas próprias cores. Navegar entre abas não ativa o modo. Só um modo
  pode estar ativo: colocar Active em Yes desativa o outro. Em pedido posterior,
  o usuário permitiu os dois em No: desativar o modo ativo restaura a sidebar
  nativa, sem ativar o outro nem apagar preferências. Show separator fica na aba Grouped, pois só esse layout
  permite um separador entre blocos de máquinas. As configurações de organização
  continuam correspondendo aos layouts nativos já aprovados.
- A escolha de Mode é manual e altera somente o visual do plugin. O usuário
  escolhe a ordem Grouped/Priority no próprio Herdr separadamente. A API 0.9.3
  não expõe a escolha atual por janela; não ler arquivos privados do cliente,
  instalar projeções para sincronizar ou modificar `ui.agent_panel_sort`.
  O plugin suporta os dois modos; a dependência da ordem nativa Grouped vale
  somente para a árvore Grouped. As linhas de Priority carregam seu contexto
  por agente e funcionam nas duas ordens nativas. A escolha em Settings não muda
  o botão de ordenação no Herdr.
- O usuário inicialmente pediu ativação automática após instalar e remover Apply do menu.
  Na baseline 0.9.3, install/link/enable não executam startup e não há hook de
  pós-instalação. Usar startup e eventos nativos de navegação/agentes para aplicar
  sem uma ação extra no Plugin Manager. Na sessão aberta, isso acontece na primeira
  atividade correspondente após o registro; uma instalação offline aplica ao iniciar
  o Herdr. Não prometer execução síncrona ao retornar o instalador nessa baseline.
  A ativação pode assumir um layout composto somente de tokens nativos, com recibo
  reversível; projeções/tokens de terceiros e mudanças posteriores permanecem
  protegidos. Em pedido posterior, substituiu a ativação inicial automática:
  a instalação nova deixa o plugin habilitado no Herdr, com ambos Active = No.
  O usuário deve abrir Settings e escolher o modo colocando-o em Yes. Startup e
  eventos respeitam essa escolha, sem ativar os modos pausados. Atualizações e
  reinstalações preservam preferências e ativação existentes.
- Em 11/10/2026, o usuário pediu adotar seus perfis atuais como snapshot de
  fábrica portátil: Grouped com a árvore fixa, View Agent e Show separator Off;
  Priority com Project na linha 1 e Status/Agent/Tab na linha 2. As cores default
  nos dois modos continuam Yellow, Blue, Purple e Dark blue. Ambos começam em No.
  Restore defaults deve restaurar exatamente esse snapshot e a sidebar nativa;
  Restart sidebar apenas recarrega o worker e preserva perfis e ativação.
- Em pedido posterior em 11/10/2026, o usuário pediu salvar sua configuração
  atual como novo snapshot, mantendo as imagens e o README existentes. Grouped
  mantém View Agent, Show separator Off e as quatro cores Default. Priority passa
  a usar Project/Machine na linha 1, Status/Agent na linha 2 e Machine em Dark blue;
  as outras três cores continuam Default. Esse snapshot substitui o anterior
  para novas instalações e Restore defaults, mantendo ambos Active em No.
  Configurações já salvas continuam preservadas.
- Em pedido posterior em 11/10/2026, o usuário esclareceu que Restore defaults
  e colocar ambos Active em No devem usar o layout nativo padrão completo do
  Herdr, incluindo Machine. Remover os overrides próprios de Rows e Row gap,
  em vez de recuperar uma personalização antiga somente com tokens nativos que
  escondia a máquina. Não alterar ordenação, tema ou atalhos; recusar layouts de
  terceiros. Disable/unlink/uninstall e falhas continuam usando a restauração
  reversível da configuração anterior, preservando mudanças posteriores.

**Recolhimento está fora do escopo.** Não implementar gavetas, filtros para simular recolhimento, cliques em cabeçalhos ou uma alternativa em painel próprio. O usuário quer agrupamento visual dentro da sidebar nativa.

O projeto chama-se `herdr-agents-sidebar`; identificador oficial: `c0r0nell.agents-sidebar`.

Não modificar fontes, executável ou arquivos internos do Herdr. A ativação local foi autorizada pelo usuário após as provas isoladas; não reiniciar o Herdr principal para instalar ou testar. Não alterar projetos, configurar SSH/Tailscale, instalar fontes ou ler credenciais de agentes. Commit, push e publicação pública da primeira versão `0.1.0` foram autorizados em 11/10/2026.

## 2. Caminho técnico comprovado e limites

Baseline examinada: **Herdr 0.9.3, protocolo 22**. Usar o CLI, schema e documentação da versão instalada como autoridade; definir a versão mínima do manifesto somente após validar os recursos usados.

A configuração `ui.sidebar.agents.rows` aceita linhas com tokens personalizados `$nome` e estilos `{ token, fg, bold, dim, rules }`. `pane.report_metadata` publica tokens de apresentação sem assumir o estado do agente. Linhas cujos tokens estão ausentes não são renderizadas.

Isso permite associar os cabeçalhos ao primeiro agente real de cada grupo, limpando esses tokens nos demais. Não é necessário criar agentes ou panes fictícios. O plugin `testy-cool/herdr-sidebar-config` já utiliza esse mecanismo para cabeçalhos de workspace/tab e separadores, com navegação nativa preservada.

Cabeçalhos são linhas visuais da entrada de um agente real, não objetos independentes de navegação. Clicar nessas linhas pode focar o agente que as ancora; não prometer seleção independente de máquina/projeto. Workspaces sem agentes continuam acessíveis na seção superior, pois não têm uma entrada para ancorar o cabeçalho nesta seção.

### Separador somente entre máquinas

`ui.sidebar.agents.row_gap` é global e adiciona espaço entre todas as entradas de agentes. **Não usar `row_gap = 1` para cumprir este requisito.**

Usar um token de separação opcional na última entrada da máquina anterior. Preenchê-lo com `·` somente quando a próxima entrada pertence a outra máquina; limpar nas demais entradas e na última máquina. Aplicar ao token a mesma cor do cabeçalho da máquina que acaba de ser exibida.

A implementação de referência usa **U+2800**, a célula braille em branco, para espaçadores que sobrevivem à normalização de metadados. Isso pode ajudar a compensar offsets de alinhamento; não deve ser usado como separador neste projeto. O separador escolhido é o caractere visível `·`. Quando o token está ausente, sua linha desaparece.

Esse mecanismo torna o separador visual possível sem mudar o Herdr. Validar o ponto e sua cor no terminal usado pelo usuário, inclusive quando o agente está focado. Não usar espaçamento global como substituto nem adicionar uma opção de linha em branco à implementação solicitada.

### Settings — decisões do usuário em 10/10 e 11/10/2026

O plugin tem uma ação **Settings** com duas abas independentes:

```text
Grouped | Priority

Grouped:
Active           [Yes/No]
View             [Agent / Agent+Tab]
Machine color    [Default e outras cores]
Project color    [Default e outras cores]
Agent color      [Default e outras cores]
Tab color        [Default e outras cores]
Show separator   [On/Off]

Priority:
Active           [Yes/No]
View             [Edit lines]
Machine color    [Default e outras cores]
Project color    [Default e outras cores]
Agent color      [Default e outras cores]
Tab color        [Default e outras cores]
```

O editor de View em Priority mostra as duas linhas e os cinco campos disponíveis.
Enter muda o campo selecionado entre Hidden, Line 1, Line 2 e Hidden; esquerda e
direita ajustam sua posição dentro da linha. Save view valida e aplica o conjunto;
Esc descarta o rascunho sem escrever. Exemplo possível, conforme o usuário:

```text
Line 1  [Machine | Project]
Line 2  [Status | Agent | Tab]
```

Em pedido posterior em 11/10/2026, o usuário pediu mostrar Line 1 e Line 2
somente após abrir Edit lines, removendo o resumo da aba Priority. O botão
Save view fica mais acima no editor, com espaço até as orientações do rodapé.

O usuário troca abas com esquerda/direita ou Tab, escolhe campos e cores com
cima/baixo e Enter, e fecha com Esc. As alterações confirmadas são salvas e
aplicadas sem reinstalação. Show separator começa desligada e só controla o ponto
entre máquinas, não o ponto inline nativo. Escolhas já salvas são preservadas.
O popup não substitui a sidebar por um painel próprio. Preferências ficam fora
do checkout.

Zero ou um modo pode estar ativo. Os dois Active em No param os workers e limpam
somente os tokens próprios, removendo os overrides de linhas e espaçamento para
usar a apresentação nativa padrão do Herdr, incluindo Machine. Esse
estado persiste ao navegar, reiniciar ou reinstalar. Colocar um modo em Yes retoma
seu perfil salvo e desativa o outro. Navegar entre abas ou editar a inativa não muda
o modo ativo nem a apresentação atual. Trocar Active não altera a ordem nativa
do Herdr. A máquina permanece na identidade mesmo quando escondida em Priority.
Cada modo salva suas quatro cores e organização separadamente. O schema 4 guarda
`enabled` e o último `mode` selecionado, além de
View/Show separator em Grouped e listas ordenadas `line1`/`line2` em Priority.

Preferências antigas dos schemas 1, 2 e 3 são carregadas sem reescrita imediata.
Cores compartilhadas viram perfis independentes; o modo ativo e o separador de
Grouped são preservados. Presets antigos de Priority viram as mesmas linhas;
Grouped mantém Tab quando selecionada e volta à árvore fixa solicitada. Tabs
já visíveis mantêm sua cor anterior durante a migração. A próxima gravação usa
schema 4. Preservar pausas do antigo `control.json` ao migrar; depois disso a
ativação de Settings é a única fonte de verdade. Recusar formatos ambíguos, campos de outro modo e schemas desconhecidos
sem sobrescrever os arquivos.

Default usa Yellow, Blue, Purple e Dark blue nos tons fixos do menu, independentemente
do tema do Herdr. Cores explícitas prevalecem. Status mantém a paleta nativa.
O renderer nativo usa offsets diferentes na primeira linha e nas seguintes de
cada entrada. Em Grouped, compensar por células com U+2800 antes de `state_icon`,
aceitando o separador inline ` · ` aprovado pelo usuário, sem `>` nem cópia de
estado. Em Priority, respeitar a posição escolhida do ícone e os offsets,
separadores e corte de texto fornecidos pelo Herdr.

## 3. Modelo e fonte de verdade

O Herdr é a única fonte de verdade para máquinas, sessões, workspaces, panes, agentes e estados.

- Máquina: conexão/sessão identificada pelo Herdr; incluir a máquina local.
- Projeto: workspace nativo, identificado por ID e apresentado por seu nome. Não agrupar apenas pelo nome da pasta nem varrer repositórios.
- Agente: registro nativo associado ao pane; usar seu nome quando disponível e um fallback documentado para identificação.
- Tabs: podem ajudar a diferenciar nomes iguais, mas não acrescentam um nível à árvore.

Chaves devem incluir máquina/conexão, sessão e IDs nativos de workspace/pane. Máquinas diferentes podem ter `w1`, `w1:p1`, projetos homônimos e agentes com o mesmo nome.

Preservar a ordem nativa de máquinas, workspaces e panes. Não reordenar automaticamente
por atividade nem mover workspaces reais. Para a árvore Grouped, o usuário escolhe
a ordem por espaços no Herdr para manter projetos contíguos. O plugin modifica
somente o layout e publica seus tokens; registrar e restaurar somente as alterações
de configuração pertencentes ao plugin. Recibos antigos que já registravam a
ordenação permanecem válidos para restauração, sem novas escritas nesse campo.

No modo Grouped, para cada lista ordenada atual:

1. Identificar o primeiro agente real de cada máquina e atribuir-lhe o cabeçalho da máquina.
2. Identificar o primeiro agente real de cada projeto nessa máquina e atribuir-lhe o nome, com recuo de projeto.
3. Atribuir a todos os agentes o espaçador de recuo antes do indicador de estado nativo e o nome após o ícone, sem marcador `>`; aceitar o ponto inline nativo.
4. Atribuir o separador `·`, na cor da máquina, ao último agente de cada máquina, exceto a última.
5. Limpar tokens que deixaram de ser aplicáveis após mudanças na lista.

View controla somente o conteúdo visível, sem filtrar agentes ou mudar suas
identidades. Em Grouped, os cabeçalhos de máquina e projeto continuam presentes
em ambas as opções. Agent / Tab acrescenta o título nativo da aba depois do nome,
sem outra linha ou nível na árvore.

No modo Priority, cada agente recebe seu próprio contexto selecionado, sem
âncoras de árvore. Limpar `has_agent_prefix`, `has_gap` e tokens de campos
escondidos. Renderizar os campos na ordem salva de cada linha, usando os tokens
nativos `state_icon` e `tab` nas posições escolhidas. O padrão usa duas linhas:
Project/Machine e Status/Agent. Linhas vazias são omitidas; não permitir ambas vazias.
As duas linhas pertencem ao mesmo agente e focam o mesmo pane. O Herdr fornece
posição, indicador, ordenação e corte de textos longos. Manter as mesmas chaves
compostas e a publicação incremental nos dois modos, mesmo quando Agent,
Machine ou Project não estiverem visíveis.

No caso de contexto incompleto, não descartar um agente; apresentar um nome de grupo explícito e registrar o problema. Desconexão não prova exclusão. Dados em cache precisam ser identificados como desatualizados.

## 4. Integração, permissões e conflitos

Usar exclusivamente APIs públicas, manifesto e diretórios de configuração/estado documentados pelo Herdr. Preferir Python 3 com dependências mínimas, se o contrato comprovado não exigir outra linguagem.

Tokens propostos, pertencentes exclusivamente a este plugin:

- `has_machine`: cabeçalho da máquina, somente no primeiro agente do bloco.
- `has_project`: cabeçalho com recuo de projeto, somente no primeiro agente do projeto.
- `has_agent_prefix`: somente espaçadores de recuo antes do ícone nativo; sem `>`.
- `has_agent`: nome normalizado do agente, sem marcador ou ícone.
- `has_gap`: separador `·`, na cor do cabeçalho da máquina imediatamente acima, somente entre máquinas.

Atualizar os valores antigos de `has_agent_prefix` para remover os marcadores de instalações já ativas e limpar o token nas transições e na desativação.

Publicar como `plugin:<HERDR_PLUGIN_ID>`. Limpar somente esses tokens. Não escrever nos tokens do plugin de sidebar anterior ou nos nomes, estados, títulos e autoridades nativas. Conferir o contrato de TTL e limpar valores obsoletos em todas as entradas ainda acessíveis.

Em 11/10/2026, o usuário relatou cabeçalhos piscando após editar Settings,
inclusive ao acessar uma instalação como machine de outro Herdr. As instalações
devem coexistir com configurações independentes: os nomes acima são campos
lógicos, enquanto as chaves publicadas incluem um UUID portátil por instalação,
guardado no estado durável e preservado em updates/reinstalações. Manter o ID
oficial e a origem de publicação. Uma instalação não pode sobrescrever nem limpar
os tokens de outra. Respeitar o limite público de 32 caracteres por chave.
Serializar a atualização de configuração do worker com a gravação de Settings,
sem bloquear a detecção de pausa e a limpeza necessárias ao Active = No.

A API de metadados aplica atualizações por token, não uma transação para a árvore inteira. Publicar diferenças, reconciliar após eventos/reconexões e evitar exibir o mesmo cabeçalho em duas entradas durante a troca de âncora. Documentar a possível janela de atualização; não prometer atomicidade inexistente.

A projeção `agent.view.set`, se necessária para ordenar, deve usar a origem própria. Existe apenas uma projeção ativa: detectar conflito antes de substituir a de outro plugin. `agent.view.clear` deve restringir-se à origem própria. Não inventar um campo de ordenação/filtro `machine`, ausente no schema examinado.

### Múltiplas máquinas

As identidades e dados remotos precisam ser obtidos pelos mecanismos públicos de máquinas do Herdr. Descobrir IDs no servidor correto e usar consistentemente sua conexão/sessão. Selecionar uma máquina na interface não muda o alvo dos comandos do pane local.

Demonstrar em teste como os metadados chegam aos panes remotos e como a ordem combinada corresponde às âncoras calculadas. Um teste somente com agentes locais não comprova agrupamento entre máquinas. Se for necessário instalar o plugin nas máquinas remotas, documentar essa exigência; não executar instalações ou alterações remotas automaticamente.

Não usar escaneamento de rede, credenciais armazenadas por outros aplicativos ou comandos shell construídos a partir de rótulos. Falhas por máquina devem ter timeout e não bloquear as demais.

## 5. Configuração e ciclo de vida

Antes de uma edição futura, preservar a configuração existente e identificar conflitos em `rows`, `rows_by_agent`, ordenação e projeções. Não apagar preferências de outros plugins. A restauração precisa respeitar mudanças que o usuário tenha feito depois da instalação.

Preservar:

- Prefixo `Ctrl+B`.
- `Ctrl+B → p`: `ray.plugin-manager.open`.
- `Ctrl+B → e`: abertura do TTT Editor.
- Seção superior da sidebar, modelos de projeto, plugins e sessões existentes.

Após uma edição real, executar `herdr config check` e recarregar somente quando autorizado pelo escopo da instalação. Não reiniciar o servidor principal para testar.

Preferências vivem nos diretórios próprios, com gravação atômica e formato versionado. Não persistir uma cópia dos agentes nem conteúdo de sessões. Usar eventos oficiais para invalidar o cache, ressincronizando com um snapshot completo após reconexão. Limitar cache, filas, tentativas e frequência de atualização; não executar processos ou consultas remotas por frame.

Desabilitar/remover deve limpar somente tokens/projeções próprios e restaurar a apresentação anterior, sem interromper agentes ou apagar projetos. Não exigir Herdr Web UI, abrir portas ou adicionar telemetria. A integração no Web UI só pode ser afirmada após teste, sem alterar seu código.

Instalações novas usam o snapshot de fábrica com ambos Active = No, mantendo
o registro habilitado para abrir Settings. Active = No preserva os perfis atuais;
Restore defaults substitui os dois pelo snapshot de fábrica e mantém ambos No.
Restart não altera as escolhas de ativação nem os perfis salvos. Serializar
operações do usuário com lock limitado, sem impedir a limpeza do worker.

## 6. Etapas para o implementador

### Etapa 0 — Prova visual isolada

Consultar `herdr --version`, `herdr api schema --json`, `herdr api --help` e `herdr plugin --help`. Usar uma sessão isolada **e raiz de configuração temporária separada**. Não compartilhar o config principal ou focar panes do usuário.

Demonstrar cabeçalhos únicos por metadados, prefixos exatos, cores, separador seletivo `·` e comportamento de foco. Registrar em `docs/viabilidade.md` versões, contratos utilizados e resultado; não incluir snapshots completos com dados sensíveis. Comprovar também a integração entre máquinas em um ambiente de teste controlado, sem alterar os perfis reais do usuário.

Se algum detalhe visual não funcionar no terminal alvo, registrar a limitação antes de prosseguir. Não buscar um fork ou uma interface substituta.

### Etapa 1 — Agrupamento e publicação

Implementar adaptador da API, modelo de identidades compostas, seleção de âncoras e publicação incremental dos tokens. O cálculo recebe somente dados nativos e a ordem efetivamente renderizada.

Cobrir projetos homônimos, IDs repetidos entre servidores, agente novo, agente removido, mudança de workspace e troca do primeiro/último agente do bloco. Nenhum prompt ou tecla pode ser enviado aos agentes.

### Etapa 2 — Lifecycle e entrega

Implementar configuração preservada, preferências mínimas, recuperação após reconexão e limpeza por propriedade. Validar manifesto, instalação/desativação/desinstalação no ambiente isolado e preparar README com versões e limitações comprovadas.

Instalação no ambiente principal: etapa posterior autorizada pelo usuário em 10/10/2026 e executada com o manifesto oficial vinculado ao checkout. Publicação da primeira versão `0.1.0`: etapa posterior autorizada em 11/10/2026, seguindo `AGENTS.md` e `scripts/release.py`.

## 7. Critérios de aceitação

- [x] Funciona como plugin na sidebar nativa, sem alterações no Herdr ou painel próprio.
- [x] Exibe máquina uma vez por bloco e projeto uma vez por máquina/workspace.
- [x] Não acrescenta `>`; nomes de projetos e agentes têm recuos distintos e consistentes, e ícones nativos ficam alinhados usando o ponto inline aceito pelo usuário.
- [x] Máquina amarela/negrito, projeto azul/negrito, agente roxo por padrão; opções de cores preservadas e indicador de estado nativo inalterado.
- [x] Settings tem abas Grouped e Priority; Priority usa duas linhas por agente
  por padrão, com projeto acima e status, IA e aba abaixo.
  A escolha de ordem no Herdr permanece manual.
- [x] Grouped oferece somente Agent ou Agent / Tab, mantendo a árvore completa.
- [x] Priority permite montar as duas linhas, esconder e ordenar os cinco campos,
  incluindo o status nativo. Cancelar preserva os arquivos; uma View vazia é recusada.
- [x] As quatro cores, incluindo Tab, são independentes por modo e sobrevivem
  às atualizações e à migração das preferências antigas.
- [x] Active permite zero ou um modo habilitado; os dois No restauram a sidebar
  nativa e preservam ambos os perfis. Yes retoma somente o modo escolhido. Navegar e editar a aba
  inativa preservam a sidebar atual e suas preferências, inclusive após migração.
- [x] Uma instalação nova fica habilitada no Herdr, com ambos Active = No, até
  a escolha em Settings; upgrades não sobrescrevem escolhas existentes.
- [x] Restore defaults volta ao snapshot dos dois modos, com ambos No; Restart
  recarrega somente o worker e preserva perfis e ativação.
- [x] Exibe uma linha com `·` entre máquinas quando habilitada, na cor do cabeçalho da máquina imediatamente acima; nenhuma linha em branco adicional. Pode sobrar ao final em um cliente com menos máquinas, conforme aceito pelo usuário.
- [x] Não depende de fontes especiais; separador validado no terminal alvo.
- [x] Não implementa recolhimento nem promete cabeçalhos com navegação independente.
- [x] Foco atinge o agente correto; cabeçalhos visuais continuam ancorados a agentes reais.
- [x] Identidades repetidas entre máquinas não misturam projetos ou agentes.
- [x] Reconexão e troca de âncora eliminam cabeçalhos/separadores obsoletos.
- [x] Rótulos Unicode e caracteres de controle são tratados por largura em células e normalização; validar 18, 22 e 36 colunas.
- [x] Desativação restaura a apresentação e preserva configuração, atalhos, processos e projetos anteriores.

Testar lógica de agrupamento, identidade e limites de largura com casos focados. Testes de integração devem comprovar a renderização e o foco reais. Ler código ou produzir um mock não equivale a validar o plugin instalado.

## 8. Referências primárias

- [Herdr — Plugins](https://herdr.dev/docs/plugins/): manifesto e ciclo de vida.
- [Herdr — Config reference](https://herdr.dev/docs/config-reference/#ui-and-sidebar): estilos por token e `row_gap` global.
- [Herdr — Socket API](https://herdr.dev/docs/socket-api/): metadados, normalização, TTL e snapshots.
- [Herdr — Agent view queries](https://herdr.dev/docs/socket-api/#agent-view-queries): projeção e propriedade.
- [Herdr — Connecting machines](https://herdr.dev/docs/connecting-machines/): conexões e identidades remotas.
- [Sidebar Config — arquitetura](https://github.com/testy-cool/herdr-sidebar-config/blob/main/docs/architecture.md): cabeçalhos ancorados no primeiro agente, separadores e U+2800.
- [Sidebar Config — sidebar.py](https://github.com/testy-cool/herdr-sidebar-config/blob/main/sidebar.py): referência de geração dos tokens; consultar, não reinstalar o plugin removido.
- [Herdr 0.9.3 — resolução de tokens](https://github.com/herdrdev/herdr/blob/v0.9.3/src/ui/sidebar/tokens.rs): omissão de linhas sem tokens resolvidos.
- [Herdr 0.9.3 — renderer de agentes](https://github.com/herdrdev/herdr/blob/v0.9.3/src/client/shell/agent_sidebar.rs): offsets nativos e espaçamento global.

A documentação online pode evoluir. Registrar data e versão na implementação; não assumir APIs futuras na baseline 0.9.3.
