const AUTOMATION_API_BASE = document.querySelector('meta[name="automation-api-base"]')?.content || "http://127.0.0.1:8090";

class ApiError extends Error {
  constructor(code, message) { super(message); this.name = "ApiError"; this.code = code; }
}

async function request(path, options = {}, timeoutMs = 10000) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(`${AUTOMATION_API_BASE}${path}`, { ...options, signal: controller.signal });
    let body = null;
    try { body = await response.json(); } catch { /* empty response */ }
    if (!response.ok) throw new ApiError(`HTTP_${response.status}`, "Không thể kết nối với dịch vụ tự động hóa.");
    return body;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    throw new ApiError(error.name === "AbortError" ? "TIMEOUT" : "NETWORK", "Không thể kết nối với dịch vụ tự động hóa.");
  } finally { clearTimeout(timer); }
}

function startJob(deliveryDate, autoPrint, printOptions) {
  return request("/api/automation/jobs", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ deliveryDate, autoPrint, printOptions }) });
}
function getJob(id) { return request(`/api/automation/jobs/${encodeURIComponent(id)}`, {}, 15000); }
function triggerPrint(id, printOptions) {
  const body = printOptions ? { printOptions } : undefined;
  return request(`/api/automation/jobs/${encodeURIComponent(id)}/print`, { method: "POST", headers: { "Content-Type": "application/json" }, ...(body ? { body: JSON.stringify(body) } : {}) }, 30000);
}
