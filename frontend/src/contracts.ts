/**
 * JSON contracts for the Opportunity vertical.
 *
 * These are the browser-facing DTOs.  The server remains the authority for
 * runtime validation; this file keeps the UI boundary explicit without
 * pretending that arbitrary JSON is trusted TypeScript data.
 */
export type JsonPrimitive = string | number | boolean | null;
export type JsonValue = JsonPrimitive | JsonObject | JsonValue[];
export type JsonObject = { [key: string]: JsonValue };

export type OpportunityPhase = "resume" | "submitted" | "interview" | "offer";
export type OpportunityResult = "active" | "accepted" | "rejected" | "withdrawn";
export type ResearchScope = "company" | "opportunity";
export type InterviewType = "real" | "simulation";
export type InterviewStatus = "pending" | "scheduled" | "completed" | "cancelled";

export interface Opportunity {
  id: string;
  company_id: string;
  company: string;
  title: string;
  jd: string;
  phase: OpportunityPhase;
  result: OpportunityResult;
  revision: number;
  legacy_job_id?: string;
  action_url?: string;
  phase_changed_on?: string | null;
  result_changed_at?: string | null;
  greeting?: string | null;
  read_only?: boolean;
}

export interface ResearchEvidence {
  source_id?: string;
  source_type?: string;
  input_method?: string;
  observed_on?: string;
  excerpt?: string;
  owner_id?: string;
  scope?: ResearchScope;
}

export interface ResearchSourceRef {
  id?: string;
  url?: string;
  title?: string;
  retrieved_at?: string;
  date_status?: "current" | "stale" | "unknown";
  owner_id?: string;
  scope?: ResearchScope;
}

export interface ResearchItem {
  id: string;
  category: string;
  classification: string;
  content: string;
  status?: "current" | "retracted";
  evidence_status?: "lead" | "excerpt_present" | "user_confirmed" | "unknown";
  evidence?: ResearchEvidence[];
  source_refs?: ResearchSourceRef[];
  duplicate_of?: string | null;
  revision?: number;
}

export interface ResearchDocument {
  id: string;
  revision: number;
  items: ResearchItem[];
}

export interface ResearchProposal {
  id: string;
  status: "pending" | "accepted" | "rejected";
  stale?: boolean;
  stale_reason?: string;
  company_items?: ResearchItem[];
  opportunity_items?: ResearchItem[];
}

export interface ResearchView {
  company: ResearchDocument;
  opportunity: ResearchDocument;
  pending_proposals?: ResearchProposal[];
}

export interface Communication {
  id: string;
  type: "text" | "phone" | "other" | string;
  content: string;
  occurred_on?: string | null;
  revision: number;
  archived?: boolean;
  raw_note_id?: string;
}

export interface TimelineItem {
  id?: string;
  occurred_on?: string | null;
  title: string;
  summary: string;
  object_id?: string;
  target?: { kind: "communication" | "submission" | "interview" | "offer" };
}

export interface TimelineView {
  items: TimelineItem[];
  unknown_date_items: TimelineItem[];
}

export interface InterviewSession {
  id: string;
  opportunity_id: string;
  type: InterviewType | null;
  name: string | null;
  status: InterviewStatus | null;
  revision: number;
  confirmed_on?: string | null;
  scheduled_on?: string | null;
  scheduled_at?: string | null;
  completed_on?: string | null;
  cancelled_on?: string | null;
  target_real_interview_id?: string | null;
  source_communication?: Communication | { id: string; missing: true };
  source_communication_id?: string;
  has_final_review?: boolean;
  final_review_id?: string;
  legacy?: boolean;
  legacy_name?: string;
}

export interface InterviewPreparation {
  revision: number;
  focus: string;
  expected_questions: string[];
  priority_projects: string[];
  risks: string[];
  notes: string;
}

export interface InterviewReview {
  revision: number;
  summary: string;
  key_qa: string[];
  patterns: string[];
  discoveries: string[];
  next_actions: string[];
}

export interface ResumeContact {
  id?: string;
  kind?: string;
  content: string;
}

export interface ResumeItem {
  id?: string;
  title?: string;
  content?: string;
  organization?: string;
  role?: string;
  responsibility?: string;
  school?: string;
  major?: string;
  date?: string;
  bullets?: ResumeItem[];
}

export interface ResumeSection {
  id?: string;
  title: string;
  items: ResumeItem[];
}

export interface ResumeDocumentBody {
  profile: { name: string; contacts: ResumeContact[] };
  sections: ResumeSection[];
}

export interface ResumeDocument {
  id: string;
  document_id?: string;
  opportunity_id: string;
  revision?: number;
  document?: ResumeDocumentBody;
  company?: string;
  title?: string;
  saved_at?: string;
}

export interface ResumeVersion {
  id: string;
  name: string;
  document_id?: string;
  opportunity_id?: string;
  resume_id?: string;
  draft_revision?: number;
  created_at?: string;
  createdAt?: string;
  content?: string;
  document?: ResumeDocumentBody;
  version_kind?: "normal" | "submission" | string;
  artifact_id?: string;
  document_hash?: string;
  renderer_version?: string;
}

export interface ResumeArtifact {
  id: string;
  version_id?: string;
  media_type?: string;
  sha256?: string;
}

export interface Application {
  id: string;
  opportunity_id?: string;
  job_id?: string;
  artifact_id?: string;
  applied_at?: string;
  submitted_on?: string;
  channel?: string;
  resume_snapshot?: ResumeVersion;
  job_snapshot?: { company: string; title: string };
  submitted_greeting_snapshot?: { state: string; content?: string };
}

