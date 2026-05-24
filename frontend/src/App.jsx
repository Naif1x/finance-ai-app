import { useState, useCallback, useRef, useEffect } from "react";
import Papa from "papaparse";

const API_BASE = import.meta.env.VITE_API_URL || "";

const B = { teal: "#0099A8", tealDark: "#007A87", tealLight: "#E6F7F8", gray: "#7A7C81", grayLight: "#F4F5F6", grayDark: "#2D2E30", white: "#FFF", red: "#D94F4F", green: "#2A9D5C", amber: "#E5A100", bg: "#F8F9FB" };

const MODULES = [
  { category: "Reconciliation", icon: "⚖️", items: [
    { id: "bank_recon", name: "Bank Reconciliation", desc: "Match bank statement vs GL ledger", files: ["Bank Statement (CSV)", "GL Ledger (CSV)"], params: [{ key: "tolerance_days", label: "Date Tolerance (days)", type: "number", default: 3 }] },
    { id: "intercompany", name: "Intercompany Recon", desc: "Reconcile AR of Entity A with AP of Entity B", files: ["Entity A - AR Ledger (CSV)", "Entity B - AP Ledger (CSV)"], params: [] },
    { id: "gl_recon", name: "GL Account Review", desc: "Flag unusual movements in trial balance", files: ["Trial Balance (CSV)"], params: [{ key: "periods", label: "Periods to Compare", type: "number", default: 3 }] },
  ]},
  { category: "Analysis", icon: "📊", items: [
    { id: "variance", name: "Variance Analysis", desc: "Compare Actual vs Budget with drivers", files: ["Actuals (CSV)", "Budget (CSV)"], params: [{ key: "threshold_pct", label: "Threshold %", type: "number", default: 10 }, { key: "threshold_sar", label: "Threshold SAR", type: "number", default: 50000 }] },
    { id: "anomaly", name: "Anomaly Detection", desc: "Flag suspicious transactions", files: ["Transactions List (CSV)"], params: [{ key: "approval_limit", label: "Approval Limit (SAR)", type: "number", default: 50000 }] },
    { id: "ar_aging", name: "AR Aging Analysis", desc: "Identify shifting payment behavior", files: ["AR Aging Report (CSV)"], params: [] },
  ]},
  { category: "Reports", icon: "📝", items: [
    { id: "commentary", name: "Management Commentary", desc: "Draft commentary from financials", files: ["Financial Statements (CSV)"], params: [{ key: "period", label: "Period", type: "text", default: "Q1 2026" }, { key: "company", label: "Company Name", type: "text", default: "" }] },
    { id: "exec_summary", name: "Executive Summary", desc: "One-page CFO brief", files: ["Financial Report (CSV)"], params: [{ key: "period", label: "Period", type: "text", default: "Q1 2026" }] },
    { id: "board_kpi", name: "Board KPI Commentary", desc: "Commentary for each KPI", files: ["KPI Dashboard (CSV)"], params: [] },
  ]},
  { category: "Automation", icon: "⚙️", items: [
    { id: "journal_entries", name: "Recurring JEs", desc: "Generate journal entries from accruals schedule", files: ["Accruals Schedule (CSV)"], params: [{ key: "posting_date", label: "Posting Date", type: "text", default: new Date().toISOString().split("T")[0] }] },
    { id: "data_cleansing", name: "Data Cleansing", desc: "Standardize and clean datasets", files: ["Raw Dataset (CSV)"], params: [] },
    { id: "report_template", name: "Report Template", desc: "Generate monthly reporting template", files: [], params: [{ key: "company", label: "Company Name", type: "text", default: "" }, { key: "period", label: "Period", type: "text", default: "May 2026" }] },
  ]},
];

