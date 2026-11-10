# Auditoria e arquitetura

O primeiro incremento é um simulador local de uma unidade, com configurações e rascunhos no navegador. O servidor usa Python padrão, escuta apenas em loopback por padrão e recebe uma configuração por cálculo. Interface em HTML, CSS e JavaScript sem dependências externas. Esta escolha permite rodar no ambiente atual com Python 3.11. A instalação local de OR-Tools não encontrou uma distribuição no índice disponível.

| Risco | Tratamento |
|---|---|
| Publicar escala com CCT desconhecida | Simulação explícita na tela e exportações. Fluxo de publicação reservado à fase autenticada. |
| Confundir busca limitada com inviabilidade | Distinguir déficit encontrado de limite estrutural comprovado no catálogo de turnos. |
| Contagem duplicada e intervalos | Uma função por turno, pausa fora da cobertura, ocupação individual em linha de tempo contínua. |
| Jornadas na virada do ciclo | Checagem dentro do intervalo conhecido e pendência de histórico externo. |
| Vazamento de dados | Dados fictícios, sem login, sem servidor compartilhado. Rascunho persiste neste navegador. |
| Alteração normativa | Versionar premissas. Antes de uso real, revisar escopo e vigência, aprovar fixtures e preservar snapshots com versão anterior para rollback. |

Sequência: demonstração local → CP-SAT com fronteiras, segmentos e matrizes → autenticação, isolamento, publicação e multiunidade → instrumentos coletivos e regimes revisados → integrações. O solver local usa busca heurística determinística por semente com limite de tentativas. A falta de solução nessa busca é inconclusiva.
