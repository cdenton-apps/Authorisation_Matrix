# app.py — Solidus Approver Finder (with emails)
# ------------------------------------------------------------
import re
import math
import unicodedata
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
        "<div class='small'>Find the correct approver based on policy rules. Update role→person in the sidebar; emails are generated automatically.</div>",
        unsafe_allow_html=True,
    )
st.divider()

# ---------- Matrix (embedded) ----------
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

GROUPS = {
    "Purchase": ["Purchase agreements", "Capex (SharePoint)", "Non-PO without contract", "Travel & Expenses"],
    "Sales": ["Quotes & Customer Contracts", "Credit Limits / Shipment blocks / Credit notes"],
    "Other": ["Stock corrections / Counting / Disposals", "Manual Journal posting review"],
    "HR": ["Employment"],
}

# ---------- Role → Person defaults (from your list) ----------
DEFAULT_PEOPLE = {
    "Shareholder": "",
    "Board": "Solidus Investment / Board",
    "CEO": "Niels Flierman",
    "CFO": "David Kubala",
    "CHRO": "Erik van Mierlo",
    "Strategy & Supply chain director": "Robert Egging/Ignacio Aguado",
    "Group Finance Director": "Hielke Bremer",
    "Group Legal": "David Kubala",
    "Vice President Division": "Jan-Willem Kleppers",
    "Location Manager": "MD (Vacant)",
    "Sales Director": "Paul Garstang",
    "Controller / Finance manager": "Tony Noble",
}

# ---------- Email helpers ----------
def strip_accents(text: str) -> str:
    return ''.join(
        c for c in unicodedata.normalize('NFKD', text)
        if not unicodedata.combining(c)
    )

def name_to_email(fullname: str) -> str | None:
    """
    Rule: firstname.lastname@solidus.com
    - Handles hyphenated first names (keeps hyphen)
    - Removes apostrophes/accents
    - Ignores extra spaces
    """
    fullname = strip_accents(fullname.strip())
    if not fullname or "vacant" in fullname.lower():
        return None
    # Split on spaces; keep hyphenated tokens
    parts = [p for p in re.split(r"\s+", fullname.replace("'", "")) if p]
    if len(parts) == 1:
        return None
    first = parts[0].lower()
    last = parts[-1].lower()
    # Keep hyphens, remove non alnum/-
    first = re.sub(r"[^a-z0-9\-]", "", first)
    last  = re.sub(r"[^a-z0-9\-]", "", last)
    if not first or not last:
        return None
    return f"{first}.{last}@solidus.com"

def names_to_emails(name_field: str) -> list[str]:
    """
    Supports 'Name1/Name2' lists.
    """
    if not name_field:
        return []
    emails = []
    for chunk in [c.strip() for c in re.split(r"[/,&]", name_field) if c.strip()]:
        e = name_to_email(chunk)
        if e:
            emails.append(e)
    return emails

# ---------- Sidebar: editable names; emails auto-generate ----------
st.sidebar.markdown("### Role → Person (editable)")
people = {}
for role, default in DEFAULT_PEOPLE.items():
    people[role] = st.sidebar.text_input(role, value=default, placeholder="Name(s)")

st.sidebar.caption("Use '/' to separate multiple names. Emails follow firstname.lastname@solidus.com.")

# ---------- Helpers for rule parsing ----------
def euro_to_number(s: str) -> float | None:
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
    s = s.replace(".", "").replace(",", ".")
    try:
        return float(s) * multi
    except Exception:
        return None

_RANGE_PATTERNS = [
    re.compile(r"[>]=?\s*€?([\d\.,kK]+)\s*<\s*€?([\d\.,kK]+)"),
    re.compile(r"<\s*€?([\d\.,kK]+)"),
    re.compile(r"[>]=?\s*€?([\d\.,kK]+)"),
]

def extract_ranges(cell: str) -> list[tuple[float|None, float|None]]:
    if not cell or cell.upper() == "N/A":
        return []
    ranges: list[tuple[float|None, float|None]] = []
    for part in re.split(r"[;•\n]+", cell):
        part = part.strip()
        if not part:
            continue
        if "Unlimited" in part:
            ranges.append((None, None))
            continue
        m = _RANGE_PATTERNS[0].search(part)
        if m:
            lo = euro_to_number(m.group(1))
            hi = euro_to_number(m.group(2))
            ranges.append((lo, hi))
            continue
        m = _RANGE_PATTERNS[1].search(part)
        if m:
            hi = euro_to_number(m.group(1))
            ranges.append((None, hi))
            continue
        m = _RANGE_PATTERNS[2].search(part)
        if m:
            hi = euro_to_number(m.group(1))
            ranges.append((None, hi))
            continue
    return ranges

def amount_matches(ranges: list[tuple[float|None, float|None]], amount: float | None) -> bool:
    if amount is None:
        return len(ranges) > 0
    if not ranges:
        return False
    for lo, hi in ranges:
        if lo is None and hi is None:
            return True
        if lo is None and hi is not None and amount <= hi + 1e-6:
            return True
        if lo is not None and hi is not None and (lo - 1e-6) <= amount <= (hi + 1e-6):
            return True
    return False

def condition_matches(cell: str, condition: str) -> bool:
    if condition == "(Any condition)":
        return True
    return condition.lower() in cell.lower()

DF = pd.DataFrame(ROWS)

# ---------- Wizard UI ----------
c1, c2, c3 = st.columns([1.2, 1.6, 1.2])

with c1:
    area = st.selectbox("Area", list(GROUPS.keys()), index=0)

with c2:
    categories = GROUPS[area]
    category = st.selectbox("Category", categories, index=0)

with c3:
    conds = ["(Any condition)"]
    for txt in DF[category].tolist():
        if isinstance(txt, str) and txt.strip() and txt.strip().upper() != "N/A":
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

# ---------- Matching ----------
results = []
for _, row in DF.iterrows():
    cell = str(row[category] or "").strip()
    if cell.upper() == "N/A" or cell == "":
        continue
    if not condition_matches(cell, condition):
        continue
    rngs = extract_ranges(cell)
    if not amount_matches(rngs, amount):
        continue

    role = row["Approver"]
    name_field = people.get(role, "")
    emails = names_to_emails(name_field)
    results.append({
        "Approving Entity": role,
        "Person(s)": name_field,
        "Email(s)": ", ".join(emails),
        "Rule Text": cell,
    })

# Seniority for tie-breaking
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
    st.markdown(f"<span class='badge'>{len(out)} match(es)</span>", unsafe_allow_html=True)
    st.dataframe(out, use_container_width=True)

    best = results[0]
    st.markdown("#### Recommended Approver")
    email_note = f" — {best['Email(s)']}" if best["Email(s)"] else ""
    person_note = f" ({best['Person(s)']})" if best["Person(s)"] else ""
    st.success(
        f"**{best['Approving Entity']}**{person_note}{email_note}\n\nPolicy match: _{best['Rule Text']}_"
    )

st.markdown("<hr/>", unsafe_allow_html=True)
st.markdown("<div class='small'>© Solidus — Internal tool. Policy owners: Finance & Legal.</div>", unsafe_allow_html=True)
