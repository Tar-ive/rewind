/**
 * TaskEmitter — converts FinanceRecords into scheduler-ready tasks
 * grouped by goal (long/medium/short) with readiness scores.
 *
 * Deterministic: no LLM. Thresholds decide urgency.
 */

/**
 * @typedef {object} SchedulerTask
 * @property {string} id
 * @property {string} title
 * @property {string} goalTag      - long|medium|short
 * @property {string} goalName
 * @property {number} urgency      - 0-1
 * @property {number} amount
 * @property {string} dueHint      - human-readable deadline hint
 * @property {string} action       - "pay" | "save" | "review" | "alert"
 */

const URGENCY_THRESHOLDS = {
  'tuition':       { base: 0.9, action: 'pay' },
  'credit-card':   { base: 0.85, action: 'pay' },
  'family-support':{ base: 0.8, action: 'pay' },
  'housing':       { base: 0.5, action: 'review' },
  'food':          { base: 0.3, action: 'review' },
  'subscriptions': { base: 0.2, action: 'review' },
  'savings':       { base: 0.6, action: 'save' },
  'income':        { base: 0.1, action: 'review' },
  'uncategorized': { base: 0.4, action: 'review' },
};

/**
 * Convert FinanceRecords into scheduler tasks.
 * @param {import('./finance-record').FinanceRecord[]} records
 * @returns {SchedulerTask[]}
 */
function emitTasks(records) {
  return records.map(r => {
    const rule = URGENCY_THRESHOLDS[r.category] || URGENCY_THRESHOLDS['uncategorized'];
    // Boost urgency for larger absolute amounts
    const amountBoost = Math.min(0.1, Math.abs(r.amount) / 50000);
    const urgency = Math.min(1.0, rule.base + amountBoost);

    return {
      id: `task-${r.id}`,
      title: `${rule.action === 'pay' ? '💸 Pay' : rule.action === 'save' ? '💰 Save' : '📋 Review'}: ${r.description || r.category} ($${Math.abs(r.amount).toFixed(2)})`,
      goalTag: r.goalTag,
      goalName: r.goalName,
      urgency: parseFloat(urgency.toFixed(3)),
      amount: r.amount,
      dueHint: r.goalTag === 'short' ? 'This week' : r.goalTag === 'medium' ? 'This month' : 'This quarter',
      action: rule.action,
    };
  });
}

/**
 * Group tasks by goal tag and sort by urgency descending.
 * @param {SchedulerTask[]} tasks
 */
function groupByGoal(tasks) {
  const groups = { long: [], medium: [], short: [] };
  for (const t of tasks) {
    (groups[t.goalTag] || groups.short).push(t);
  }
  for (const key of Object.keys(groups)) {
    groups[key].sort((a, b) => b.urgency - a.urgency);
  }
  return groups;
}

/**
 * Summarize tasks into a human-readable string.
 * @param {SchedulerTask[]} tasks
 */
function summarize(tasks) {
  const groups = groupByGoal(tasks);
  const lines = [];
  for (const [tag, items] of Object.entries(groups)) {
    if (items.length === 0) continue;
    const total = items.reduce((s, t) => s + t.amount, 0);
    lines.push(`[${tag.toUpperCase()}] ${items.length} task(s), net $${total.toFixed(2)}`);
    for (const t of items.slice(0, 5)) {
      lines.push(`  • ${t.title} (urgency: ${t.urgency})`);
    }
  }
  return lines.join('\n');
}

module.exports = { emitTasks, groupByGoal, summarize, URGENCY_THRESHOLDS };
