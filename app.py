# app.py — Approver Finder (Streamlit)

import re
import json
import math
import io
from dataclasses import dataclass
from typing import Optional, Tuple, List, Dict

import pandas as pd
import streamlit as st

# -------------------------------
# Page config + small CSS
# -------------------------------
st.set_page_config(page_title="Approver Finder", layout="wide")
st.markdown("""
<style>
#MainMenu {visibility: hidden;} footer {visibility: hidden;}
.small { color: #666; font-size: 0.9em; }
.highlight { background: #ecfdf5; padding: .5rem .75rem; border-radius: .5rem; }
</style>
""", unsafe_allow_html=True)

# -------------------------------
# Data model
# -------------------------------
@dataclass
class Rule:
    block: str                 # Purchase / Sales / Other / HR
    activity: str              # e.g. "Purchase agreements", "Capex", "Quotes", ...
    condition: str             # human text: "=> €25k < €100k", "Outside normal course of business => €1,000k"
    approver_role: str         # e.g. "Board", "CEO"
    notes: str = ""            # optional extra note

# -------------------------------
# Parsing helpers
# -------------------------------
_c_eur = re.compile(r"€\s*([\d.,]+)\s*([kKmM]?)")
def _to_eur(value: str) -> Optional[float]:
    """
    Convert strings like '€25k', '€1,000k', '€750k', '€100k', '€1.5m' to float euros.
    Returns None if not found.
    """
    m = _c_eur.search(value.replace("’", "'"))
    if not m:
        return None
    num = float(m.group(1).replace(",", ""))
    suf = m.group(2).lower()
    if suf == "k":
        num *= 1_000
    elif suf == "m":
        num *= 1_000_000
    return num

def parse_range(text: str) -> Tuple[Optional[float], Optional[float]]:
    """
    Parse ranges from condition text.
    Supports:
      - '=> €25k < €100k'  -> (25000, 100000)
      - '< €25k'           -> (None, 25000)
      - '=> €100k'         -> (100000, None)
      - 'Unlimited'        -> (0, inf)
      - 'N/A'              -> (None, None)
    If nothing numeric is found, returns (None, None) and we’ll match by flags.
    """
    t = text.replace(",", "").lower()

    if "unlimited" in t:
        return (0.0, math.inf)
    if "n/a" in t or "na" == t.strip():
        return (None, None)

    # "=> €25k < €100k"  (inclusive lower, exclusive upper)
    m = re.search(r"=>\s*€\s*([\d.,]+)\s*([kKmM]?)\s*<\s*€\s*([\d.,]+)\s*([kKmM]?)", text)
    if m:
        lo = float(m.group(1).replace(",", ""))
        hi = float(m.group(3).replace(",", ""))
        if m.group(2).lower() == "k": lo *= 1_000
        if m.group(2).lower() == "m": lo *= 1_000_000
        if m.group(4).lower() == "k": hi *= 1_000
        if m.group(4).lower() == "m": hi *= 1_000_000
        return (lo, hi)

    # "=> €100k"
    m = re.search(r"=>\s*€\s*([\d.,]+)\s*([kKmM]?)", text)
    if m:
        lo = float(m.group(1).replace(",", ""))
        if m.group(2).lower() == "k": lo *= 1_000
        if m.group(2).lower() == "m": lo *= 1_000_000
        return (lo, None)

    # "< €25k"
    m = re.search(r"<\s*€\s*([\d.,]+)\s*([kKmM]?)", text)
    if m:
        hi = float(m.group(1).replace(",", ""))
        if m.group(2).lower() == "k": hi *= 1_000
        if m.group(2).lower() == "m": hi *= 1_000_000
        return (None, hi)

    return (None, None)

def amount_matches(amount: Optional[float], rng: Tuple[Optional[float], Optional[float]]) -> bool:
    """Check if amount fits (lo, hi) with lo inclusive, hi exclusive."""
    if amount is None:  # if no amount given we allow match-by-flags later
        return True
    lo, hi = rng
    if lo is None and hi is None:
        return True
    if lo is None:
        return amount < hi
    if hi is None:
        return amount >= lo
    return (amount >= lo) and (amount < hi)

