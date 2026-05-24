"""
Finance AI Assistant — Backend API v2
Python handles data matching. Claude handles intelligence (explanations, anomalies, commentary).
"""

import os
import json
import logging
import re
import csv
import io
from datetime import datetime, timedelta
from typing import Optional

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import anthropic

# ── Config ──────────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6")
MAX_TOKENS = int(os.environ.get("MAX_TOKENS", "8000"))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("finance-ai")

app = FastAPI(title="Finance AI Assistant API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc)},
        headers={"Access-Control-Allow-Origin": "*"},
    )


@app.options("/{path:path}")
async def preflight(path: str):
    return JSONResponse(content={}, headers={
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "POST, GET, OPTIONS",
        "Access-Control-Allow-Headers": "*",
    })


# ── Helpers ─────────────────────────────────────────────────────
def get_client():
    if not ANTHROPIC_API_KEY:
        raise HTTPException(500, "ANTHROPIC_API_KEY not configured")
    return anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


def parse_csv(content: bytes) -> dict:
    text = content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    rows = list(reader)
    return {"data": rows, "fields": reader.fieldnames or [], "row_count": len(rows)}


def clean_amount(val):
    """Parse any amount string to float."""
    if not val:
        return 0.0
    val = str(val).strip().replace("$", "").replace(",", "").replace('"', '')
    if val.startswith("(") and val.endswith(")"):
        return -float(val[1:-1])
    try:
        return float(val)
    except (ValueError, TypeError):
        return 0.0


def parse_date(val):
    """Try multiple date formats."""
    if not val:
        return None
    val = str(val).strip()
    for fmt in ["%m/%d/%Y", "%Y-%m-%d", "%d/%m/%Y", "%m/%d/%y", "%d-%m-%Y"]:
        try:
            return datetime.strptime(val, fmt).date()
        except ValueError:
            continue
    return None


def find_amount_field(fields, keywords):
    """Find the best matching field name from a list."""
    for kw in keywords:
        for f in fields:
            if kw.lower() in f.lower():
                return f
    return None


def call_claude(prompt: str, client: anthropic.Anthropic) -> str:
    """Call Claude and return raw text."""
    logger.info(f"Calling Claude ({MODEL}) — prompt: {len(prompt)} chars")
    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        messages=[{"role": "user", "content": prompt}],
    )
    return "".join(b.text for b in response.content if b.type == "text")


def parse_json_response(text: str) -> dict:
    """Robustly parse JSON from Claude's response."""
    clean = text.strip()
    # Remove markdown fences
    clean = re.sub(r"^```(?:json)?\s*", "", clean)
    clean = re.sub(r"\s*```$", "", clean)
    clean = clean.strip()
    # Fix trailing commas
    clean = re.sub(r",\s*}", "}", clean)
    clean = re.sub(r",\s*]", "]", clean)
    # Try parsing
    try:
        return json.loads(clean)
    except json.JSONDecodeError:
        pass
    # If truncated, try closing brackets
    truncated = clean.rstrip(", \n\t")
    ob = truncated.count("{") - truncated.count("}")
    osq = truncated.count("[") - truncated.count("]")
    truncated += '""' if truncated.rstrip().endswith(":") else ""
    truncated += "]" * max(osq, 0)
    truncated += "}" * max(ob, 0)
    try:
        return json.loads(truncated)
    except json.JSONDecodeError as e:
        logger.error(f"JSON failed after repair: {e}")
        logger.error(f"First 500 chars: {clean[:500]}")
        return {"error": "Could not parse response", "raw_preview": clean[:500]}


