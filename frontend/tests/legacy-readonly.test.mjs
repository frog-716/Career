import assert from "node:assert/strict";
import { knowledgeUI, knowledgeView, resumeUses } from "../src/knowledge-ui.ts";

const old = { id: "old-entry", title: "虚构旧资料", content: "过去记录的虚构内容", entry_type: "project", scope_type: "personal", scope_id: "", status: "active", revision: 1 };
const data = {
  state: { jobs: [{ id: "job-old", company: "虚构公司", title: "旧岗位" }], opportunities: [{ id: "opportunity-old", legacy_job_id: "job-old" }] },
  journey: { episodes: [] },
  knowledge: { sources: [old], candidates: [{ ...old, id: "old-candidate", status: "pending" }], entries: [old] },
  domain: { resume_uses: [{ id: "use-old", version_name: "虚构旧版", target_name: "虚构方向", version_id: "version-old", artifact_id: "artifact-old", scope_type: "job", scope_id: "job-old" }] },
};
for (const tab of ["sources", "candidates", "entries"]) {
  knowledgeUI.tab = tab;
  knowledgeUI.scope = "all";
  knowledgeUI.selected = "";
  const html = knowledgeView(data, () => "");
  assert.match(html, /过去记录的虚构内容/, `旧 ${tab} 内容仍可读`);
  assert.doesNotMatch(html, /data-source-add|data-candidate-new|data-candidate-edit|data-candidate-confirm/, `旧 ${tab} 不再新增事实`);
  if (tab === "candidates") assert.match(html, /data-candidate-reject/, "旧待审建议仍可拒绝");
  if (tab === "entries") {
    assert.match(html, /data-entry-history/, "旧条目历史保留");
    assert.match(html, /data-entry-edit/, "旧已确认事实仍可纠错或撤回");
  }
}
const uses = resumeUses(data, "job-old");
assert.match(uses, /虚构旧版/);
assert.match(uses, /data-protected-artifact="artifact-old"/, "旧 PDF 仍可下载");
assert.doesNotMatch(uses, /id="resume-use"|data-application=/, "旧用途不再创建或驱动新投递");
assert.equal(resumeUses({ ...data, domain: { resume_uses: [] } }, "job-old"), "", "没有旧关联时不显示空用途模块");
console.log("legacy-readonly: ok");
