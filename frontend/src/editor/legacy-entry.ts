const source = new URLSearchParams(location.search);
const target = new URLSearchParams();
const documentId = source.get("document_id");
if (documentId) target.set("document_id", documentId);
if (source.get("legacy") === "1") target.set("legacy", "1");
if (source.get("submit") === "1") target.set("submit", "1");

if (source.get("job_id") && !documentId) {
  location.replace(`/#opportunities/${encodeURIComponent(source.get("job_id")!)}`);
} else {
  location.replace(`/#resume${target.size ? `?${target.toString()}` : ""}`);
}