# ═══════════════════════════════════════════════════════════════
# BANK RECONCILIATION — Python does matching, Claude explains
# ═══════════════════════════════════════════════════════════════
def run_bank_recon(bank_data, gl_data, tolerance_days=3):
    """
    Step 1: Python matches transactions by amount + date tolerance.
    Step 2: Claude analyzes only the unmatched items.
    """
    bank_rows = bank_data["data"]
    gl_rows = gl_data["data"]

    # Detect field names dynamically
    bank_fields = bank_data["fields"]
    gl_fields = gl_data["fields"]

    bank_date_f = find_amount_field(bank_fields, ["date"])
    bank_amt_f = find_amount_field(bank_fields, ["amount", "net_amount", "debit", "value", "sum"])
    bank_desc_f = find_amount_field(bank_fields, ["description", "desc", "memo", "name", "narrative", "details"])
    bank_ref_f = find_amount_field(bank_fields, ["reference", "ref", "document", "number", "id", "check"])

    gl_date_f = find_amount_field(gl_fields, ["date"])
    gl_desc_f = find_amount_field(gl_fields, ["name", "description", "desc", "memo"])
    gl_ref_f = find_amount_field(gl_fields, ["document_number", "document", "ref", "number", "id"])

    # For GL: compute net amount from debit/credit or use net_amount
    gl_net_f = find_amount_field(gl_fields, ["net_amount", "amount"])
    gl_debit_f = find_amount_field(gl_fields, ["debit"])
    gl_credit_f = find_amount_field(gl_fields, ["credit"])

    def get_bank_amount(row):
        return clean_amount(row.get(bank_amt_f, 0))

    def get_gl_amount(row):
        if gl_net_f:
            return clean_amount(row.get(gl_net_f, 0))
        d = clean_amount(row.get(gl_debit_f, 0))
        c = clean_amount(row.get(gl_credit_f, 0))
        return d - c

    # Build lookup structures
    bank_items = []
    for i, row in enumerate(bank_rows):
        bank_items.append({
            "idx": i,
            "date": parse_date(row.get(bank_date_f, "")),
            "amount": get_bank_amount(row),
            "desc": row.get(bank_desc_f, ""),
            "ref": row.get(bank_ref_f, ""),
            "matched": False,
        })

    gl_items = []
    for i, row in enumerate(gl_rows):
        gl_items.append({
            "idx": i,
            "date": parse_date(row.get(gl_date_f, "")),
            "amount": get_gl_amount(row),
            "desc": row.get(gl_desc_f, ""),
            "ref": row.get(gl_ref_f, ""),
            "matched": False,
        })

    # ── MATCHING ALGORITHM ──────────────────────────────
    matched = []
    tolerance = timedelta(days=tolerance_days)

    for bi in bank_items:
        if bi["matched"] or bi["date"] is None:
            continue
        best_match = None
        best_date_diff = None
        for gi in gl_items:
            if gi["matched"] or gi["date"] is None:
                continue
            # Amount must match exactly
            if abs(bi["amount"] - gi["amount"]) < 0.01:
                date_diff = abs((bi["date"] - gi["date"]).days)
                if date_diff <= tolerance_days:
                    if best_match is None or date_diff < best_date_diff:
                        best_match = gi
                        best_date_diff = date_diff
        if best_match:
            bi["matched"] = True
            best_match["matched"] = True
            matched.append({
                "bank_date": str(bi["date"]),
                "gl_date": str(best_match["date"]),
                "amount": bi["amount"],
                "bank_desc": bi["desc"],
                "gl_desc": best_match["desc"],
                "bank_ref": bi["ref"],
                "gl_ref": best_match["ref"],
                "date_diff_days": best_date_diff,
            })

    # Check for amount mismatches (same ref or description, different amount)
    mismatches = []
    bank_unmatched = [b for b in bank_items if not b["matched"]]
    gl_unmatched = [g for g in gl_items if not g["matched"]]

    for bi in bank_unmatched[:]:
        if bi["date"] is None:
            continue
        for gi in gl_unmatched[:]:
            if gi["date"] is None:
                continue
            date_diff = abs((bi["date"] - gi["date"]).days)
            if date_diff <= tolerance_days:
                amt_diff = abs(bi["amount"] - gi["amount"])
                # Close but not exact (within 5% or $100)
                max_amt = max(abs(bi["amount"]), abs(gi["amount"]), 1)
                if 0.01 < amt_diff < max(max_amt * 0.05, 100):
                    mismatches.append({
                        "bank_date": str(bi["date"]),
                        "gl_date": str(gi["date"]),
                        "bank_amount": bi["amount"],
                        "gl_amount": gi["amount"],
                        "difference": round(bi["amount"] - gi["amount"], 2),
                        "bank_desc": bi["desc"],
                        "gl_desc": gi["desc"],
                    })
                    bi["matched"] = True
                    gi["matched"] = True
                    break

    # Final unmatched
    bank_only = [{"date": str(b["date"]), "amount": b["amount"], "description": b["desc"], "reference": b["ref"]}
                 for b in bank_items if not b["matched"]]
    gl_only = [{"date": str(g["date"]), "amount": g["amount"], "description": g["desc"], "reference": g["ref"]}
               for g in gl_items if not g["matched"]]

    return {
        "matched": matched,
        "bank_only": bank_only,
        "gl_only": gl_only,
        "mismatches": mismatches,
        "summary": {
            "total_matched": len(matched),
            "total_bank_only": len(bank_only),
            "total_gl_only": len(gl_only),
            "total_mismatches": len(mismatches),
            "net_difference": round(
                sum(b["amount"] for b in bank_only) + sum(g["amount"] for g in gl_only), 2
            ),
        },
    }


