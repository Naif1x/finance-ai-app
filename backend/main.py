"""
Finance AI Assistant — Backend API
"""

import os
import json
import logging
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import anthropic
import csv
import io

# ── Config ──────────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
MODEL = os.environ.get("CLAUDE_MODEL", "claude-3-5-sonnet-20241022")
MAX_TOKENS = int(os.environ.get("MAX_TOKENS", "4096"))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("finance-ai")

app = FastAPI(title="Finance AI Assistant API", version="1.0.0")

# Bulletproof CORS — allow everything
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Catch ALL errors and return JSON with CORS headers
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc)},
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "*",
            "Access-Control-Allow-Headers": "*",
        },
    )


# Handle CORS preflight requests explicitly
@app.options("/{rest_of_path:path}")
async def preflight_handler(rest_of_path: str):
    return JSONResponse(
        content={"message": "OK"},
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST, GET, OPTIONS, PUT, DELETE",
            "Access-Control-Allow-Headers": "*",
        },
    )


# ── Helpers ─────────────────────────────────────────────────────
def get_client():
    if not ANTHROPIC_API_KEY:
        raise HTTPException(500, "ANTHROPIC_API_KEY not configured on server")
    return anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


def parse_csv_upload(content: bytes) -> dict:
    text = content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    rows = [row for row in reader]
    fields = reader.fieldnames or []
    return {"data": rows, "fields": fields, "row_count": len(rows)}


def call_claude(prompt: str, client: anthropic.Anthropic) -> dict:
    logger.info(f"Calling Claude ({MODEL}) — prompt length: {len(prompt)} chars")
    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        messages=[{"role": "user", "content": prompt}],
    )
    text = "".join(block.text for block in response.content if block.type == "text")
    clean = text.replace("```json", "").replace("```", "").strip()

    # Fix common JSON issues from LLMs
    import re
    clean = re.sub(r',\s*}', '}', clean)
    clean = re.sub(r',\s*]', ']', clean)

    # If JSON is truncated, try to close it
    if not clean.endswith('}'):
        open_braces = clean.count('{') - clean.count('}')
        open_brackets = clean.count('[') - clean.count(']')
        clean = clean.rstrip(',\n ')
        clean += ']' * open_brackets
        clean += '}' * open_braces

    try:
        return json.loads(clean)
    except json.JSONDecodeError as e:
        logger.error(f"JSON parse error: {e}\nRaw: {clean[:1000]}")
        raise HTTPException(500, f"Claude returned invalid JSON: {str(e)}")


# ── Prompt Builders ─────────────────────────────────────────────
PROMPT_BUILDERS = {}


def prompt_builder(module_id):
    def decorator(fn):
        PROMPT_BUILDERS[module_id] = fn
        return fn
    return decorator


@prompt_builder("bank_recon")
def _(files, params):
    return f"""You are a senior financial analyst performing a bank reconciliation.

## Bank Statement Data ({files[0]['row_count']} rows)
{json.dumps(files[0]['data'][:200], indent=2)}

## GL Ledger Data ({files[1]['row_count']} rows)
{json.dumps(files[1]['data'][:200], indent=2)}

## Instructions
Match transactions between bank and GL based on amount (exact) and date (plus or minus {params.get('tolerance_days', 3)} days).
Classify each as: MATCHED, BANK_ONLY, GL_ONLY, or AMOUNT_MISMATCH.
For unmatched items, suggest causes.

Respond ONLY with JSON:
{{"matched":[],"bank_only":[],"gl_only":[],"mismatches":[],"summary":{{"total_matched":0,"total_bank_only":0,"total_gl_only":0,"total_mismatches":0,"net_difference":0}}}}"""


@prompt_builder("intercompany")
def _(files, params):
    return f"""You are performing intercompany reconciliation between Entity A (AR) and Entity B (AP).

## Entity A - AR Ledger ({files[0]['row_count']} rows)
{json.dumps(files[0]['data'][:200], indent=2)}

## Entity B - AP Ledger ({files[1]['row_count']} rows)
{json.dumps(files[1]['data'][:200], indent=2)}

Classify variances into: FX differences, timing differences, and items requiring investigation.

Respond ONLY with JSON:
{{"matched":[],"fx_differences":[],"timing_differences":[],"investigation_required":[],"summary":{{"total_matched":0,"total_fx":0,"total_timing":0,"total_investigate":0,"net_variance":0}}}}"""


@prompt_builder("gl_recon")
def _(files, params):
    return f"""Review this trial balance for unusual movements over {params.get('periods', 3)} periods.

## Trial Balance Data
{json.dumps(files[0]['data'][:300], indent=2)}

Flag accounts with unusual movement and balances inconsistent with their nature.

Respond ONLY with JSON:
{{"unusual_movements":[],"nature_inconsistencies":[],"summary":{{"total_accounts_reviewed":0,"flags_raised":0,"critical_flags":0}}}}"""


