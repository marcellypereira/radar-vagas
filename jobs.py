#!/usr/bin/env python3
"""Radar de vagas: fontes públicas, histórico SQLite e dashboard local."""
from __future__ import annotations

import argparse, datetime as dt, hashlib, html, json, re, sqlite3, sys
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"; REPORTS = ROOT / "reports"; CONFIG = ROOT / "config"
DB = DATA / "jobs.sqlite3"
APP_STATUSES = ["Não analisada", "Interessante", "Quero me candidatar", "Currículo precisa ser adaptado", "Candidatura realizada", "Processo seletivo", "Entrevista", "Teste técnico", "Rejeitada", "Encerrada", "Oferta recebida"]
ROLE_TERMS = ("front end", "front-end", "frontend", "react", "next.js", "nextjs", "react native", "ui engineer", "design engineer", "web developer", "javascript developer", "typescript developer")
SKILLS = {"react": 10, "react native": 10, "typescript": 9, "javascript": 8, "next.js": 8, "nextjs": 8, "tailwind": 5, "styled components": 4, "scss": 3, "material ui": 4, "shadcn": 4, "redux": 4, "zustand": 4, "react query": 4, "zod": 3, "rest": 3, "design system": 6, "accessibility": 4, "wcag": 4, "git": 2}
UA = "RadarDeVagas/1.0 (personal job tracking; public feeds only)"

def now(): return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
def load(path):
    with open(path, encoding="utf-8") as f: return json.load(f)
def clean(value): return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", value or ""))).strip()
def iso_date(value):
    if not value: return None
    try:
        if isinstance(value, (int, float)):
            if value > 10_000_000_000: value /= 1000
            return dt.datetime.fromtimestamp(value, tz=dt.timezone.utc).isoformat()
        value = str(value).replace("Z", "+00:00")
        return dt.datetime.fromisoformat(value).astimezone(dt.timezone.utc).isoformat()
    except ValueError:
        try: return parsedate_to_datetime(value).astimezone(dt.timezone.utc).isoformat()
        except (TypeError, ValueError): return None
def fetch_json(url):
    req = Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urlopen(req, timeout=25) as res: return json.load(res)
def fetch_text(url):
    req = Request(url, headers={"User-Agent": UA, "Accept": "application/rss+xml,text/xml,text/html"})
    with urlopen(req, timeout=25) as res: return res.read().decode("utf-8", "replace")
def uid(company, title, location, url):
    key = "|".join((company or "", title or "", location or "", url or "")).lower().strip()
    return hashlib.sha256(key.encode()).hexdigest()[:20]
def normal(**values):
    values.setdefault("id", uid(values.get("company"), values.get("title"), values.get("location"), values.get("apply_url") or values.get("url")))
    values.setdefault("application_status", "Não analisada"); values.setdefault("status", "open")
    values.setdefault("source", "Não informado"); values.setdefault("requirements", ""); values.setdefault("description", "")
    values.setdefault("technologies", []); values.setdefault("differentials", ""); values.setdefault("employment_type", None)
    values.setdefault("salary", None); values.setdefault("candidates", None); values.setdefault("seniority", None)
    values.setdefault("remote", "Não informado"); values.setdefault("english", "Não informado")
    values.setdefault("published_at", None); values.setdefault("location", "Não informado")
    values.setdefault("url", values.get("apply_url")); values.setdefault("apply_url", values.get("url"))
    return values

def matches(job):
    title = (job.get("title") or "").lower()
    description = " ".join(str(job.get(k, "")) for k in ("description", "requirements", "technologies")).lower()
    if any(term in title for term in ROLE_TERMS):
        return True
    # O cargo precisa declarar a especialidade. Menções isoladas a React/front-end
    # em uma descrição de back-end não tornam a vaga compatível.
    return False
def technologies(text):
    low = text.lower(); found = []
    for term in SKILLS:
        if term in low: found.append(term.title() if term != "next.js" else "Next.js")
    return found
