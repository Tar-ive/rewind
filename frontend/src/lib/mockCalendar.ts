/**
 * Mock Google Calendar events for demo — ADHD student (Sarah) at Stanford.
 *
 * Shows a realistic week of an ADHD student:
 *  - Overcommitted, back-to-back blocks with no breaks
 *  - Scattered priorities (academic, social, health, admin)
 *  - Poor time estimation (overlapping events)
 *  - Natural disruption points the scheduler can recover from
 *
 * "Before Rewind" = this raw calendar chaos.
 * "After Rewind" = the Dashboard's clean, prioritized, energy-aware schedule.
 */

// Demo base: Feb 15, 2026
const DEMO_BASE = new Date(2026, 1, 15); // month is 0-indexed

function today(hour: number, min = 0): string {
  const d = new Date(DEMO_BASE);
  d.setHours(hour, min, 0, 0);
  return d.toISOString();
}

function dayOffset(days: number, hour: number, min = 0): string {
  const d = new Date(DEMO_BASE);
  d.setDate(d.getDate() + days);
  d.setHours(hour, min, 0, 0);
  return d.toISOString();
}

export interface MockCalendarEvent {
  id: string;
  summary: string;
  title: string;
  description?: string;
  location?: string;
  start: { dateTime: string };
  end: { dateTime: string };
}

