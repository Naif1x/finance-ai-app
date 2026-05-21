import { useState, useCallback, useRef, useEffect } from "react";
import Papa from "papaparse";

/* ── The key difference from the prototype: ──────────────────────
   Instead of calling Claude's API directly from the browser,
   this sends files + params to YOUR backend at /api/analyze,
   which securely proxies to Claude with the API key server-side.
   ─────────────────────────────────────────────────────────────── */

const API_BASE = import.meta.env.VITE_API_URL || "";

// ── Theme ──────────────────────────────────────────────────────
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

// ── Styles (same as prototype) ─────────────────────────────────
const S = {
  app: { display: "flex", height: "100vh", fontFamily: "'DM Sans', 'Segoe UI', sans-serif", background: B.bg, color: B.grayDark, overflow: "hidden" },
  sidebar: { width: 280, background: B.grayDark, color: B.white, display: "flex", flexDirection: "column", flexShrink: 0, overflowY: "auto" },
  sidebarHeader: { padding: "24px 20px 16px", borderBottom: "1px solid rgba(255,255,255,0.08)" },
  logo: { fontSize: 20, fontWeight: 700, letterSpacing: "-0.02em", color: B.teal },
  logoSub: { fontSize: 11, color: "rgba(255,255,255,0.4)", marginTop: 4, letterSpacing: "0.06em", textTransform: "uppercase" },
  catLabel: { fontSize: 10, fontWeight: 600, letterSpacing: "0.1em", textTransform: "uppercase", color: "rgba(255,255,255,0.3)", padding: "20px 20px 8px", display: "flex", alignItems: "center", gap: 6 },
  navItem: (a) => ({ padding: "10px 20px", fontSize: 13, cursor: "pointer", background: a ? "rgba(0,153,168,0.15)" : "transparent", color: a ? B.teal : "rgba(255,255,255,0.6)", borderLeft: a ? `3px solid ${B.teal}` : "3px solid transparent", transition: "all 0.15s", fontWeight: a ? 600 : 400 }),
  main: { flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" },
  header: { padding: "20px 32px", borderBottom: `1px solid ${B.grayLight}`, background: B.white, display: "flex", alignItems: "center", justifyContent: "space-between" },
  content: { flex: 1, overflowY: "auto", padding: 32 },
  card: { background: B.white, borderRadius: 10, border: `1px solid ${B.grayLight}`, padding: 24, marginBottom: 20, boxShadow: "0 1px 3px rgba(0,0,0,0.04)" },
  uploadZone: (d) => ({ border: `2px dashed ${d ? B.teal : "#D1D5DB"}`, borderRadius: 8, padding: "28px 16px", textAlign: "center", cursor: "pointer", background: d ? B.tealLight : "#FAFBFC", transition: "all 0.15s" }),
  uploadedFile: { display: "flex", alignItems: "center", justifyContent: "space-between", padding: "8px 12px", background: B.tealLight, borderRadius: 6, fontSize: 12, color: B.tealDark, fontWeight: 500, marginTop: 8 },
  paramRow: { display: "flex", gap: 16, flexWrap: "wrap", marginTop: 8 },
  paramGroup: { display: "flex", flexDirection: "column", gap: 4, flex: "1 1 200px" },
  paramLabel: { fontSize: 11, fontWeight: 600, color: B.gray, textTransform: "uppercase", letterSpacing: "0.05em" },
  paramInput: { padding: "8px 12px", border: "1px solid #D1D5DB", borderRadius: 6, fontSize: 13, outline: "none", fontFamily: "inherit" },
  btn: (v = "primary", dis = false) => ({
    padding: "10px 24px", borderRadius: 8, border: "none", fontWeight: 600, fontSize: 13, cursor: dis ? "not-allowed" : "pointer",
    fontFamily: "inherit", transition: "all 0.15s", opacity: dis ? 0.5 : 1,
    ...(v === "primary" ? { background: B.teal, color: B.white } : { background: B.grayLight, color: B.grayDark }),
  }),
  summaryGrid: { display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: 12, marginBottom: 20 },
  summaryCard: (c) => ({ padding: "16px 20px", borderRadius: 8, background: c === "green" ? "#F0FAF4" : c === "red" ? "#FEF2F2" : c === "amber" ? "#FFFBEB" : B.tealLight, borderLeft: `4px solid ${c === "green" ? B.green : c === "red" ? B.red : c === "amber" ? B.amber : B.teal}` }),
  table: { width: "100%", borderCollapse: "collapse", fontSize: 12 },
  th: { textAlign: "left", padding: "10px 12px", borderBottom: `2px solid ${B.grayLight}`, fontWeight: 600, fontSize: 11, textTransform: "uppercase", letterSpacing: "0.05em", color: B.gray },
  td: { padding: "9px 12px", borderBottom: `1px solid ${B.grayLight}`, color: B.grayDark },
  tab: (a) => ({ padding: "8px 16px", fontSize: 12, fontWeight: a ? 600 : 400, color: a ? B.teal : B.gray, cursor: "pointer", background: "none", border: "none", borderBottom: `2px solid ${a ? B.teal : "transparent"}`, fontFamily: "inherit" }),
  badge: (t) => ({ display: "inline-block", padding: "2px 8px", borderRadius: 4, fontSize: 10, fontWeight: 600,
    background: ["HIGH","DETERIORATING","OFF_TRACK"].includes(t) ? "#FEE2E2" : ["MEDIUM","AT_RISK"].includes(t) ? "#FEF3C7" : "#D1FAE5",
    color: ["HIGH","DETERIORATING","OFF_TRACK"].includes(t) ? B.red : ["MEDIUM","AT_RISK"].includes(t) ? "#92400E" : B.green }),
  spinner: { display: "inline-block", width: 16, height: 16, border: "2px solid rgba(255,255,255,0.3)", borderTopColor: B.white, borderRadius: "50%", animation: "spin 0.6s linear infinite" },
};

// ── Reusable Components ────────────────────────────────────────
function FileUpload({ label, onFile, file, onRawFile }) {
  const [dragging, setDragging] = useState(false);
  const ref = useRef();

  const handleFile = useCallback((f) => {
    if (!f) return;
    onRawFile(f); // store raw File for upload
    Papa.parse(f, {
      header: true, skipEmptyLines: true,
      complete: (r) => onFile({ name: f.name, data: r.data, fields: r.meta.fields }),
    });
  }, [onFile, onRawFile]);

  return (
    <div>
      <div style={S.uploadZone(dragging)} onClick={() => ref.current?.click()}
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => { e.preventDefault(); setDragging(false); handleFile(e.dataTransfer.files[0]); }}>
        <div style={{ fontSize: 24, marginBottom: 4 }}>📎</div>
        <div style={{ fontSize: 13, fontWeight: 600, color: B.grayDark }}>{label}</div>
        <div style={{ fontSize: 13, color: B.gray, marginTop: 4 }}>Drop CSV here or click to browse</div>
        <input ref={ref} type="file" accept=".csv,.tsv" style={{ display: "none" }} onChange={(e) => handleFile(e.target.files[0])} />
      </div>
      {file && (
        <div style={S.uploadedFile}>
          <span>✓ {file.name} ({file.data?.length || 0} rows)</span>
          <span style={{ cursor: "pointer", opacity: 0.6 }} onClick={() => { onFile(null); onRawFile(null); }}>✕</span>
        </div>
      )}
    </div>
  );
}