def score(job):
    text = " ".join(str(job.get(k, "")) for k in ("title", "description", "requirements", "technologies")).lower()
    points, strengths, gaps = 0, [], []
    if any(x in (job.get("title") or "").lower() for x in ROLE_TERMS): points += 35; strengths.append("cargo alinhado a Front-end/React")
    for skill, weight in SKILLS.items():
        if skill in text:
            points += weight
            if skill in ("react", "typescript", "javascript", "next.js", "react native", "design system"): strengths.append(skill.title())
    loc = (job.get("location") or "").lower()
    if any(x in loc for x in ("remote", "remoto", "brazil", "brasil", "latin america", "latam")): points += 8; strengths.append("localização compatível")
    if any(x in text for x in ("senior", "staff", "principal", "lead")): points -= 12; gaps.append("senioridade possivelmente acima do perfil")
    if any(x in text for x in ("english fluent", "fluent english", "inglês fluente", "advanced english")): gaps.append("verificar nível de inglês exigido")
    for gap in ("angular", "graphql", "web vitals", "fintech"):
        if gap in text: gaps.append(f"pede/valoriza {gap.title()}")
    return min(100, max(0, points)), list(dict.fromkeys(strengths))[:4], list(dict.fromkeys(gaps))[:3]

def remotive():
    data = fetch_json("https://remotive.com/api/remote-jobs?category=software-dev")
    out=[]
    for x in data.get("jobs", []):
        j=normal(company=x.get("company_name"), title=x.get("title"), location=x.get("candidate_required_location") or "Remote", remote="Remoto", published_at=iso_date(x.get("publication_date")), source="Remotive", url=x.get("url"), apply_url=x.get("url"), description=clean(x.get("description")), employment_type=x.get("job_type"), salary=x.get("salary"))
        j["technologies"] = technologies(j["description"]); out.append(j)
    return out
def remoteok():
    data = fetch_json("https://remoteok.com/api")
    out=[]
    for x in data:
        if not isinstance(x, dict) or not x.get("position"): continue
        url=x.get("url") or ("https://remoteok.com/remote-jobs/" + str(x.get("id", "")))
        j=normal(company=x.get("company"), title=x.get("position"), location=x.get("location") or "Remote", remote="Remoto", published_at=iso_date(x.get("epoch")), source="Remote OK", url=url, apply_url=x.get("apply_url") or url, description=clean(x.get("description")), employment_type=x.get("type"), salary=x.get("salary"))
        j["technologies"] = [str(t) for t in x.get("tags", [])] or technologies(j["description"]); out.append(j)
    return out
class RSS(HTMLParser):
    def __init__(self): super().__init__(); self.items=[]; self.item=None; self.tag=None
    def handle_starttag(self,t,a):
        if t=="item": self.item={}
        elif self.item is not None: self.tag=t
    def handle_endtag(self,t):
        if t=="item" and self.item is not None: self.items.append(self.item); self.item=None
        self.tag=None
    def handle_data(self,d):
        if self.item is not None and self.tag: self.item[self.tag]=self.item.get(self.tag,"")+d
def wwr():
    p=RSS(); p.feed(fetch_text("https://weworkremotely.com/categories/remote-programming-jobs.rss")); out=[]
    for x in p.items:
        title=clean(x.get("title")); company=clean(x.get("company"))
        if not company and ":" in title:
            company, title = (part.strip() for part in title.split(":", 1))
        j=normal(company=company or "Não informado", title=title, location=clean(x.get("region") or "Remote"), remote="Remoto", published_at=iso_date(x.get("pubdate")), source="We Work Remotely", url=clean(x.get("link")), apply_url=clean(x.get("link")), description=clean(x.get("description")))
        j["technologies"]=technologies(j["title"]+" "+j["description"]); out.append(j)
    return out
def greenhouse(entry):
    data=fetch_json(f"https://boards-api.greenhouse.io/v1/boards/{quote(entry['token'])}/jobs?content=true")
    out=[]
    for x in data.get("jobs",[]):
        content=clean(x.get("content")); j=normal(company=entry["company"],title=x.get("title"),location=(x.get("location") or {}).get("name"),remote="Remoto" if "remote" in (content+str(x.get('location'))).lower() else "Não informado",published_at=iso_date(x.get("updated_at")),source="Greenhouse",url=x.get("absolute_url"),apply_url=x.get("absolute_url"),description=content)
        j["technologies"]=technologies(content); out.append(j)
    return out