function FileUpload({ label, onFile, file, onRawFile }) {
  const [dragging, setDragging] = useState(false);
  const ref = useRef();
  const handleFile = useCallback((f) => {
    if (!f) return;
    onRawFile(f);
    Papa.parse(f, { header: true, skipEmptyLines: true, complete: (r) => onFile({ name: f.name, data: r.data, fields: r.meta.fields }) });
  }, [onFile, onRawFile]);

  return (
    <div>
      <div className="upload-zone" data-dragging={dragging} onClick={() => ref.current?.click()}
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => { e.preventDefault(); setDragging(false); handleFile(e.dataTransfer.files[0]); }}>
        <div style={{ fontSize: 24, marginBottom: 4 }}>📎</div>
        <div style={{ fontSize: 13, fontWeight: 600, color: B.grayDark }}>{label}</div>
        <div style={{ fontSize: 12, color: B.gray, marginTop: 4 }}>Drop CSV here or tap to browse</div>
        <input ref={ref} type="file" accept=".csv,.tsv" style={{ display: "none" }} onChange={(e) => handleFile(e.target.files[0])} />
      </div>
      {file && (
        <div className="uploaded-file">
          <span>✓ {file.name} ({file.data?.length || 0} rows)</span>
          <span style={{ cursor: "pointer", opacity: 0.6 }} onClick={() => { onFile(null); onRawFile(null); }}>✕</span>
        </div>
      )}
    </div>
  );
}

function SummaryCards({ items }) {
  if (!items?.length) return null;
  return <div className="summary-grid">{items.map((it, i) => (
    <div key={i} className={`summary-card summary-card-${it.color}`}>
      <div className="summary-value">{typeof it.value === "number" ? it.value.toLocaleString() : it.value}</div>
      <div className="summary-label">{it.label}</div>
    </div>
  ))}</div>;
}

function DataTable({ data, maxRows = 50 }) {
  if (!data?.length) return <div style={{ fontSize: 13, color: B.gray, padding: 16 }}>No items.</div>;
  const keys = Object.keys(data[0]);
  return (
    <div className="table-wrap">
      <table className="data-table">
        <thead><tr>{keys.map(k => <th key={k}>{k.replace(/_/g, " ")}</th>)}</tr></thead>
        <tbody>{data.slice(0, maxRows).map((row, i) => (
          <tr key={i} className={i % 2 === 0 ? "" : "alt"}>
            {keys.map(k => <td key={k}>
              {["materiality","risk","status","trend"].includes(k) ? <span className={`badge badge-${(row[k]||"").toLowerCase()}`}>{row[k]}</span> : typeof row[k] === "number" ? row[k].toLocaleString() : String(row[k] ?? "")}
            </td>)}
          </tr>
        ))}</tbody>
      </table>
    </div>
  );
}

function TabbedTables({ tabs }) {
  const [active, setActive] = useState(0);
  if (!tabs?.length) return null;
  return (
    <div>
      <div className="tabs-bar">
        {tabs.map((t, i) => <button key={i} className={`tab ${i === active ? "active" : ""}`} onClick={() => setActive(i)}>{t.label} {t.data?.length ? `(${t.data.length})` : ""}</button>)}
      </div>
      <DataTable data={tabs[active]?.data || []} />
    </div>
  );
}

