import assert from 'node:assert/strict';
import { createServer } from 'vite';

const vite = await createServer({
  configFile: false,
  root: new URL('..', import.meta.url).pathname,
  server: { middlewareMode: true },
  appType: 'custom',
});

try {
  const { opportunityHTML, opportunityReminderLabel } = await vite.ssrLoadModule('/src/opportunity-ui.ts');
  const empty = opportunityHTML({ state: { opportunities: [] }, journey: { plans: [] }, id: '', filter: 'all' });
  assert.match(empty, /<h3>还没有机会<\/h3><button class="op-empty-link" id="op-create-empty">添加第一个机会<\/button>/);
  assert.doesNotMatch(empty, /op-views|0 条|阶段筛选/);

  const phases = ['resume', 'submitted', 'interview', 'offer'];
  const opportunities = phases.map((phase, index) => ({
    id: `opportunity:o${index + 1}`,
    company: `虚构公司${index + 1}`,
    title: `虚构岗位${index + 1}`,
    phase,
    phase_changed_on: '2026-09-28',
    result: 'active',
  }));
  const journey = { plans: opportunities.map((item, index) => ({
    job_id: item.id.slice('opportunity:'.length),
    next_action: `虚构下一步${index + 1}`,
    due_date: '2026-09-30',
  })) };
  const list = opportunityHTML({ state: { opportunities }, journey, id: '', filter: 'all' });

  assert.match(list, /公司 \/ 岗位[\s\S]*阶段[\s\S]*下一步[\s\S]*提醒日期/);
  assert.equal((list.match(/class="op-stage-dot"/g) || []).length, 4);
  for (const phase of phases) assert.match(list, new RegExp(`op-stage-${phase}`));
  assert.match(list, /虚构下一步1/);
  assert.match(list, /26年9月30日/);
  assert.doesNotMatch(list.replace(/datetime="[^"]+"/g, ''), /阶段日期|2026-09-28|2026-09-30/);
  assert.equal(opportunityReminderLabel('2026-09-28', new Date('2026-09-28T04:00:00Z')), '今天');
  console.log('opportunity-visual: ok');
} finally {
  await vite.close();
}
