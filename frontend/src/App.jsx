import { useCallback, useEffect, useState } from "react";
import {
  approveRecord,
  fetchAuditTrail,
  fetchDashboard,
  fetchRecords,
  lockForAudit,
  login,
  rejectRecord,
  updateRecord,
  uploadFile,
} from "./api";

const SOURCE_LABELS = {
  sap: "SAP",
  utility: "Utility",
  travel: "Travel",
};

function Login({ onLogin }) {
  const [username, setUsername] = useState("analyst");
  const [password, setPassword] = useState("demo1234");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const data = await login(username, password);
      localStorage.setItem("token", data.token);
      localStorage.setItem("user", JSON.stringify(data.user));
      localStorage.setItem("tenant", JSON.stringify(data.tenant));
      onLogin(data);
    } catch {
      setError("Invalid username or password");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="login-box">
      <h1>Breathe ESG</h1>
      <p className="subtitle">Analyst review portal</p>
      {error && <div className="error-banner">{error}</div>}
      <form onSubmit={handleSubmit}>
        <label>Username</label>
        <input value={username} onChange={(e) => setUsername(e.target.value)} />
        <label>Password</label>
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        <button className="btn" type="submit" disabled={loading} style={{ width: "100%" }}>
          {loading ? "Signing in…" : "Sign in"}
        </button>
      </form>
      <p className="hint">Demo: analyst / demo1234</p>
    </div>
  );
}

function StatCard({ label, value, variant }) {
  return (
    <div className={`stat-card ${variant || ""}`}>
      <div className="label">{label}</div>
      <div className="value">{value}</div>
    </div>
  );
}