def lever(entry):
    data=fetch_json(f"https://api.lever.co/v0/postings/{quote(entry['site'])}?mode=json")
    out=[]
    for x in data:
        content=clean(x.get("descriptionPlain") or x.get("description")); cats=x.get("categories") or {}; j=normal(company=entry["company"],title=x.get("text"),location=cats.get("location"),remote="Remoto" if "remote" in (content+str(cats)).lower() else "Não informado",published_at=iso_date(x.get("createdAt")),source="Lever",url=x.get("hostedUrl"),apply_url=x.get("applyUrl") or x.get("hostedUrl"),description=content,employment_type=cats.get("commitment"))
        j["technologies"]=technologies(content); out.append(j)
    return out
def ashby(entry):
    data=fetch_json(f"https://api.ashbyhq.com/posting-api/job-board/{quote(entry['board'])}?includeCompensation=true")
    out=[]
    for x in data.get("jobs",[]):
        content=clean(x.get("descriptionHtml") or x.get("descriptionPlain")); j=normal(company=entry["company"],title=x.get("title"),location=x.get("location"),remote="Remoto" if "remote" in (content+str(x.get('location'))).lower() else "Não informado",published_at=iso_date(x.get("publishedAt")),source="Ashby",url=x.get("jobUrl"),apply_url=x.get("applyUrl") or x.get("jobUrl"),description=content,salary=json.dumps(x.get("compensation")) if x.get("compensation") else None)
        j["technologies"]=technologies(content); out.append(j)
    return out

def connect():
    DATA.mkdir(exist_ok=True); REPORTS.mkdir(exist_ok=True)
    db=sqlite3.connect(DB); db.row_factory=sqlite3.Row
    db.executescript("""CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, company TEXT,title TEXT,seniority TEXT,location TEXT,remote TEXT,published_at TEXT,source TEXT,url TEXT,apply_url TEXT,technologies TEXT,requirements TEXT,differentials TEXT,english TEXT,employment_type TEXT,salary TEXT,candidates TEXT,status TEXT,application_status TEXT NOT NULL DEFAULT 'Não analisada',description TEXT,compatibility INTEGER,strengths TEXT,gaps TEXT,first_seen_at TEXT,last_seen_at TEXT,discovered_at TEXT,source_run TEXT); CREATE TABLE IF NOT EXISTS runs (id INTEGER PRIMARY KEY AUTOINCREMENT, started_at TEXT,finished_at TEXT, source_results TEXT); CREATE TABLE IF NOT EXISTS companies (name TEXT PRIMARY KEY,site TEXT,careers_url TEXT,technologies TEXT,product_type TEXT,remote_hiring TEXT,ats TEXT,last_job_at TEXT,frequency TEXT);""")
    return db
def upsert(db, job, run_at):
    job["compatibility"], job["strengths"], job["gaps"] = score(job)
    old=db.execute("SELECT application_status, first_seen_at FROM jobs WHERE id=?",(job["id"],)).fetchone(); is_new=old is None
    if old: job["application_status"]=old["application_status"]; job["first_seen_at"]=old["first_seen_at"]
    else: job["first_seen_at"]=run_at
    job["last_seen_at"]=run_at; job["discovered_at"]=run_at; job["status"]="open"
    cols=["id","company","title","seniority","location","remote","published_at","source","url","apply_url","technologies","requirements","differentials","english","employment_type","salary","candidates","status","application_status","description","compatibility","strengths","gaps","first_seen_at","last_seen_at","discovered_at","source_run"]
    job["source_run"]=run_at
    values=[json.dumps(job[c],ensure_ascii=False) if c in ("technologies","strengths","gaps") else job.get(c) for c in cols]
    db.execute(f"INSERT INTO jobs ({','.join(cols)}) VALUES ({','.join('?'*len(cols))}) ON CONFLICT(id) DO UPDATE SET " + ",".join(f"{c}=excluded.{c}" for c in cols if c not in ("id","first_seen_at","application_status")),values)
    db.execute("INSERT INTO companies(name,technologies,remote_hiring,ats,last_job_at,frequency) VALUES(?,?,?,?,?,?) ON CONFLICT(name) DO UPDATE SET technologies=excluded.technologies, remote_hiring=excluded.remote_hiring, ats=excluded.ats,last_job_at=excluded.last_job_at",(job["company"],json.dumps(job["technologies"]),job["remote"],job["source"],job["published_at"],"A calcular após mais execuções"))
    return is_new