def flags_match(flag_text: str, within_budget: Optional[bool], outside_normal: Optional[bool], company_level: Optional[str]) -> bool:
    """
    Tries to match simple flags based on substrings present in the condition:
    - within budget
    - outside annual budget
    - outside normal course of business
    - individual company / group basis
    """
    t = flag_text.lower()

    if within_budget is True and "within annual budget" not in t and "within normal course" not in t:
        return False
    if within_budget is False and ("outside annual budget" not in t and "outside normal course" not in t):
        # if user says not within budget, condition must mention outside
        return False

    if outside_normal is True and "outside normal course" not in t:
        return False
    # if outside_normal is False we don't require any special phrase

    if company_level == "Individual" and "individual company" not in t and "group" in t:
        # rule specifically mentions group but not individual
        return False
    if company_level == "Group" and "group" not in t and "individual company" in t:
        return False

    return True

# -------------------------------
# Built-in SAMPLE rules (you can extend or replace via CSV)
# -------------------------------
SAMPLE_RULES: List[Rule] = [
    # PURCHASE — Purchase agreements
    Rule("Purchase", "Purchase agreements",
         "Outside normal course of business => €1,000k", "Board"),
    Rule("Purchase", "Purchase agreements",
         "Within normal course of business => €1,000k", "CEO"),
    Rule("Purchase", "Purchase agreements",
         "Within normal course of business => €1,000k", "CFO"),

    # PURCHASE — Capex
    Rule("Purchase", "Capex / Capex (SharePoint)",
         "Unlimited-subject to Capex committee review", "Shareholder"),
    Rule("Purchase", "Capex / Capex (SharePoint)",
         "Within annual budget: => €100k", "CEO"),
    Rule("Purchase", "Capex / Capex (SharePoint)",
         "Outside annual budget: < €250k (individual company) < €750k (group basis)", "CEO"),
    Rule("Purchase", "Capex / Capex (SharePoint)",
         "Within annual budget: => €100k", "CFO"),
    Rule("Purchase", "Capex / Capex (SharePoint)",
         "Outside annual budget: < €250k (individual company) < €750k (group basis)", "CFO"),
    Rule("Purchase", "Capex / Capex (SharePoint)",
         "Within annual budget: => €25k < €100k", "CHRO"),
    Rule("Purchase", "Capex / Capex (SharePoint)",
         "Within annual budget: => €25k < €100k", "Group Finance Director"),
    Rule("Purchase", "Capex / Capex (SharePoint)",
         "=> €25k < €100k (VPD)", "Vice President Division"),
    Rule("Purchase", "Capex / Capex (SharePoint)",
         "< €25k (Location Manager)", "Location Manager"),
    Rule("Purchase", "Capex / Capex (SharePoint)",
         "Within annual budget: < €25k (Controller)", "Controller / Finance manager"),

    # PURCHASE — (non) PO without contract
    Rule("Purchase", "(non) PO-purchases without a contract", "=> €100k", "CFO"),
    Rule("Purchase", "(non) PO-purchases without a contract", "=> €25k < €100k", "Vice President Division"),
    Rule("Purchase", "(non) PO-purchases without a contract", "< €25k", "Location Manager"),

    # PURCHASE — Travel & Expense
    Rule("Purchase", "Travel approval & Expense Reports", "CEO", "CEO"),
    Rule("Purchase", "Travel approval & Expense Reports", "Direct reports", "All Directors"),

    # SALES — Quotes & Customer Contracts
    Rule("Sales", "Quotes & Customer Contracts", "=> €1,000k", "CEO"),
    Rule("Sales", "Commercial Credit Limits & Release of shipment blocks & Credit notes",
         "Unlimited", "Board"),

    # SALES — Credit limits / credit notes typical
    Rule("Sales", "Commercial Credit Limits & Release of shipment blocks & Credit notes",
         "=> €100k", "CFO"),
    Rule("Sales", "Commercial Credit Limits & Release of shipment blocks & Credit notes",
         "=> €25k < €100k", "Vice President Division"),
    Rule("Sales", "Commercial Credit Limits & Release of shipment blocks & Credit notes",
         "< €10k < €25k", "Location Manager"),
    Rule("Sales", "Commercial Credit Limits & Release of shipment blocks & Credit notes",
         "< €10k", "Sales Director"),

    # OTHER — Stock corrections & disposals
    Rule("Other", "Stock corrections & Counting differences & Stock disposals",
         "=> €50k < €100k", "CFO"),
    Rule("Other", "Stock corrections & Counting differences & Stock disposals",
         "=> €10k < €50k", "Vice President Division"),
    Rule("Other", "Stock corrections & Counting differences & Stock disposals",
         "=> €2.5k < €10k", "Location Manager"),
    Rule("Other", "Stock corrections & Counting differences & Stock disposals",
         "=> €2.5k < €10k", "Controller / Finance manager"),  # from lower block

    # OTHER — Manual Journal
    Rule("Other", "Manual Journal entry posting review", "=> €100k EBITDA Impact", "Group Finance Director"),
    Rule("Other", "Manual Journal entry posting review", "< €100k EBITDA Impact", "Controller / Finance manager"),

    # HR — Employment (very high-level placeholders)
    Rule("HR", "Employment", "Board members", "Board"),
    Rule("HR", "Employment", "signs yearly salary/ hiring costs => €125k", "CEO"),
    Rule("HR", "Employment", "signs yearly salary/ hiring costs < €125k", "CFO"),
    Rule("HR", "Employment", "signs yearly salary/ hiring costs < €125k", "CHRO"),
    Rule("HR", "Employment", "signs yearly salary/ hiring costs < €125k", "Vice President Division"),
]

