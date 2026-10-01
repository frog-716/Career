import assert from 'node:assert/strict';
import {
  feishuImportRequest,
  feishuPreviewHTML,
  feishuResultsHTML,
  readLocalTextFile,
} from '../src/feishu-source-ui.ts';

const hostile = '<img src=x onerror="alert(1)"> & title';
assert.equal(feishuResultsHTML([], false, false), '');
assert.ok(feishuResultsHTML([], false, true).includes('没有找到匹配文档'));
const results = feishuResultsHTML([{
  title: hostile,
  resource_type: 'docx',
  edited_at: '<script>bad</script>',
  selection_id: 'selection_fixture_1234567890',
  summary_highlighted: 'PRIVATE_SEARCH_SNIPPET',
}], true);
assert.ok(results.includes('&lt;img src=x onerror=&quot;alert(1)&quot;&gt; &amp; title'));
assert.ok(results.includes('&lt;script&gt;bad&lt;/script&gt;'));
assert.ok(!results.includes('<img'));
assert.ok(!results.includes('PRIVATE_SEARCH_SNIPPET'));
assert.ok(results.includes('data-feishu-more'));

const preview = feishuPreviewHTML({
  resource: { title: hostile, resource_type: 'doc', url: 'https://attacker.invalid/phish' },
  content: '<script>exfiltrate()</script> & harmless text',
});
assert.ok(preview.includes('&lt;script&gt;exfiltrate()&lt;/script&gt; &amp; harmless text'));
assert.ok(!preview.includes('<script>'));
assert.ok(!preview.includes('attacker.invalid'));
assert.ok(!preview.includes('href='));

const trusted = feishuPreviewHTML({
  resource: { title: '方案', resource_type: 'docx', url: 'https://team.feishu.cn/docx/abc' },
  content: 'only this selected content',
});
assert.ok(trusted.includes('href="https://team.feishu.cn/docx/abc"'));

const payload = feishuImportRequest('preview_fixture_1234567890', {
  scope_type: 'personal', scope_id: '',
}, 'idempotency_fixture_1234567890');
assert.deepEqual(payload, {
  preview_id: 'preview_fixture_1234567890',
  scope_type: 'personal',
  scope_id: '',
  idempotency_key: 'idempotency_fixture_1234567890',
});
assert.ok(!JSON.stringify(payload).includes('only this selected content'));
assert.ok(!JSON.stringify(payload).includes('content'));

const localBytes = new TextEncoder().encode('本机合成资料');
const localDraft = await readLocalTextFile({
  name: 'notes.md',
  size: localBytes.byteLength,
  async arrayBuffer() { return localBytes.buffer; },
});
assert.deepEqual(localDraft, { title: 'notes.md', content: '本机合成资料' });
await assert.rejects(readLocalTextFile({
  name: 'private.pdf', size: 1, async arrayBuffer() { return new ArrayBuffer(0); },
}), /仅支持 TXT 或 Markdown/);
await assert.rejects(readLocalTextFile({
  name: 'oversized.txt', size: 400_001, async arrayBuffer() { return new ArrayBuffer(0); },
}), /不能超过 400 KB/);
await assert.rejects(readLocalTextFile({
  name: 'invalid.txt', size: 1, async arrayBuffer() { return Uint8Array.from([255]).buffer; },
}), /encoded|encoding|encoded data/i);
console.log('Feishu source UI contract tests passed');