def run():
    db=connect(); run_at=now(); sources=[("Remotive",remotive), ("Remote OK",remoteok), ("We Work Remotely",wwr)]
    configured=load(CONFIG/"sources.json")
    sources += [(f"Greenhouse:{x['company']}",lambda x=x:greenhouse(x)) for x in configured.get("greenhouse",[])]
    sources += [(f"Lever:{x['company']}",lambda x=x:lever(x)) for x in configured.get("lever",[])]
    sources += [(f"Ashby:{x['company']}",lambda x=x:ashby(x)) for x in configured.get("ashby",[])]
    result={}; new=0
    for name, getter in sources:
        try:
            all_jobs=[j for j in getter() if matches(j)]; ids=set()
            if ":" in name:
                for j in all_jobs: j["source"] = name
            for j in all_jobs: ids.add(j["id"]); new += upsert(db,j,run_at)
            # Only close jobs scoped to this exact source after a successful complete source response.
            source=name if ":" in name else name
            existing=db.execute("SELECT id FROM jobs WHERE source=? AND status='open'",(source,)).fetchall()
            for row in existing:
                if row["id"] not in ids: db.execute("UPDATE jobs SET status='aparentemente_removida' WHERE id=?",(row["id"],))
            result[name]={"ok":True,"jobs":len(all_jobs)}
        except Exception as e: result[name]={"ok":False,"error":str(e)[:180]}
    db.execute("INSERT INTO runs(started_at,finished_at,source_results) VALUES(?,?,?)",(run_at,now(),json.dumps(result,ensure_ascii=False))); db.commit(); export(db); report(db,run_at,result,new); db.close()
    print(f"Radar atualizado. {new} novas vagas. Relatório: reports/latest.md")
def rows(db):
    result=[]
    for r in db.execute("SELECT * FROM jobs ORDER BY published_at DESC, compatibility DESC"):
        x=dict(r)
        for k in ("technologies","strengths","gaps"):
            try:x[k]=json.loads(x[k] or "[]")
            except json.JSONDecodeError:x[k]=[]
        result.append(x)
    return result
def export(db):
    content=json.dumps(rows(db),ensure_ascii=False,indent=2)
    (DATA/"jobs.json").write_text(content,encoding="utf-8")
    web_data=ROOT / "public" / "data"
    web_data.mkdir(parents=True, exist_ok=True)
    (web_data / "jobs.json").write_text(content,encoding="utf-8")
def report(db,run_at,result,new):
    all_rows=rows(db); last_run=db.execute("SELECT started_at FROM runs ORDER BY id DESC LIMIT 1 OFFSET 1").fetchone(); since=last_run["started_at"] if last_run else None
    current=dt.datetime.now(dt.timezone.utc)
    def age(x,h):
        try:return (current-dt.datetime.fromisoformat(x["published_at"])).total_seconds()<=h*3600
        except:return False
    newly=[x for x in all_rows if not since or x["first_seen_at"]>=since]
    top=[x for x in newly if x["status"]=="open" and x["compatibility"]>=65][:12]
    def line(x): return f"- **{x['company']} — {x['title']}** · {x['compatibility']}/100 · {x['remote']} · publicada: {x['published_at'] or 'Não informado'} · [Candidatar]({x['apply_url']})"
    text=["# Radar de Vagas",f"\n**Data da busca:** {run_at}",f"\n**Novas vagas encontradas:** {len(newly)}  ",f"**Publicadas hoje:** {sum(age(x,24) and dt.datetime.fromisoformat(x['published_at']).date()==current.date() for x in newly if x['published_at'])}  ",f"**Últimas 24h:** {sum(age(x,24) for x in newly)}  ",f"**Alta compatibilidade:** {sum(x['compatibility']>=75 for x in newly)}  ",f"**Candidaturas recomendadas:** {len(top)}  ",f"**Vagas aparentemente encerradas:** {sum(x['status']=='aparentemente_removida' for x in all_rows)}\n","## 🔥 Top oportunidades para se candidatar agora\n"]
    text += [line(x) for x in top] or ["Nenhuma oportunidade nova com pontuação alta nesta execução."]
    text += ["\n## 🆕 Todas as vagas novas\n"] + ([line(x) for x in newly] or ["Nenhuma vaga nova."])
    closed=[x for x in all_rows if x["status"]=="aparentemente_removida"]
    text += ["\n## ❌ Vagas aparentemente encerradas\n"] + ([line(x) for x in closed] or ["Nenhuma."])
    text += ["\n## Fontes consultadas\n"] + [f"- {k}: {'ok ('+str(v.get('jobs'))+' vagas compatíveis)' if v['ok'] else 'falhou — '+v['error']}" for k,v in result.items()]
    (REPORTS/"latest.md").write_text("\n".join(text),encoding="utf-8")
