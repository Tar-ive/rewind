import Image from "next/image";
import Link from "next/link";
import Reveal from "@/components/landing/Reveal";
import { CascadeGraphic, StuckGraphic, ToolsGraphic } from "@/components/landing/ProblemGraphics";

const GITHUB_URL = "https://github.com/Tar-ive/rewind";

const problems = [
  {
    eyebrow: "Executive dysfunction",
    title: "Planning isn't the problem",
    description:
      "6.1 million adults in the U.S. are diagnosed with ADHD. Diagnosis isn't the hard part. With the executive dysfunction that comes with ADHD, starting can feel impossible even when you know exactly what you need to do. The problem is what happens when the plan breaks.",
    graphic: <StuckGraphic />,
  },
  {
    eyebrow: "Every tool, same flaw",
    title: "They help you plan, then abandon you",
    description:
      "Two members of our team live with ADHD. We've tried every productivity system: Notion databases, time-blocking in Google Calendar, even gamified to-do apps. They all fail the same way: they help you plan, then leave you on your own the moment something goes wrong.",
    graphic: <ToolsGraphic />,
  },
  {
    eyebrow: "The moment we target",
    title: "The 15–30 minutes after a disruption",
    description:
      "A meeting runs 15 minutes over. You space out for 10. By the time you've replanned, 45 minutes are gone, and your momentum with it. That window after the plan breaks, when you're silently stuck with no idea what to do next, is exactly where Rewind steps in.",
    graphic: <CascadeGraphic />,
  },
];

const schedulers = [
  {
    tier: "LTS",
    name: "Long-Term Scheduler",
    os: "Plans allocation",
    life: "Plans your day. Scores tasks by deadline urgency (40%), priority (30%), peak-hour fit (15%) and duration (15%), then bin-packs them into your available hours, correcting for how much you usually underestimate.",
  },
  {
    tier: "MTS",
    name: "Medium-Term Scheduler",
    os: "Handles swaps",
    life: "Recovers from disruptions. When time is freed or lost, it swaps tasks between your active schedule and the backlog, and never schedules a task that's beyond your current energy.",
  },
  {
    tier: "STS",
    name: "Short-Term Scheduler",
    os: "Decides what runs now",
    life: "Picks what you do next. A four-level multilevel feedback queue (P0–P3) lets urgent tasks jump the line while respecting energy constraints.",
  },
];

const features = [
  {
    badge: "Targets: Disruption paralysis",
    title: "Disruption detection",
    description:
      "The Context Sentinel watches your Google Calendar, Gmail and Slack. The moment reality diverges from your plan, the Disruption Detector rates it: minor (a meeting ran 5 min over), major (a meeting was cancelled) or critical (an urgent Slack from your manager).",
    image: "/images/agent-activity.png",
    alt: "Agent activity feed showing Scheduler Kernel and GhostWorker events",
  },
  {
    badge: "Targets: Cognitive overload from replanning",
    title: "Auto-rescheduling",
    description:
      "You never replan by hand. The Scheduler Kernel rebalances your day across all three tiers and puts the single next thing to do in front of you.",
    image: "/images/dashboard.png",
    alt: "Dashboard with today's prioritized tasks and backlog",
  },
  {
    badge: "Targets: Time blindness",
    title: "Estimation correction",
    description:
      "The Profiler Agent learns your actual peak hours (not when you think you're productive) and how much you underestimate tasks, then corrects every plan it makes. It gets smarter with every interaction.",
    image: "/images/profile.png",
    alt: "Profile with success plot, behavioral traits and daily energy curve",
  },
  {
    badge: "Targets: Working memory limitations",
    title: "Energy-aware scheduling",
    description:
      "The Energy Monitor combines research-backed circadian patterns with how you actually complete tasks. The goal: never assign a task your brain can't handle right now.",
    image: "/images/calendar.png",
    alt: "Weekly calendar view of the scheduled tasks",
  },
  {
    badge: "Proactive: one-tap approvals",
    title: "GhostWorker does the busywork",
    description:
      "When being proactive can save you from a disruption, GhostWorker drafts the email, Slack reply or meeting reschedule for you. You approve it with one tap.",
    image: "/images/ghostworker-draft.png",
    alt: "A drafted email waiting for approval",
  },
];

const steps = [
  { agent: "Context Sentinel", text: "Notices your meeting ran 15 minutes over." },
  { agent: "Disruption Detector", text: "Classifies it and calculates the time you lost." },
  { agent: "Scheduler Kernel", text: "Swaps tasks out and reorders the rest of your day." },
  { agent: "You", text: "See the one next thing to do, in under 3 seconds." },
];

