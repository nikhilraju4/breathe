const API_BASE = import.meta.env.VITE_API_URL || "";

function headers() {
  const token = localStorage.getItem("token");
  const h = { "Content-Type": "application/json" };
  if (token) h.Authorization = `Token ${token}`;
  return h;
}

export async function login(username, password) {
  const res = await fetch(`${API_BASE}/api/auth/login/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  if (!res.ok) throw new Error("Invalid credentials");
  return res.json();
}

export async function fetchDashboard() {
  const res = await fetch(`${API_BASE}/api/dashboard/`, { headers: headers() });
  if (!res.ok) throw new Error("Failed to load dashboard");
  return res.json();
}

export async function fetchRecords(params = {}) {
  const qs = new URLSearchParams(params).toString();
  const res = await fetch(`${API_BASE}/api/records/?${qs}`, { headers: headers() });
  if (!res.ok) throw new Error("Failed to load records");
  return res.json();
}

export async function approveRecord(id) {
  const res = await fetch(`${API_BASE}/api/records/${id}/approve/`, {
    method: "POST",
    headers: headers(),
  });
  if (!res.ok) throw new Error("Approve failed");
  return res.json();
}

export async function rejectRecord(id, note = "") {
  const res = await fetch(`${API_BASE}/api/records/${id}/reject/`, {
    method: "POST",
    headers: headers(),
    body: JSON.stringify({ note }),
  });
  if (!res.ok) throw new Error("Reject failed");
  return res.json();
}

export async function updateRecord(id, data) {
  const res = await fetch(`${API_BASE}/api/records/${id}/`, {
    method: "PATCH",
    headers: headers(),
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error("Update failed");
  return res.json();
}

export async function fetchAuditTrail(id) {
  const res = await fetch(`${API_BASE}/api/records/${id}/audit_trail/`, { headers: headers() });
  if (!res.ok) throw new Error("Audit trail failed");
  return res.json();
}

export async function uploadFile(sourceType, file) {
  const form = new FormData();
  form.append("source_type", sourceType);
  form.append("file", file);
  const token = localStorage.getItem("token");
  const res = await fetch(`${API_BASE}/api/ingest/upload/`, {
    method: "POST",
    headers: token ? { Authorization: `Token ${token}` } : {},
    body: form,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Upload failed");
  }
  return res.json();
}

export async function lockForAudit() {
  const res = await fetch(`${API_BASE}/api/audit/lock/`, {
    method: "POST",
    headers: headers(),
  });
  if (!res.ok) throw new Error("Lock failed");
  return res.json();
}