function SummaryCards({ items }) {
  if (!items?.length) return null;
  return <div style={S.summaryGrid}>{items.map((it, i) => (
    <div key={i} style={S.summaryCard(it.color)}>
      <div style={{ fontSize: 22, fontWeight: 700 }}>{typeof it.value === "number" ? it.value.toLocaleString() : it.value}</div>
      <div style={{ fontSize: 11, color: B.gray, marginTop: 2, textTransform: "uppercase", letterSpacing: "0.05em" }}>{it.label}</div>
    </div>
  ))}</div>;
}

function DataTable({ data, maxRows = 50 }) {
  if (!data?.length) return <div style={{ fontSize: 13, color: B.gray, padding: 16 }}>No items.</div>;
  const keys = Object.keys(data[0]);
  return (
    <div style={{ overflowX: "auto" }}>
      <table style={S.table}>
        <thead><tr>{keys.map(k => <th key={k} style={S.th}>{k.replace(/_/g, " ")}</th>)}</tr></thead>
        <tbody>{data.slice(0, maxRows).map((row, i) => (
          <tr key={i} style={{ background: i % 2 === 0 ? B.white : "#FAFBFC" }}>
            {keys.map(k => <td key={k} style={S.td}>
              {["materiality","risk","status","trend"].includes(k) ? <span style={S.badge(row[k])}>{row[k]}</span> : typeof row[k] === "number" ? row[k].toLocaleString() : String(row[k] ?? "")}
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
      <div style={{ display: "flex", gap: 4, borderBottom: `1px solid ${B.grayLight}`, marginBottom: 12 }}>
        {tabs.map((t, i) => <button key={i} style={S.tab(i === active)} onClick={() => setActive(i)}>{t.label} {t.data?.length ? `(${t.data.length})` : ""}</button>)}
      </div>
      <DataTable data={tabs[active]?.data || []} />
    </div>
  );
}

// ── Result Renderer ────────────────────────────────────────────
function renderResults(id, d) {
  if (!d) return null;
  const renderers = {
    bank_recon: () => <>
      <SummaryCards items={[{ label: "Matched", value: d.summary?.total_matched||0, color: "green" },{ label: "Bank Only", value: d.bank_only?.length||0, color: "amber" },{ label: "GL Only", value: d.gl_only?.length||0, color: "amber" },{ label: "Net Diff", value: `SAR ${(d.summary?.net_difference||0).toLocaleString()}`, color: d.summary?.net_difference===0?"green":"red" }]} />
      <TabbedTables tabs={[{ label:"Matched",data:d.matched },{ label:"Bank Only",data:d.bank_only },{ label:"GL Only",data:d.gl_only },{ label:"Mismatches",data:d.mismatches }]} />
    </>,
    intercompany: () => <>
      <SummaryCards items={[{ label:"Matched",value:d.summary?.total_matched||0,color:"green" },{ label:"FX Diff",value:d.summary?.total_fx||0,color:"amber" },{ label:"Timing",value:d.summary?.total_timing||0,color:"amber" },{ label:"Investigate",value:d.summary?.total_investigate||0,color:"red" }]} />
      <TabbedTables tabs={[{ label:"Matched",data:d.matched },{ label:"FX Differences",data:d.fx_differences },{ label:"Timing",data:d.timing_differences },{ label:"Investigation",data:d.investigation_required }]} />
    </>,
    gl_recon: () => <>
      <SummaryCards items={[{ label:"Reviewed",value:d.summary?.total_accounts_reviewed||0,color:"teal" },{ label:"Flags",value:d.summary?.flags_raised||0,color:"amber" },{ label:"Critical",value:d.summary?.critical_flags||0,color:"red" }]} />
      <TabbedTables tabs={[{ label:"Unusual Movements",data:d.unusual_movements },{ label:"Nature Issues",data:d.nature_inconsistencies }]} />
    </>,
    variance: () => <>
      <SummaryCards items={[{ label:"Favorable",value:`SAR ${(d.summary?.total_favorable||0).toLocaleString()}`,color:"green" },{ label:"Unfavorable",value:`SAR ${(d.summary?.total_unfavorable||0).toLocaleString()}`,color:"red" },{ label:"Items Flagged",value:d.summary?.items_flagged||0,color:"teal" }]} />
      <DataTable data={d.variances} />
    </>,
    anomaly: () => <>
      <SummaryCards items={[{ label:"Total Flags",value:d.summary?.total_flags||0,color:"red" },{ label:"High Risk",value:d.summary?.high_risk||0,color:"red" },{ label:"Medium",value:d.summary?.medium_risk||0,color:"amber" },{ label:"Low",value:d.summary?.low_risk||0,color:"green" }]} />
      <TabbedTables tabs={[{ label:"Duplicates",data:d.duplicates },{ label:"Round Numbers",data:d.round_numbers },{ label:"After Hours",data:d.after_hours },{ label:"Threshold Gaming",data:d.threshold_gaming }]} />
    </>,
    ar_aging: () => <>
      <SummaryCards items={[{ label:"Total AR",value:`SAR ${(d.summary?.total_ar||0).toLocaleString()}`,color:"teal" },{ label:"Overdue",value:`${d.summary?.overdue_pct||0}%`,color:"amber" },{ label:"Deteriorating",value:d.summary?.customers_deteriorating||0,color:"red" }]} />
      <TabbedTables tabs={[{ label:"Behavior Shifts",data:d.behavior_shifts },{ label:"Abnormal Growth",data:d.abnormal_growth },{ label:"Concentration",data:d.concentration_risk }]} />
    </>,
    commentary: () => <>
      <div style={S.card}><div style={{ fontSize: 14, fontWeight: 600, marginBottom: 12 }}>📄 Management Commentary</div>
        <p style={{ fontSize: 13.5, lineHeight: 1.7, marginBottom: 12 }}>{d.commentary?.performance_summary}</p>
        <p style={{ fontSize: 13.5, lineHeight: 1.7, marginBottom: 12 }}>{d.commentary?.key_drivers}</p>
        <p style={{ fontSize: 13.5, lineHeight: 1.7 }}>{d.commentary?.outlook}</p>
      </div>
    </>,
    exec_summary: () => <>
      <div style={S.card}><div style={{ fontSize: 14, fontWeight: 600, marginBottom: 12 }}>📋 Executive Summary</div>
        <p style={{ fontSize: 13.5, lineHeight: 1.7 }}>{d.executive_summary}</p>
      </div>
      {d.risk_highlights?.length > 0 && <div style={S.card}><div style={{ fontSize: 14, fontWeight: 600, marginBottom: 8 }}>🔴 Risks</div>{d.risk_highlights.map((r,i)=><div key={i} style={{ fontSize: 13, padding: "3px 0" }}>• {r}</div>)}</div>}
    </>,
    board_kpi: () => (d.kpis||[]).map((k,i)=><div key={i} style={{...S.card, borderLeft:`4px solid ${k.status==="ON_TRACK"?B.green:k.status==="AT_RISK"?B.amber:B.red}`}}>
      <div style={{ display:"flex",justifyContent:"space-between",marginBottom:8 }}><span style={{ fontSize:15,fontWeight:700 }}>{k.kpi_name}</span><span style={S.badge(k.status)}>{k.status?.replace("_"," ")}</span></div>
      <p style={{ fontSize:13, lineHeight:1.6 }}>{k.commentary}</p>
    </div>),
    journal_entries: () => <>
      <SummaryCards items={[{ label:"Entries",value:d.summary?.total_entries||0,color:"teal" },{ label:"Total Debits",value:`SAR ${(d.summary?.total_debits||0).toLocaleString()}`,color:"teal" },{ label:"Balanced",value:d.summary?.balanced?"Yes ✓":"No ✗",color:d.summary?.balanced?"green":"red" }]} />
      <DataTable data={d.journal_entries} />
    </>,
    data_cleansing: () => <>
      <SummaryCards items={[{ label:"Issues",value:d.summary?.total_issues||0,color:"amber" },{ label:"Duplicates",value:d.summary?.duplicates_found||0,color:"red" },{ label:"Names Fixed",value:d.summary?.names_standardized||0,color:"teal" }]} />
      <TabbedTables tabs={[{ label:"Issues",data:d.issues_found },{ label:"Name Fixes",data:d.name_standardizations }]} />
    </>,
    report_template: () => <div>
      <div style={{ fontSize: 18, fontWeight: 700, marginBottom: 16 }}>{d.template?.title}</div>
      {(d.template?.sections||[]).map((sec,i)=><div key={i} style={{...S.card,borderLeft:`4px solid ${B.teal}`}}>
        <div style={{ fontSize: 15, fontWeight: 700, marginBottom: 8, color: B.tealDark }}>{sec.section}</div>
        {(sec.subsections||[]).map((sub,j)=><div key={j} style={{ marginBottom: 10 }}><div style={{ fontSize: 13, fontWeight: 600, marginBottom: 4 }}>{sub.name}</div>
          {(sub.line_items||[]).map((li,k)=><div key={k} style={{ fontSize: 12, color: B.gray, padding:"2px 0 2px 12px", borderLeft:`2px solid ${B.grayLight}` }}><strong>{li.item}</strong> — {li.description}</div>)}
        </div>)}
      </div>)}
    </div>,
  };
  return (renderers[id] || (() => <pre style={{ fontSize: 12, background: "#F9FAFB", padding: 16, borderRadius: 8, overflow: "auto" }}>{JSON.stringify(d, null, 2)}</pre>))();
}

// ── Main App ───────────────────────────────────────────────────
export default function App() {
  const [activeModule, setActiveModule] = useState(null);
  const [files, setFiles] = useState({});
  const [rawFiles, setRawFiles] = useState({}); // actual File objects for upload
  const [params, setParams] = useState({});
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [loadingMsg, setLoadingMsg] = useState("");

  const module = MODULES.flatMap(c => c.items).find(m => m.id === activeModule);
  const msgs = ["Analyzing financial data...", "Cross-referencing entries...", "Identifying patterns...", "Preparing results..."];

  const canRun = () => {
    if (!module) return false;
    if (module.files.length === 0) return true;
    return module.files.every((_, i) => files[`${activeModule}_${i}`]?.data?.length > 0);
  };

  const runAnalysis = async () => {
    setLoading(true); setError(null); setResults(null);
    let mi = 0;
    setLoadingMsg(msgs[0]);
    const iv = setInterval(() => { mi = (mi+1) % msgs.length; setLoadingMsg(msgs[mi]); }, 3000);

    try {
      // Build FormData with files + params
      const fd = new FormData();
      fd.append("module_id", activeModule);

      const moduleParams = {};
      (module?.params || []).forEach(p => {
        moduleParams[p.key] = params[`${activeModule}_${p.key}`] ?? p.default;
      });
      fd.append("params_json", JSON.stringify(moduleParams));

      // Attach raw CSV files
      const f0 = rawFiles[`${activeModule}_0`];
      const f1 = rawFiles[`${activeModule}_1`];
      if (f0) fd.append("file_0", f0);
      if (f1) fd.append("file_1", f1);

      const resp = await fetch(`${API_BASE}/api/analyze`, { method: "POST", body: fd });

      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        throw new Error(err.detail || `Server error: ${resp.status}`);
      }

      const data = await resp.json();
      setResults(data.results);
    } catch (err) {
      setError(err.message);
    } finally {
      clearInterval(iv); setLoading(false); setLoadingMsg("");
    }
  };

  useEffect(() => { setResults(null); setError(null); }, [activeModule]);

  return (
    <div style={S.app}>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600;700&display=swap');
        @keyframes spin { to { transform: rotate(360deg) } }
        @keyframes fadeIn { from { opacity:0; transform:translateY(8px) } to { opacity:1; transform:translateY(0) } }
        * { box-sizing: border-box; margin: 0; padding: 0; }
      `}</style>

      <div style={S.sidebar}>
        <div style={S.sidebarHeader}>
          <div style={S.logo}>Trustangle</div>
          <div style={S.logoSub}>Finance AI Assistant</div>
        </div>
        {MODULES.map(cat => (
          <div key={cat.category}>
            <div style={S.catLabel}>{cat.icon} {cat.category}</div>
            {cat.items.map(item => (
              <div key={item.id} style={S.navItem(activeModule === item.id)} onClick={() => setActiveModule(item.id)}>
                {item.name}
              </div>
            ))}
          </div>
        ))}
        <div style={{ flex: 1 }} />
        <div style={{ padding: 20, fontSize: 10, color: "rgba(255,255,255,0.2)", borderTop: "1px solid rgba(255,255,255,0.05)" }}>
          Powered by Claude API · v1.0
        </div>
      </div>

      <div style={S.main}>
        {!module ? (
          <div style={S.content}>
            <div style={{ textAlign: "center", padding: "80px 40px", maxWidth: 520, margin: "0 auto" }}>
              <div style={{ fontSize: 48, marginBottom: 16 }}>🏦</div>
              <div style={{ fontSize: 26, fontWeight: 700, marginBottom: 8 }}>Finance AI Assistant</div>
              <div style={{ fontSize: 14, color: B.gray, lineHeight: 1.6 }}>
                Upload your financial data and let AI handle reconciliations, analysis, reporting, and automation.
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginTop: 32, textAlign: "left" }}>
                {MODULES.map(cat => (
                  <div key={cat.category} style={{ ...S.card, padding: 16 }}>
                    <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 4 }}>{cat.icon} {cat.category}</div>
                    {cat.items.map(item => <div key={item.id} style={{ fontSize: 12, color: B.gray, padding: "2px 0", cursor: "pointer" }} onClick={() => setActiveModule(item.id)}>→ {item.name}</div>)}
                  </div>
                ))}
              </div>
            </div>
          </div>
        ) : (
          <>
            <div style={S.header}>
              <div>
                <div style={{ fontSize: 22, fontWeight: 700 }}>{module.name}</div>
                <div style={{ fontSize: 13, color: B.gray, marginTop: 2 }}>{module.desc}</div>
              </div>
            </div>
            <div style={S.content}>
              <div style={S.card}>
                <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 16, display: "flex", alignItems: "center", gap: 8 }}>📂 Data Input</div>
                {module.files.length > 0 ? (
                  <div style={{ display: "grid", gridTemplateColumns: module.files.length > 1 ? "1fr 1fr" : "1fr", gap: 16 }}>
                    {module.files.map((label, i) => (
                      <FileUpload key={i} label={label}
                        file={files[`${activeModule}_${i}`]}
                        onFile={(f) => setFiles({ ...files, [`${activeModule}_${i}`]: f })}
                        onRawFile={(f) => setRawFiles({ ...rawFiles, [`${activeModule}_${i}`]: f })}
                      />
                    ))}
                  </div>
                ) : <div style={{ fontSize: 13, color: B.gray }}>No file upload required.</div>}

                {module.params.length > 0 && (
                  <div style={{ marginTop: 16 }}>
                    <div style={{ ...S.paramLabel, marginBottom: 8 }}>Parameters</div>
                    <div style={S.paramRow}>
                      {module.params.map(p => (
                        <div key={p.key} style={S.paramGroup}>
                          <label style={S.paramLabel}>{p.label}</label>
                          <input type={p.type} style={S.paramInput}
                            value={params[`${activeModule}_${p.key}`] ?? p.default}
                            onChange={e => setParams({ ...params, [`${activeModule}_${p.key}`]: p.type === "number" ? Number(e.target.value) : e.target.value })} />
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                <div style={{ marginTop: 20, display: "flex", gap: 12, alignItems: "center" }}>
                  <button style={S.btn("primary", loading || !canRun())} onClick={runAnalysis} disabled={loading || !canRun()}>
                    {loading ? <span style={{ display: "flex", alignItems: "center", gap: 8 }}><span style={S.spinner} /> Analyzing...</span> : "▶ Run Analysis"}
                  </button>
                  {loading && <span style={{ fontSize: 12, color: B.gray, fontStyle: "italic" }}>{loadingMsg}</span>}
                </div>
              </div>

              {error && <div style={{ ...S.card, borderLeft: `4px solid ${B.red}`, background: "#FEF2F2", animation: "fadeIn 0.3s ease" }}>
                <div style={{ fontSize: 13, color: B.red, fontWeight: 600 }}>Error: {error}</div>
              </div>}

              {results && <div style={{ animation: "fadeIn 0.4s ease" }}>
                <div style={{ ...S.card, background: "#F0FAF4", borderLeft: `4px solid ${B.green}`, padding: "12px 20px", marginBottom: 20 }}>
                  <span style={{ fontSize: 13, fontWeight: 600, color: B.green }}>✓ Analysis Complete</span>
                </div>
                {renderResults(activeModule, results)}
              </div>}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
