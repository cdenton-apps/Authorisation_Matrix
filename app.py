# app.py — Solidus Approvals Finder (matrix wizard)

import re
import math
import streamlit as st
from PIL import Image

# -----------------------------
# Page setup & branding
# -----------------------------
st.set_page_config(page_title="Solidus Approvals Finder", layout="wide")

hide = """
<style>
 #MainMenu{visibility:hidden;} footer{visibility:hidden;}
 .smallgray{color:#6b7280;font-size:0.9rem}
 .note{background:#f7f7fb;border:1px solid #e5e7eb;border-radius:10px;padding:10px}
 .role{font-weight:600}
 .pill{display:inline-block;padding:.15rem .5rem;background:#eef2ff;border-radius:9999px;margin-left:.35rem;font-size:.8rem;color:#3730a3}
</style>
"""
st.markdown(hide, unsafe_allow_html=True)

left, right = st.columns([1, 3], gap="large")

with left:
    try:
        st.image("assets/solidus_logo.png", width=260)  # bigger & wide
    except Exception:
        st.write(" ")

with right:
    st.markdown("<h1 style='color:#0D4B6A;margin:.2rem 0 .4rem 0'>Solidus Approvals Finder</h1>", unsafe_allow_html=True)
    st.markdown(
        "<div class='smallgray'>Answer a few questions. We’ll filter down to the correct approving role(s). "
        "If multiple roles are required, we list them in the recommended (lowest level first) order.</div>",
        unsafe_allow_html=True,
    )

st.divider()

# -----------------------------
# People in roles (easy to edit)
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
    """Build firstname.lastname@solidus.com (handles slashes, hyphens, spaces)."""
    if not name or "vacant" in name.lower():
        return []
    parts = re.split(r"[\/,]| and ", name, flags=re.I)
    emails = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        # remove parentheses content
        p = re.sub(r"\(.*?\)", "", p).strip()
        # keep letters, spaces, hyphens
        p = re.sub(r"[^A-Za-z\-\s]", "", p)
        p = re.sub(r"\s+", " ", p).strip().lower()
        if not p:
            continue
        first_last = p.replace(" ", ".")
        emails.append(f"{first_last}@solidus.com")
    return emails

# -----------------------------
# Rules (short, practical mapping)
# -----------------------------
EUR = "€"

# Helper to display amount nicely
def money(x: float) -> str:
    return f"{EUR}{x:,.0f}".replace(",", " ")  # thin-space

# Purchase – Purchase (contract) agreements
def purchase_contract_rules(amount: float, in_normal_course: bool) -> list[str]:
    roles: list[str] = []
    if not in_normal_course:
        # Outside normal course: Board if >= 1,000k
        if amount >= 1_000_000:
            roles.append("Solidus Investment / Board")
        # and still follow the amount routing below for business owner chain
    # Within the normal course (or regardless, pick level by amount)
    if amount < 100_000:
        # Lowest level first
        roles += ["Location Director", "Group Finance Director"]
    elif 100_000 <= amount < 150_000:
        roles.append("Vice President Division")
    elif 150_000 <= amount < 1_000_000:
        roles.append("Strategy & Supply chain director")
    else:  # >= 1,000,000
        roles.append("CEO")
    # Always include Legal review for contracts (at the end)
    roles.append("Group Legal")
    return roles

# Purchase – (non) PO purchases without a contract
def purchase_nonpo_rules(amount: float) -> list[str]:
    if amount < 25_000:
        return ["Location Director"]
    elif amount < 100_000:
        return ["Vice President Division"]
    else:
        return ["CFO"]

# Purchase – Capital / Capex
def capex_rules(amount: float, within_budget: bool, scope: str) -> list[str]:
    """
    within_budget: True/False
    scope: "Individual company" | "Group"
    """
    chain: list[str] = []
    # Lowest levels by budget bands (from matrix)
    if within_budget:
        if amount < 25_000:
            chain.append("Controller / Finance manager")
        elif amount < 100_000:
            chain += ["Group Finance Director", "Vice President Division"]
        else:
            chain.append("CEO")
    else:
        # outside budget – different caps
        if scope == "Individual company":
            if amount < 25_000:
                chain.append("Vice President Division")
            elif amount < 250_000:
                chain.append("CEO")
            else:
                chain.append("CEO")  # CEO and likely Board via Capex committee
        else:  # Group basis
            if amount < 750_000:
                chain.append("CEO")
            else:
                chain.append("Solidus Investment / Board")
    return chain

# Sales – Quotes & Customer Contracts
def sales_quotes_rules(amount: float) -> list[str]:
    if amount < 25_000:
        # two roles at the low end; keep lowest level first
        return ["Location Director", "Sales Director"]
    elif amount < 1_000_000:
        return ["Vice President Division"]
    else:
        return ["CEO"]

# Sales – Commercial Credit Limits & release of shipment blocks & credit notes
def sales_credit_rules(amount: float) -> list[str]:
    if amount < 10_000:
        return ["Sales Director"]
    elif amount < 25_000:
        return ["Location Director"]
    elif amount < 100_000:
        return ["Vice President Division"]
    else:
        return ["CFO"]

# Other – Stock corrections & counting differences & stock disposals
def other_stock_rules(amount: float) -> list[str]:
    if amount < 2_500:
        return []
    elif amount < 10_000:
        # matrix shows both; keep lowest level first and include Controller (finance impact)
        return ["Location Director", "Controller / Finance manager"]
    elif amount < 50_000:
        return ["Vice President Division"]
    elif amount < 100_000:
        return ["CFO"]
    else:
        return ["CFO"]  # escalate