function renderResults(id, d) {
  if (!d) return null;
  const R = {
    bank_recon: () => <>
      <SummaryCards items={[{ label:"Matched",value:d.summary?.total_matched||0,color:"green" },{ label:"Bank Only",value:d.summary?.total_bank_only||0,color:"amber" },{ label:"GL Only",value:d.summary?.total_gl_only||0,color:"amber" },{ label:"Net Diff",value:`SAR ${(d.summary?.net_difference||0).toLocaleString()}`,color:d.summary?.net_difference===0?"green":"red" }]} />
      <TabbedTables tabs={[{ label:"Matched",data:d.matched },{ label:"Bank Only",data:d.bank_only },{ label:"GL Only",data:d.gl_only },{ label:"Mismatches",data:d.mismatches }]} />
    </>,
    intercompany: () => <>
      <SummaryCards items={[{ label:"Matched",value:d.summary?.total_matched||0,color:"green" },{ label:"FX Diff",value:d.summary?.total_fx||0,color:"amber" },{ label:"Timing",value:d.summary?.total_timing||0,color:"amber" },{ label:"Investigate",value:d.summary?.total_investigate||0,color:"red" }]} />
      <TabbedTables tabs={[{ label:"Matched",data:d.matched },{ label:"FX",data:d.fx_differences },{ label:"Timing",data:d.timing_differences },{ label:"Investigation",data:d.investigation_required }]} />
    </>,
    gl_recon: () => <>
      <SummaryCards items={[{ label:"Reviewed",value:d.summary?.total_accounts_reviewed||0,color:"teal" },{ label:"Flags",value:d.summary?.flags_raised||0,color:"amber" },{ label:"Critical",value:d.summary?.critical_flags||0,color:"red" }]} />
      <TabbedTables tabs={[{ label:"Unusual",data:d.unusual_movements },{ label:"Nature Issues",data:d.nature_inconsistencies }]} />
    </>,
    variance: () => <>
      <SummaryCards items={[{ label:"Favorable",value:`SAR ${(d.summary?.total_favorable||0).toLocaleString()}`,color:"green" },{ label:"Unfavorable",value:`SAR ${(d.summary?.total_unfavorable||0).toLocaleString()}`,color:"red" },{ label:"Flagged",value:d.summary?.items_flagged||0,color:"teal" }]} />
      <DataTable data={d.variances} />
    </>,
    anomaly: () => <>
      <SummaryCards items={[{ label:"Total Flags",value:d.summary?.total_flags||0,color:"red" },{ label:"High",value:d.summary?.high_risk||0,color:"red" },{ label:"Medium",value:d.summary?.medium_risk||0,color:"amber" },{ label:"Low",value:d.summary?.low_risk||0,color:"green" }]} />
      <TabbedTables tabs={[{ label:"Duplicates",data:d.duplicates },{ label:"Round Numbers",data:d.round_numbers },{ label:"After Hours",data:d.after_hours },{ label:"Threshold",data:d.threshold_gaming }]} />
    </>,
    ar_aging: () => <>
      <SummaryCards items={[{ label:"Total AR",value:`SAR ${(d.summary?.total_ar||0).toLocaleString()}`,color:"teal" },{ label:"Overdue",value:`${d.summary?.overdue_pct||0}%`,color:"amber" },{ label:"Deteriorating",value:d.summary?.customers_deteriorating||0,color:"red" }]} />
      <TabbedTables tabs={[{ label:"Shifts",data:d.behavior_shifts },{ label:"Growth",data:d.abnormal_growth },{ label:"Concentration",data:d.concentration_risk }]} />
    </>,
    commentary: () => <div className="card"><div className="card-title">📄 Management Commentary</div>
      <p className="prose">{d.commentary?.performance_summary}</p><hr className="divider" />
      <p className="prose">{d.commentary?.key_drivers}</p><hr className="divider" />
      <p className="prose">{d.commentary?.outlook}</p></div>,
    exec_summary: () => <>
      <div className="card"><div className="card-title">📋 Executive Summary</div><p className="prose">{d.executive_summary}</p></div>
      {d.risk_highlights?.length > 0 && <div className="card"><div className="card-title">🔴 Risks</div>{d.risk_highlights.map((r,i)=><div key={i} style={{ fontSize: 13, padding: "3px 0" }}>• {r}</div>)}</div>}
    </>,
    board_kpi: () => (d.kpis||[]).map((k,i)=><div key={i} className={`card kpi-card kpi-${(k.status||"").toLowerCase().replace("_","")}`}>
      <div style={{ display:"flex",justifyContent:"space-between",alignItems:"center",marginBottom:8,flexWrap:"wrap",gap:8 }}><span style={{ fontSize:15,fontWeight:700 }}>{k.kpi_name}</span><span className={`badge badge-${(k.status||"").toLowerCase()}`}>{k.status?.replace("_"," ")}</span></div>
      <p className="prose">{k.commentary}</p></div>),
    journal_entries: () => <>
      <SummaryCards items={[{ label:"Entries",value:d.summary?.total_entries||0,color:"teal" },{ label:"Total Debits",value:`SAR ${(d.summary?.total_debits||0).toLocaleString()}`,color:"teal" },{ label:"Balanced",value:d.summary?.balanced?"Yes ✓":"No ✗",color:d.summary?.balanced?"green":"red" }]} />
      <DataTable data={d.journal_entries} /></>,
    data_cleansing: () => <>
      <SummaryCards items={[{ label:"Issues",value:d.summary?.total_issues||0,color:"amber" },{ label:"Duplicates",value:d.summary?.duplicates_found||0,color:"red" },{ label:"Names Fixed",value:d.summary?.names_standardized||0,color:"teal" }]} />
      <TabbedTables tabs={[{ label:"Issues",data:d.issues_found },{ label:"Names",data:d.name_standardizations }]} /></>,
    report_template: () => <div>
      <div style={{ fontSize: 18, fontWeight: 700, marginBottom: 16 }}>{d.template?.title}</div>
      {(d.template?.sections||[]).map((sec,i)=><div key={i} className="card" style={{ borderLeft:`4px solid ${B.teal}` }}>
        <div style={{ fontSize: 15, fontWeight: 700, marginBottom: 8, color: B.tealDark }}>{sec.section}</div>
        {(sec.subsections||[]).map((sub,j)=><div key={j} style={{ marginBottom: 10 }}><div style={{ fontSize: 13, fontWeight: 600, marginBottom: 4 }}>{sub.name}</div>
          {(sub.line_items||[]).map((li,k)=><div key={k} style={{ fontSize: 12, color: B.gray, padding:"2px 0 2px 12px", borderLeft:`2px solid ${B.grayLight}` }}><strong>{li.item}</strong> — {li.description}</div>)}</div>)}</div>)}
    </div>,
  };
  return (R[id] || (() => <pre style={{ fontSize: 12, background:"#F9FAFB", padding:16, borderRadius:8, overflow:"auto", whiteSpace:"pre-wrap" }}>{JSON.stringify(d,null,2)}</pre>))();
}