export interface ApiActions {
  api: <T extends JsonValue = JsonObject>(path: string, body?: JsonObject, method?: string) => Promise<T>;
  refresh: () => Promise<void>;
  go: (id: string, filter?: string) => void;
}

export interface OpportunityContext {
  state: {
    opportunities: Opportunity[];
    applications: Application[];
    resume_documents: ResumeDocument[];
    [key: string]: unknown;
  };
  domain: Record<string, unknown>;
  journey: { notes: Array<Record<string, unknown>> };
  id: string;
  filter: string;
  anchor: string;
  communications: Communication[];
  timeline: TimelineView;
  interviews: InterviewSession[];
  offer: Record<string, unknown> | null;
  research?: ResearchView;
}

export function isJsonObject(value: unknown): value is JsonObject {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export function parseJsonEnvelope(value: unknown): JsonValue {
  if (value !== null && typeof value !== "object") {
    throw new Error("服务器返回格式不正确");
  }
  return value as JsonValue;
}

function objectField(value: unknown, field: string): JsonValue {
  if (!isJsonObject(value) || !(field in value)) {
    throw new Error(`服务器返回缺少字段：${field}`);
  }
  return value[field];
}

function stringField(value: unknown, field: string, nullable = false): string | null {
  const fieldValue = objectField(value, field);
  if (nullable && fieldValue === null) return null;
  if (typeof fieldValue !== "string") throw new Error(`服务器返回字段格式不正确：${field}`);
  return fieldValue;
}

function numberField(value: unknown, field: string): number {
  const fieldValue = objectField(value, field);
  if (typeof fieldValue !== "number" || !Number.isInteger(fieldValue)) {
    throw new Error(`服务器返回字段格式不正确：${field}`);
  }
  return fieldValue;
}

function objectList(value: unknown, field: string): JsonObject[] {
  const fieldValue = objectField(value, field);
  if (!Array.isArray(fieldValue) || !fieldValue.every(isJsonObject)) {
    throw new Error(`服务器返回列表格式不正确：${field}`);
  }
  return fieldValue;
}

export function parseInterviewSessions(value: unknown): InterviewSession[] {
  if (!Array.isArray(value)) throw new Error("服务器返回 Interview 列表格式不正确");
  return value.map((item) => {
    if (!isJsonObject(item)) throw new Error("服务器返回 Interview 项格式不正确");
    const rawType = item.type;
    if (rawType !== null && rawType !== "real" && rawType !== "simulation") {
      throw new Error("服务器返回 Interview 类型不正确");
    }
    return {
      ...item,
      id: stringField(item, "id"),
      opportunity_id: stringField(item, "opportunity_id"),
      type: rawType,
      name: stringField(item, "name", true),
      status: stringField(item, "status", true) as InterviewStatus | null,
      revision: numberField(item, "revision"),
    } as InterviewSession;
  });
}

export function parseResearchView(value: unknown): ResearchView {
  if (!isJsonObject(value)) throw new Error("服务器返回 Research 格式不正确");
  const parseItems = (rawItems: JsonObject[]): ResearchItem[] => rawItems.map((item) => ({
    ...item,
    id: stringField(item, "id"),
    category: stringField(item, "category"),
    classification: stringField(item, "classification"),
    content: stringField(item, "content"),
  } as ResearchItem));
  const parseDocument = (field: string): ResearchDocument => {
    const raw = objectField(value, field);
    if (!isJsonObject(raw)) throw new Error(`服务器返回 Research 文档格式不正确：${field}`);
    const items = parseItems(objectList(raw, "items"));
    return { ...raw, id: stringField(raw, "id"), revision: numberField(raw, "revision"), items } as ResearchDocument;
  };
  const pending = value.pending_proposals;
  const proposals = Array.isArray(pending) ? pending.map((raw) => {
    if (!isJsonObject(raw)) throw new Error("服务器返回 Research proposal 格式不正确");
    const status = stringField(raw, "status");
    if (status !== "pending" && status !== "accepted" && status !== "rejected") {
      throw new Error("服务器返回 Research proposal 状态不正确");
    }
    return {
      ...raw,
      id: stringField(raw, "id"),
      status,
      ...(raw.company_items !== undefined ? { company_items: parseItems(objectList(raw, "company_items")) } : {}),
      ...(raw.opportunity_items !== undefined ? { opportunity_items: parseItems(objectList(raw, "opportunity_items")) } : {}),
    } as ResearchProposal;
  }) : undefined;
  return {
    company: parseDocument("company"),
    opportunity: parseDocument("opportunity"),
    ...(proposals ? { pending_proposals: proposals } : {}),
  };
}

export function parseResumeDocuments(value: unknown): ResumeDocument[] {
  if (!Array.isArray(value)) throw new Error("服务器返回简历工作稿列表格式不正确");
  return value.map((item) => {
    if (!isJsonObject(item)) throw new Error("服务器返回简历工作稿格式不正确");
    const rawDocument = item.document;
    if (rawDocument !== undefined &&
        (!isJsonObject(rawDocument) || !isJsonObject(rawDocument.profile) || !Array.isArray(rawDocument.sections))) {
      throw new Error("服务器返回简历工作稿正文格式不正确");
    }
    const id = typeof item.id === "string" ? item.id : stringField(item, "document_id");
    const revision = item.revision === undefined ? undefined : numberField(item, "revision");
    return {
      ...item,
      id,
      document_id: typeof item.document_id === "string" ? item.document_id : id,
      opportunity_id: stringField(item, "opportunity_id"),
      ...(revision === undefined ? {} : {revision}),
      ...(rawDocument === undefined ? {} : {document: rawDocument as unknown as ResumeDocumentBody}),
    } as ResumeDocument;
  });
}