const team = [
  {
    name: "Saksham Adhikari",
    photo: "/images/team/saksham.jpg",
    roles: ["2x Intern @ AskSLM", "6x Hackathon Winner", "Google TPU Research Cloud Grantee"],
  },
  {
    name: "Kusum Bhattarai Sharma",
    photo: "/images/team/kusum.jpg",
    roles: ["4x Hackathon Winner", "AI Research @ THRC"],
  },
  {
    name: "Himavanth Karpurapu",
    photo: "/images/team/himavanth.jpg",
    roles: ["MS CS @ SJSU", "Amazon Web Services ABW Grant Scholar"],
  },
  {
    name: "Pranavi Rohit",
    photo: "/images/team/pranavi.jpg",
    roles: ["ECE & AI @ CMU", "Agentic AI @ Boeing"],
  },
];

function Arrow() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M5 12h14M13 6l6 6-6 6" />
    </svg>
  );
}

function SectionHeading({ title, subtitle }: { title: string; subtitle: string }) {
  return (
    <Reveal className="mx-auto mb-20 max-w-2xl text-center">
      <h2 className="mb-4 text-3xl font-bold tracking-tight text-stone-900 md:text-4xl">{title}</h2>
      <p className="text-lg leading-relaxed text-stone-500">{subtitle}</p>
    </Reveal>
  );
}

