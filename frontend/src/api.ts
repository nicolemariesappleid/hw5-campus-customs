// All calls go to the FastAPI backend from Problem 7.
export const API = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export type Role = "boss" | "inventory" | "accounting" | "facilities" | "customer_service";

export interface Decision {
  ticket_id: number;
  status: "resolved" | "needs_human_approval" | "blocked";
  decision: string;
  agents_used?: Role[];
  actions?: string[];
  approvals_needed?: string[];
  customer_message_draft?: string;
}

export interface Ticket {
  id: number;
  type: string;
  requester: string;
  subject: string;
  status: "open" | "resolved";
  decision: Decision | null;
}

export interface AgentEvent {
  id: number;
  ts: string;
  event: "step" | "ticket_start" | "ticket_end" | "ticket_error" | "reset";
  ticket_id: number | null;
  run_id: string | null;
  agent?: Role;
  called_by?: Role | null;
  depth?: number;
  said?: string | null;
  tools?: { tool: string; args: Record<string, unknown> }[];
  output?: string;
  decision?: Decision;
  error?: string;
  usage?: { requests: number; tool_calls: number; input_tokens: number; output_tokens: number };
}

export interface Approval {
  id: number;
  ticket_id: number;
  type: "payment" | "purchase_order";
  status: "pending" | "approved";
  draft: Record<string, string | number>;
}

export interface Cash {
  found: boolean;
  name: string;
  balance: number;
  date: string;
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(API + path, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(body.detail ?? `${res.status} ${res.statusText}`);
  return body as T;
}

export const api = {
  tickets: () => call<Ticket[]>("/tickets"),
  run: (id: number) => call<{ decision?: Decision; error?: string }>(`/tickets/${id}/run`, { method: "POST" }),
  events: (after = -1, ticketId?: number) =>
    call<AgentEvent[]>(`/events?after=${after}&limit=500${ticketId ? `&ticket_id=${ticketId}` : ""}`),
  approvals: () => call<Approval[]>("/approvals"),
  approve: (id: number) =>
    call(`/approvals/${id}/approve`, { method: "POST", body: JSON.stringify({ approved_by: "dashboard" }) }),
  cash: () => call<Cash>("/cash"),
  reset: () => call("/reset", { method: "POST" }),
};