def enrich_with_claude(recon_results, client):
    """Ask Claude to explain only the unmatched items — small, focused prompt."""
    bank_only = recon_results["bank_only"][:30]  # Cap at 30 items
    gl_only = recon_results["gl_only"][:30]
    mismatches = recon_results["mismatches"][:20]

    if not bank_only and not gl_only and not mismatches:
        return recon_results

    prompt = f"""You are a senior financial analyst. A bank reconciliation has been completed algorithmically.
Below are the UNMATCHED items that need your analysis. For each item, suggest a likely cause.

## Bank-Only Items (in bank but not GL) — {len(bank_only)} items:
{json.dumps(bank_only, indent=2)}

## GL-Only Items (in GL but not bank) — {len(gl_only)} items:
{json.dumps(gl_only, indent=2)}

## Amount Mismatches (close but not exact) — {len(mismatches)} items:
{json.dumps(mismatches, indent=2)}

For each item, add a "likely_cause" field. Common causes: bank fees, timing difference, outstanding check, deposit in transit, unrecorded transaction, duplicate entry, FX/rounding difference, auto-debit not recorded, interest not recorded, data entry error.

Respond ONLY with this JSON structure (no other text):
{{"bank_only":[{{"date":"...","amount":0,"description":"...","reference":"...","likely_cause":"..."}}],"gl_only":[{{"date":"...","amount":0,"description":"...","reference":"...","likely_cause":"..."}}],"mismatches":[{{"bank_amount":0,"gl_amount":0,"difference":0,"bank_desc":"...","likely_cause":"..."}}]}}"""

    text = call_claude(prompt, client)
    explanations = parse_json_response(text)

    if "error" not in explanations:
        if explanations.get("bank_only"):
            recon_results["bank_only"] = explanations["bank_only"]
        if explanations.get("gl_only"):
            recon_results["gl_only"] = explanations["gl_only"]
        if explanations.get("mismatches"):
            recon_results["mismatches"] = explanations["mismatches"]

    return recon_results


# ═══════════════════════════════════════════════════════════════
# OTHER MODULES — Claude handles directly (small data)
# ═══════════════════════════════════════════════════════════════
PROMPT_BUILDERS = {}


def prompt_builder(module_id):
    def decorator(fn):
        PROMPT_BUILDERS[module_id] = fn
        return fn
    return decorator


