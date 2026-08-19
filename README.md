# Radar de Vagas

Radar local e recorrente para oportunidades de front-end. Ele consulta apenas feeds e APIs públicas, mantém o histórico em SQLite e compara cada execução com a anterior.

## Uso

```bash
cd /home/marcelly/radar-vagas
python3 jobs.py
python3 jobs.py dashboard
python3 jobs.py status <id> "Candidatura realizada"
python3 jobs.py import minha-vaga-linkedin.json
```

O primeiro comando atualiza as fontes, grava `data/jobs.sqlite3`, exporta `data/jobs.json` e gera `reports/latest.md`. O dashboard abre em `http://127.0.0.1:8787`.

## Fontes automáticas

- Remotive API: vagas remotas; limite recomendado pela própria fonte é de até 4 consultas/dia.
- Remote OK API: vagas remotas públicas.
- We Work Remotely RSS: feed público de programação.
- Greenhouse, Lever e Ashby: APIs públicas de boards configurados em `config/sources.json`.
- Jooble e Adzuna: ativadas quando suas chaves estão configuradas nas variáveis de ambiente.

LinkedIn, Indeed, Glassdoor, Gupy, Revelo, GeekHunter e plataformas com login/CAPTCHA não são coletados automaticamente. Use os links de busca em `config/search-links.json` ou importe uma vaga manualmente; isso evita automação não autorizada.

## Ampliar vagas brasileiras

Copie `.env.example` para `.env` e preencha as chaves que possuir. Na Vercel, crie as mesmas variáveis em **Settings → Environment Variables** e faça um novo deploy.

- `JOOBLE_API_KEY`: consulta cinco termos de Front-end no Brasil.
- `ADZUNA_APP_ID` e `ADZUNA_APP_KEY`: segunda fonte agregadora brasileira.
- `SUPABASE_URL` e `SUPABASE_SERVICE_ROLE_KEY`: sincroniza candidaturas entre dispositivos. Execute antes o SQL em `supabase/schema.sql` no Supabase.

Sem essas credenciais, o painel continua funcionando com ATS públicos e mantém candidaturas no navegador. A aba **Importar vaga** aceita qualquer link de LinkedIn, Gupy, Indeed ou página de carreira.

Exemplo de importação manual:

```json
{"company":"Empresa","title":"Frontend Developer","url":"https://...","location":"Brasil","remote":"Remoto","source":"LinkedIn","published_at":null}
```

## Adicionar uma empresa/ATS

Em `config/sources.json`, informe o identificador público do board. Exemplos:

```json
{ "type": "greenhouse", "company": "Empresa", "token": "empresa" }
{ "type": "lever", "company": "Empresa", "site": "empresa" }
{ "type": "ashby", "company": "Empresa", "board": "Empresa" }
```

Depois execute `python3 jobs.py`. O radar armazena a URL oficial da candidatura sempre que a fonte a fornece.

## Status de candidatura

`Não analisada`, `Interessante`, `Quero me candidatar`, `Currículo precisa ser adaptado`, `Candidatura realizada`, `Processo seletivo`, `Entrevista`, `Teste técnico`, `Rejeitada`, `Encerrada`, `Oferta recebida`.

Esses status nunca são alterados pelo processo de atualização.
