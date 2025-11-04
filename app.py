# app.py — Solidus Approvals Finder (with Recommended badge + Alternative table)

import re
import streamlit as st
from PIL import Image

# -----------------------------
# Page + simple styling
# -----------------------------
st.set_page_config(page_title="Solidus Approvals Finder", layout="wide")
st.markdown(
    """
    <style>
      #MainMenu{visibility:hidden;} footer{visibility:hidden;}
      .smallgray{color:#6b7280;font-size:0.9rem}
      .note{background:#f7f7fb;border:1px solid #e5e7eb;border-radius:10px;padding:12px}
      .role{font-weight:600}
      .pill{display:inline-block;padding:.15rem .55rem;background:#ecfdf5;border:1px solid #10b98133;
            border-radius:9999px;margin-left:.45rem;font-size:.8rem;color:#047857}
    </style>
    """,
    unsafe_allow_html=True,
)

# -----------------------------
# Header (previous arrangement)
# -----------------------------
left, right = st.columns([1, 3], gap="large")
with left:
    try:
        st.image("assets/solidus_logo.png", width=260)  # wide/bigger
    except Exception:
        st.write(" ")

with right:
    st.markdown(
        "<h1 style='color:#0D4B6A;margin:.2rem 0 .4rem 0'>Solidus Approvals Finder</h1>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<div class='smallgray'>Answer the minimum required questions. "
        "We’ll show the recommended approver(s) and also list alternatives (higher or backup roles).</div>",
        unsafe_allow_html=True,
    )

st.divider()

# -----------------------------
# People per role (editable)
# -----------------------------
ROLE_PEOPLE = {
    "Shareholder": "",
    "Solidus Investment / Board": "Board members",
    "CEO": "Niels Flierman",
    "CFO": "David Kubala",
    "CHRO": "Erik van Mierlo",
    "Strategy & Supply chain director": "Robert Egging/Ignacio Aguado",
    "Group Finance Director": "Hielke Bremer",
    "Group Legal": "David Kubala",
    "Vice President Division": "Jan-Willem Kleppers",
    "Location Director": "MD (Vacant)",
    "Sales Director": "Paul Garstang",
    "Controller / Finance manager": "Tony Noble",
}

def to_emails(name: str) -> list[str]:
    """firstname.lastname@solidus.com, supports 'A/B' etc."""
    if not name or "vacant" in name.lower():
        return []
    parts = re.split(r"[\/,]| and ", name, flags=re.I)
    out = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        p = re.sub(r"\(.*?\)", "", p).strip()
        p = re.sub(r"[^A-Za-z\\-\\s]", "", p)
        p = re.sub(r"\s+", " ", p).strip().lower()
        if not p:
            continue
        out.append(p.replace(" ", ".") + "@solidus.com")
    return out

# -----------------------------
# Rule helpers
# -----------------------------
def purchase_contract_rules(amount: float, in_normal_course: bool) -> list[str]:
    roles: list[str] = []
    # base ladder (lowest → highest)
    ladder = [
        "Location Director",
        "Group Finance Director",
        "Vice President Division",
        "Strategy & Supply chain director",
        "CEO",
        "Solidus Investment / Board",
    ]
    if not in_normal_course and amount >= 1_000_000:
        roles.append("Solidus Investment / Board")
    if amount < 100_000:
        roles += ["Location Director", "Group Finance Director"]
    elif 100_000 <= amount < 150_000:
        roles.append("Vice President Division")
    elif 150_000 <= amount < 1_000_000:
        roles.append("Strategy & Supply chain director")
    else:
        roles.append("CEO")
    # Legal always
    roles.append("Group Legal")
    return roles, ladder + ["Group Legal"]

def purchase_nonpo_rules(amount: float) -> tuple[list[str], list[str]]:
    ladder = ["Location Director", "Vice President Division", "CFO"]
    if amount < 25_000:
        return (["Location Director"], ladder)
    elif amount < 100_000:
        return (["Vice President Division"], ladder)
    else:
        return (["CFO"], ladder)

def capex_rules(amount: float, within_budget: bool, scope: str) -> tuple[list[str], list[str]]:
    ladder = [
        "Controller / Finance manager",
        "Group Finance Director",
        "Vice President Division",
        "CEO",
        "Solidus Investment / Board",
    ]
    roles: list[str] = []
    if within_budget:
        if amount < 25_000:
            roles.append("Controller / Finance manager")
        elif amount < 100_000:
            roles += ["Group Finance Director", "Vice President Division"]
        else:
            roles.append("CEO")
    else:
        if scope == "Individual company":
            if amount < 25_000:
                roles.append("Vice President Division")
            elif amount < 250_000:
                roles.append("CEO")
            else:
                roles.append("CEO")
        else:  # Group basis
            if amount < 750_000:
                roles.append("CEO")
            else:
                roles.append("Solidus Investment / Board")
    return roles, ladder

def sales_quotes_rules(amount: float) -> tuple[list[str], list[str]]:
    ladder = ["Location Director", "Sales Director", "Vice President Division", "CEO"]
    if amount < 25_000:
        return (["Location Director", "Sales Director"], ladder)
    elif amount < 1_000_000:
        return (["Vice President Division"], ladder)
    else:
        return (["CEO"], ladder)

def sales_credit_rules(amount: float) -> tuple[list[str], list[str]]:
    ladder = ["Sales Director", "Location Director", "Vice President Division", "CFO"]
    if amount < 10_000:
        return (["Sales Director"], ladder)
    elif amount < 25_000:
        return (["Location Director"], ladder)
    elif amount < 100_000:
        return (["Vice President Division"], ladder)
    else:
        return (["CFO"], ladder)

