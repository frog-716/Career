import type { ResumeEditorController } from "../resume-workspace";

export function mountResumeEditor(options: {
  root: HTMLElement;
  documentId: string;
  legacy: boolean;
  submit: boolean;
  request: typeof fetch;
}): Promise<ResumeEditorController>;
