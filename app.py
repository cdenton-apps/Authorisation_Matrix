# -- app.py

import os, re
import streamlit as st
from PIL import Image
import pandas as pd

# -- page style
st.set_page_config(page_title="Solidus Approvals Finder", layout="wide")
st.markdown(
    """
    <style>
      #MainMenu{visibility:hidden;} footer{visibility:hidden;}
      .smallgray{color:#6b7280;font-size:0.9rem}
      .note{background:#f7f7fb;border:1px solid #e5e7eb;border-radius:10px;padding:12px;margin-bottom:10px}
      .role{font-weight:600}
      .pill{display:inline-block;padding:.15rem .55rem;background:#ecfdf5;border:1px solid #10b98133;
            border-radius:9999px;margin-left:.45rem;font-size:.8rem;color:#047857}
    </style>
    """,
    unsafe_allow_html=True,
)

# --  header
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
        "<div class='smallgray'>Answer only what’s needed. We’ll show the recommended approver(s) "
        "and a higher-level alternative list. You can update people via CSV.</div>",
        unsafe_allow_html=True,
    )

st.divider()

# -- default roles
DEFAULT_ROLE_PEOPLE = {
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

# --   csv import for amending roles
st.sidebar.subheader("Approver people (CSV)")
st.sidebar.caption("Columns required: **Role, Person**")

uploaded = st.sidebar.file_uploader("Import approvers.csv", type=["csv"])
if uploaded is not None:
    try:
        df_csv = pd.read_csv(uploaded)
        role_col = [c for c in df_csv.columns if c.strip().lower() == "role"]
        person_col = [c for c in df_csv.columns if c.strip().lower() == "person"]
        if role_col and person_col:
            ROLE_PEOPLE = DEFAULT_ROLE_PEOPLE.copy()
            for _, r in df_csv.iterrows():
                role = str(r[role_col[0]]).strip()
                person = "" if pd.isna(r[person_col[0]]) else str(r[person_col[0]]).strip()
                if role:
                    ROLE_PEOPLE[role] = person
            st.sidebar.success("CSV loaded.")
        else:
            st.sidebar.error("CSV must contain Role and Person columns.")
            ROLE_PEOPLE = DEFAULT_ROLE_PEOPLE.copy()
    except Exception as e:
        st.sidebar.error(f"Failed to read CSV: {e}")
        ROLE_PEOPLE = DEFAULT_ROLE_PEOPLE.copy()
else:
    ROLE_PEOPLE = DEFAULT_ROLE_PEOPLE.copy()

# Export current mapping
export_df = pd.DataFrame(
    [{"Role": k, "Person": v} for k, v in ROLE_PEOPLE.items()]
)
st.sidebar.download_button(
    "Download current approvers.csv",
    data=export_df.to_csv(index=False),
    file_name="approvers.csv",
    mime="text/csv",
)

# --  email html (mailto) anchors
def _clean_token(token: str) -> str:
    token = token.lower()
    token = re.sub(r"[^\w\- ]", "", token, flags=re.I)
    token = token.replace("_", "")
    token = re.sub(r"\s+", " ", token).strip()
    return token

def _first_last(name: str):
    if not name:
        return None
    name = re.sub(r"\(.*?\)", "", name)  # remove parentheses notes
    tokens = [_clean_token(t) for t in name.split() if t.strip()]
    if len(tokens) < 2:
        return None
    return tokens[0], tokens[-1]

def names_to_emails(person_field: str) -> list[str]:
    if not person_field or "vacant" in person_field.lower():
        return []
    parts = re.split(r"[\/,]| and ", person_field, flags=re.I)
    emails = []
    for p in parts:
        p = p.strip()
        fl = _first_last(p)
        if not fl:
            continue
        first, last = fl
        first = re.sub(r"[^a-z\-]", "", first)
        last  = re.sub(r"[^a-z\-]", "", last)
        if first and last:
            emails.append(f"{first}.{last}@solidus.com")
    return emails

def mailto_html(emails: list[str]) -> str:
    if not emails:
        return "—"
    return ", ".join([f"<a href='mailto:{e}'>{e}</a>" for e in emails])

# --- rules
def purchase_contract_rules(amount: float, in_normal_course: bool):
    ladder = [
        "Location Director",
        "Group Finance Director",
        "Vice President Division",
        "Strategy & Supply chain director",
        "CEO",
        "Solidus Investment / Board",
        "Group Legal",
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
        else:
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

# --- wizard/entry
st.subheader("1) Choose area")
area = st.selectbox("Area", ["— Select —", "Purchase", "Sales", "Other", "HR"], index=0)
recommended, ladder, notes = [], [], []

if area == "Purchase":
    sub = st.selectbox(
        "Type",
        ["— Select —", "Purchase (contract) agreements", "(non) PO-purchases without a contract", "Capital / Capex"],
        index=0
    )
    if sub == "Purchase (contract) agreements":
        in_course_str = st.selectbox("Within normal course of business?", ["— Select —", "Yes", "No"], index=0)
        if in_course_str != "— Select —":
            in_course = (in_course_str == "Yes")
            amount = st.number_input("Contract value (cumulative across term, €)", min_value=0.0, step=1000.0, format="%.0f")
            recommended, ladder = purchase_contract_rules(amount, in_course)
            if not in_course and amount >= 1_000_000:
                notes.append("Outside normal course ≥ €1,000k requires Board approval.")
    elif sub == "(non) PO-purchases without a contract":
        amount = st.number_input("Amount (€)", min_value=0.0, step=500.0, format="%.0f")
        recommended, ladder = purchase_nonpo_rules(amount)
    elif sub == "Capital / Capex":
        within_str = st.selectbox("Within annual budget?", ["— Select —", "Yes", "No"], index=0)
        if within_str != "— Select —":
            within = (within_str == "Yes")
            scope = "Individual company"
            if not within:
                scope = st.selectbox("Scope (if outside budget)", ["Individual company", "Group"])
            amount = st.number_input("Capex amount (€)", min_value=0.0, step=1000.0, format="%.0f")
            recommended, ladder = capex_rules(amount, within, scope)

elif area == "Sales":
    sub = st.selectbox("Type", ["— Select —", "Quotes & Customer Contracts", "Commercial Credit Limits / Blocks / Credit notes"], index=0)
    if sub != "— Select —":
        amount = st.number_input("Amount (€)", min_value=0.0, step=500.0, format="%.0f")
        if sub.startswith("Quotes"):
            recommended, ladder = sales_quotes_rules(amount)
        else:
            recommended, ladder = sales_credit_rules(amount)

elif area == "Other":
    sub = st.selectbox("Type", ["— Select —", "Stock corrections / counting differences / stock disposals", "Manual journal entry posting review"], index=0)
    if sub.startswith("Stock"):
        amount = st.number_input("Absolute value of stock adjustment (€)", min_value=0.0, step=100.0, format="%.0f")
        recommended, ladder = other_stock_rules(amount)
    elif sub == "Manual journal entry posting review":
        impact = st.number_input("EBITDA impact of the journal (absolute value, €)", min_value=0.0, step=100.0, format="%.0f")
        recommended, ladder = other_manual_journal_rules(impact)

elif area == "HR":
    is_board_str = st.selectbox("Is the person a Board member?", ["— Select —", "No", "Yes"], index=0)
    if is_board_str != "— Select —":
        is_board = (is_board_str == "Yes")
        salary = st.number_input("Annual salary (€)", min_value=0.0, step=1000.0, format="%.0f")
        bonus  = st.number_input("Annual bonus (€)",  min_value=0.0, step=1000.0, format="%.0f")
        recommended, ladder = hr_employment_rules(salary, bonus, is_board)

st.divider()

# ---   output
st.subheader("2) Approver(s)")

if not recommended:
    st.info("Provide the required inputs above to see approvers.")
else:
    # Unique recommended roles in order
    seen, rec = set(), []
    for r in recommended:
        if r not in seen:
            rec.append(r); seen.add(r)

    for idx, role in enumerate(rec, start=1):
        person = ROLE_PEOPLE.get(role, "")
        emails = names_to_emails(person)
        st.markdown(
            f"<div class='note'><span class='role'>{idx}. {role}</span>"
            f"<span class='pill'>Recommended</span><br>"
            f"Current person: {person or '—'}<br>"
            f"Email: {mailto_html(emails)}</div>",
            unsafe_allow_html=True,
        )

    # --- Alternatives
    ladder_pos = {r:i for i,r in enumerate(ladder)}
    highest_idx = max([ladder_pos.get(r, -1) for r in rec]) if rec else -1
    alt = [r for i, r in enumerate(ladder) if i > highest_idx and r not in rec]

    if alt:
        # Markdown table (markdown links parse fine here)
        md_lines = ["| Role | Current person | Email |", "|---|---|---|"]
        for r in alt:
            person = ROLE_PEOPLE.get(r, "") or "—"
            emails = names_to_emails(ROLE_PEOPLE.get(r, ""))
            md_email = ", ".join([f"[{e}](mailto:{e})" for e in emails]) if emails else "—"
            md_lines.append(f"| {r} | {person} | {md_email} |")
        st.markdown("**Alternative approvers (higher level):**")
        st.markdown("\n".join(md_lines))

    if notes:
        st.markdown("<br>".join([f"• {n}" for n in notes]), unsafe_allow_html=True)

st.divider()
