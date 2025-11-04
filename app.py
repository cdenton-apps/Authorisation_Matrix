# app.py — Solidus Approvals Finder (Recommended badge + strict alternatives + clickable emails)

import re
import streamlit as st
from PIL import Image

# -----------------------------
# Page + styling
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
# Header (logo left, title right)
# -----------------------------
left, right = st.columns([1, 3], gap="large")
with left:
    try:
        st.image("assets/solidus_logo.png", width=260)
    except Exception:
        st.write(" ")
with right:
    st.markdown(
        "<h1 style='color:#0D4B6A;margin:.2rem 0 .4rem 0'>Solidus Approvals Finder</h1>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<div class='smallgray'>Answer the minimum required questions. "
        "We’ll show the recommended approver(s) and a higher-level alternative list.</div>",
        unsafe_allow_html=True,
    )

st.divider()

# -----------------------------
# Role → person (editable)
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

def names_to_emails(name: str) -> list[str]:
    if not name or "vacant" in name.lower():
        return []
    parts = re.split(r"[\/,]| and ", name, flags=re.I)
    out = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        p = re.sub(r"\(.*?\)", "", p).strip()         # remove (notes)
        p = re.sub(r"[^A-Za-z\\-\\s]", "", p)         # letters, hyphen, space
        p = re.sub(r"\s+", " ", p).strip().lower()
        if not p:
            continue
        out.append(p.replace(" ", ".") + "@solidus.com")
    return out

def mailto_md(emails: list[str]) -> str:
    if not emails:
        return "—"
    return ", ".join([f"[{e}](mailto:{e})" for e in emails])

# -----------------------------
# Rule helpers
# -----------------------------
def purchase_contract_rules(amount: float, in_normal_course: bool):
    ladder = [
        "Location Director",
        "Group Finance Director",
        "Vice President Division",
        "Strategy & Supply chain director",
        "CEO",
        "Solidus Investment / Board",
        "Group Legal",   # legal review is always required for contracts (kept at end)
    ]
    roles = []
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
    roles.append("Group Legal")
    return roles, ladder

def purchase_nonpo_rules(amount: float):
    ladder = ["Location Director", "Vice President Division", "CFO"]
    if amount < 25_000:
        return (["Location Director"], ladder)
    elif amount < 100_000:
        return (["Vice President Division"], ladder)
    else:
        return (["CFO"], ladder)

def capex_rules(amount: float, within_budget: bool, scope: str):
    ladder = [
        "Controller / Finance manager",
        "Group Finance Director",
        "Vice President Division",
        "CEO",
        "Solidus Investment / Board",
    ]
    roles = []
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
        else:  # Group
            if amount < 750_000:
                roles.append("CEO")
            else:
                roles.append("Solidus Investment / Board")
    return roles, ladder

def sales_quotes_rules(amount: float):
    ladder = ["Location Director", "Sales Director", "Vice President Division", "CEO"]
    if amount < 25_000:
        return (["Location Director", "Sales Director"], ladder)
    elif amount < 1_000_000:
        return (["Vice President Division"], ladder)
    else:
        return (["CEO"], ladder)

def sales_credit_rules(amount: float):
    ladder = ["Sales Director", "Location Director", "Vice President Division", "CFO"]
    if amount < 10_000:
        return (["Sales Director"], ladder)
    elif amount < 25_000:
        return (["Location Director"], ladder)
    elif amount < 100_000:
        return (["Vice President Division"], ladder)
    else:
        return (["CFO"], ladder)

def other_stock_rules(amount: float):
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

def other_manual_journal_rules(impact: float):
    ladder = ["Controller / Finance manager", "Group Finance Director"]
    if abs(impact) < 100_000:
        return (["Controller / Finance manager"], ladder)
    else:
        return (["Group Finance Director"], ladder)

def hr_employment_rules(salary: float, bonus: float, is_board_member: bool):
    ladder = ["Vice President Division", "CHRO", "CFO", "CEO", "Solidus Investment / Board"]
    if is_board_member:
        return (["Solidus Investment / Board"], ladder)
    if salary >= 125_000 or bonus >= 50_000:
        return (["CEO"], ladder)
    return (["Vice President Division", "CHRO", "CFO"], ladder)

# -----------------------------
# Wizard
# -----------------------------
st.subheader("1) Choose area")
area = st.selectbox("Area", ["Purchase", "Sales", "Other", "HR"])

recommended, ladder, notes = [], [], []

if area == "Purchase":
    sub = st.selectbox("Type", ["Purchase (contract) agreements", "(non) PO-purchases without a contract", "Capital / Capex"])

    if sub == "Purchase (contract) agreements":
        in_course = st.selectbox("Within normal course of business?", ["Yes", "No"]) == "Yes"
        amount = st.number_input("Contract value (cumulative across term, €)", min_value=0.0, step=1000.0, format="%.0f")
        if amount >= 0:
            recommended, ladder = purchase_contract_rules(amount, in_course)
            if not in_course and amount >= 1_000_000:
                notes.append("Outside normal course ≥ €1,000k requires Board approval.")

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
# Output — Recommended + Strict Alternatives
# -----------------------------
st.subheader("2) Approver(s)")

if not recommended:
    st.info("Provide the required inputs above to see approvers.")
else:
    # Keep order, dedupe
    seen = set()
    rec = []
    for r in recommended:
        if r not in seen:
            rec.append(r); seen.add(r)

    # Recommended cards (with clickable emails)
    for idx, role in enumerate(rec, start=1):
        person = ROLE_PEOPLE.get(role, "")
        emails = mailto_md(names_to_emails(person))
        st.markdown(
            f"<div class='note'><span class='role'>{idx}. {role}</span>"
            f"<span class='pill'>Recommended</span><br>"
            f"Current person: {person or '—'}<br>"
            f"Email: {emails}</div>",
            unsafe_allow_html=True,
        )

    # Strict alternatives: only roles above the highest recommended in the ladder
    # find highest index among recommended present in ladder
    ladder_pos = {r:i for i,r in enumerate(ladder)}
    highest_idx = max([ladder_pos.get(r, -1) for r in rec]) if rec else -1
    alt = [r for i, r in enumerate(ladder) if i > highest_idx and r not in rec]

    if alt:
        # Markdown table so links are clickable
        md_lines = ["| Role | Current person | Email |", "|---|---|---|"]
        for r in alt:
            person = ROLE_PEOPLE.get(r, "") or "—"
            emails = mailto_md(names_to_emails(ROLE_PEOPLE.get(r, "")))
            md_lines.append(f"| {r} | {person} | {emails} |")
        st.markdown("**Alternative approvers (higher level):**")
        st.markdown("\n".join(md_lines), unsafe_allow_html=True)

    if notes:
        st.markdown("**Notes:**")
        for n in notes:
            st.markdown(f"- {n}")

st.divider()
st.markdown(
    "<div class='smallgray'>Roles, names, and thresholds are defined in this file — update easily as people change.</div>",
    unsafe_allow_html=True,
)
