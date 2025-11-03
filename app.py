# app.py — Solidus Approver Finder
# ------------------------------------------------------------
import re
import math
import streamlit as st
import pandas as pd
from PIL import Image

# ---------- Branding & page config ----------
st.set_page_config(
    page_title="Approver Finder — Solidus",
    page_icon="assets/solidus_favicon.png",
    layout="wide",
)

st.markdown("""
<style>
#MainMenu {visibility:hidden} footer {visibility:hidden}
.block-container {padding-top: 2rem;}
thead tr th { background:#0D4B6A; color:#fff !important; }
tbody tr td { border-top: 1px solid #E5E7EB !important; }
.stButton>button { background:#0D4B6A; color:#fff; border:0; border-radius:10px; padding:.5rem 1rem; }
.stButton>button:hover { filter:brightness(1.05); }
.small { color:#64748B; font-size:.9rem; }
.badge { display:inline-block; padding:.15rem .5rem; border-radius:.5rem; background:#EEF2FF; color:#3730A3; font-size:.8rem; }
</style>
""", unsafe_allow_html=True)

head1, head2 = st.columns([1,6], vertical_alignment="center")
with head1:
    try:
        st.image("assets/solidus_logo.png", width=72)
    except Exception:
        st.write("")
with head2:
    st.markdown(
        "<h1 style='margin:0; color:#0D4B6A;'>Approver Finder</h1>"
        "<div class='small'>Find the correct approver based on policy rules. Update role→person in the sidebar.</div>",
        unsafe_allow_html=True,
    )
st.divider()

