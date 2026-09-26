export type PersonRow = {
  id: string;
  employment_id?: string | null;
  identity_status?: "confirmed" | "unresolved";
  name: string;
  role?: string;
};

export type ProjectRow = { id?: string; employment_id?: string | null };
export type ParticipantRow = { id: string; project_id: string; person_id: string; role: string };

export function peopleForEmployment(persons: PersonRow[], employmentId: string): PersonRow[] {
  if (!employmentId) return [];
  return persons.filter((person) => person.employment_id === employmentId);
}

export function eligiblePeopleForProject(project: ProjectRow, persons: PersonRow[]): PersonRow[] {
  if (!project.employment_id) return [];
  return persons.filter(
    (person) => person.employment_id === project.employment_id && person.identity_status === "confirmed",
  );
}

export function participantsForProject(
  project: ProjectRow,
  persons: PersonRow[],
  participants: ParticipantRow[],
): Array<{ person: PersonRow; role: string }> {
  if (!project.id || !project.employment_id) return [];
  const eligible = new Map(eligiblePeopleForProject(project, persons).map((person) => [person.id, person]));
  return participants
    .filter((participant) => participant.project_id === project.id)
    .flatMap((participant) => {
      const person = eligible.get(participant.person_id);
      return person ? [{ person, role: participant.role }] : [];
    });
}
