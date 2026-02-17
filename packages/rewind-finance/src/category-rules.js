/**
 * Deterministic category tagger — regex-based, no LLM needed.
 * Maps transaction descriptions → categories + goal tags.
 */

const RULES = [
  // Tuition / education
  { pattern: /tuition|university|txstate|texas state|student|registrar/i, category: 'tuition', goalTag: 'short', goalName: 'Pay tuition' },
  // Credit card payments
  { pattern: /amex|american express|credit card|visa payment|chase payment/i, category: 'credit-card', goalTag: 'short', goalName: 'Pay off credit card' },
  // Family support
  { pattern: /nepal|family|zelle.*(?:mom|dad|ama|baba)|western union|remit/i, category: 'family-support', goalTag: 'short', goalName: 'Support parents monthly' },
  // Savings / investment
  { pattern: /savings|invest|transfer.*savings|deposit.*savings/i, category: 'savings', goalTag: 'medium', goalName: 'Save 15k by semester' },
  // Rent / housing
  { pattern: /rent|housing|apartment|lease|landlord/i, category: 'housing', goalTag: 'long', goalName: 'Move to SF' },
  // Food
  { pattern: /grocery|restaurant|uber\s?eats|doordash|grubhub|dining|food/i, category: 'food', goalTag: 'short', goalName: 'Daily expenses' },
  // Subscriptions
  { pattern: /spotify|netflix|openai|anthropic|github|aws|cloud|subscription/i, category: 'subscriptions', goalTag: 'short', goalName: 'Daily expenses' },
  // Income
  { pattern: /payroll|salary|stipend|freelance|invoice.*paid|direct deposit/i, category: 'income', goalTag: 'medium', goalName: 'Save 15k by semester' },
];

/**
 * Tag a transaction description with category + goal.
 * @param {string} description
 * @returns {{ category: string, goalTag: string, goalName: string }}
 */
function categorize(description) {
  for (const rule of RULES) {
    if (rule.pattern.test(description)) {
      return { category: rule.category, goalTag: rule.goalTag, goalName: rule.goalName };
    }
  }
  return { category: 'uncategorized', goalTag: 'short', goalName: 'Uncategorized expense' };
}

module.exports = { categorize, RULES };