export default function App() {
  const [session, setSession] = useState(() => {
    const token = localStorage.getItem("token");
    if (!token) return null;
    return {
      user: JSON.parse(localStorage.getItem("user") || "{}"),
      tenant: JSON.parse(localStorage.getItem("tenant") || "null"),
    };
  });
  const [dashboard, setDashboard] = useState(null);
  const [records, setRecords] = useState([]);
  const [selected, setSelected] = useState(null);
  const [audit, setAudit] = useState([]);
  const [filter, setFilter] = useState({
    status: "",
    source: "",
    suspicious: "",
    errors: "",
    q: "",
  });
  const [editQty, setEditQty] = useState("");
  const [uploadSource, setUploadSource] = useState("sap");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    if (!session) return;
    setLoading(true);
    setError("");
    try {
      const [dash, recData] = await Promise.all([
        fetchDashboard(),
        fetchRecords({
          ...(filter.status && { status: filter.status }),
          ...(filter.source && { source: filter.source }),
          ...(filter.suspicious && { suspicious: "true" }),
          ...(filter.errors && { errors: "true" }),
          ...(filter.q && { q: filter.q }),
        }),
      ]);
      setDashboard(dash);
      setRecords(recData.results || recData);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [session, filter]);

  useEffect(() => {
    load();
  }, [load]);

  async function selectRecord(rec) {
    setSelected(rec);
    setEditQty(rec.quantity != null ? String(rec.quantity) : "");
    try {
      const trail = await fetchAuditTrail(rec.id);
      setAudit(trail);
    } catch {
      setAudit([]);
    }
  }

  async function handleApprove() {
    if (!selected) return;
    await approveRecord(selected.id);
    await load();
    selectRecord({ ...selected, review_status: "approved" });
  }

  async function handleReject() {
    if (!selected) return;
    await rejectRecord(selected.id);
    await load();
    setSelected(null);
  }

  async function handleSaveEdit() {
    if (!selected || !editQty) return;
    const updated = await updateRecord(selected.id, { quantity: editQty });
    setSelected(updated);
    await load();
    selectRecord(updated);
  }

  async function handleLockAll() {
    const res = await lockForAudit();
    alert(`Locked ${res.locked_count} approved records for audit.`);
    await load();
  }

  async function handleUpload(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    setError("");
    try {
      await uploadFile(uploadSource, file);
      await load();
      e.target.value = "";
    } catch (err) {
      setError(err.message);
    }
  }

  function logout() {
    localStorage.clear();
    setSession(null);
  }

  if (!session) {
    return <Login onLogin={(data) => setSession(data)} />;
  }

  const tenantName = session.tenant?.name || "Workspace";

  return (
    <div className="app-shell">
      <header className="app-header">
        <div>
          <h1>Breathe ESG — Review</h1>
          <p className="subtitle">
            {tenantName} · Signed in as {session.user?.username}
          </p>
        </div>
        <button className="btn secondary" onClick={logout}>
          Sign out
        </button>
      </header>

      {error && <div className="error-banner">{error}</div>}

      {dashboard && (
        <div className="stats-grid">
          <StatCard label="Total rows" value={dashboard.total_records} />
          <StatCard label="Pending" value={dashboard.pending} />
          <StatCard label="Suspicious" value={dashboard.suspicious} variant="warn" />
          <StatCard label="Parse issues" value={dashboard.failed_parses} variant="danger" />
          <StatCard label="Approved" value={dashboard.approved} />
          <StatCard label="Locked" value={dashboard.locked} />
        </div>
      )}

      {dashboard?.recent_batches?.length > 0 && (
        <div className="panel">
          <h2>Recent ingestions (what came in)</h2>
          <table className="data-table">
            <thead>
              <tr>
                <th>When</th>
                <th>Source</th>
                <th>File</th>
                <th>Status</th>
                <th>Rows</th>
                <th>Errors</th>
                <th>Flagged</th>
              </tr>
            </thead>
            <tbody>
              {dashboard.recent_batches.map((b) => (
                <tr key={b.id}>
                  <td>{new Date(b.created_at).toLocaleString()}</td>
                  <td>{b.source_type_display}</td>
                  <td>{b.file_name}</td>
                  <td>
                    <span className={`badge ${b.status === "failed" ? "rejected" : "pending"}`}>
                      {b.status}
                    </span>
                  </td>
                  <td>{b.success_count}/{b.row_count}</td>
                  <td>{b.error_count || "—"}</td>
                  <td>{b.suspicious_count || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="panel">
        <h2>Ingest data</h2>
        <div className="upload-row">
          <select value={uploadSource} onChange={(e) => setUploadSource(e.target.value)}>
            <option value="sap">SAP — fuel & procurement (CSV)</option>
            <option value="utility">Utility — electricity (CSV)</option>
            <option value="travel">Travel — Concur export (CSV)</option>
          </select>
          <input type="file" accept=".csv,.txt" onChange={handleUpload} />
        </div>
        <p className="hint">
          Upload semicolon or comma-separated exports. Sample files are in the repo under sample_data/.
        </p>
      </div>

      <div className="panel">
        <h2>Activity records</h2>
        <div className="toolbar">
          <select
            value={filter.status}
            onChange={(e) => setFilter((f) => ({ ...f, status: e.target.value }))}
          >
            <option value="">All statuses</option>
            <option value="pending">Pending</option>
            <option value="approved">Approved</option>
            <option value="rejected">Rejected</option>
            <option value="locked">Locked</option>
          </select>
          <select
            value={filter.source}
            onChange={(e) => setFilter((f) => ({ ...f, source: e.target.value }))}
          >
            <option value="">All sources</option>
            <option value="sap">SAP</option>
            <option value="utility">Utility</option>
            <option value="travel">Travel</option>
          </select>
          <label>
            <input
              type="checkbox"
              checked={filter.suspicious === "true"}
              onChange={(e) =>
                setFilter((f) => ({ ...f, suspicious: e.target.checked ? "true" : "" }))
              }
            />{" "}
            Suspicious only
          </label>
          <label>
            <input
              type="checkbox"
              checked={filter.errors === "true"}
              onChange={(e) =>
                setFilter((f) => ({ ...f, errors: e.target.checked ? "true" : "" }))
              }
            />{" "}
            Parse errors only
          </label>
          <input
            placeholder="Search description, facility…"
            value={filter.q}
            onChange={(e) => setFilter((f) => ({ ...f, q: e.target.value }))}
          />
          <button className="btn secondary" onClick={load} disabled={loading}>
            Refresh
          </button>
          <button className="btn" onClick={handleLockAll}>
            Lock approved for audit
          </button>
        </div>

        <table className="data-table">
          <thead>
            <tr>
              <th>Source</th>
              <th>Scope</th>
              <th>Category</th>
              <th>Date</th>
              <th>Description</th>
              <th>Qty</th>
              <th>Status</th>
              <th>Flags</th>
            </tr>
          </thead>
          <tbody>
            {records.map((r) => (
              <tr
                key={r.id}
                className={selected?.id === r.id ? "selected" : ""}
                onClick={() => selectRecord(r)}
                style={{ cursor: "pointer" }}
              >
                <td>{SOURCE_LABELS[r.source_type] || r.source_type}</td>
                <td className={`scope-${r.scope}`}>S{r.scope}</td>
                <td>{r.category}</td>
                <td>{r.activity_date || "—"}</td>
                <td>{r.description?.slice(0, 50)}</td>
                <td>
                  {r.quantity != null ? `${r.quantity} ${r.unit}` : "—"}
                </td>
                <td>
                  <span className={`badge ${r.review_status}`}>{r.review_status}</span>
                </td>
                <td>
                  {r.is_suspicious && (
                    <span className="badge suspicious">Review</span>
                  )}
                  {r.parse_error && (
                    <span className="badge rejected">Error</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        {selected && (
          <div className="detail-drawer">
            <h2>Record detail — {selected.source_row_id}</h2>
            <dl className="detail-grid">
              <dt>Scope / category</dt>
              <dd>
                Scope {selected.scope} · {selected.category}
              </dd>
              <dt>Facility / route</dt>
              <dd>
                {selected.facility_code || "—"}
                {selected.origin && ` · ${selected.origin} → ${selected.destination}`}
              </dd>
              <dt>Normalized qty</dt>
              <dd>
                {selected.quantity} {selected.unit} (raw: {selected.raw_quantity}{" "}
                {selected.raw_unit})
              </dd>
              <dt>Supplier</dt>
              <dd>{selected.supplier || "—"}</dd>
              <dt>Source file</dt>
              <dd>{selected.batch_file || "—"}</dd>
              {selected.is_suspicious && (
                <>
                  <dt>Suspicious</dt>
                  <dd>{selected.suspicious_reason}</dd>
                </>
              )}
              {selected.parse_error && (
                <>
                  <dt>Parse error</dt>
                  <dd>{selected.parse_error}</dd>
                </>
              )}
            </dl>
            {selected.review_status !== "locked" && (
              <div className="toolbar" style={{ marginTop: "0.75rem" }}>
                <label style={{ fontSize: "0.85rem", color: "var(--muted)" }}>
                  Correct quantity (analyst edit):
                </label>
                <input
                  type="text"
                  value={editQty}
                  onChange={(e) => setEditQty(e.target.value)}
                  placeholder="e.g. 1250.5"
                  style={{ width: "120px" }}
                />
                <button className="btn secondary" onClick={handleSaveEdit}>
                  Save correction
                </button>
                {selected.edited_by_analyst && (
                  <span className="badge suspicious">Edited by analyst</span>
                )}
              </div>
            )}
            <div className="toolbar">
              <button
                className="btn"
                onClick={handleApprove}
                disabled={selected.review_status === "locked" || selected.review_status === "approved"}
              >
                Approve
              </button>
              <button
                className="btn danger"
                onClick={handleReject}
                disabled={selected.review_status === "locked"}
              >
                Reject
              </button>
            </div>
            {audit.length > 0 && (
              <>
                <h3 style={{ fontSize: "0.9rem", marginTop: "1rem" }}>Audit trail</h3>
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>When</th>
                      <th>Action</th>
                      <th>By</th>
                      <th>Note</th>
                    </tr>
                  </thead>
                  <tbody>
                    {audit.map((a) => (
                      <tr key={a.id}>
                        <td>{new Date(a.created_at).toLocaleString()}</td>
                        <td>{a.action}</td>
                        <td>{a.actor_name}</td>
                        <td>{a.note || "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