@prompt_builder("variance")
def _(files, params):
    return f"""Perform variance analysis: Actual vs Budget.

## Actuals
{json.dumps(files[0]['data'][:200], indent=2)}

## Budget
{json.dumps(files[1]['data'][:200], indent=2)}

Highlight variances exceeding {params.get('threshold_pct', 10)}% or SAR {params.get('threshold_sar', 50000)}.
Suggest 3 plausible drivers for each significant variance.

Respond ONLY with JSON:
{{"variances":[],"summary":{{"total_favorable":0,"total_unfavorable":0,"net_variance":0,"items_flagged":0}}}}"""


@prompt_builder("anomaly")
def _(files, params):
    return f"""Analyze transactions for anomalies.

## Transaction Data ({files[0]['row_count']} rows)
{json.dumps(files[0]['data'][:300], indent=2)}

Flag: duplicates, round numbers, after-hours entries, and amounts just below SAR {params.get('approval_limit', 50000)}.

Respond ONLY with JSON:
{{"duplicates":[],"round_numbers":[],"after_hours":[],"threshold_gaming":[],"summary":{{"total_flags":0,"high_risk":0,"medium_risk":0,"low_risk":0}}}}"""


@prompt_builder("ar_aging")
def _(files, params):
    return f"""Analyze this AR aging report for shifting payment behavior.

## AR Aging Data
{json.dumps(files[0]['data'][:300], indent=2)}

Respond ONLY with JSON:
{{"behavior_shifts":[],"abnormal_growth":[],"concentration_risk":[],"summary":{{"total_ar":0,"overdue_pct":0,"customers_deteriorating":0,"top_risk_customer":""}}}}"""


@prompt_builder("commentary")
def _(files, params):
    return f"""Draft a 3-paragraph management commentary from these financials.
Period: {params.get('period', 'current')} Company: {params.get('company', '')}

## Financial Data
{json.dumps(files[0]['data'][:200], indent=2)}

Respond ONLY with JSON:
{{"commentary":{{"performance_summary":"","key_drivers":"","outlook":""}},"key_figures":[]}}"""


@prompt_builder("exec_summary")
def _(files, params):
    return f"""Summarize this financial report into a CFO brief.
Period: {params.get('period', 'current')}

## Financial Data
{json.dumps(files[0]['data'][:200], indent=2)}

Respond ONLY with JSON:
{{"executive_summary":"","key_figures":[],"material_changes":[],"risk_highlights":[],"action_items":[]}}"""


@prompt_builder("board_kpi")
def _(files, params):
    return f"""For each KPI, write 5-7 line commentary: what happened, why, and action plan.

## KPI Data
{json.dumps(files[0]['data'][:200], indent=2)}

Respond ONLY with JSON:
{{"kpis":[{{"kpi_name":"","value":"","target":"","status":"ON_TRACK","commentary":""}}]}}"""


@prompt_builder("journal_entries")
def _(files, params):
    return f"""Generate journal entries from this accruals schedule.
Posting date: {params.get('posting_date', datetime.now().strftime('%Y-%m-%d'))}

## Accruals Schedule
{json.dumps(files[0]['data'][:200], indent=2)}

Respond ONLY with JSON:
{{"journal_entries":[],"summary":{{"total_entries":0,"total_debits":0,"total_credits":0,"balanced":true}}}}"""


@prompt_builder("data_cleansing")
def _(files, params):
    return f"""Clean this dataset: standardize names, unify dates, find duplicates, flag inconsistencies.

## Raw Data ({files[0]['row_count']} rows)
{json.dumps(files[0]['data'][:200], indent=2)}

Respond ONLY with JSON:
{{"issues_found":[],"name_standardizations":[],"date_fixes":[],"summary":{{"total_issues":0,"duplicates_found":0,"names_standardized":0,"dates_fixed":0}}}}"""


@prompt_builder("report_template")
def _(files, params):
    return f"""Create a monthly financial reporting template for {params.get('company', 'the company')}, {params.get('period', 'current period')}.
Cover: P&L summary, balance sheet highlights, cash flow summary, key ratios.

Respond ONLY with JSON:
{{"template":{{"title":"","sections":[{{"section":"","subsections":[{{"name":"","line_items":[{{"item":"","description":""}}]}}]}}]}},"key_ratios":[]}}"""


# ── API Endpoints ───────────────────────────────────────────────
@app.get("/api/health")
def health():
    return {"status": "ok", "api_key_configured": bool(ANTHROPIC_API_KEY), "model": MODEL}


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
                parsed = parse_csv_upload(content)
                files.append(parsed)
            else:
                files.append({"data": [], "fields": [], "row_count": 0})

        builder = PROMPT_BUILDERS.get(module_id)
        if not builder:
            raise HTTPException(400, f"Unknown module: {module_id}")

        prompt = builder(files, params)

        logger.info(f"Module: {module_id} | Files: {[f.filename for f in [file_0, file_1] if f and f.filename]} | Params: {params}")

        result = call_claude(prompt, client)

        return {
            "module_id": module_id,
            "results": result,
            "timestamp": datetime.utcnow().isoformat(),
            "model": MODEL,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Analysis error: {e}")
        return JSONResponse(
            status_code=500,
            content={"detail": str(e)},
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "*",
                "Access-Control-Allow-Headers": "*",
            },
        )


@app.get("/api/modules")
def list_modules():
    return {
        "modules": [
            {"id": mid, "has_prompt": True}
            for mid in PROMPT_BUILDERS.keys()
        ]
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