def dashboard():
    class Handler(BaseHTTPRequestHandler):
        def send(self,code,body,ctype="application/json"):
            raw=body.encode(); self.send_response(code); self.send_header("Content-Type",ctype+"; charset=utf-8"); self.send_header("Content-Length",str(len(raw))); self.end_headers(); self.wfile.write(raw)
        def do_GET(self):
            if self.path=="/": return self.send(200,(ROOT/"index.html").read_text(encoding="utf-8"),"text/html")
            if self.path=="/api/jobs":
                db=connect(); body=json.dumps(rows(db),ensure_ascii=False); db.close(); return self.send(200,body)
            self.send(404,"{\"error\":\"not found\"}")
        def do_PATCH(self):
            if not self.path.startswith("/api/jobs/"): return self.send(404,"{}")
            try:
                payload=json.loads(self.rfile.read(int(self.headers["Content-Length"]))); status=payload["application_status"]
                if status not in APP_STATUSES: raise ValueError("status inválido")
                db=connect(); db.execute("UPDATE jobs SET application_status=? WHERE id=?",(status,self.path.rsplit('/',1)[-1])); db.commit(); export(db); db.close(); self.send(200,"{}")
            except Exception as e:self.send(400,json.dumps({"error":str(e)}))
        def log_message(self,*args): pass
    print("Dashboard em http://127.0.0.1:8787 (Ctrl+C para encerrar)")
    ThreadingHTTPServer(("127.0.0.1",8787),Handler).serve_forever()
def set_status(job_id,status):
    if status not in APP_STATUSES: raise SystemExit("Status inválido. Veja README.md")
    db=connect(); db.execute("UPDATE jobs SET application_status=? WHERE id=?",(status,job_id)); db.commit(); export(db); db.close()
def import_jobs(path):
    """Importa vagas salvas manualmente de fontes que não permitem coleta pública."""
    payload=json.loads(Path(path).read_text(encoding="utf-8")); payload=payload if isinstance(payload,list) else [payload]
    db=connect(); stamp=now(); added=0
    for item in payload:
        required=[key for key in ("company","title","url") if not item.get(key)]
        if required: raise SystemExit("Importação inválida; faltam: " + ", ".join(required))
        job=normal(**item); job["source"]=job.get("source") or "Importação manual"
        added += upsert(db,job,stamp)
    db.commit(); export(db); db.close(); print(f"{added} vaga(s) nova(s) importada(s).")
def main():
    p=argparse.ArgumentParser(); p.add_argument("command",nargs="?",default="run",choices=["run","dashboard","status","import"]); p.add_argument("id",nargs="?"); p.add_argument("value",nargs="?"); a=p.parse_args()
    if a.command=="run":run()
    elif a.command=="dashboard":dashboard()
    elif a.command=="import":
        if not a.id: raise SystemExit("Uso: python3 jobs.py import vaga.json")
        import_jobs(a.id)
    else:
        if not a.id or not a.value: raise SystemExit("Uso: python3 jobs.py status <id> \"Candidatura realizada\"")
        set_status(a.id,a.value)
if __name__=="__main__":main()
