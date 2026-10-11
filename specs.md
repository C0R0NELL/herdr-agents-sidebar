# herdr-agents-sidebar

Especificação para outro agente implementar. Atualizada em 11/10/2026.

**Estado:** implementação local, com provas isoladas em Herdr 0.9.3. Ativado no ambiente principal por solicitação posterior do usuário em 10/10/2026, usando o checkout e a identidade oficial. Primeira versão `0.1.0` aprovada e publicação pública no GitHub autorizada em 11/10/2026. Os resultados e limites estão em `docs/viabilidade.md`.

## 1. Objetivo e decisões do usuário

Organizar visualmente a seção nativa de agentes por **Máquina → Projeto → Agente**, sem alterar o código ou fazer fork do Herdr.

Formato escolhido:

```text
machine01
  projeto01
     · ○ agente01
     · ○ agente02
  projeto02
     · ○ agente03
·
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
- Uma linha contendo somente `·` entre máquinas, na mesma cor do cabeçalho da máquina imediatamente acima. Não inserir linhas em branco nem separadores entre projetos/agentes. Em 10/10/2026, o usuário aceitou que o ponto permaneça ao final quando outro cliente mostra menos máquinas: os tokens são compartilhados no servidor, enquanto o catálogo é do cliente.
- Não acrescentar um nível para tabs, controles de expansão ou ícones que exijam fontes especiais.
- Em 11/10/2026, o usuário pediu remover todos os `>` e inicialmente o ponto inline antes do ícone. Após reproduzir o desalinhamento dos ícones sem esse ponto, aprovou manter o ponto inline para alinhá-los. Todos os `>` continuam removidos. O ponto opcional entre máquinas continua separado dessa decisão.
- Em 11/10/2026, após experimentar as cores em Settings, o usuário definiu Default como Machine = Yellow, Project = Blue e Agent = Purple, nos tons já oferecidos pelo menu. Isso substitui as propostas intermediárias. Não alterar o tema global nem as cores de status do Herdr; escolhas explícitas em Settings continuam preservadas.

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

### Settings — decisão do usuário em 10/10/2026

O plugin terá uma ação **Settings**, com somente quatro opções na tela:

```text
Machine color    [Default e outras cores]
Project color    [Default e outras cores]
Agent color      [Default e outras cores]
Show separator   [On/Off]
```

O usuário escolhe cores com setas e Enter, e fecha com Esc. As alterações são
salvas e aplicadas sem reinstalação. A preferência `show_separator` começa ligada,
para facilitar comparar o ponto com sua ausência. O popup de settings não
substitui a sidebar por um painel próprio. Preferências ficam fora do checkout.
Show separator controla somente o ponto entre máquinas, não o ponto inline nativo.
Default usa Yellow, Blue e Purple nos tons fixos do menu, independentemente do
tema do Herdr. As cores explicitamente escolhidas pelo usuário prevalecem sobre Default.

O renderer nativo usa offsets diferentes na primeira linha e nas linhas seguintes de uma entrada. Compensar a posição por células, usando um token de espaçadores U+2800 antes do `state_icon`. O separador inline ` · ` imposto pelo Herdr entre esse token e o ícone foi aceito pelo usuário para manter ícones e nomes alinhados. Não acrescentar `>` a esse token nem copiar estados para produzir ícones próprios. A API examinada não permite alinhar também os ícones sem esse ponto, linhas extras ou alterações no Herdr.

## 3. Modelo e fonte de verdade

O Herdr é a única fonte de verdade para máquinas, sessões, workspaces, panes, agentes e estados.

- Máquina: conexão/sessão identificada pelo Herdr; incluir a máquina local.
- Projeto: workspace nativo, identificado por ID e apresentado por seu nome. Não agrupar apenas pelo nome da pasta nem varrer repositórios.
- Agente: registro nativo associado ao pane; usar seu nome quando disponível e um fallback documentado para identificação.
- Tabs: podem ajudar a diferenciar nomes iguais, mas não acrescentam um nível à árvore.

Chaves devem incluir máquina/conexão, sessão e IDs nativos de workspace/pane. Máquinas diferentes podem ter `w1`, `w1:p1`, projetos homônimos e agentes com o mesmo nome.

Preservar a ordem nativa de máquinas, workspaces e panes. Não reordenar automaticamente por atividade nem mover workspaces reais. Usar ordenação por espaços na apresentação para manter projetos contíguos; registrar e restaurar somente as alterações de configuração pertencentes ao plugin.

Para cada lista ordenada atual:

1. Identificar o primeiro agente real de cada máquina e atribuir-lhe o cabeçalho da máquina.
2. Identificar o primeiro agente real de cada projeto nessa máquina e atribuir-lhe o nome, com recuo de projeto.
3. Atribuir a todos os agentes o espaçador de recuo antes do indicador de estado nativo e o nome após o ícone, sem marcador `>`; aceitar o ponto inline nativo.
4. Atribuir o separador `·`, na cor da máquina, ao último agente de cada máquina, exceto a última.
5. Limpar tokens que deixaram de ser aplicáveis após mudanças na lista.

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
