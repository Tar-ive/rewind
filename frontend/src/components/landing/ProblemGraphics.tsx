// Illustrations for "The Problem" section, drawn with markup instead of image files.

function Check() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" className="text-emerald-600">
      <path d="M20 6 9 17l-5-5" />
    </svg>
  );
}

function Cross() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" className="text-rose-500">
      <path d="M18 6 6 18M6 6l12 12" />
    </svg>
  );
}

const Card = ({ children }: { children: React.ReactNode }) => (
  <div className="w-full max-w-[460px] rounded-3xl border border-stone-200 bg-white p-7 shadow-xl shadow-stone-200/60">
    {children}
  </div>
);

export function StuckGraphic() {
  const items = [
    { label: "Reply to Prof. Martinez", done: true },
    { label: "CS 229 problem set", done: false, stuck: true },
    { label: "Gym: cardio", done: false },
    { label: "Update study group on Slack", done: false },
  ];
  return (
    <Card>
      <div className="mb-5 flex items-baseline justify-between">
        <span className="text-xs font-semibold uppercase tracking-widest text-stone-400">Today</span>
        <span className="text-xs text-stone-400">2:14 PM</span>
      </div>
      <ul className="space-y-3">
        {items.map((item) => (
          <li
            key={item.label}
            className={`flex items-center gap-3 rounded-xl border px-4 py-3 text-sm ${
              item.stuck ? "border-orange-300 bg-orange-50 text-stone-900" : "border-stone-200 text-stone-600"
            }`}
          >
            <span className={`flex h-5 w-5 items-center justify-center rounded-md border ${item.done ? "border-emerald-500 bg-emerald-50" : "border-stone-300"}`}>
              {item.done && <Check />}
            </span>
            <span className={item.done ? "line-through decoration-stone-300" : ""}>{item.label}</span>
            {item.stuck && <span className="ml-auto h-4 w-0.5 animate-pulse bg-orange-500" aria-hidden />}
          </li>
        ))}
      </ul>
      <p className="mt-5 text-sm text-stone-500">
        You know exactly what&apos;s next. <span className="font-medium text-stone-800">Starting is the hard part.</span>
      </p>
    </Card>
  );
}

export function ToolsGraphic() {
  const rows = [
    { tool: "Notion databases", plan: true, recover: false },
    { tool: "Time-blocking in Google Calendar", plan: true, recover: false },
    { tool: "Gamified to-do apps", plan: true, recover: false },
    { tool: "Rewind", plan: true, recover: true, highlight: true },
  ];
  return (
    <Card>
      <div className="grid grid-cols-[1fr_auto_auto] items-center gap-x-5 gap-y-1 text-sm">
        <span />
        <span className="text-center text-[11px] font-semibold uppercase tracking-wider text-stone-400">Plans</span>
        <span className="text-center text-[11px] font-semibold uppercase tracking-wider text-stone-400">Recovers</span>
        {rows.map((row) => (
          <div key={row.tool} className="contents">
            <span className={`border-t border-stone-100 py-3.5 ${row.highlight ? "font-semibold text-orange-600" : "text-stone-700"}`}>{row.tool}</span>
            <span className="flex justify-center border-t border-stone-100 py-3.5">{row.plan ? <Check /> : <Cross />}</span>
            <span className="flex justify-center border-t border-stone-100 py-3.5">{row.recover ? <Check /> : <Cross />}</span>
          </div>
        ))}
      </div>
    </Card>
  );
}

export function CascadeGraphic() {
  const segments = [
    { label: "Meeting runs over", minutes: 15, color: "bg-amber-400" },
    { label: "You space out", minutes: 10, color: "bg-orange-500" },
    { label: "Replanning", minutes: 20, color: "bg-rose-500" },
  ];
  return (
    <Card>
      <div className="mb-2 text-xs font-semibold uppercase tracking-widest text-stone-400">After one disruption</div>
      <div className="mb-6 text-5xl font-bold tracking-tight text-stone-900">
        45 <span className="text-2xl font-semibold text-stone-400">min gone</span>
      </div>
      <div className="flex h-4 w-full overflow-hidden rounded-full bg-stone-100">
        {segments.map((s) => (
          <div key={s.label} className={s.color} style={{ width: `${(s.minutes / 45) * 100}%` }} />
        ))}
      </div>
      <ul className="mt-5 space-y-2.5 text-sm">
        {segments.map((s) => (
          <li key={s.label} className="flex items-center gap-3 text-stone-600">
            <span className={`h-2.5 w-2.5 rounded-full ${s.color}`} />
            {s.label}
            <span className="ml-auto font-mono text-stone-900">+{s.minutes}m</span>
          </li>
        ))}
      </ul>
      <div className="mt-6 rounded-xl bg-stone-900 px-4 py-3 text-sm text-white">
        With Rewind: a replanned day and a nudge on screen in <span className="font-semibold text-amber-300">under 3 seconds</span>.
      </div>
    </Card>
  );
}
