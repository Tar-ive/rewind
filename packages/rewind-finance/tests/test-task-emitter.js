const { describe, it } = require('node:test');
const assert = require('node:assert/strict');
const { FinanceRecord } = require('../src/finance-record');
const { emitTasks, groupByGoal, summarize } = require('../src/task-emitter');

const RECORDS = [
  new FinanceRecord({ description: 'Tuition', amount: -4500, category: 'tuition', goalTag: 'short', goalName: 'Pay tuition' }),
  new FinanceRecord({ description: 'AMEX', amount: -350, category: 'credit-card', goalTag: 'short', goalName: 'Pay off credit card' }),
  new FinanceRecord({ description: 'Zelle Mom', amount: -500, category: 'family-support', goalTag: 'short', goalName: 'Support parents monthly' }),
  new FinanceRecord({ description: 'Savings', amount: -1000, category: 'savings', goalTag: 'medium', goalName: 'Save 15k by semester' }),
  new FinanceRecord({ description: 'Rent', amount: -950, category: 'housing', goalTag: 'long', goalName: 'Move to SF' }),
  new FinanceRecord({ description: 'Payroll', amount: 2200, category: 'income', goalTag: 'medium', goalName: 'Save 15k by semester' }),
];

describe('emitTasks', () => {
  it('converts records to tasks with correct urgency ordering', () => {
    const tasks = emitTasks(RECORDS);
    assert.equal(tasks.length, 6);

    // Tuition should have highest urgency (base 0.9 + amount boost)
    const tuition = tasks.find(t => t.title.includes('Tuition'));
    assert.ok(tuition.urgency >= 0.9);
    assert.equal(tuition.action, 'pay');
    assert.equal(tuition.dueHint, 'This week');
  });

  it('tags pay actions for bills', () => {
    const tasks = emitTasks(RECORDS);
    const payTasks = tasks.filter(t => t.action === 'pay');
    assert.equal(payTasks.length, 3); // tuition, amex, family
  });

  it('tags save actions for savings', () => {
    const tasks = emitTasks(RECORDS);
    const saveTasks = tasks.filter(t => t.action === 'save');
    assert.equal(saveTasks.length, 1);
    assert.equal(saveTasks[0].goalName, 'Save 15k by semester');
  });
});

describe('groupByGoal', () => {
  it('groups and sorts by urgency desc', () => {
    const tasks = emitTasks(RECORDS);
    const groups = groupByGoal(tasks);

    assert.equal(groups.short.length, 3);
    assert.equal(groups.medium.length, 2);
    assert.equal(groups.long.length, 1);

    // Short tasks sorted by urgency descending
    assert.ok(groups.short[0].urgency >= groups.short[1].urgency);
  });
});

describe('summarize', () => {
  it('produces readable summary', () => {
    const tasks = emitTasks(RECORDS);
    const text = summarize(tasks);
    assert.ok(text.includes('[SHORT]'));
    assert.ok(text.includes('[MEDIUM]'));
    assert.ok(text.includes('[LONG]'));
    assert.ok(text.includes('task(s)'));
  });
});
