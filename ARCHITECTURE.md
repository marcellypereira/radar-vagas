# Arquitetura do Radar

## Decisões

- **Runtime:** Python 3 padrão, sem dependências externas; execução diária por `python3 jobs.py`.
- **Base persistente:** `data/jobs.sqlite3`. A exportação legível fica em `data/jobs.json`.
- **Chave de deduplicação:** hash de `empresa + cargo + localização + URL de candidatura`.
- **Histórico:** `first_seen_at`, `last_seen_at`, `published_at`, `discovered_at`, `status` e `application_status`.
- **Atualização:** os campos da vaga são atualizados, mas `application_status` e `first_seen_at` nunca são substituídos.

## Fontes e limites

| Fonte | Modo | Situação |
|---|---|---|
| Remotive | API pública | Automática; respeitar máximo de 4 consultas/dia indicado pela fonte. |
| Remote OK | API pública | Automática. |
| We Work Remotely | RSS público | Automática. |
| Greenhouse | Job Board API por `board_token` | Automática após configuração. |
| Lever | Postings API por `site` | Automática após configuração. |
| Ashby | Public Job Posting API por `board` | Automática após configuração. |
| LinkedIn, Indeed, Glassdoor, Gupy, Wellfound, Revelo, GeekHunter, Trampos, Vagas.com, APInfo | Busca/link ou importação | Sem automação de login, CAPTCHA, rate-limit ou área protegida. |
| Carreiras próprias/ATS não listados | Conector futuro ou importação | Só adicionar se houver feed/API pública ou autorização. |

## Descoberta e encerramento

Uma vaga é **nova** se a sua chave nunca existiu no SQLite. A diferença desde a última busca usa o `first_seen_at` comparado ao início da execução anterior.

Quando uma fonte conclui uma coleta com sucesso, vagas abertas daquela mesma fonte que deixaram de aparecer são marcadas como `aparentemente_removida`; uma falha de fonte nunca fecha vagas. Isso é proposital: feeds podem oscilar ou limitar resultados.

## Compatibilidade (0–100)

- 35 pontos: cargo diretamente alinhado a front-end, React, Next.js, React Native, UI/Design Engineer ou Web Developer.
- Até 67 pontos: tecnologias do perfil, com maior peso para React, React Native, TypeScript, JavaScript e Next.js.
- 8 pontos: remoto, Brasil ou LATAM.
- Penalidade: termos de senioridade Staff/Lead/Principal/Senior.

O relatório também lista forças e lacunas verificáveis. Requisitos ausentes não são inventados; ficam como `Não informado` quando a fonte não os fornece.

## Checklist de implementação

- [x] Consulta de feeds/APIs públicas
- [x] Conectores ATS extensíveis
- [x] Normalização, deduplicação e SQLite
- [x] Comparação entre execuções
- [x] Detecção conservadora de removidas
- [x] Compatibilidade e prioridades
- [x] Relatório Markdown por execução
- [x] Exportação JSON
- [x] Status de candidatura preservado
- [x] Dashboard local com busca, ordenação e status
- [x] Importação manual para fontes restritas
- [ ] Configurar boards das empresas-alvo que você escolher
- [ ] Agendar execução diária (cron/Agendador do sistema), se desejar
