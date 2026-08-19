const json = (res, status, body) => res.status(status).json(body);
const config = () => ({
  url: process.env.SUPABASE_URL,
  key: process.env.SUPABASE_SERVICE_ROLE_KEY,
});

async function supabase(path, options = {}) {
  const { url, key } = config();
  if (!url || !key) throw new Error("Supabase não configurado");
  const response = await fetch(`${url}/rest/v1/${path}`, {
    ...options,
    headers: { apikey: key, Authorization: `Bearer ${key}`, "Content-Type": "application/json", Prefer: "return=representation", ...(options.headers || {}) },
  });
  if (!response.ok) throw new Error(await response.text());
  return response.status === 204 ? null : response.json();
}

export default async function handler(req, res) {
  try {
    if (req.method === "GET") return json(res, 200, await supabase("applications?select=*&order=applied_at.desc"));
    if (req.method === "POST") {
      const app = req.body;
      return json(res, 201, await supabase("applications?on_conflict=id", { method: "POST", body: JSON.stringify(app), headers: { Prefer: "resolution=merge-duplicates,return=representation" } }));
    }
    if (req.method === "PATCH") {
      const { id, ...body } = req.body;
      return json(res, 200, await supabase(`applications?id=eq.${encodeURIComponent(id)}`, { method: "PATCH", body: JSON.stringify(body) }));
    }
    return json(res, 405, { error: "Método não permitido" });
  } catch (error) {
    return json(res, 503, { error: error.message });
  }
}