function Screenshot({ src, alt }: { src: string; alt: string }) {
  return (
    <div className="overflow-hidden rounded-2xl border border-stone-200 bg-zinc-950 shadow-2xl shadow-stone-300/60">
      <div className="flex gap-1.5 border-b border-zinc-800 px-4 py-3">
        <span className="h-2.5 w-2.5 rounded-full bg-zinc-700" />
        <span className="h-2.5 w-2.5 rounded-full bg-zinc-700" />
        <span className="h-2.5 w-2.5 rounded-full bg-zinc-700" />
      </div>
      <Image src={src} alt={alt} width={1318} height={720} className="h-auto w-full" />
    </div>
  );
}

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-[#FBFAF8] text-stone-900">
      {/* Navigation */}
      <nav className="sticky top-0 z-50 border-b border-stone-200/80 bg-white/85 backdrop-blur-xl">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-6">
          <Link href="/" className="text-sm font-bold tracking-[0.3em]">REWIND</Link>
          <div className="hidden items-center gap-10 text-sm font-medium text-stone-500 md:flex">
            <a href="#problem" className="transition-colors hover:text-stone-900">Problem</a>
            <a href="#idea" className="transition-colors hover:text-stone-900">The idea</a>
            <a href="#features" className="transition-colors hover:text-stone-900">Features</a>
            <a href="#how" className="transition-colors hover:text-stone-900">How it works</a>
            <a href="#team" className="transition-colors hover:text-stone-900">Team</a>
          </div>
          <Link href="/dashboard" className="rounded-xl bg-stone-900 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-stone-700">
            Open dashboard
          </Link>
        </div>
      </nav>

      {/* Hero */}
      <section className="relative overflow-hidden">
        <div className="pointer-events-none absolute -top-40 right-0 h-[520px] w-[520px] rounded-full bg-orange-200/50 blur-3xl" />
        <div className="relative mx-auto grid max-w-7xl items-center gap-16 px-6 py-24 md:px-12 lg:grid-cols-2 lg:py-32">
          <Reveal>
            <p className="mb-5 text-xs font-semibold uppercase tracking-[0.25em] text-orange-600">An operating system for your life</p>
            <h1 className="mb-6 text-4xl font-bold leading-[1.05] tracking-tight md:text-6xl">
              When the plan breaks,{" "}
              <span className="bg-gradient-to-r from-amber-500 to-orange-600 bg-clip-text text-transparent">Rewind picks it up.</span>
            </h1>
            <p className="mb-10 max-w-xl text-lg leading-relaxed text-stone-500">
              Every productivity tool helps you make a plan. Rewind, built for people with ADHD, helps when the plan breaks. It detects disruptions,
              reschedules your day like an OS schedules processes, and drafts the busywork for you.
            </p>
            <div className="flex flex-wrap items-center gap-4">
              <Link href="/dashboard" className="inline-flex h-14 items-center gap-2 rounded-2xl bg-orange-600 px-8 text-base font-medium text-white shadow-lg shadow-orange-600/25 transition-colors hover:bg-orange-700">
                View dashboard <Arrow />
              </Link>
              <a href={GITHUB_URL} className="inline-flex h-14 items-center rounded-2xl border border-stone-300 px-8 text-base font-medium text-stone-700 transition-colors hover:bg-white">
                View on GitHub
              </a>
            </div>
            <dl className="mt-14 grid max-w-lg grid-cols-3 gap-6">
              {[
                ["6.1M", "U.S. adults diagnosed with ADHD"],
                ["<3s", "from disruption to nudge"],
                ["3-tier", "OS-style scheduler"],
              ].map(([value, label]) => (
                <div key={label}>
                  <dt className="text-2xl font-bold tracking-tight">{value}</dt>
                  <dd className="mt-1 text-xs leading-snug text-stone-500">{label}</dd>
                </div>
              ))}
            </dl>
          </Reveal>
          <Reveal delay={200} className="relative">
            <Screenshot src="/images/agent-activity.png" alt="Rewind dashboard with the agent activity feed" />
            <Image
              src="/images/glasses-hud.jpg"
              alt="The schedule viewed through Meta Ray-Ban glasses"
              width={1318}
              height={720}
              className="absolute -bottom-10 -left-6 hidden w-56 rounded-xl border-4 border-white shadow-2xl sm:block"
            />
          </Reveal>
        </div>
      </section>

      {/* The Problem */}
      <section id="problem" className="bg-white py-28">
        <div className="mx-auto max-w-7xl px-6">
          <SectionHeading title="The Problem" subtitle="Productivity tools are built for the plan. People with ADHD need help with what happens after it breaks." />
          <div className="space-y-28">
            {problems.map((problem, i) => (
              <Reveal key={problem.title}>
                <div className={`flex flex-col items-center gap-12 md:gap-24 ${i % 2 === 1 ? "md:flex-row-reverse" : "md:flex-row"}`}>
                  <div className="flex-1">
                    <p className="mb-4 text-xs font-semibold uppercase tracking-[0.2em] text-orange-600">{problem.eyebrow}</p>
                    <h3 className="mb-6 text-3xl font-bold leading-tight md:text-4xl">{problem.title}</h3>
                    <p className="text-lg leading-relaxed text-stone-500">{problem.description}</p>
                  </div>
                  <div className="flex w-full flex-1 justify-center">{problem.graphic}</div>
                </div>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* The Idea */}
      <section id="idea" className="bg-stone-900 py-28 text-white">
        <div className="mx-auto max-w-6xl px-6">
          <Reveal className="mx-auto mb-16 max-w-3xl text-center">
            <h2 className="mb-5 text-3xl font-bold tracking-tight md:text-4xl">It&apos;s not a willpower problem. It&apos;s a working-memory problem.</h2>
            <p className="text-lg leading-relaxed text-stone-400">
              When processes compete for limited CPU time and interrupts fire unexpectedly, an operating system doesn&apos;t panic. It doesn&apos;t delete
              processes when something changes; it reschedules them. Rewind applies the same model to your day.
            </p>
          </Reveal>
          <div className="grid gap-6 md:grid-cols-3">
            {schedulers.map((s, i) => (
              <Reveal key={s.tier} delay={i * 120}>
                <div className="h-full rounded-2xl border border-stone-700 bg-stone-800/60 p-7">
                  <div className="mb-5 flex items-center justify-between">
                    <span className="rounded-lg bg-orange-500/15 px-2.5 py-1 font-mono text-sm font-semibold text-orange-400">{s.tier}</span>
                    <span className="text-xs text-stone-500">OS: {s.os.toLowerCase()}</span>
                  </div>
                  <h3 className="mb-3 text-lg font-semibold">{s.name}</h3>
                  <p className="text-sm leading-relaxed text-stone-400">{s.life}</p>
                </div>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* Features */}
      <section id="features" className="bg-[#FBFAF8] py-28">
        <div className="mx-auto max-w-7xl px-6">
          <SectionHeading
            title="Built from clinical research"
            subtitle="We didn't start from a feature list. Each core workflow targets a specific ADHD challenge documented in clinical research."
          />
          <div className="space-y-32">
            {features.map((feature, i) => (
              <Reveal key={feature.title}>
                <div className={`flex flex-col items-center gap-12 md:gap-20 ${i % 2 === 0 ? "md:flex-row" : "md:flex-row-reverse"}`}>
                  <div className="flex-1">
                    <span className="mb-5 inline-block rounded-full border border-orange-200 bg-orange-50 px-3 py-1 text-xs font-medium text-orange-700">
                      {feature.badge}
                    </span>
                    <h3 className="mb-6 text-3xl font-bold leading-tight md:text-4xl">{feature.title}</h3>
                    <p className="text-lg leading-relaxed text-stone-500">{feature.description}</p>
                  </div>
                  <div className="w-full flex-1">
                    <Screenshot src={feature.image} alt={feature.alt} />
                  </div>
                </div>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* How it works */}
      <section id="how" className="bg-white py-28">
        <div className="mx-auto max-w-6xl px-6">
          <SectionHeading title="How it works" subtitle="Seven agents share context and talk to each other. Here's what happens when your meeting runs over." />
          <div className="grid gap-6 md:grid-cols-4">
            {steps.map((step, i) => (
              <Reveal key={step.agent} delay={i * 120}>
                <div className="h-full rounded-2xl border border-stone-200 bg-[#FBFAF8] p-7">
                  <div className="mb-5 flex h-10 w-10 items-center justify-center rounded-xl bg-orange-100 font-mono text-sm font-semibold text-orange-700">{i + 1}</div>
                  <h3 className="mb-2 font-semibold">{step.agent}</h3>
                  <p className="text-sm leading-relaxed text-stone-500">{step.text}</p>
                </div>
              </Reveal>
            ))}
          </div>
          <Reveal className="mx-auto mt-20 max-w-4xl">
            <div className="overflow-hidden rounded-2xl border border-stone-200 shadow-2xl shadow-stone-300/60">
              {/* Animated GIF: bypass the image optimizer so it keeps playing */}
              <Image src="/images/demo-ghostworker.gif" alt="GhostWorker drafts an email, the user approves it and it is sent" width={960} height={524} unoptimized className="h-auto w-full" />
            </div>
            <p className="mt-4 text-center text-sm text-stone-500">
              The Scheduler Kernel hands a task to GhostWorker, which drafts the email for you to approve with one tap.
            </p>
          </Reveal>
        </div>
      </section>

      {/* Team */}
      <section id="team" className="bg-[#2E1F3D] py-28">
        <div className="mx-auto max-w-6xl px-6">
          <Reveal className="mx-auto mb-20 max-w-2xl text-center">
            <h2 className="mb-5 text-4xl font-bold tracking-tight text-[#FBF6EC] md:text-6xl">Meet the team.</h2>
            <p className="text-lg leading-relaxed text-stone-300">
              Two of us live with ADHD. We built Rewind at TreeHacks for the moment the plan breaks.
            </p>
          </Reveal>
          <div className="grid grid-cols-2 gap-x-6 gap-y-14 md:grid-cols-4">
            {team.map((member, i) => (
              <Reveal key={member.name} delay={i * 100} className="text-center">
                <Image
                  src={member.photo}
                  alt={member.name}
                  width={400}
                  height={400}
                  className="mx-auto mb-6 h-32 w-32 rounded-full border-4 border-[#1F1529] object-cover md:h-36 md:w-36"
                />
                <h3 className="text-lg font-semibold text-orange-400 md:text-xl">{member.name}</h3>
                <ul className="mt-2 space-y-1 text-sm text-stone-300">
                  {member.roles.map((role) => (
                    <li key={role}>{role}</li>
                  ))}
                </ul>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="bg-gradient-to-br from-amber-500 via-orange-500 to-orange-600 py-24">
        <Reveal className="mx-auto max-w-4xl px-6 text-center">
          <h2 className="mb-4 text-3xl font-bold tracking-tight text-white md:text-4xl">Every tool helps you make a plan. Rewind helps when it breaks.</h2>
          <p className="mx-auto mb-10 max-w-2xl text-lg text-white/85">
            Catch the disruption, replan the day and get back to the next task before momentum is gone.
          </p>
          <Link href="/dashboard" className="inline-flex h-14 items-center gap-2 rounded-2xl bg-stone-900 px-8 text-lg font-medium text-white transition-colors hover:bg-stone-800">
            Open the dashboard <Arrow />
          </Link>
        </Reveal>
      </section>

      {/* Footer */}
      <footer className="border-t border-stone-200 bg-[#FBFAF8] py-8">
        <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-3 px-6 sm:flex-row">
          <span className="text-sm font-bold tracking-[0.3em] text-stone-500">REWIND</span>
          <p className="text-sm text-stone-400">
            Built at TreeHacks ·{" "}
            <a href={GITHUB_URL} className="underline decoration-stone-300 underline-offset-4 hover:text-stone-600">GitHub</a>
          </p>
        </div>
      </footer>
    </div>
  );
}