def other_stock_rules(amount: float) -> tuple[list[str], list[str]]:
    ladder = ["Location Director", "Controller / Finance manager", "Vice President Division", "CFO"]
    if amount < 2_500:
        return ([], ladder)
    elif amount < 10_000:
        return (["Location Director", "Controller / Finance manager"], ladder)
    elif amount < 50_000:
        return (["Vice President Division"], ladder)
    elif amount < 100_000:
        return (["CFO"], ladder)
    else:
        return (["CFO"], ladder)

def other_manual_journal_rules(impact: float) -> tuple[list[str], list[str]]:
    ladder = ["Controller / Finance manager", "Group Finance Director"]
    if abs(impact) < 100_000:
        return (["Controller / Finance manager"], ladder)
    else:
        return (["Group Finance Director"], ladder)

def hr_employment_rules(salary: float, bonus: float, is_board_member: bool) -> tuple[list[str], list[str]]:
    ladder = ["Vice President Division", "CHRO", "CFO", "CEO", "Solidus Investment / Board"]
    if is_board_member:
        return (["Solidus Investment / Board"], ladder)
    if salary >= 125_000 or bonus >= 50_000:
        return (["CEO"], ladder)
    return (["Vice President Division", "CHRO", "CFO"], ladder)

# -----------------------------
# Wizard (same flow as before)
# -----------------------------
st.subheader("1) Choose area")
area = st.selectbox("Area", ["Purchase", "Sales", "Other", "HR"])

recommended: list[str] = []
ladder: list[str] = []
notes: list[str] = []

if area == "Purchase":
    sub = st.selectbox("Type", ["Purchase (contract) agreements", "(non) PO-purchases without a contract", "Capital / Capex"])

    if sub == "Purchase (contract) agreements":
        in_course = st.selectbox("Within normal course of business?", ["Yes", "No"]) == "Yes"
        amount = st.number_input("Contract value (cumulative across term, €)", min_value=0.0, step=1000.0, format="%.0f")
        if amount >= 0:
            recommended, ladder = purchase_contract_rules(amount, in_course)
            if not in_course and amount >= 1_000_000:
                notes.append("Outside normal course ≥ €1,000k requires Board approval.")
            notes.append("Group Legal review is required for contracts.")

    elif sub == "(non) PO-purchases without a contract":
        amount = st.number_input("Amount (€)", min_value=0.0, step=500.0, format="%.0f")
        if amount >= 0:
            recommended, ladder = purchase_nonpo_rules(amount)

    else:  # Capex
        within = st.selectbox("Within annual budget?", ["Yes", "No"]) == "Yes"
        scope = st.selectbox("Scope (if outside budget)", ["Individual company", "Group"]) if not within else "Individual company"
        amount = st.number_input("Capex amount (€)", min_value=0.0, step=1000.0, format="%.0f")
        if amount >= 0:
            recommended, ladder = capex_rules(amount, within, scope)

elif area == "Sales":
    sub = st.selectbox("Type", ["Quotes & Customer Contracts", "Commercial Credit Limits / Blocks / Credit notes"])
    amount = st.number_input("Amount (€)", min_value=0.0, step=500.0, format="%.0f")
    if sub.startswith("Quotes"):
        recommended, ladder = sales_quotes_rules(amount)
    else:
        recommended, ladder = sales_credit_rules(amount)

elif area == "Other":
    sub = st.selectbox("Type", ["Stock corrections / counting differences / stock disposals", "Manual journal entry posting review"])
    if sub.startswith("Stock"):
        amount = st.number_input("Absolute value of stock adjustment (€)", min_value=0.0, step=100.0, format="%.0f")
        recommended, ladder = other_stock_rules(amount)
    else:
        impact = st.number_input("EBITDA impact of the journal (absolute value, €)", min_value=0.0, step=100.0, format="%.0f")
        recommended, ladder = other_manual_journal_rules(impact)

else:  # HR
    is_board = st.checkbox("Is the person a Board member?")
    salary = st.number_input("Annual salary (€)", min_value=0.0, step=1000.0, format="%.0f")
    bonus = st.number_input("Annual bonus (€)", min_value=0.0, step=1000.0, format="%.0f")
    recommended, ladder = hr_employment_rules(salary, bonus, is_board)

st.divider()

# -----------------------------
# Output — Recommended + Alternatives
# -----------------------------
st.subheader("2) Approver(s)")

if not recommended:
    st.info("Provide the required inputs above to see approvers.")
else:
    # De-dupe and keep order
    seen = set()
    rec_clean = []
    for r in recommended:
        if r not in seen:
            rec_clean.append(r)
            seen.add(r)

    # Show recommended cards (like before, but badge text updated)
    for idx, role in enumerate(rec_clean, start=1):
        person = ROLE_PEOPLE.get(role, "")
        emails = ", ".join(to_emails(person)) or "—"
        st.markdown(
            f"<div class='note'><span class='role'>{idx}. {role}</span>"
            f"<span class='pill'>Recommended</span><br>"
            f"Current person: {person or '—'}<br>"
            f"Email: {emails}</div>",
            unsafe_allow_html=True,
        )

    # Alternatives = ladder minus recommended (keep order)
    alt = [r for r in ladder if r not in rec_clean]
    if alt:
        st.markdown("**Alternative approvers (higher or backup):**")
        # Build simple table
        rows = []
        for r in alt:
            person = ROLE_PEOPLE.get(r, "")
            email = ", ".join(to_emails(person)) or "—"
            rows.append({"Role": r, "Current person": person or "—", "Email": email})
        st.table(rows)

    if notes:
        st.markdown("**Notes:**")
        for n in notes:
            st.markdown(f"- {n}")

st.divider()
st.markdown(
    "<div class='smallgray'>Role → person and thresholds are defined in the file and can be updated easily.</div>",
    unsafe_allow_html=True,
)