@prompt_builder("intercompany")
def _(files, params):
    return f"""You are performing intercompany reconciliation between Entity A (AR) and Entity B (AP).

## Entity A - AR Ledger ({files[0]['row_count']} rows)
{json.dumps(files[0]['data'][:100], indent=2)}

## Entity B - AP Ledger ({files[1]['row_count']} rows)
{json.dumps(files[1]['data'][:100], indent=2)}

Classify variances into: FX differences, timing differences, and items requiring investigation. Be concise.

Respond ONLY with JSON:
{{"matched":[],"fx_differences":[],"timing_differences":[],"investigation_required":[],"summary":{{"total_matched":0,"total_fx":0,"total_timing":0,"total_investigate":0,"net_variance":0}}}}"""


@prompt_builder("gl_recon")
def _(files, params):
    return f"""Review this trial balance for unusual movements over {params.get('periods', 3)} periods.

## Trial Balance Data
{json.dumps(files[0]['data'][:150], indent=2)}

Flag accounts with unusual movement and balances inconsistent with their nature. Be concise.

Respond ONLY with JSON:
{{"unusual_movements":[],"nature_inconsistencies":[],"summary":{{"total_accounts_reviewed":0,"flags_raised":0,"critical_flags":0}}}}"""


@prompt_builder("variance")
def _(files, params):
    return f"""Perform variance analysis: Actual vs Budget.

## Actuals
{json.dumps(files[0]['data'][:100], indent=2)}

## Budget
{json.dumps(files[1]['data'][:100], indent=2)}

Highlight variances exceeding {params.get('threshold_pct', 10)}% or SAR {params.get('threshold_sar', 50000)}. Suggest 3 drivers per variance. Be concise.

Respond ONLY with JSON:
{{"variances":[],"summary":{{"total_favorable":0,"total_unfavorable":0,"net_variance":0,"items_flagged":0}}}}"""


@prompt_builder("anomaly")
def _(files, params):
    return f"""Analyze transactions for anomalies.

## Transaction Data ({files[0]['row_count']} rows)
{json.dumps(files[0]['data'][:150], indent=2)}

Flag: duplicates, round numbers, after-hours entries, amounts just below SAR {params.get('approval_limit', 50000)}. Be concise.

Respond ONLY with JSON:
{{"duplicates":[],"round_numbers":[],"after_hours":[],"threshold_gaming":[],"summary":{{"total_flags":0,"high_risk":0,"medium_risk":0,"low_risk":0}}}}"""


@prompt_builder("ar_aging")
def _(files, params):
    return f"""Analyze this AR aging report for shifting payment behavior.

## AR Aging Data
{json.dumps(files[0]['data'][:150], indent=2)}

Respond ONLY with JSON:
{{"behavior_shifts":[],"abnormal_growth":[],"concentration_risk":[],"summary":{{"total_ar":0,"overdue_pct":0,"customers_deteriorating":0,"top_risk_customer":""}}}}"""


@prompt_builder("commentary")
def _(files, params):
    return f"""Draft a 3-paragraph management commentary.
Period: {params.get('period', 'current')} Company: {params.get('company', '')}

## Financial Data
{json.dumps(files[0]['data'][:100], indent=2)}

Respond ONLY with JSON:
{{"commentary":{{"performance_summary":"","key_drivers":"","outlook":""}},"key_figures":[]}}"""


@prompt_builder("exec_summary")
def _(files, params):
    return f"""Summarize this financial report into a CFO brief.
Period: {params.get('period', 'current')}

## Financial Data
{json.dumps(files[0]['data'][:100], indent=2)}

Respond ONLY with JSON:
{{"executive_summary":"","key_figures":[],"material_changes":[],"risk_highlights":[],"action_items":[]}}"""