# ---------- Matrix (embedded) ----------
# Columns are grouped for clarity. Each row = Approving Entity.
# Cell text mirrors your matrix (kept deliberately close for auditability).
ROWS = [
    {
        "Approver": "Shareholder",
        "Purchase agreements": "N/A",
        "Capex (SharePoint)": "Unlimited-subject to Capex committee review",
        "Non-PO without contract": "N/A",
        "Travel & Expenses": "N/A",
        "Quotes & Customer Contracts": "N/A",
        "Credit Limits / Shipment blocks / Credit notes": "N/A",
        "Stock corrections / Counting / Disposals": "N/A",
        "Manual Journal posting review": "N/A",
        "Employment": "N/A",
    },
    {
        "Approver": "Board",
        "Purchase agreements": "Outside normal course of business => €1.000k",
        "Capex (SharePoint)": "=> €1.000k",
        "Non-PO without contract": "N/A",
        "Travel & Expenses": "CEO",
        "Quotes & Customer Contracts": "N/A",
        "Credit Limits / Shipment blocks / Credit notes": "Unlimited",
        "Stock corrections / Counting / Disposals": "N/A",
        "Manual Journal posting review": "N/A",
        "Employment": "Board members",
    },
    {
        "Approver": "CEO",
        "Purchase agreements": "Within normal course of business => €1.000k",
        "Capex (SharePoint)": "- Within annual budget: => €100k ; - Outside annual budget: < €250k (individual) ; < €750k (group)",
        "Non-PO without contract": "N/A",
        "Travel & Expenses": "Direct reports",
        "Quotes & Customer Contracts": "=> €1.000k",
        "Credit Limits / Shipment blocks / Credit notes": "N/A",
        "Stock corrections / Counting / Disposals": "=> €100k",
        "Manual Journal posting review": "N/A",
        "Employment": "signs yearly salary/ hiring costs => €125k ; signs bonus => €50k",
    },
    {
        "Approver": "CFO",
        "Purchase agreements": "Within normal course of business => €1.000k",
        "Capex (SharePoint)": "- Within annual budget: => €100k ; - Outside annual budget: < €250k (individual) ; < €750k (group)",
        "Non-PO without contract": "=> €100k",
        "Travel & Expenses": "Direct reports",
        "Quotes & Customer Contracts": "N/A",
        "Credit Limits / Shipment blocks / Credit notes": "=> €100k",
        "Stock corrections / Counting / Disposals": "=> €50k < €100k",
        "Manual Journal posting review": "N/A",
        "Employment": "signs yearly salary/ hiring costs < €125k ; signs bonus < €50k",
    },
    {
        "Approver": "CHRO",
        "Purchase agreements": "N/A",
        "Capex (SharePoint)": "- Within annual budget: => €25k < €100k ; - Others follow approval scheme",
        "Non-PO without contract": "N/A",
        "Travel & Expenses": "Direct reports",
        "Quotes & Customer Contracts": "N/A",
        "Credit Limits / Shipment blocks / Credit notes": "N/A",
        "Stock corrections / Counting / Disposals": "N/A",
        "Manual Journal posting review": "N/A",
        "Employment": "signs yearly salary/ hiring costs < €125k ; signs bonus < €50k",
    },
    {
        "Approver": "Group Finance Director",
        "Purchase agreements": "< €100k",
        "Capex (SharePoint)": "- Within annual budget: => €25k < €100k ; - Others follow approval scheme",
        "Non-PO without contract": "N/A",
        "Travel & Expenses": "Direct reports",
        "Quotes & Customer Contracts": "N/A",
        "Credit Limits / Shipment blocks / Credit notes": "N/A",
        "Stock corrections / Counting / Disposals": "N/A",
        "Manual Journal posting review": "=> €100k EBITDA Impact",
        "Employment": "N/A",
    },
    {
        "Approver": "Strategy & Supply chain director",
        "Purchase agreements": "=> €150k < €1.000k",
        "Capex (SharePoint)": "Price / quality",
        "Non-PO without contract": "N/A",
        "Travel & Expenses": "Direct reports",
        "Quotes & Customer Contracts": "N/A",
        "Credit Limits / Shipment blocks / Credit notes": "N/A",
        "Stock corrections / Counting / Disposals": "N/A",
        "Manual Journal posting review": "N/A",
        "Employment": "N/A",
    },
    {
        "Approver": "Group Legal",
        "Purchase agreements": "Review Contract",
        "Capex (SharePoint)": "N/A",
        "Non-PO without contract": "N/A",
        "Travel & Expenses": "N/A",
        "Quotes & Customer Contracts": "N/A",
        "Credit Limits / Shipment blocks / Credit notes": "N/A",
        "Stock corrections / Counting / Disposals": "N/A",
        "Manual Journal posting review": "N/A",
        "Employment": "N/A",
    },
    {
        "Approver": "Vice President Division",
        "Purchase agreements": "=> €100k < €150k",
        "Capex (SharePoint)": "- Within annual budget: => €25k < €100k ; - Outside annual budget: < €25k ; - Others follow approval scheme",
        "Non-PO without contract": "=> €25k < €100k",
        "Travel & Expenses": "Direct reports",
        "Quotes & Customer Contracts": "=> €25k < €1.000k",
        "Credit Limits / Shipment blocks / Credit notes": "=> €25k < €100k",
        "Stock corrections / Counting / Disposals": "=> €10k < €50k",
        "Manual Journal posting review": "N/A",
        "Employment": "signs yearly salary/ hiring costs < €125k ; signs bonus < €50k",
    },
    {
        "Approver": "Location Manager",
        "Purchase agreements": "< €100k",
        "Capex (SharePoint)": "- Within annual budget: => €25k < €100k ; - Others follow approval scheme",
        "Non-PO without contract": "< €25k",
        "Travel & Expenses": "Direct reports",
        "Quotes & Customer Contracts": "< €25k",
        "Credit Limits / Shipment blocks / Credit notes": "=> €10k < €25k",
        "Stock corrections / Counting / Disposals": "=> €2.5k < €10k",
        "Manual Journal posting review": "N/A",
        "Employment": "N/A",
    },
    {
        "Approver": "Sales Director",
        "Purchase agreements": "N/A",
        "Capex (SharePoint)": "N/A",
        "Non-PO without contract": "N/A",
        "Travel & Expenses": "Direct reports",
        "Quotes & Customer Contracts": "< €25k",
        "Credit Limits / Shipment blocks / Credit notes": "< €10k",
        "Stock corrections / Counting / Disposals": "N/A",
        "Manual Journal posting review": "N/A",
        "Employment": "N/A",
    },
    {
        "Approver": "Controller / Finance manager",
        "Purchase agreements": "N/A",
        "Capex (SharePoint)": "- Within annual budget: < €25k",
        "Non-PO without contract": "N/A",
        "Travel & Expenses": "Direct reports",
        "Quotes & Customer Contracts": "N/A",
        "Credit Limits / Shipment blocks / Credit notes": "N/A",
        "Stock corrections / Counting / Disposals": "=> €2.5k < €10k",
        "Manual Journal posting review": "< €100k EBITDA Impact",
        "Employment": "N/A",
    },
]

