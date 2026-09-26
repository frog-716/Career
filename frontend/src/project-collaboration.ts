import { participantsForProject, type ParticipantRow, type PersonRow, type ProjectRow } from "./person-relations.ts";

const e = (value: unknown): string =>
  String(value ?? "").replace(/[&<>"']/g, (char) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char]!,
  );

export function projectCollaborationHTML(
  project: ProjectRow,
  persons: PersonRow[],
  participants: ParticipantRow[],
): string {
  if (!project.id || !project.employment_id) return "";
  const linked = participantsForProject(project, persons, participants);
  const rows = linked.length
    ? linked.map(({ person, role }) =>
        `<div class="setting-row"><span>${e(person.name)}${person.role ? ` · ${e(person.role)}` : ""}</span><span>${e(role || "项目成员")}</span></div>`,
      ).join("")
    : `<span class="muted">还没有关联人物。</span>`;
  return `<section class="work-domain-card project-collaboration"><div class="pane-heading"><h3>协作人物</h3><div class="actions"><button class="secondary" data-work-participant="${e(project.id)}">关联人物</button></div></div>${rows}</section>`;
}