@prompt_builder("board_kpi")
def _(files, params):
    return f"""For each KPI, write 5-7 line commentary: what happened, why, and action plan.

## KPI Data
{json.dumps(files[0]['data'][:100], indent=2)}

Respond ONLY with JSON:
{{"kpis":[{{"kpi_name":"","value":"","target":"","status":"ON_TRACK","commentary":""}}]}}"""


@prompt_builder("journal_entries")
def _(files, params):
    return f"""Generate journal entries from this accruals schedule.
Posting date: {params.get('posting_date', datetime.now().strftime('%Y-%m-%d'))}

## Accruals Schedule
{json.dumps(files[0]['data'][:100], indent=2)}

Respond ONLY with JSON:
{{"journal_entries":[],"summary":{{"total_entries":0,"total_debits":0,"total_credits":0,"balanced":true}}}}"""


@prompt_builder("data_cleansing")
def _(files, params):
    return f"""Clean this dataset: standardize names, unify dates, find duplicates, flag inconsistencies.

## Raw Data ({files[0]['row_count']} rows)
{json.dumps(files[0]['data'][:100], indent=2)}

Respond ONLY with JSON:
{{"issues_found":[],"name_standardizations":[],"date_fixes":[],"summary":{{"total_issues":0,"duplicates_found":0,"names_standardized":0,"dates_fixed":0}}}}"""


@prompt_builder("report_template")
def _(files, params):
    return f"""Create a monthly financial reporting template for {params.get('company', 'the company')}, {params.get('period', 'current period')}.
Cover: P&L summary, balance sheet highlights, cash flow summary, key ratios.

Respond ONLY with JSON:
{{"template":{{"title":"","sections":[{{"section":"","subsections":[{{"name":"","line_items":[{{"item":"","description":""}}]}}]}}]}},"key_ratios":[]}}"""


# ═══════════════════════════════════════════════════════════════
# API ENDPOINTS
# ═══════════════════════════════════════════════════════════════
@app.get("/api/health")
def health():
    return {"status": "ok", "api_key_configured": bool(ANTHROPIC_API_KEY), "model": MODEL, "version": "2.0"}


@app.post("/api/analyze")
async def analyze(
    module_id: str = Form(...),
    params_json: str = Form("{}"),
    file_0: Optional[UploadFile] = File(None),
    file_1: Optional[UploadFile] = File(None),
):
    try:
        client = get_client()
        params = json.loads(params_json)

        files = []
        for f in [file_0, file_1]:
            if f and f.filename:
                content = await f.read()
                parsed = parse_csv(content)
                files.append(parsed)
            else:
                files.append({"data": [], "fields": [], "row_count": 0})

        logger.info(f"Module: {module_id} | Files: {[f.filename for f in [file_0, file_1] if f and f.filename]} | Params: {params}")

        # ── BANK RECON: Python matching + Claude explanation ──
        if module_id == "bank_recon":
            tolerance = int(params.get("tolerance_days", 3))
            result = run_bank_recon(files[0], files[1], tolerance)
            result = enrich_with_claude(result, client)
            return {"module_id": module_id, "results": result, "timestamp": datetime.utcnow().isoformat(), "model": MODEL}

        # ── ALL OTHER MODULES: Claude handles directly ──
        builder = PROMPT_BUILDERS.get(module_id)
        if not builder:
            raise HTTPException(400, f"Unknown module: {module_id}")

        prompt = builder(files, params)
        text = call_claude(prompt, client)
        result = parse_json_response(text)

        return {"module_id": module_id, "results": result, "timestamp": datetime.utcnow().isoformat(), "model": MODEL}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Analysis error: {e}")
        return JSONResponse(
            status_code=500,
            content={"detail": str(e)},
            headers={"Access-Control-Allow-Origin": "*"},
        )


@app.get("/api/modules")
def list_modules():
    return {"modules": [{"id": "bank_recon", "has_prompt": True}] + [{"id": mid} for mid in PROMPT_BUILDERS]}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
