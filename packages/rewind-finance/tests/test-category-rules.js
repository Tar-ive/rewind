const { describe, it } = require('node:test');
const assert = require('node:assert/strict');
const { categorize } = require('../src/category-rules');

describe('categorize', () => {
  it('tags tuition payments', () => {
    const r = categorize('Texas State University tuition payment');
    assert.equal(r.category, 'tuition');
    assert.equal(r.goalTag, 'short');
  });

  it('tags AMEX credit card', () => {
    const r = categorize('AMEX autopay statement');
    assert.equal(r.category, 'credit-card');
    assert.equal(r.goalTag, 'short');
  });

  it('tags family support via Zelle', () => {
    const r = categorize('Zelle to Mom for monthly support');
    assert.equal(r.category, 'family-support');
    assert.equal(r.goalTag, 'short');
    assert.equal(r.goalName, 'Support parents monthly');
  });

  it('tags savings deposits', () => {
    const r = categorize('Transfer to savings account');
    assert.equal(r.category, 'savings');
    assert.equal(r.goalTag, 'medium');
    assert.equal(r.goalName, 'Save 15k by semester');
  });

  it('tags rent as long-term housing', () => {
    const r = categorize('Monthly rent payment - apartment');
    assert.equal(r.category, 'housing');
    assert.equal(r.goalTag, 'long');
    assert.equal(r.goalName, 'Move to SF');
  });

  it('tags payroll as income', () => {
    const r = categorize('Direct deposit - payroll');
    assert.equal(r.category, 'income');
    assert.equal(r.goalTag, 'medium');
  });

  it('returns uncategorized for unknown descriptions', () => {
    const r = categorize('Random wire transfer XYZ');
    assert.equal(r.category, 'uncategorized');
  });

  it('tags Nepal remittance as family support', () => {
    const r = categorize('Western Union to Nepal');
    assert.equal(r.category, 'family-support');
    assert.equal(r.goalName, 'Support parents monthly');
  });
});
