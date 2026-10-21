const API = "";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API}${path}`, {
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
    ...init,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || res.statusText);
  }
  return res.json() as Promise<T>;
}

export const api = {
  health: () => request<Record<string, unknown>>("/api/health"),
  recommend: () =>
    request<{ ram_gb: number; recommendation: { tier: string; model: string; provider: string } }>(
      "/api/setup/recommend"
    ),
  openWorkspace: (path: string) =>
    request<{ ok: boolean; path: string }>("/api/workspace/open", {
      method: "POST",
      body: JSON.stringify({ path }),
    }),
  workspace: () => request<{ path: string | null }>("/api/workspace"),
  tree: () => request<{ entries: FileEntry[] }>("/api/files/tree"),
  readFile: (path: string) =>
    request<{ path: string; content: string; truncated: boolean }>("/api/files/read?path=" + encodeURIComponent(path)),
  writeFile: (path: string, content: string) =>
    request("/api/files/write", { method: "POST", body: JSON.stringify({ path, content }) }),
  models: () =>
    request<{ models: { id: string; provider: string; name: string; available: boolean }[] }>("/api/models"),
  selectModel: (payload: { provider?: string; model?: string; agent?: string }) =>
    request("/api/models/select", { method: "POST", body: JSON.stringify(payload) }),
  configureOpenai: (base_url: string, api_key: string) =>
    request("/api/models/openai", {
      method: "POST",
      body: JSON.stringify({ base_url, api_key }),
    }),
  runAgents: (task: string) =>
    request<{ ok: boolean; session_id: string }>("/api/agents/run", {
      method: "POST",
      body: JSON.stringify({ task }),
    }),
  pending: () =>
    request<{
      pending: {
        id: string;
        action_type: string;
        agent: string;
        summary: string;
        payload: Record<string, unknown>;
      }[];
    }>("/api/safety/pending"),
  approve: (action_id: string, approved: boolean) =>
    request("/api/safety/approve", {
      method: "POST",
      body: JSON.stringify({ action_id, approved }),
    }),
  safetyConfig: (cfg: { require_write_approval?: boolean; require_terminal_approval?: boolean }) =>
    request("/api/safety/config", { method: "POST", body: JSON.stringify(cfg) }),
  undos: () =>
    request<{
      snapshots: { id: string; path: string; reason: string; agent: string; created_at: string }[];
    }>("/api/undo"),
  undo: (snapshot_id: string) =>
    request("/api/undo", { method: "POST", body: JSON.stringify({ snapshot_id }) }),
  gitStatus: () => request<Record<string, unknown>>("/api/git/status"),
  gitDiff: () => request<{ ok: boolean; diff?: string; error?: string }>("/api/git/diff"),
  gitCommit: (message: string) =>
    request("/api/git/commit", { method: "POST", body: JSON.stringify({ message }) }),
  terminalStart: () => request<{ ok: boolean; id: string }>("/api/terminal/start", { method: "POST" }),
  terminalInput: (id: string, data: string) =>
    request(`/api/terminal/${id}/input`, { method: "POST", body: JSON.stringify({ data }) }),
};

export type FileEntry = {
  path: string;
  type: "file" | "dir";
  name: string;
  size?: number;
};

export function wsUrl(): string {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  if (import.meta.env.DEV) {
    return `${proto}://${location.hostname}:8765/ws`;
  }
  return `${proto}://${location.host}/ws`;
}
