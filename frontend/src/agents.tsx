import type { Role } from "./api";

// Original blob characters. Each role has its own body shape, color, and a tiny prop,
// so you can tell them apart at a glance even without reading the name.
export const AGENTS: Record<Role, { name: string; job: string; color: string; soft: string; body: string }> = {
  boss: {
    name: "Boss", job: "reads tickets, makes the call", color: "#FF9F5A", soft: "#FFE8D6",
    body: "M50 10 C78 10 92 30 92 56 C92 80 74 92 50 92 C26 92 8 80 8 56 C8 30 22 10 50 10Z",
  },
  inventory: {
    name: "Inventory", job: "stock, sizes, restocks", color: "#6FA8F5", soft: "#E1EDFD",
    body: "M18 22 C30 12 70 12 82 22 C92 32 92 70 84 82 C74 94 26 94 16 82 C8 70 8 32 18 22Z",
  },
  accounting: {
    name: "Accounting", job: "cash, invoices, margins", color: "#5CC48A", soft: "#DDF3E6",
    body: "M50 8 C72 8 86 28 88 52 C90 78 72 94 50 94 C28 94 10 78 12 52 C14 28 28 8 50 8Z",
  },
  facilities: {
    name: "Facilities", job: "lease, rent, the space", color: "#A890EE", soft: "#ECE6FC",
    body: "M50 6 C60 6 66 16 76 22 C88 30 94 46 90 64 C86 84 70 94 50 94 C30 94 14 84 10 64 C6 46 12 30 24 22 C34 16 40 6 50 6Z",
  },
  customer_service: {
    name: "Customer Care", job: "drafts customer notes", color: "#FF8DAF", soft: "#FFE3EC",
    body: "M50 14 C64 4 90 12 92 40 C94 70 74 92 50 92 C26 92 6 70 8 40 C10 12 36 4 50 14Z",
  },
};

export const ROLES = Object.keys(AGENTS) as Role[];

function Prop({ role }: { role: Role }) {
  switch (role) {
    case "boss": // tiny crown
      return <path d="M36 14 L40 2 L46 10 L50 0 L54 10 L60 2 L64 14 Z" fill="#FFD166" stroke="#E8A93C" strokeWidth="2" strokeLinejoin="round" />;
    case "inventory": // little box
      return <g><rect x="68" y="58" width="22" height="18" rx="4" fill="#F3C98B" stroke="#C99A5B" strokeWidth="2" /><path d="M68 64 H90" stroke="#C99A5B" strokeWidth="2" /></g>;
    case "accounting": // coin
      return <g><circle cx="80" cy="66" r="11" fill="#FFD166" stroke="#E0A93A" strokeWidth="2" /><text x="80" y="71" textAnchor="middle" fontSize="13" fontWeight="800" fill="#B8862A">$</text></g>;
    case "facilities": // key
      return <g stroke="#7E68C9" strokeWidth="3" fill="none" strokeLinecap="round"><circle cx="82" cy="60" r="6" fill="#FFD166" /><path d="M82 66 V82 M82 76 H88" /></g>;
    case "customer_service": // heart
      return <path d="M80 80 C70 72 66 66 70 60 C73 56 78 57 80 61 C82 57 87 56 90 60 C94 66 90 72 80 80Z" fill="#FF5C8A" />;
  }
}

export type Mood = "idle" | "talking" | "done" | "asleep";

export function AgentBlob({ role, mood = "idle", size = 84 }: { role: Role; mood?: Mood; size?: number }) {
  const a = AGENTS[role];
  const eyesOpen = mood !== "asleep";
  return (
    <svg className={`blob blob-${mood}`} width={size} height={size} viewBox="0 0 100 100" aria-label={a.name}>
      <ellipse cx="50" cy="96" rx="30" ry="4" fill="#00000012" />
      <path d={a.body} fill={a.color} />
      <ellipse cx="34" cy="34" rx="10" ry="6" fill="#ffffff55" transform="rotate(-25 34 34)" />
      {eyesOpen ? (
        <g fill="#2B2A33">
          <ellipse className="eye" cx="38" cy="50" rx="4.5" ry="5.5" />
          <ellipse className="eye" cx="62" cy="50" rx="4.5" ry="5.5" />
          <circle cx="39.5" cy="48" r="1.5" fill="#fff" />
          <circle cx="63.5" cy="48" r="1.5" fill="#fff" />
        </g>
      ) : (
        <g stroke="#2B2A33" strokeWidth="2.5" fill="none" strokeLinecap="round">
          <path d="M33 51 Q38 55 43 51" /><path d="M57 51 Q62 55 67 51" />
        </g>
      )}
      <ellipse cx="28" cy="60" rx="5" ry="3" fill="#FF6B8B44" />
      <ellipse cx="72" cy="60" rx="5" ry="3" fill="#FF6B8B44" />
      {mood === "talking" ? (
        <ellipse className="mouth-talk" cx="50" cy="64" rx="5" ry="4" fill="#2B2A33" />
      ) : (
        <path d={mood === "done" ? "M42 61 Q50 70 58 61" : "M45 63 Q50 66 55 63"} stroke="#2B2A33" strokeWidth="2.5" fill="none" strokeLinecap="round" />
      )}
      <Prop role={role} />
    </svg>
  );
}

const TOOL_WORDS: Record<string, string> = {
  get_ticket: "Reading the ticket",
  list_open_tickets: "Scanning open tickets",
  list_tickets: "Scanning tickets",
  get_shop_date: "Checking the calendar",
  check_inventory: "Checking the shelves",
  list_vendors: "Calling around vendors",
  get_pricing: "Looking up prices",
  check_margin: "Crunching the margin",
  get_cash_balance: "Peeking at the cash",
  get_invoice: "Opening the invoice",
  find_payments: "Checking past payments",
  get_lease: "Pulling up the lease",
  prepare_payment: "Drafting a payment for you",
  prepare_purchase_order: "Drafting a purchase order",
};

export function toolSentence(tool: string, args: Record<string, unknown>): string {
  if (tool === "ask_agent") {
    const r = args.role as Role;
    return `Asking ${AGENTS[r]?.name ?? r} for help`;
  }
  const detail = Object.values(args).filter((v) => v !== undefined && v !== "").join(" · ");
  return `${TOOL_WORDS[tool] ?? tool}${detail ? ` (${detail})` : ""}`;
}
