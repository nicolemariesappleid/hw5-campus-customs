import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, type AgentEvent, type Approval, type Cash, type Role, type Ticket } from "./api";
import { AGENTS, AgentBlob, ROLES, toolSentence, type Mood } from "./agents";

const money = (n: number) => n.toLocaleString("en-US", { style: "currency", currency: "USD" });

function greeting() {
  const h = new Date().getHours();
  return h < 12 ? "Good morning" : h < 18 ? "Good afternoon" : "Good evening";
}

// One line an agent "said" during a step: its words if it spoke, otherwise what it was doing.
function lineFor(e: AgentEvent): string | null {
  if (e.said) return e.said;
  if (e.tools?.length) return e.tools.map((t) => toolSentence(t.tool, t.args)).join(" · ");
  return null;
}

// Pull a specialist's summary out of its final output (clipped JSON in the audit trail).
function summaryFrom(output?: string): string | null {
  if (!output) return null;
  try {
    const o = JSON.parse(output);
    return o.summary ?? o.decision ?? null;
  } catch {
    const m = output.match(/"(?:summary|decision)":\s*"((?:[^"\\]|\\.)*)/);
    return m ? m[1] : null;
  }
}

export default function App() {
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [cash, setCash] = useState<Cash | null>(null);
  const [cashDelta, setCashDelta] = useState<number | null>(null);
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [selected, setSelected] = useState<number | null>(null);
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [running, setRunning] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const lastId = useRef(-1);
  const prevBalance = useRef<number | null>(null);
  const feedEnd = useRef<HTMLDivElement>(null);

  const refresh = useCallback(async () => {
    try {
      const [t, c, a] = await Promise.all([api.tickets(), api.cash(), api.approvals()]);
      setTickets(t);
      setApprovals(a);
      if (prevBalance.current !== null && c.balance !== prevBalance.current) {
        setCashDelta(c.balance - prevBalance.current);
        setTimeout(() => setCashDelta(null), 3500);
      }
      prevBalance.current = c.balance;
      setCash(c);
      setSelected((s) => s ?? t[0]?.id ?? null);
      setError(null);
    } catch (e) {
      setError(`Can't reach the backend at ${import.meta.env.VITE_API_URL}. Is uvicorn running? (${(e as Error).message})`);
    }
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  // Load this ticket's history whenever you pick a ticket.
  useEffect(() => {
    if (selected == null) return;
    api.events(-1, selected).then((ev) => {
      setEvents(ev);
      lastId.current = ev.length ? ev[ev.length - 1].id : lastId.current;
    }).catch(() => {});
  }, [selected]);

  // While the team runs, poll for new events so the bubbles update live.
  useEffect(() => {
    if (running == null) return;
    const timer = setInterval(async () => {
      try {
        const fresh = await api.events(lastId.current);
        if (!fresh.length) return;
        lastId.current = fresh[fresh.length - 1].id;
        const mine = fresh.filter((e) => e.ticket_id === running);
        if (mine.length) setEvents((ev) => [...ev, ...mine]);
      } catch { /* keep polling */ }
    }, 900);
    return () => clearInterval(timer);
  }, [running]);

  // Only show the latest run for this ticket.
  const runEvents = useMemo(() => {
    const starts = events.filter((e) => e.event === "ticket_start");
    const runId = starts.length ? starts[starts.length - 1].run_id : null;
    return runId ? events.filter((e) => e.run_id === runId) : [];
  }, [events]);

  const ticket = tickets.find((t) => t.id === selected) ?? null;
  const isRunning = running === selected && selected != null;
  const finished = runEvents.find((e) => e.event === "ticket_end" || e.event === "ticket_error");
  const steps = runEvents.filter((e) => e.event === "step" && lineFor(e));
  const lastStep = [...runEvents].reverse().find((e) => e.event === "step");

  useEffect(() => { feedEnd.current?.scrollIntoView({ behavior: "smooth", block: "nearest" }); }, [steps.length]);

  const perAgent = useMemo(() => {
    const out = {} as Record<Role, { lines: string[]; tools: string[]; summary: string | null; done: boolean }>;
    for (const r of ROLES) out[r] = { lines: [], tools: [], summary: null, done: false };
    for (const e of runEvents) {
      if (e.event !== "step" || !e.agent) continue;
      const a = out[e.agent];
      const line = lineFor(e);
      if (line) a.lines.push(line);
      for (const t of e.tools ?? []) if (!a.tools.includes(t.tool)) a.tools.push(t.tool);
      if (e.output) { a.done = true; a.summary = summaryFrom(e.output) ?? a.summary; }
    }
    const end = runEvents.find((e) => e.event === "ticket_end");
    if (end?.decision) { out.boss.summary = end.decision.decision; out.boss.done = true; }
    return out;
  }, [runEvents]);

  const moodOf = (r: Role): Mood => {
    if (isRunning) return lastStep?.agent === r ? "talking" : perAgent[r].lines.length ? "idle" : "asleep";
    if (finished) return perAgent[r].lines.length ? "done" : "asleep";
    return r === "boss" ? "idle" : "asleep";
  };

  async function start() {
    if (!ticket) return;
    setError(null);
    setRunning(ticket.id);
    try {
      const res = await api.run(ticket.id);
      if (res.error) setError(`The team stopped: ${res.error}`);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      const ev = await api.events(-1, ticket.id).catch(() => null);
      if (ev) { setEvents(ev); if (ev.length) lastId.current = Math.max(lastId.current, ev[ev.length - 1].id); }
      setRunning(null);
      refresh();
    }
  }

  async function approve(id: number) {
    let problem: string | null = null;
    try { await api.approve(id); } catch (e) { problem = `Couldn't approve: ${(e as Error).message}`; }
    await refresh();
    if (problem) setError(problem); // show after refresh so it isn't cleared
  }

  async function reset() {
    try { await api.reset(); setEvents([]); } catch (e) { setError((e as Error).message); }
    refresh();
  }

  const ticketApprovals = approvals.filter((a) => a.ticket_id === selected);

  return (
    <div className="app">
      <header className="top">
        <div>
          <div className="brand"><span className="dot" />Campus Customs</div>
          <h1>{greeting()}. Let's tidy up the desk.</h1>
        </div>
        <div className={`cash ${cashDelta && cashDelta < 0 ? "cash-drop" : ""}`}>
          <span className="cash-label">Checking</span>
          <span className="cash-amount">{cash ? money(cash.balance) : "—"}</span>
          {cashDelta != null && <span className="cash-delta">{cashDelta < 0 ? "−" : "+"}{money(Math.abs(cashDelta))}</span>}
          {cash && <span className="cash-date">as of {cash.date}</span>}
        </div>
      </header>

      {error && <div className="toast" role="alert">{error}</div>}

      <main className="layout">
        <aside className="tickets">
          <h2>Tickets</h2>
          {tickets.map((t) => {
            const waiting = approvals.filter((a) => a.ticket_id === t.id).length;
            return (
              <button key={t.id} className={`ticket ${t.id === selected ? "on" : ""} ${t.status}`} onClick={() => setSelected(t.id)}>
                <span className="ticket-id">#{t.id}</span>
                <span className="ticket-subject">{t.subject}</span>
                <span className="ticket-from">{t.requester}</span>
                <span className="chips">
                  {running === t.id ? <span className="chip chip-run">Team working…</span>
                    : t.status === "resolved" ? <span className="chip chip-done">✓ Resolved</span>
                    : <span className="chip">Open</span>}
                  {waiting > 0 && <span className="chip chip-wait">{waiting} to approve</span>}
                </span>
              </button>
            );
          })}
          <button className="ghost" onClick={reset} disabled={running != null}>Reset shop to original</button>
        </aside>

        {ticket && (
          <section className="stage-wrap">
            <div className="hero">
              <div>
                <span className="eyebrow">{ticket.type.replace(/_/g, " ")} · #{ticket.id}</span>
                <h2>{ticket.subject}</h2>
                <p className="muted">from {ticket.requester}</p>
              </div>
              <button className="go" onClick={start} disabled={running != null}>
                {isRunning ? "The team is on it…" : finished ? "Run the team again" : "Start the team"}
              </button>
            </div>

            <div className="stage">
              {ROLES.map((r) => {
                const lines = perAgent[r].lines;
                const bubble = isRunning && lastStep?.agent === r ? lineFor(lastStep)
                  : finished && r === "boss" ? perAgent.boss.summary
                  : null;
                return (
                  <div key={r} className={`agent agent-${moodOf(r)}`} style={{ ["--soft" as string]: AGENTS[r].soft }}>
                    <div className={`bubble ${bubble ? "show" : ""}`}>{bubble ?? " "}</div>
                    <AgentBlob role={r} mood={moodOf(r)} />
                    <div className="agent-name">{AGENTS[r].name}</div>
                    <div className="agent-job">{lines.length ? `${lines.length} step${lines.length > 1 ? "s" : ""}` : AGENTS[r].job}</div>
                  </div>
                );
              })}
            </div>

            <div className="panels">
              <div className="panel">
                <h3>Conversation</h3>
                {steps.length === 0 && !isRunning && <p className="muted empty">Nobody's said anything yet. Start the team and the conversation shows up here.</p>}
                <div className="feed">
                  {steps.map((e) => (
                    <div key={e.id} className="msg" style={{ ["--soft" as string]: AGENTS[e.agent!].soft }}>
                      <AgentBlob role={e.agent!} mood="idle" size={34} />
                      <div className="msg-body">
                        <div className="msg-who">
                          {AGENTS[e.agent!].name}
                          {e.called_by && <span className="muted"> · asked by {AGENTS[e.called_by].name}</span>}
                        </div>
                        <div className="msg-text">{lineFor(e)}</div>
                      </div>
                    </div>
                  ))}
                  {isRunning && <div className="typing"><span /><span /><span /></div>}
                  <div ref={feedEnd} />
                </div>
              </div>

              <div className="side">
                {ticketApprovals.length > 0 && (
                  <div className="panel approve-panel">
                    <h3>Waiting for you</h3>
                    {ticketApprovals.map((a) => (
                      <div key={a.id} className="approval">
                        <div>
                          <div className="approval-title">
                            {a.type === "payment" ? `Pay ${a.draft.payee}` : `Order ${a.draft.qty} × ${a.draft.sku} ${a.draft.size} from ${a.draft.vendor}`}
                          </div>
                          <div className="muted small">
                            {a.type === "payment" ? `${a.draft.kind} · due ${a.draft.due_date}` : `${a.draft.lead_days} day lead time`}
                          </div>
                        </div>
                        <div className="approval-right">
                          <span className="approval-amt">{money(Number(a.type === "payment" ? a.draft.amount : a.draft.total_cost))}</span>
                          <button className="approve" onClick={() => approve(a.id)}>Approve</button>
                        </div>
                      </div>
                    ))}
                    <p className="muted small">Simulated shop: approving only updates the practice database.</p>
                  </div>
                )}

                <div className="panel">
                  <h3>What each agent did</h3>
                  {!finished && <p className="muted empty">The summary appears when the run finishes.</p>}
                  {finished && ROLES.filter((r) => perAgent[r].lines.length).map((r) => (
                    <div key={r} className="sum" style={{ ["--soft" as string]: AGENTS[r].soft }}>
                      <AgentBlob role={r} mood="done" size={30} />
                      <div>
                        <div className="sum-who">{AGENTS[r].name}</div>
                        <div className="sum-text">{perAgent[r].summary ?? "Helped out."}</div>
                        {perAgent[r].tools.length > 0 && (
                          <div className="tools">{perAgent[r].tools.map((t) => <span key={t} className="tool">{t}</span>)}</div>
                        )}
                      </div>
                    </div>
                  ))}
                  {finished && ROLES.filter((r) => !perAgent[r].lines.length).length > 0 && (
                    <p className="muted small">Sat this one out: {ROLES.filter((r) => !perAgent[r].lines.length).map((r) => AGENTS[r].name).join(", ")}</p>
                  )}
                  {finished?.event === "ticket_end" && finished.usage && (
                    <p className="muted small">{finished.usage.requests} model calls · {finished.usage.tool_calls} tool calls · {(finished.usage.input_tokens + finished.usage.output_tokens).toLocaleString()} tokens</p>
                  )}
                </div>
              </div>
            </div>
          </section>
        )}
      </main>
    </div>
  );
}