export default function App() {
  const [activeModule, setActiveModule] = useState(null);
  const [files, setFiles] = useState({});
  const [rawFiles, setRawFiles] = useState({});
  const [params, setParams] = useState({});
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [loadingMsg, setLoadingMsg] = useState("");
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const module = MODULES.flatMap(c => c.items).find(m => m.id === activeModule);
  const msgs = ["Analyzing financial data...", "Cross-referencing entries...", "Identifying patterns...", "Preparing results..."];

  const canRun = () => {
    if (!module) return false;
    if (module.files.length === 0) return true;
    return module.files.every((_, i) => files[`${activeModule}_${i}`]?.data?.length > 0);
  };

  const selectModule = (id) => {
    setActiveModule(id);
    setSidebarOpen(false);
  };

  const runAnalysis = async () => {
    setLoading(true); setError(null); setResults(null);
    let mi = 0;
    setLoadingMsg(msgs[0]);
    const iv = setInterval(() => { mi = (mi+1) % msgs.length; setLoadingMsg(msgs[mi]); }, 3000);
    try {
      const fd = new FormData();
      fd.append("module_id", activeModule);
      const moduleParams = {};
      (module?.params || []).forEach(p => { moduleParams[p.key] = params[`${activeModule}_${p.key}`] ?? p.default; });
      fd.append("params_json", JSON.stringify(moduleParams));
      const f0 = rawFiles[`${activeModule}_0`];
      const f1 = rawFiles[`${activeModule}_1`];
      if (f0) fd.append("file_0", f0);
      if (f1) fd.append("file_1", f1);
      const resp = await fetch(`${API_BASE}/api/analyze`, { method: "POST", body: fd });
      if (!resp.ok) { const err = await resp.json().catch(() => ({})); throw new Error(err.detail || `Server error: ${resp.status}`); }
      const data = await resp.json();
      setResults(data.results);
    } catch (err) { setError(err.message); } finally { clearInterval(iv); setLoading(false); setLoadingMsg(""); }
  };

  useEffect(() => { setResults(null); setError(null); }, [activeModule]);

  return (
    <div className="app">
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600;700&display=swap');
        @keyframes spin { to { transform: rotate(360deg) } }
        @keyframes fadeIn { from { opacity:0; transform:translateY(8px) } to { opacity:1; transform:translateY(0) } }
        * { box-sizing: border-box; margin: 0; padding: 0; }

        .app { display: flex; height: 100vh; height: 100dvh; font-family: 'DM Sans','Segoe UI',sans-serif; background: ${B.bg}; color: ${B.grayDark}; overflow: hidden; }

        /* ── Sidebar ── */
        .sidebar { width: 280px; background: ${B.grayDark}; color: ${B.white}; display: flex; flex-direction: column; flex-shrink: 0; overflow-y: auto; z-index: 100; }
        .sidebar-header { padding: 24px 20px 16px; border-bottom: 1px solid rgba(255,255,255,0.08); display: flex; align-items: center; justify-content: space-between; }
        .logo { font-size: 20px; font-weight: 700; letter-spacing: -0.02em; color: ${B.teal}; }
        .logo-sub { font-size: 11px; color: rgba(255,255,255,0.4); margin-top: 4px; letter-spacing: 0.06em; text-transform: uppercase; }
        .close-btn { display: none; background: none; border: none; color: rgba(255,255,255,0.5); font-size: 24px; cursor: pointer; padding: 4px 8px; }
        .cat-label { font-size: 10px; font-weight: 600; letter-spacing: 0.1em; text-transform: uppercase; color: rgba(255,255,255,0.3); padding: 20px 20px 8px; display: flex; align-items: center; gap: 6px; }
        .nav-item { padding: 10px 20px; font-size: 13px; cursor: pointer; border-left: 3px solid transparent; transition: all 0.15s; color: rgba(255,255,255,0.6); }
        .nav-item:hover { background: rgba(255,255,255,0.05); }
        .nav-item.active { background: rgba(0,153,168,0.15); color: ${B.teal}; border-left-color: ${B.teal}; font-weight: 600; }

        /* ── Overlay ── */
        .sidebar-overlay { display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.5); z-index: 90; }

        /* ── Main ── */
        .main { flex: 1; display: flex; flex-direction: column; overflow: hidden; min-width: 0; }
        .header { padding: 16px 24px; border-bottom: 1px solid ${B.grayLight}; background: ${B.white}; display: flex; align-items: center; gap: 12px; }
        .hamburger { display: none; background: none; border: 1px solid ${B.grayLight}; border-radius: 6px; padding: 6px 10px; font-size: 20px; cursor: pointer; color: ${B.grayDark}; flex-shrink: 0; }
        .header-title { font-size: 20px; font-weight: 700; letter-spacing: -0.02em; }
        .header-desc { font-size: 13px; color: ${B.gray}; margin-top: 2px; }
        .content { flex: 1; overflow-y: auto; padding: 24px; }

        /* ── Cards ── */
        .card { background: ${B.white}; border-radius: 10px; border: 1px solid ${B.grayLight}; padding: 20px; margin-bottom: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.04); }
        .card-title { font-size: 14px; font-weight: 600; margin-bottom: 16px; display: flex; align-items: center; gap: 8px; }

        /* ── Upload ── */
        .upload-zone { border: 2px dashed #D1D5DB; border-radius: 8px; padding: 24px 16px; text-align: center; cursor: pointer; background: #FAFBFC; transition: all 0.15s; }
        .upload-zone[data-dragging="true"] { border-color: ${B.teal}; background: ${B.tealLight}; }
        .uploaded-file { display: flex; align-items: center; justify-content: space-between; padding: 8px 12px; background: ${B.tealLight}; border-radius: 6px; font-size: 12px; color: ${B.tealDark}; font-weight: 500; margin-top: 8px; }
        .file-grid { display: grid; gap: 16px; }
        .file-grid-2 { grid-template-columns: 1fr 1fr; }

        /* ── Params ── */
        .param-row { display: flex; gap: 12px; flex-wrap: wrap; margin-top: 8px; }
        .param-group { display: flex; flex-direction: column; gap: 4px; flex: 1 1 180px; }
        .param-label { font-size: 11px; font-weight: 600; color: ${B.gray}; text-transform: uppercase; letter-spacing: 0.05em; }
        .param-input { padding: 8px 12px; border: 1px solid #D1D5DB; border-radius: 6px; font-size: 13px; outline: none; font-family: inherit; width: 100%; }

        /* ── Buttons ── */
        .btn-primary { padding: 10px 24px; border-radius: 8px; border: none; font-weight: 600; font-size: 13px; cursor: pointer; font-family: inherit; transition: all 0.15s; background: ${B.teal}; color: ${B.white}; }
        .btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
        .spinner { display: inline-block; width: 16px; height: 16px; border: 2px solid rgba(255,255,255,0.3); border-top-color: ${B.white}; border-radius: 50%; animation: spin 0.6s linear infinite; }

        /* ── Summary Cards ── */
        .summary-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 10px; margin-bottom: 16px; }
        .summary-card { padding: 14px 16px; border-radius: 8px; border-left: 4px solid; }
        .summary-card-green { background: #F0FAF4; border-left-color: ${B.green}; }
        .summary-card-red { background: #FEF2F2; border-left-color: ${B.red}; }
        .summary-card-amber { background: #FFFBEB; border-left-color: ${B.amber}; }
        .summary-card-teal { background: ${B.tealLight}; border-left-color: ${B.teal}; }
        .summary-value { font-size: 20px; font-weight: 700; letter-spacing: -0.02em; }
        .summary-label { font-size: 10px; color: ${B.gray}; margin-top: 2px; text-transform: uppercase; letter-spacing: 0.05em; }

        /* ── Table ── */
        .table-wrap { overflow-x: auto; -webkit-overflow-scrolling: touch; }
        .data-table { width: 100%; border-collapse: collapse; font-size: 12px; min-width: 500px; }
        .data-table th { text-align: left; padding: 10px 12px; border-bottom: 2px solid ${B.grayLight}; font-weight: 600; font-size: 11px; text-transform: uppercase; letter-spacing: 0.05em; color: ${B.gray}; white-space: nowrap; }
        .data-table td { padding: 9px 12px; border-bottom: 1px solid ${B.grayLight}; }
        .data-table tr.alt { background: #FAFBFC; }

        /* ── Tabs ── */
        .tabs-bar { display: flex; gap: 2px; border-bottom: 1px solid ${B.grayLight}; margin-bottom: 12px; overflow-x: auto; -webkit-overflow-scrolling: touch; }
        .tab { padding: 8px 14px; font-size: 12px; font-weight: 400; color: ${B.gray}; cursor: pointer; background: none; border: none; border-bottom: 2px solid transparent; font-family: inherit; white-space: nowrap; }
        .tab.active { font-weight: 600; color: ${B.teal}; border-bottom-color: ${B.teal}; }

        /* ── Badges ── */
        .badge { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 10px; font-weight: 600; }
        .badge-high, .badge-deteriorating, .badge-off_track { background: #FEE2E2; color: ${B.red}; }
        .badge-medium, .badge-at_risk { background: #FEF3C7; color: #92400E; }
        .badge-low, .badge-on_track, .badge-improving { background: #D1FAE5; color: ${B.green}; }

        /* ── Misc ── */
        .prose { font-size: 13.5px; line-height: 1.7; white-space: pre-wrap; }
        .divider { border: none; border-top: 1px solid ${B.grayLight}; margin: 16px 0; }
        .error-card { border-left: 4px solid ${B.red}; background: #FEF2F2; animation: fadeIn 0.3s ease; }
        .success-card { background: #F0FAF4; border-left: 4px solid ${B.green}; padding: 12px 20px; margin-bottom: 16px; }
        .kpi-card { border-left: 4px solid ${B.gray}; }
        .kpi-ontrack { border-left-color: ${B.green}; }
        .kpi-atrisk { border-left-color: ${B.amber}; }
        .kpi-offtrack { border-left-color: ${B.red}; }
        .welcome { text-align: center; padding: 60px 24px; max-width: 520px; margin: 0 auto; }
        .welcome-icon { font-size: 48px; margin-bottom: 16px; }
        .welcome-title { font-size: 24px; font-weight: 700; margin-bottom: 8px; letter-spacing: -0.02em; }
        .welcome-desc { font-size: 14px; color: ${B.gray}; line-height: 1.6; }
        .welcome-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-top: 32px; text-align: left; }
        .welcome-grid .card { padding: 16px; cursor: pointer; }
        .welcome-grid .card:hover { border-color: ${B.teal}; }

        /* ── MOBILE ── */
        @media (max-width: 768px) {
          .sidebar { position: fixed; left: -300px; top: 0; bottom: 0; width: 280px; transition: left 0.25s ease; box-shadow: none; }
          .sidebar.open { left: 0; box-shadow: 4px 0 20px rgba(0,0,0,0.3); }
          .sidebar-overlay.open { display: block; }
          .close-btn { display: block; }
          .hamburger { display: block; }
          .header-title { font-size: 17px; }
          .header-desc { font-size: 12px; }
          .content { padding: 16px; }
          .card { padding: 16px; }
          .file-grid-2 { grid-template-columns: 1fr; }
          .summary-grid { grid-template-columns: repeat(2, 1fr); }
          .summary-value { font-size: 17px; }
          .welcome-grid { grid-template-columns: 1fr; }
          .welcome { padding: 40px 16px; }
          .welcome-title { font-size: 20px; }
          .param-row { flex-direction: column; }
        }

        @media (max-width: 380px) {
          .summary-grid { grid-template-columns: 1fr; }
        }
      `}</style>

      {/* Sidebar overlay for mobile */}
      <div className={`sidebar-overlay ${sidebarOpen ? "open" : ""}`} onClick={() => setSidebarOpen(false)} />

      {/* Sidebar */}
      <div className={`sidebar ${sidebarOpen ? "open" : ""}`}>
        <div className="sidebar-header">
          <div>
            <div className="logo">Trustangle</div>
            <div className="logo-sub">Finance AI Assistant</div>
          </div>
          <button className="close-btn" onClick={() => setSidebarOpen(false)}>✕</button>
        </div>
        {MODULES.map(cat => (
          <div key={cat.category}>
            <div className="cat-label">{cat.icon} {cat.category}</div>
            {cat.items.map(item => (
              <div key={item.id} className={`nav-item ${activeModule === item.id ? "active" : ""}`} onClick={() => selectModule(item.id)}>
                {item.name}
              </div>
            ))}
          </div>
        ))}
      </div>

      {/* Main */}
      <div className="main">
        {!module ? (
          <div className="content">
            <div className="welcome">
              <div className="welcome-icon">🏦</div>
              <div className="welcome-title">Finance AI Assistant</div>
              <div className="welcome-desc">Upload your financial data and let AI handle reconciliations, analysis, reporting, and automation.</div>
              <div className="welcome-grid">
                {MODULES.map(cat => (
                  <div key={cat.category} className="card" onClick={() => selectModule(cat.items[0].id)}>
                    <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 4 }}>{cat.icon} {cat.category}</div>
                    {cat.items.map(item => <div key={item.id} style={{ fontSize: 12, color: B.gray, padding: "2px 0", cursor: "pointer" }} onClick={(e) => { e.stopPropagation(); selectModule(item.id); }}>→ {item.name}</div>)}
                  </div>
                ))}
              </div>
            </div>
          </div>
        ) : (
          <>
            <div className="header">
              <button className="hamburger" onClick={() => setSidebarOpen(true)}>☰</button>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div className="header-title">{module.name}</div>
                <div className="header-desc">{module.desc}</div>
              </div>
            </div>
            <div className="content">
              <div className="card">
                <div className="card-title">📂 Data Input</div>
                {module.files.length > 0 ? (
                  <div className={`file-grid ${module.files.length > 1 ? "file-grid-2" : ""}`}>
                    {module.files.map((label, i) => (
                      <FileUpload key={i} label={label}
                        file={files[`${activeModule}_${i}`]}
                        onFile={(f) => setFiles({ ...files, [`${activeModule}_${i}`]: f })}
                        onRawFile={(f) => setRawFiles({ ...rawFiles, [`${activeModule}_${i}`]: f })} />
                    ))}
                  </div>
                ) : <div style={{ fontSize: 13, color: B.gray }}>No file upload required.</div>}

                {module.params.length > 0 && (
                  <div style={{ marginTop: 16 }}>
                    <div className="param-label" style={{ marginBottom: 8 }}>Parameters</div>
                    <div className="param-row">
                      {module.params.map(p => (
                        <div key={p.key} className="param-group">
                          <label className="param-label">{p.label}</label>
                          <input type={p.type} className="param-input"
                            value={params[`${activeModule}_${p.key}`] ?? p.default}
                            onChange={e => setParams({ ...params, [`${activeModule}_${p.key}`]: p.type === "number" ? Number(e.target.value) : e.target.value })} />
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                <div style={{ marginTop: 20, display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
                  <button className="btn-primary" onClick={runAnalysis} disabled={loading || !canRun()}>
                    {loading ? <span style={{ display:"flex",alignItems:"center",gap:8 }}><span className="spinner" /> Analyzing...</span> : "▶ Run Analysis"}
                  </button>
                  {loading && <span style={{ fontSize: 12, color: B.gray, fontStyle: "italic" }}>{loadingMsg}</span>}
                </div>
              </div>

              {error && <div className="card error-card"><div style={{ fontSize: 13, color: B.red, fontWeight: 600 }}>Error: {error}</div></div>}

              {results && <div style={{ animation: "fadeIn 0.4s ease" }}>
                <div className="card success-card"><span style={{ fontSize: 13, fontWeight: 600, color: B.green }}>✓ Analysis Complete</span></div>
                {renderResults(activeModule, results)}
              </div>}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