# Group → Category list (drives the wizard)
GROUPS = {
    "Purchase": ["Purchase agreements", "Capex (SharePoint)", "Non-PO without contract", "Travel & Expenses"],
    "Sales": ["Quotes & Customer Contracts", "Credit Limits / Shipment blocks / Credit notes"],
    "Other": ["Stock corrections / Counting / Disposals", "Manual Journal posting review"],
    "HR": ["Employment"],
}

# ---------- Sidebar: role→person mapping (editable) ----------
st.sidebar.markdown("### Role → Person")
default_people = {
    "Shareholder": "",
    "Board": "",
    "CEO": "",
    "CFO": "",
    "CHRO": "",
    "Group Finance Director": "",
    "Strategy & Supply chain director": "",
    "Group Legal": "",
    "Vice President Division": "",
    "Location Manager": "",
    "Sales Director": "",
    "Controller / Finance manager": "",
}
people = {}
for role in default_people:
    people[role] = st.sidebar.text_input(role, value=default_people[role], placeholder="Name")

st.sidebar.caption("Leave blank if unassigned. Names are shown on results.")

# ---------- Helpers ----------
def euro_to_number(s: str) -> float | None:
    """
    Parse a euro-ish string to float (supports '€', '.', ',', 'k').
    '€1.000k' -> 1_000_000 ; '€25k' -> 25_000 ; '€10k' -> 10_000
    Returns None if not parseable.
    """
    if s is None:
        return None
    s = s.strip()
    if not s:
        return None
    s = s.replace("€", "").replace(" ", "")
    multi = 1.0
    if s.lower().endswith("k"):
        multi = 1_000.0
        s = s[:-1]
    # European thousands with '.' and decimal ',' — normalize
    s = s.replace(".", "").replace(",", ".")
    try:
        return float(s) * multi
    except Exception:
        return None

_RANGE_PATTERNS = [
    # "=> €25k < €100k" or ">= €25k < €100k"
    re.compile(r"[>]=?\s*€?([\d\.,kK]+)\s*<\s*€?([\d\.,kK]+)"),
    # "< €25k"
    re.compile(r"<\s*€?([\d\.,kK]+)"),
    # "=> €100k" or ">= €100k"
    re.compile(r"[>]=?\s*€?([\d\.,kK]+)"),
]

def extract_ranges(cell: str) -> list[tuple[float|None, float|None]]:
    """
    From a cell string, extract numeric ranges as tuples (min, max).
    None means open-ended. We treat '=> €X' as '≤ X' by policy convention.
    """
    if not cell or cell.upper() == "N/A":
        return []
    ranges: list[tuple[float|None, float|None]] = []

    # Cells can contain multiple clauses separated by ';'
    for part in re.split(r"[;•\n]+", cell):
        part = part.strip()
        if not part:
            continue
        # Unlimited → always match
        if "Unlimited" in part:
            ranges.append((None, None))
            continue

        # Match range patterns in order
        m = _RANGE_PATTERNS[0].search(part)
        if m:
            lo = euro_to_number(m.group(1))
            hi = euro_to_number(m.group(2))
            if lo is not None or hi is not None:
                ranges.append((lo, hi))
            continue

        m = _RANGE_PATTERNS[1].search(part)
        if m:
            hi = euro_to_number(m.group(1))
            ranges.append((None, hi))
            continue

        m = _RANGE_PATTERNS[2].search(part)
        if m:
            # Interpret '=> €X' as up-to X (≤ X) based on matrix wording
            hi = euro_to_number(m.group(1))
            ranges.append((None, hi))
            continue

    return ranges

