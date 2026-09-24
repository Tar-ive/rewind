"use client";

import { useEffect, useState } from "react";
import { API_URL } from "@/lib/constants";
import {
  RadarChart,
  Radar,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  BarChart,
  Bar,
  LineChart,
  Line,
  ReferenceLine,
  ScatterChart,
  Scatter,
} from "recharts";

// ── Types ──────────────────────────────────────────────────────────────

interface ProfileData {
  user_profile: {
    peak_hours: number[];
    avg_task_durations: Record<string, number>;
    energy_curve: number[];
    adherence_score: number;
    distraction_patterns: Record<string, number>;
    estimation_bias: number;
    automation_comfort: Record<string, number>;
    disruption_recovery: { avg_recovery_score: number; num_observations: number };
    drift_direction: string;
  };
  grouping: {
    archetype: string;
    archetype_label: string;
    archetype_description: string;
    execution_composite: number;
    growth_composite: number;
    confidence: number;
    traits: Record<string, number>;
    normalized_traits: Record<string, number>;
  };
  success_plot: {
    execution_velocity: number;
    growth_trajectory: number;
    quadrant: string;
    quadrant_label: string;
    components: {
      x: Record<string, number>;
      y: Record<string, number>;
    };
  };
  sentiment: {
    trend: string;
    avg_score: number;
    scores: number[];
  };
  temporal_drift: {
    changed_fields: string[];
    magnitude: number;
    avg_magnitude: number;
    direction: Record<string, string>;
  } | null;
}

// ── Constants ──────────────────────────────────────────────────────────

const ARCHETYPE_STYLES: Record<string, { color: string; bg: string; border: string }> = {
  compounding_builder: { color: "text-green-400", bg: "bg-green-500/10", border: "border-green-500/30" },
  reliable_operator: { color: "text-blue-400", bg: "bg-blue-500/10", border: "border-blue-500/30" },
  emerging_talent: { color: "text-amber-400", bg: "bg-amber-500/10", border: "border-amber-500/30" },
  at_risk: { color: "text-red-400", bg: "bg-red-500/10", border: "border-red-500/30" },
};

const TRAIT_LABELS: Record<string, string> = {
  completion_consistency: "Completion",
  execution_rate: "Execution",
  growth_velocity: "Growth",
  self_awareness: "Awareness",
  ambition_calibration: "Ambition",
  recovery_speed: "Recovery",
};

const TREND_STYLES: Record<string, { color: string; label: string; stroke: string }> = {
  improving: { color: "text-green-400", label: "Improving", stroke: "#22c55e" },
  stable: { color: "text-blue-400", label: "Stable", stroke: "#3b82f6" },
  declining: { color: "text-red-400", label: "Declining", stroke: "#ef4444" },
  neutral: { color: "text-zinc-400", label: "Neutral", stroke: "#a1a1aa" },
};

// ── Reusable ChartCard ─────────────────────────────────────────────────

function ChartCard({
  title,
  children,
  className = "",
}: {
  title: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={`rounded-xl border border-zinc-800 bg-zinc-900 p-5 ${className}`}>
      <h3 className="text-sm font-semibold text-zinc-300 mb-4">{title}</h3>
      {children}
    </div>
  );
}

// ── Component ──────────────────────────────────────────────────────────