# -------------------------------
# Role → Person mapping
# -------------------------------
MAP_FILE = "approver_people.json"
default_people = {
    "Shareholder": "—",
    "Board": "—",
    "CEO": "—",
    "CFO": "—",
    "CHRO": "—",
    "Group Finance Director": "—",
    "Strategy & Supply chain director": "—",
    "Group Legal": "—",
    "Vice President Division": "—",
    "Location Manager": "—",
    "Sales Director": "—",
    "Controller / Finance manager": "—",
    "All Directors": "—",
}

def load_people_map() -> Dict[str, str]:
    try:
        with open(MAP_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return default_people.copy()

def save_people_map(d: Dict[str, str]):
    with open(MAP_FILE, "w") as f:
        json.dump(d, f, indent=2)

people_map = load_people_map()

# -------------------------------
# Data source: built-in vs CSV upload
# -------------------------------
st.sidebar.markdown("### Data Source")
use_upload = st.sidebar.toggle("Use uploaded CSV (instead of built-in)", value=False)

def df_to_rules(df: pd.DataFrame) -> List[Rule]:
    req = {"block", "activity", "condition", "approver_role"}
    if not req.issubset({c.lower() for c in df.columns}):
        st.error("CSV must include columns: block, activity, condition, approver_role")
        return []
    # Normalize column names
    cols = {c.lower(): c for c in df.columns}
    rules: List[Rule] = []
    for _, r in df.iterrows():
        rules.append(
            Rule(
                str(r[cols["block"]]).strip(),
                str(r[cols["activity"]]).strip(),
                str(r[cols["condition"]]).strip(),
                str(r[cols["approver_role"]]).strip(),
                str(r.get(cols.get("notes", ""), "")).strip() if "notes" in cols else ""
            )
        )
    return rules

rules: List[Rule] = SAMPLE_RULES

if use_upload:
    upl = st.sidebar.file_uploader("Upload rules CSV", type=["csv"])
    if upl:
        try:
            df_up = pd.read_csv(upl)
            rules = df_to_rules(df_up) or SAMPLE_RULES
            st.sidebar.success(f"Loaded {len(rules)} rules from CSV.")
        except Exception as e:
            st.sidebar.error(f"Could not read CSV: {e}")

# People mapping editor
st.sidebar.markdown("### Role → Person")
editable = pd.DataFrame(
    {"Role": sorted({r.approver_role for r in rules}), "Person": [people_map.get(role, "—") for role in sorted({r.approver_role for r in rules})]}
)
edited = st.sidebar.data_editor(editable, key="people_edit", hide_index=True)
if st.sidebar.button("Save People Map"):
    people_map = {row["Role"]: row["Person"] for _, row in edited.iterrows()}
    save_people_map(people_map)
    st.sidebar.success("Saved.")

# -------------------------------
# UI — Wizard
# -------------------------------
st.header("Find the Approver")

# Step 1: Block
blocks = sorted({r.block for r in rules})
block = st.selectbox("Select block", blocks)

# Step 2: Activity
activities = sorted({r.activity for r in rules if r.block == block})
activity = st.selectbox("Select activity", activities)

# Step 3: Scenario flags (optional but help disambiguate)
colf1, colf2, colf3 = st.columns(3)
with colf1:
    within_budget_opt = st.selectbox("Within annual budget?", ["Unspecified", "Yes", "No"])
with colf2:
    outside_normal_opt = st.selectbox("Outside normal course?", ["Unspecified", "Yes", "No"])
with colf3:
    company_level = st.selectbox("Company level", ["Unspecified", "Individual", "Group"])

within_budget = None if within_budget_opt == "Unspecified" else (within_budget_opt == "Yes")
outside_normal = None if outside_normal_opt == "Unspecified" else (outside_normal_opt == "Yes")

# Step 4: Amount (optional, auto-parsed in €)
amount_eur = None
amount_str = st.text_input("Amount (e.g., 25k, 1,000k, 1.5m). Leave blank if not applicable.")
if amount_str.strip():
    parsed = _to_eur("€" + amount_str.strip())
    if parsed is None:
        st.warning("Could not parse that amount. Examples: 25k, 1000k, 1.5m")
    else:
        amount_eur = parsed
        st.caption(f"Parsed amount: €{parsed:,.0f}")

# -------------------------------
# Match rules
# -------------------------------
candidate_rules = [r for r in rules if r.block == block and r.activity == activity]

matches: List[Rule] = []
for r in candidate_rules:
    lo, hi = parse_range(r.condition)
    # First filter by amount range (if any), then by flags
    if amount_matches(amount_eur, (lo, hi)) and flags_match(r.condition, within_budget, outside_normal, company_level if company_level != "Unspecified" else None):
        matches.append(r)

# If nothing matched, relax flag constraints and match just by amount
if not matches:
    for r in candidate_rules:
        lo, hi = parse_range(r.condition)
        if amount_matches(amount_eur, (lo, hi)):
            matches.append(r)

# -------------------------------
# Results
# -------------------------------
if not matches:
    st.error("No approver found for the selected inputs.")
else:
    st.subheader("Approver")
    results = []
    for r in matches:
        results.append({
            "Approver Role": r.approver_role,
            "Person": people_map.get(r.approver_role, "—"),
            "Condition": r.condition,
            "Notes": r.notes
        })
    out = pd.DataFrame(results).drop_duplicates()
    st.dataframe(out, hide_index=True, use_container_width=True)
    st.markdown(
        "<p class='small'>If multiple rows appear, your inputs match multiple policy lines—use the most senior or clarify the scenario flags above.</p>",
        unsafe_allow_html=True
    )

# -------------------------------
# Download / Manage rules
# -------------------------------
st.markdown("---")
st.markdown("### Manage Rules")
colm1, colm2 = st.columns(2)
with colm1:
    if st.button("Download current rules as CSV"):
        df_rules = pd.DataFrame([r.__dict__ for r in rules])
        csv_bytes = df_rules.to_csv(index=False).encode("utf-8")
        st.download_button("Save rules.csv", data=csv_bytes, file_name="rules.csv", mime="text/csv", use_container_width=True)
with colm2:
    st.markdown(
        "<div class='small'>You can upload a CSV on the left sidebar (toggle “Use uploaded CSV”). "
        "Expected columns: <b>block, activity, condition, approver_role</b> (+ optional <i>notes</i>).</div>",
        unsafe_allow_html=True
    )