def amount_matches(ranges: list[tuple[float|None, float|None]], amount: float | None) -> bool:
    if amount is None:
        # If user did not provide amount, match any non-N/A cell
        return len(ranges) > 0
    if not ranges:
        return False
    for lo, hi in ranges:
        if lo is None and hi is None:
            return True  # Unlimited
        if lo is None and hi is not None and amount <= hi + 1e-6:
            return True
        if lo is not None and hi is not None and (lo - 1e-6) <= amount <= (hi + 1e-6):
            return True
    return False

def condition_matches(cell: str, condition: str) -> bool:
    if condition == "(Any condition)":
        return True
    return condition.lower() in cell.lower()

def build_df() -> pd.DataFrame:
    return pd.DataFrame(ROWS)

DF = build_df()

# ---------- Wizard UI ----------
c1, c2, c3 = st.columns([1.2, 1.6, 1.2])

with c1:
    area = st.selectbox("Area", list(GROUPS.keys()), index=0)

with c2:
    categories = GROUPS[area]
    category = st.selectbox("Category", categories, index=0)

with c3:
    # Collect distinct condition phrases seen in selected category (excluding 'N/A')
    conds = ["(Any condition)"]
    for txt in DF[category].tolist():
        if isinstance(txt, str) and txt.strip() and txt.strip().upper() != "N/A":
            # Split by ';' to surface sub-clauses as selectable conditions
            parts = [p.strip() for p in re.split(r"[;]+", txt) if p.strip()]
            for p in parts:
                if p not in conds:
                    conds.append(p)
    condition = st.selectbox("Condition", conds, index=0)

st.markdown("")

cc1, cc2 = st.columns([1,1])
with cc1:
    amount_eur = st.number_input("Amount (€)", min_value=0.0, value=0.0, step=1000.0, format="%.2f")
    amount = None if amount_eur == 0.0 else amount_eur
with cc2:
    st.markdown("<span class='small'>Leave amount at 0 to ignore amount filtering.</span>", unsafe_allow_html=True)

st.divider()

# ---------- Matching logic ----------
results = []
for _, row in DF.iterrows():
    cell = str(row[category] or "").strip()
    if cell.upper() == "N/A" or cell == "":
        continue

    # Condition filter
    if not condition_matches(cell, condition):
        continue

    # Amount filter
    rngs = extract_ranges(cell)
    if not amount_matches(rngs, amount):
        continue

    results.append({
        "Approving Entity": row["Approver"],
        "Person": people.get(row["Approver"], "").strip(),
        "Rule Text": cell,
    })

# Seniority order (top = higher)
seniority = [
    "Shareholder","Board","CEO","CFO","CHRO","Group Finance Director",
    "Strategy & Supply chain director","Group Legal","Vice President Division",
    "Location Manager","Sales Director","Controller / Finance manager"
]
order_map = {name:i for i,name in enumerate(seniority)}
results.sort(key=lambda r: order_map.get(r["Approving Entity"], math.inf))

# ---------- Output ----------
st.markdown(f"### Results for **{area} → {category}**")
if not results:
    st.info("No matching approver found with the selected filters. Try loosening the condition or clearing the amount.")
else:
    out = pd.DataFrame(results)
    # Show badge with count
    st.markdown(f"<span class='badge'>{len(out)} match(es)</span>", unsafe_allow_html=True)
    # Pretty table
    st.dataframe(out, use_container_width=True)

    # Primary recommendation (top by seniority order)
    best = results[0]
    st.markdown("#### Recommended Approver")
    st.success(
        f"**{best['Approving Entity']}**"
        + (f" — {best['Person']}" if best['Person'] else "")
        + f"\n\nPolicy match: _{best['Rule Text']}_"
    )

st.markdown("<hr/>", unsafe_allow_html=True)
st.markdown("<div class='small'>© Solidus — Internal tool. Policy owners: Finance & Legal.</div>", unsafe_allow_html=True)