export default function ProfilePage() {
  const [data, setData] = useState<ProfileData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchProfile() {
      try {
        const res = await fetch(`${API_URL}/api/profile/full`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const json = await res.json();
        setData(json);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load profile");
      } finally {
        setLoading(false);
      }
    }
    fetchProfile();
  }, []);

  if (loading) {
    return (
      <div className="flex h-full flex-col">
        <header className="border-b border-zinc-800 px-6 py-5">
          <h1 className="text-lg font-semibold text-white">Profile</h1>
        </header>
        <div className="flex-1 overflow-y-auto p-6">
          <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-4">
            <div className="col-span-full h-32 animate-pulse rounded-xl bg-zinc-800/50" />
            {Array.from({ length: 6 }, (_, i) => (
              <div key={i} className="h-64 animate-pulse rounded-xl bg-zinc-800/50" />
            ))}
          </div>
        </div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="flex h-full flex-col">
        <header className="border-b border-zinc-800 px-6 py-5">
          <h1 className="text-lg font-semibold text-white">Profile</h1>
        </header>
        <div className="flex-1 flex items-center justify-center">
          <p className="text-sm text-zinc-500">{error || "No profile data available."}</p>
        </div>
      </div>
    );
  }

  const { user_profile, grouping, success_plot, sentiment } = data;
  const archetypeStyle = ARCHETYPE_STYLES[grouping.archetype] ?? ARCHETYPE_STYLES.at_risk;
  const trendStyle = TREND_STYLES[sentiment.trend] ?? TREND_STYLES.neutral;

  // ── Chart data transforms ──

  const radarData = Object.entries(grouping.normalized_traits || {}).map(([key, val]) => ({
    trait: TRAIT_LABELS[key] || key,
    value: Math.round(val * 100),
  }));

  const energyData = (user_profile.energy_curve || []).map((val, i) => ({
    hour: i,
    label: i % 6 === 0 ? `${i === 0 ? "12" : i > 12 ? i - 12 : i}${i < 12 ? "am" : "pm"}` : "",
    energy: val,
  }));

  const sentimentData = (sentiment.scores || []).map((score, i) => ({
    index: i + 1,
    score,
  }));

  const distractionData = Object.entries(user_profile.distraction_patterns || {}).map(
    ([key, val]) => ({
      name: key.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()),
      probability: Math.round(val * 100),
    })
  );

  const adherencePercent = Math.round((user_profile.adherence_score || 0) * 100);
  const adherenceColor = adherencePercent >= 75 ? "#22c55e" : adherencePercent >= 50 ? "#f59e0b" : "#ef4444";

  // Scatter plot data
  const scatterData = [
    { x: success_plot.execution_velocity, y: success_plot.growth_trajectory },
  ];

  return (
    <div className="flex h-full flex-col">
      <header className="border-b border-zinc-800 px-6 py-5">
        <h1 className="text-lg font-semibold text-white">Profile</h1>
        <p className="mt-1 text-sm text-zinc-500">
          Behavioral analytics from the Profiler Agent.
        </p>
      </header>

      <div className="flex-1 overflow-y-auto p-6">
        <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-4">
          {/* ── Archetype Badge (full width) ── */}
          <div
            className={`col-span-full rounded-xl border p-6 ${archetypeStyle.border} ${archetypeStyle.bg}`}
          >
            <div className="flex items-center gap-5">
              <div
                className={`flex h-14 w-14 items-center justify-center rounded-xl border ${archetypeStyle.border} ${archetypeStyle.bg}`}
              >
                <span className={`text-2xl font-bold ${archetypeStyle.color}`}>
                  {grouping.archetype_label?.charAt(0) || "?"}
                </span>
              </div>
              <div className="flex-1">
                <h2 className={`text-xl font-bold ${archetypeStyle.color}`}>
                  {grouping.archetype_label || grouping.archetype}
                </h2>
                <p className="text-sm text-zinc-400 mt-1">
                  {grouping.archetype_description}
                </p>
                <div className="flex items-center gap-3 mt-2">
                  <div className="flex items-center gap-1.5">
                    <span className="text-[10px] text-zinc-500">Confidence</span>
                    <div className="w-20 h-1.5 rounded-full bg-zinc-800 overflow-hidden">
                      <div
                        className="h-full rounded-full bg-amber-400"
                        style={{ width: `${Math.round(grouping.confidence * 100)}%` }}
                      />
                    </div>
                    <span className="text-[10px] text-zinc-500">
                      {Math.round(grouping.confidence * 100)}%
                    </span>
                  </div>
                  <span className="text-[10px] text-zinc-600">|</span>
                  <span className="text-[10px] text-zinc-500">
                    Exec: {Math.round(grouping.execution_composite * 100)}%
                  </span>
                  <span className="text-[10px] text-zinc-500">
                    Growth: {Math.round(grouping.growth_composite * 100)}%
                  </span>
                </div>
              </div>
            </div>
          </div>

          {/* ── Success Plot ── */}
          <ChartCard title="Success Plot">
            <ResponsiveContainer width="100%" height={250}>
              <ScatterChart margin={{ top: 10, right: 10, bottom: 20, left: 10 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#3f3f46" />
                <XAxis
                  type="number"
                  dataKey="x"
                  domain={[0, 1]}
                  name="Execution Velocity"
                  tick={{ fill: "#a1a1aa", fontSize: 10 }}
                  label={{
                    value: "Execution Velocity",
                    position: "insideBottom",
                    offset: -10,
                    fill: "#71717a",
                    fontSize: 11,
                  }}
                />
                <YAxis
                  type="number"
                  dataKey="y"
                  domain={[0, 1]}
                  name="Growth Trajectory"
                  tick={{ fill: "#a1a1aa", fontSize: 10 }}
                  label={{
                    value: "Growth",
                    angle: -90,
                    position: "insideLeft",
                    fill: "#71717a",
                    fontSize: 11,
                  }}
                />
                <ReferenceLine x={0.5} stroke="#3f3f46" strokeDasharray="3 3" />
                <ReferenceLine y={0.5} stroke="#3f3f46" strokeDasharray="3 3" />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "#18181b",
                    border: "1px solid #3f3f46",
                    borderRadius: "8px",
                    fontSize: "12px",
                  }}
                  formatter={(value: number) => value.toFixed(2)}
                />
                <Scatter
                  data={scatterData}
                  fill="#3b82f6"
                  shape={(props: { cx: number; cy: number }) => (
                    <circle cx={props.cx} cy={props.cy} r={10} fill="#3b82f6" stroke="#60a5fa" strokeWidth={2} />
                  )}
                />
              </ScatterChart>
            </ResponsiveContainer>
            <div className="flex justify-between text-[10px] text-zinc-600 mt-1 px-2">
              <span>Emerging Talent</span>
              <span>Compounding Builder</span>
            </div>
          </ChartCard>

          {/* ── Traits Radar ── */}
          <ChartCard title="Behavioral Traits">
            <ResponsiveContainer width="100%" height={280}>
              <RadarChart data={radarData} cx="50%" cy="50%" outerRadius="70%">
                <PolarGrid stroke="#3f3f46" />
                <PolarAngleAxis
                  dataKey="trait"
                  tick={{ fill: "#a1a1aa", fontSize: 11 }}
                />
                <PolarRadiusAxis
                  domain={[0, 100]}
                  tick={{ fill: "#52525b", fontSize: 9 }}
                  axisLine={false}
                />
                <Radar
                  dataKey="value"
                  stroke="#3b82f6"
                  fill="#3b82f6"
                  fillOpacity={0.15}
                  strokeWidth={2}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "#18181b",
                    border: "1px solid #3f3f46",
                    borderRadius: "8px",
                    fontSize: "12px",
                  }}
                />
              </RadarChart>
            </ResponsiveContainer>
          </ChartCard>

          {/* ── Energy Curve ── */}
          <ChartCard title="Daily Energy Curve">
            <ResponsiveContainer width="100%" height={200}>
              <AreaChart data={energyData} margin={{ top: 5, right: 5, bottom: 5, left: -20 }}>
                <defs>
                  <linearGradient id="energyGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#f59e0b" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#f59e0b" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#3f3f46" vertical={false} />
                <XAxis
                  dataKey="hour"
                  tick={{ fill: "#a1a1aa", fontSize: 10 }}
                  tickFormatter={(h) =>
                    h % 6 === 0
                      ? `${h === 0 ? "12a" : h === 12 ? "12p" : h > 12 ? `${h - 12}p` : `${h}a`}`
                      : ""
                  }
                />
                <YAxis
                  domain={[0, 5]}
                  ticks={[1, 2, 3, 4, 5]}
                  tick={{ fill: "#52525b", fontSize: 10 }}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "#18181b",
                    border: "1px solid #3f3f46",
                    borderRadius: "8px",
                    fontSize: "12px",
                  }}
                  labelFormatter={(h) => `${h}:00`}
                />
                <Area
                  type="monotone"
                  dataKey="energy"
                  stroke="#f59e0b"
                  strokeWidth={2}
                  fill="url(#energyGradient)"
                />
              </AreaChart>
            </ResponsiveContainer>
          </ChartCard>

          {/* ── Adherence Score ── */}
          <ChartCard title="Adherence Score">
            <div className="flex flex-col items-center justify-center py-4">
              <svg width="160" height="160" viewBox="0 0 160 160">
                {/* Background ring */}
                <circle
                  cx="80"
                  cy="80"
                  r="60"
                  stroke="#27272a"
                  strokeWidth="12"
                  fill="none"
                />
                {/* Progress ring */}
                <circle
                  cx="80"
                  cy="80"
                  r="60"
                  stroke={adherenceColor}
                  strokeWidth="12"
                  fill="none"
                  strokeDasharray={`${2 * Math.PI * 60}`}
                  strokeDashoffset={`${2 * Math.PI * 60 * (1 - adherencePercent / 100)}`}
                  strokeLinecap="round"
                  transform="rotate(-90 80 80)"
                  className="transition-all duration-1000"
                />
                <text
                  x="80"
                  y="76"
                  textAnchor="middle"
                  fill="white"
                  fontSize="28"
                  fontWeight="bold"
                >
                  {adherencePercent}%
                </text>
                <text
                  x="80"
                  y="96"
                  textAnchor="middle"
                  fill="#71717a"
                  fontSize="10"
                >
                  adherence
                </text>
              </svg>
              <div className="mt-3 text-center">
                <p className="text-xs text-zinc-500">
                  Estimation bias: {user_profile.estimation_bias?.toFixed(2) || "N/A"}x
                </p>
                <p className="text-xs text-zinc-600 mt-0.5">
                  Drift: {user_profile.drift_direction || "balanced"}
                </p>
              </div>
            </div>
          </ChartCard>

          {/* ── Sentiment Trend ── */}
          <ChartCard
            title={
              <span className="flex items-center gap-2">
                Sentiment Trend
                <span
                  className={`text-[10px] px-1.5 py-0.5 rounded ${trendStyle.color} bg-zinc-800`}
                >
                  {trendStyle.label}
                </span>
              </span>
            }
          >
            {sentimentData.length > 0 ? (
              <ResponsiveContainer width="100%" height={200}>
                <LineChart data={sentimentData} margin={{ top: 5, right: 5, bottom: 5, left: -20 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#3f3f46" vertical={false} />
                  <XAxis
                    dataKey="index"
                    tick={{ fill: "#a1a1aa", fontSize: 10 }}
                    label={{
                      value: "Entry",
                      position: "insideBottom",
                      offset: -5,
                      fill: "#71717a",
                      fontSize: 10,
                    }}
                  />
                  <YAxis
                    domain={[-1, 1]}
                    ticks={[-1, -0.5, 0, 0.5, 1]}
                    tick={{ fill: "#52525b", fontSize: 10 }}
                  />
                  <ReferenceLine y={0} stroke="#3f3f46" />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "#18181b",
                      border: "1px solid #3f3f46",
                      borderRadius: "8px",
                      fontSize: "12px",
                    }}
                    formatter={(value: number) => value.toFixed(3)}
                  />
                  <Line
                    type="monotone"
                    dataKey="score"
                    stroke={trendStyle.stroke}
                    strokeWidth={2}
                    dot={{ fill: trendStyle.stroke, r: 3 }}
                  />
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <p className="text-xs text-zinc-600 py-8 text-center">
                No reflection data available yet.
              </p>
            )}
          </ChartCard>

          {/* ── Distraction Patterns ── */}
          <ChartCard title="Distraction Patterns">
            {distractionData.length > 0 ? (
              <ResponsiveContainer width="100%" height={200}>
                <BarChart data={distractionData} margin={{ top: 5, right: 5, bottom: 5, left: -20 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#3f3f46" vertical={false} />
                  <XAxis
                    dataKey="name"
                    tick={{ fill: "#a1a1aa", fontSize: 10 }}
                    interval={0}
                    angle={-20}
                    textAnchor="end"
                    height={60}
                  />
                  <YAxis
                    domain={[0, 100]}
                    tick={{ fill: "#52525b", fontSize: 10 }}
                    tickFormatter={(v) => `${v}%`}
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "#18181b",
                      border: "1px solid #3f3f46",
                      borderRadius: "8px",
                      fontSize: "12px",
                    }}
                    formatter={(value: number) => `${value}%`}
                  />
                  <Bar dataKey="probability" fill="#ef4444" fillOpacity={0.6} radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <p className="text-xs text-zinc-600 py-8 text-center">
                No distraction data available.
              </p>
            )}
          </ChartCard>
        </div>
      </div>
    </div>
  );
}