export const MOCK_CALENDAR_EVENTS: MockCalendarEvent[] = [
  // ─── TODAY (Sunday) — The demo day ──────────────────────────────────
  {
    id: "cal-1",
    summary: "CS 161 — Operating Systems Lecture",
    title: "CS 161 — Operating Systems Lecture",
    description: "Prof. Cain. Chapters 26-28: Concurrency, Locks.",
    location: "Gates B01",
    start: { dateTime: today(9, 0) },
    end: { dateTime: today(10, 20) },
  },
  {
    id: "cal-2",
    summary: "Study Group — CS 229 ML",
    title: "Study Group — CS 229 ML",
    description: "Review gradient descent convergence proofs for midterm",
    location: "Huang Basement",
    start: { dateTime: today(10, 30) },
    end: { dateTime: today(12, 0) },
  },
  {
    id: "cal-3",
    summary: "Gym — Cardio + Stretching",
    title: "Gym — Cardio + Stretching",
    description: "30 min run, 15 min stretch. Skip = guilt spiral",
    location: "AOERC",
    start: { dateTime: today(12, 0) },
    end: { dateTime: today(13, 0) },
  },
  {
    id: "cal-overcommit-1",
    summary: "Lunch w/ Rachel (forgot to cancel)",
    title: "Lunch w/ Rachel (forgot to cancel)",
    description: "Said yes 2 weeks ago, totally forgot about gym",
    location: "Coupa Café",
    start: { dateTime: today(12, 15) },
    end: { dateTime: today(13, 15) },
  },
  {
    id: "cal-4",
    summary: "CS 229 Problem Set 4",
    title: "CS 229 Problem Set 4",
    description: "⚠️ DUE TOMORROW 11:59 PM. Gradient descent + regularization.",
    start: { dateTime: today(14, 0) },
    end: { dateTime: today(16, 0) },
  },
  {
    id: "cal-5",
    summary: "Office Hours — Prof. Ng",
    title: "Office Hours — Prof. Ng",
    description: "Ask about Q3 on pset. Last chance before due date.",
    location: "Gates 259",
    start: { dateTime: today(16, 0) },
    end: { dateTime: today(17, 0) },
  },
  {
    id: "cal-6",
    summary: "Reply to Prof. Martinez — Research Position",
    title: "Reply to Prof. Martinez — Research Position",
    description: "Follow up on research assistant position. She emailed 3 days ago. URGENT.",
    start: { dateTime: today(17, 0) },
    end: { dateTime: today(17, 15) },
  },
  {
    id: "cal-7",
    summary: "TreeHacks team sync",
    title: "TreeHacks team sync",
    description: "Check in with hackathon team about project status",
    location: "Zoom",
    start: { dateTime: today(17, 30) },
    end: { dateTime: today(18, 0) },
  },
  {
    id: "cal-adhd-1",
    summary: "ADHD meds refill — call pharmacy",
    title: "ADHD meds refill — call pharmacy",
    description: "CVS closes at 6. MUST call before then. Kept forgetting all week.",
    start: { dateTime: today(17, 0) },
    end: { dateTime: today(17, 10) },
  },
  {
    id: "cal-8",
    summary: "Dinner — Arrillaga",
    title: "Dinner — Arrillaga",
    start: { dateTime: today(18, 30) },
    end: { dateTime: today(19, 15) },
  },
  {
    id: "cal-9",
    summary: "Physics 41 Lab Report (procrastinated)",
    title: "Physics 41 Lab Report (procrastinated)",
    description: "Due Friday but haven't started intro. Will take 2+ hours.",
    start: { dateTime: today(20, 0) },
    end: { dateTime: today(22, 0) },
  },

  // ─── TOMORROW (Monday) ─────────────────────────────────────────────
  {
    id: "cal-m1",
    summary: "CS 229 Lecture",
    title: "CS 229 Lecture",
    description: "Support Vector Machines + Kernel Methods",
    location: "NVIDIA Auditorium",
    start: { dateTime: dayOffset(1, 9, 30) },
    end: { dateTime: dayOffset(1, 10, 50) },
  },
  {
    id: "cal-m2",
    summary: "CAPS Therapy Session",
    title: "CAPS Therapy Session",
    description: "Biweekly session. Don't skip again.",
    location: "Vaden Health Center",
    start: { dateTime: dayOffset(1, 11, 0) },
    end: { dateTime: dayOffset(1, 12, 0) },
  },
  {
    id: "cal-m3",
    summary: "CS 161 Section",
    title: "CS 161 Section",
    location: "Gates B03",
    start: { dateTime: dayOffset(1, 13, 0) },
    end: { dateTime: dayOffset(1, 14, 0) },
  },
  {
    id: "cal-m4",
    summary: "Research meeting — Prof. Martinez",
    title: "Research meeting — Prof. Martinez",
    description: "First meeting if she accepts. Need to reply to email first!",
    location: "Clark Center S295",
    start: { dateTime: dayOffset(1, 15, 0) },
    end: { dateTime: dayOffset(1, 16, 0) },
  },
  {
    id: "cal-m5",
    summary: "Club meeting — AI Society",
    title: "Club meeting — AI Society",
    description: "Committed to presenting but haven't prepped slides",
    location: "Hewlett 200",
    start: { dateTime: dayOffset(1, 17, 0) },
    end: { dateTime: dayOffset(1, 18, 0) },
  },
  {
    id: "cal-m6",
    summary: "Dentist (conflicts w/ study session)",
    title: "Dentist (conflicts w/ study session)",
    description: "Need to cancel — conflicts with everything. $50 cancellation fee if < 24hrs",
    location: "Palo Alto Dental",
    start: { dateTime: dayOffset(1, 14, 0) },
    end: { dateTime: dayOffset(1, 15, 0) },
  },

  // ─── TUESDAY ────────────────────────────────────────────────────────
  {
    id: "cal-t1",
    summary: "Physics 41 Lecture",
    title: "Physics 41 Lecture",
    location: "Hewlett 201",
    start: { dateTime: dayOffset(2, 10, 0) },
    end: { dateTime: dayOffset(2, 11, 30) },
  },
  {
    id: "cal-t2",
    summary: "CS 229 Project — Team Work Session",
    title: "CS 229 Project — Team Work Session",
    description: "Build model pipeline. Need GPU access sorted first.",
    location: "Huang 018",
    start: { dateTime: dayOffset(2, 13, 0) },
    end: { dateTime: dayOffset(2, 16, 0) },
  },
  {
    id: "cal-t3",
    summary: "Gym — Weights",
    title: "Gym — Weights",
    location: "AOERC",
    start: { dateTime: dayOffset(2, 17, 0) },
    end: { dateTime: dayOffset(2, 18, 0) },
  },
  {
    id: "cal-t4",
    summary: "Order textbook — CS 161",
    title: "Order textbook — CS 161",
    description: "Keep forgetting. Amazon same-day delivery if ordered before 2pm.",
    start: { dateTime: dayOffset(2, 11, 30) },
    end: { dateTime: dayOffset(2, 11, 45) },
  },

  // ─── WEDNESDAY ──────────────────────────────────────────────────────
  {
    id: "cal-w1",
    summary: "CS 161 Lecture",
    title: "CS 161 Lecture",
    location: "Gates B01",
    start: { dateTime: dayOffset(3, 9, 0) },
    end: { dateTime: dayOffset(3, 10, 20) },
  },
  {
    id: "cal-w2",
    summary: "CS 229 Lecture",
    title: "CS 229 Lecture",
    location: "NVIDIA Auditorium",
    start: { dateTime: dayOffset(3, 10, 30) },
    end: { dateTime: dayOffset(3, 11, 50) },
  },
  {
    id: "cal-w3",
    summary: "Read ML Paper — Attention Is All You Need",
    title: "Read ML Paper — Attention Is All You Need",
    description: "Presenting next week. Haven't started reading.",
    start: { dateTime: dayOffset(3, 14, 0) },
    end: { dateTime: dayOffset(3, 15, 30) },
  },
  {
    id: "cal-w4",
    summary: "Notion — Update project tracker",
    title: "Notion — Update project tracker",
    description: "CS 229 project milestones. Team keeps asking for updates.",
    start: { dateTime: dayOffset(3, 15, 30) },
    end: { dateTime: dayOffset(3, 16, 0) },
  },

  // ─── THURSDAY ───────────────────────────────────────────────────────
  {
    id: "cal-th1",
    summary: "Physics 41 Lab",
    title: "Physics 41 Lab",
    location: "Varian Physics Building",
    start: { dateTime: dayOffset(4, 9, 0) },
    end: { dateTime: dayOffset(4, 12, 0) },
  },
  {
    id: "cal-th2",
    summary: "Study Group — CS 161 Midterm Prep",
    title: "Study Group — CS 161 Midterm Prep",
    location: "Green Library",
    start: { dateTime: dayOffset(4, 13, 0) },
    end: { dateTime: dayOffset(4, 15, 0) },
  },
  {
    id: "cal-th3",
    summary: "Uber to airport pickup (mom visiting)",
    title: "Uber to airport pickup (mom visiting)",
    description: "Flight lands 5:30 PM. Need to leave by 4:45.",
    location: "SFO Terminal 2",
    start: { dateTime: dayOffset(4, 16, 45) },
    end: { dateTime: dayOffset(4, 18, 30) },
  },

  // ─── FRIDAY ─────────────────────────────────────────────────────────
  {
    id: "cal-f1",
    summary: "Physics 41 Lab Report DUE",
    title: "Physics 41 Lab Report DUE",
    description: "⚠️ DEADLINE 5:00 PM. Submit on Gradescope.",
    start: { dateTime: dayOffset(5, 16, 0) },
    end: { dateTime: dayOffset(5, 17, 0) },
  },
  {
    id: "cal-f2",
    summary: "CS 161 Office Hours",
    title: "CS 161 Office Hours",
    location: "Gates 178",
    start: { dateTime: dayOffset(5, 10, 0) },
    end: { dateTime: dayOffset(5, 11, 0) },
  },
  {
    id: "cal-f3",
    summary: "Dinner w/ Mom",
    title: "Dinner w/ Mom",
    description: "She's visiting for the weekend. Reservation made.",
    location: "Evvia Estiatorio, Palo Alto",
    start: { dateTime: dayOffset(5, 18, 30) },
    end: { dateTime: dayOffset(5, 20, 0) },
  },

  // ─── SATURDAY ───────────────────────────────────────────────────────
  {
    id: "cal-s1",
    summary: "Brunch w/ Mom",
    title: "Brunch w/ Mom",
    location: "The Creamery",
    start: { dateTime: dayOffset(6, 10, 0) },
    end: { dateTime: dayOffset(6, 11, 30) },
  },
  {
    id: "cal-s2",
    summary: "Catch up on CS 229 recordings (behind 2 lectures)",
    title: "Catch up on CS 229 recordings (behind 2 lectures)",
    description: "Missed Tuesday + Thursday lectures. Need to watch before Monday.",
    start: { dateTime: dayOffset(6, 13, 0) },
    end: { dateTime: dayOffset(6, 16, 0) },
  },
  {
    id: "cal-s3",
    summary: "Laundry + clean room (overdue)",
    title: "Laundry + clean room (overdue)",
    description: "Haven't done laundry in 2 weeks. Running out of clean clothes.",
    start: { dateTime: dayOffset(6, 16, 30) },
    end: { dateTime: dayOffset(6, 18, 0) },
  },
];