# Other – Manual journal entry posting review
def other_manual_journal_rules(ebitda_impact: float) -> list[str]:
    if abs(ebitda_impact) < 100_000:
        return ["Controller / Finance manager"]
    else:
        return ["Group Finance Director"]

# HR – Employment & benefits
def hr_employment_rules(salary: float, bonus: float, is_board_member: bool) -> list[str]:
    if is_board_member:
        return ["Solidus Investment / Board"]
    # CEO thresholds: salary >= 125k OR bonus >= 50k
    if salary >= 125_000 or bonus >= 50_000:
        return ["CEO"]
    # otherwise multiple roles can sign; list lowest level first
    return ["Vice President Division", "CHRO", "CFO"]

# -----------------------------
# Wizard
# -----------------------------
st.subheader("1) Choose area")
area = st.selectbox(
    "Area",
    ["Purchase", "Sales", "Other", "HR"],
)

# The user journey splits here, only asking for relevant inputs.
result_roles: list[str] = []
extra_notes: list[str] = []

if area == "Purchase":
    sub = st.selectbox(
        "Type",
        ["Purchase (contract) agreements", "(non) PO-purchases without a contract", "Capital / Capex"],
    )

    if sub == "Purchase (contract) agreements":
        in_course = st.selectbox("Within normal course of business?", ["Yes", "No"]) == "Yes"
        amount = st.number_input("Contract value (cumulative across term)", min_value=0.0, step=1000.0, format="%.0f")
        if amount and amount >= 0:
            result_roles = purchase_contract_rules(amount, in_course)
            extra_notes.append("Group Legal review is always required for contracts.")
            if not in_course and amount >= 1_000_000:
                extra_notes.append("Outside normal course ≥ €1,000k requires Board approval.")

    elif sub == "(non) PO-purchases without a contract":
        amount = st.number_input("Amount", min_value=0.0, step=500.0, format="%.0f")
        if amount and amount >= 0:
            result_roles = purchase_nonpo_rules(amount)

    else:  # Capital / Capex
        within = st.selectbox("Within annual budget?", ["Yes", "No"]) == "Yes"
        scope = st.selectbox("Scope (if outside budget)", ["Individual company", "Group"]) if not within else "Individual company"
        amount = st.number_input("Capex amount", min_value=0.0, step=1000.0, format="%.0f")
        if amount and amount >= 0:
            result_roles = capex_rules(amount, within, scope)
            extra_notes.append("Board may review high-value Capex via the Capex committee.")

elif area == "Sales":
    sub = st.selectbox(
        "Type",
        ["Quotes & Customer Contracts", "Commercial Credit Limits / Blocks / Credit notes"],
    )
    amount = st.number_input("Amount", min_value=0.0, step=500.0, format="%.0f")
    if sub.startswith("Quotes"):
        if amount and amount >= 0:
            result_roles = sales_quotes_rules(amount)
    else:
        if amount and amount >= 0:
            result_roles = sales_credit_rules(amount)

elif area == "Other":
    sub = st.selectbox(
        "Type",
        ["Stock corrections / counting differences / stock disposals", "Manual journal entry posting review"],
    )
    if sub.startswith("Stock"):
        amount = st.number_input("Absolute value of stock adjustment", min_value=0.0, step=100.0, format="%.0f")
        if amount and amount >= 0:
            result_roles = other_stock_rules(amount)
    else:
        impact = st.number_input("EBITDA impact of the journal (absolute value)", min_value=0.0, step=100.0, format="%.0f")
        if impact and impact >= 0:
            result_roles = other_manual_journal_rules(impact)

else:  # HR
    is_board = st.checkbox("Is the person a Board member?")
    salary = st.number_input("Annual salary (EUR)", min_value=0.0, step=1000.0, format="%.0f")
    bonus = st.number_input("Annual bonus (EUR)", min_value=0.0, step=1000.0, format="%.0f")
    # Only evaluate once user typed something meaningful
    result_roles = hr_employment_rules(salary, bonus, is_board)

st.divider()

# -----------------------------
# Output results
# -----------------------------
st.subheader("2) Approver(s)")

if not result_roles:
    st.info("Provide the required inputs above to see approvers.")
else:
    # Deduplicate but keep order
    seen = set()
    ordered_roles = []
    for r in result_roles:
        if r not in seen:
            ordered_roles.append(r)
            seen.add(r)

    for idx, role in enumerate(ordered_roles, start=1):
        person = ROLE_PEOPLE.get(role, "")
        emails = to_emails(person)
        email_txt = ", ".join(emails) if emails else "—"
        st.markdown(
            f"<div class='note'><span class='role'>{idx}. {role}</span>"
            f"<span class='pill'>lowest level first</span><br>"
            f"Current person: {person or '—'}<br>"
            f"Email: {email_txt}</div>",
            unsafe_allow_html=True,
        )

    if extra_notes:
        st.markdown("**Notes:**")
        for n in extra_notes:
            st.markdown(f"- {n}")

st.divider()

st.markdown(
    "<div class='smallgray'>Clarifications, guidelines & definitions are embedded in this wizard. "
    "Values/ranges and role-to-person mappings can be edited at the top of the file.</div>",
    unsafe_allow_html=True,
)
