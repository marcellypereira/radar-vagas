create table if not exists public.applications (
  id text primary key,
  job jsonb not null,
  application_status text not null default 'Candidatura realizada',
  applied_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table public.applications enable row level security;

-- Este projeto usa a service role apenas no endpoint serverless da Vercel.
-- Não exponha SUPABASE_SERVICE_ROLE_KEY no navegador.
