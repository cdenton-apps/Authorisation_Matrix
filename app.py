# --  app.py

import streamlit as st
import pandas as pd
from PIL import Image

# -- Page config & branding
st.set_page_config(page_title="Financial Approval Finder", layout="wide")

HIDE = """
<style>
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
.block-container {padding-top: 2.25rem; padding-bottom: 3rem;}  /* was 1rem */
.badge {display:inline-block;background:#10b981;color:#062E2E;padding:.15rem .5rem;border-radius:999px;font-weight:600;font-size:.8rem;vertical-align:middle;margin-left:.5rem;}
.role-card {padding:1rem;border:1px solid #eaeaea;border-radius:.75rem;margin:.25rem 0;}
.role-title{font-weight:700;}
.small {color:#6b7280;}
a.mail {text-decoration:none;}
[data-testid="stSidebar"] {min-width: 320px; max-width: 340px; overflow:auto;}
[data-testid="stSidebar"] button {width:100%;}
[data-testid="stSidebar"] [data-testid="stFileUploader"] section {width:100% !important;}
[data-testid="stSidebar"] [data-testid="stFileUploadDropzone"] {width:100% !important; padding:.75rem !important; border-radius:.5rem;}
</style>
"""

st.markdown(HIDE, unsafe_allow_html=True)

left, right = st.columns([1, 3], gap="large")
with left:
    try:
        st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)  # spacer to prevent visual clipping
        logo = Image.open("assets/solidus_logo.png")
        st.image(logo, use_column_width=True)
    except Exception:
        st.write("")

with right:
    st.markdown("<h1>Solidus Approval Finder</h1>", unsafe_allow_html=True)
    st.caption("Select the area and context to identify the correct approving entity. "
               "If multiple approvers qualify, recommend the **lowest level** first.")

st.divider()

# --   Sidebar: Role to Person

DEFAULT_PEOPLE = pd.DataFrame([
    {"Role": "Shareholder",                    "Person": "",                      "Email": ""},
    {"Role": "Solidus Investment / Board",     "Person": "Board members",         "Email": "board.members@solidus.com"},
    {"Role": "CEO",                            "Person": "Niels Flierman",        "Email": "niels.flierman@solidus.com"},
    {"Role": "CFO",                            "Person": "David Kubala",          "Email": "david.kubala@solidus.com"},
    {"Role": "CHRO",                           "Person": "Erik van Mierlo",       "Email": "erik.van.mierlo@solidus.com"},
    {"Role": "Strategy & Supply chain director","Person": "Robert Egging / Ignacio Aguado","Email": "robert.egging@solidus.com"},
    {"Role": "Group Finance Director",         "Person": "Hielke Bremer",         "Email": "hielke.bremer@solidus.com"},
    {"Role": "Group Legal",                    "Person": "David Kubala",          "Email": "david.kubala@solidus.com"},
    {"Role": "Vice President Division",        "Person": "Jan-Willem Kleppers",   "Email": "jan-willem.kleppers@solidus.com"},
    {"Role": "Location Director",              "Person": "MD (Vacant)",           "Email": ""},
    {"Role": "Sales Director",                 "Person": "Paul Garstang",         "Email": "paul.garstang@solidus.com"},
    {"Role": "Controller / Finance manager",   "Person": "Tony Noble",            "Email": "tony.noble@solidus.com"},
])

@st.cache_data
def get_people_df() -> pd.DataFrame:
    return DEFAULT_PEOPLE.copy()

people_df = get_people_df()

with st.sidebar:
    st.subheader("Approver contacts")

    # full-width export button
    st.download_button(
        "Export CSV",
        data=people_df.to_csv(index=False).encode("utf-8"),
        file_name="approver_contacts.csv",
        mime="text/csv",
        use_container_width=True
    )

    # full-width uploader
    up = st.file_uploader("Import CSV", type=["csv"])
    if up is not None:
        try:
            new_df = pd.read_csv(up).fillna("")
            assert {"Role","Person","Email"} <= set(new_df.columns)
            people_df = new_df[["Role","Person","Email"]].copy()
            st.success("Contacts updated for this session.")
        except Exception as e:
            st.error(f"Could not import: {e}")

def person_of(role: str) -> tuple[str, str]:
    row = people_df.loc[people_df["Role"].str.lower()==role.lower()]
    if row.empty:
        return "", ""
    return row.iloc[0]["Person"], row.iloc[0]["Email"]

def mailto(email: str, label: str|None=None) -> str:
    if not email:
        return "<span class='small'>No email on file</span>"
    return f"<a class='mail' href='mailto:{email}'>{label or email}</a>"

# ---   Input step (default empty)
st.markdown("### 1) Choose area")

area = st.selectbox(
    "Area",
    options=["", "Purchase", "Sales", "Other", "HR"],
    index=0
)

if area == "":
    st.stop()

TYPE_OPTIONS = {
    "Purchase": [
        "Purchase (contract) agreements",
        "Capital / Capex",
        "(non) PO-purchases without a contract",
        "Travel approval & Expense Reports",
    ],
    "Sales": [
        "Quotes & Customer Contracts",
        "Commercial Credit Limits & Release of shipment blocks & Credit notes",
    ],
    "Other": [
        "Stock corrections & Counting differences & Stock disposals",
        "Manual Journal entry posting review",
    ],
    "HR": [
        "Employment and Benefits Matters",
    ],
}

dtype = st.selectbox("Type", options=[""] + TYPE_OPTIONS.get(area, []), index=0)
if dtype == "":
    st.stop()

# Contextual inputs (show only when needed)
within_ncb = None
capex_amount = None
purchase_amount = None
sales_amount = None
other_amount = None
ebitda_impact = None
salary_cost = None
bonus_amt = None

if area == "Purchase" and dtype == "Capital / Capex":
    within_ncb = st.selectbox("Within annual budget?", ["", "Yes", "No"], index=0)
    capex_amount = st.number_input("Capex amount (€)", min_value=0.0, step=1.0)
    if within_ncb == "":
        st.stop()

if area == "Purchase" and dtype == "Purchase (contract) agreements":
    within_ncb = st.selectbox("Within normal course of business?", ["", "Yes", "No"], index=0)
    purchase_amount = st.number_input("Cumulative contract value (€)", min_value=0.0, step=1.0)
    if within_ncb == "":
        st.stop()

if area == "Sales":
    sales_amount = st.number_input("Amount (€)", min_value=0.0, step=1.0)

if area == "Other":
    if "Manual Journal" in dtype:
        ebitda_impact = st.number_input("EBITDA impact (€)", min_value=0.0, step=1.0)
    else:
        other_amount = st.number_input("Amount (€)", min_value=0.0, step=1.0)

if area == "HR":
    cols = st.columns(2)
    with cols[0]:
        salary_cost = st.number_input("Annual salary / hiring cost (€)", min_value=0.0, step=1.0)
    with cols[1]:
        bonus_amt = st.number_input("Bonus / discretionary payment (€)", min_value=0.0, step=1.0)

# ---   Rules

def capex_board_override(amount_eur: float) -> bool:
    try:
        return amount_eur is not None and float(amount_eur) >= 1_000_000
    except Exception:
        return False

def get_capex_approver(amount: float, within_budget: str):
    if capex_board_override(amount):
        return ["Solidus Investment / Board"], []
    roles_order_low_to_high = [
        "Controller / Finance manager",
        "Location Director",
        "Group Finance Director",
        "Vice President Division",
        "CFO",
        "CEO",
        "Solidus Investment / Board",
    ]
    if within_budget == "Yes":
        if amount < 25_000:
            rec = "Controller / Finance manager"
        elif amount < 100_000:
            rec = "Group Finance Director"
        elif amount >= 100_000:
            rec = "CFO"
    else:
        if amount < 100_000:
            rec = "CFO"
        elif amount < 1_000_000:
            rec = "CEO"
        else:
            rec = "Solidus Investment / Board"
    idx = roles_order_low_to_high.index(rec)
    alts = roles_order_low_to_high[idx+1:]
    return [rec], alts

def get_purchase_contract_approver(amount: float, within_course: str):
    # Ranges from matrix + example (lowest level first)
    if within_course == "Yes":
        if amount < 100_000:
            rec = "Location Director"           # < €100k
            alts = ["Group Finance Director", "Vice President Division", "Strategy & Supply chain director", "CFO", "CEO"]
        elif amount < 150_000:
            rec = "Vice President Division"     # => €100k < €150k
            alts = ["Strategy & Supply chain director", "CFO", "CEO"]
        elif amount < 1_000_000:
            rec = "Strategy & Supply chain director"  # => €150k < €1,000k
            alts = ["CFO", "CEO"]
        else:
            rec = "CEO"                         # within course => €1,000k
            alts = ["Solidus Investment / Board"]
    else:
        # Outside normal course: escalate faster; Board for >= €1,000k
        if amount >= 1_000_000:
            rec = "Solidus Investment / Board"
            alts = []
        else:
            rec = "CEO"
            alts = ["Solidus Investment / Board"]
    return [rec], alts

def get_sales_approver(dtype: str, amount: float):
    if dtype == "Quotes & Customer Contracts":
        if amount < 25_000:
            return ["Sales Director"], ["Location Director", "Vice President Division", "CEO"]
        elif amount < 1_000_000:
            return ["Vice President Division"], ["CEO"]
        else:
            return ["CEO"], ["Solidus Investment / Board"]
    # Credit limits / notes
    if amount < 10_000:
        return ["Sales Director"], ["Location Director", "Vice President Division", "CFO", "CEO"]
    elif amount < 25_000:
        return ["Location Director"], ["Vice President Division", "CFO", "CEO"]
    elif amount < 100_000:
        return ["Vice President Division"], ["CFO", "CEO"]
    else:
        return ["CFO"], ["CEO"]

def get_other_approver(dtype: str, amount: float|None, ebitda: float|None):
    if "Manual Journal" in dtype:
        if ebitda is not None and ebitda >= 100_000:
            return ["Group Finance Director"], ["CFO", "CEO"]
        else:
            return ["Controller / Finance manager"], ["Group Finance Director", "CFO"]
    # Stock corrections / disposals
    if amount is None:
        return [], []
    if amount < 2_500:
        # Not explicitly in matrix; treat as no special approval required -> recommend Controller as lowest control point
        return ["Controller / Finance manager"], ["Location Director", "Vice President Division", "CFO"]
    elif amount < 10_000:
        return ["Controller / Finance manager"], ["Location Director", "Vice President Division", "CFO"]
    elif amount < 50_000:
        return ["Vice President Division"], ["CFO", "CEO"]
    elif amount < 100_000:
        return ["CFO"], ["CEO"]
    else:
        return ["CEO"], ["Solidus Investment / Board"]

def get_hr_approver(salary: float, bonus: float):
    if (salary is not None and salary >= 125_000) or (bonus is not None and bonus >= 50_000):
        return ["CEO"], ["Solidus Investment / Board"]
    else:
        return ["CHRO"], ["CEO"]

# --  Compute approver(s)

recommended: list[str] = []
alternates: list[str] = []

if area == "Purchase" and dtype == "Capital / Capex":
    recommended, alternates = get_capex_approver(capex_amount, within_ncb)

elif area == "Purchase" and dtype == "Purchase (contract) agreements":
    recommended, alternates = get_purchase_contract_approver(purchase_amount, within_ncb)

elif area == "Purchase" and dtype == "(non) PO-purchases without a contract":
    # Lowest group control then escalate
    recommended, alternates = ["Group Finance Director"], ["CFO", "CEO", "Solidus Investment / Board"]

elif area == "Purchase" and dtype == "Travel approval & Expense Reports":
    recommended, alternates = ["Direct reports"], ["Location Director", "Vice President Division", "CEO"]

elif area == "Sales":
    recommended, alternates = get_sales_approver(dtype, sales_amount or 0.0)

elif area == "Other":
    recommended, alternates = get_other_approver(dtype, other_amount, ebitda_impact)

elif area == "HR":
    recommended, alternates = get_hr_approver(salary_cost or 0.0, bonus_amt or 0.0)

# --- Result

st.markdown("### 2) Approver(s)")

# Recommended blocks
if recommended:
    for i, role in enumerate(recommended, start=1):
        person, email = person_of(role)
        st.markdown(
            f"""
            <div class='role-card'>
              <div class='role-title'>{i}. {role}
                <span class='badge'>Recommended</span>
              </div>
              <div class='small'>Current person: {person or '—'}</div>
              <div class='small'>Email: {mailto(email)}</div>
            </div>
            """,
            unsafe_allow_html=True
        )
else:
    st.info("No recommendation could be determined with the current inputs.")

# Special note for Purchase (contract): always involve Group Legal
if area == "Purchase" and dtype == "Purchase (contract) agreements":
    gl_person, gl_email = person_of("Group Legal")
    st.markdown(
        f"""
        <div class='small' style='margin-top:.25rem'>
          <b>Note:</b> Always contact <b>Group Legal (Review Contract)</b>
          — {gl_person or '—'} — {mailto(gl_email)}.
        </div>
        """,
        unsafe_allow_html=True
    )

# Alternative approvers table (higher level)
if alternates:
    alt_rows = []
    for role in alternates:
        person, email = person_of(role)
        alt_rows.append({
            "Role": role,
            "Current person": person or "—",
            "Email": email,
        })
    alt_df = pd.DataFrame(alt_rows)[["Role","Current person","Email"]]
    st.markdown("#### Alternative approvers (higher level)")
    st.table(alt_df)

st.divider()

with st.expander("Clarifications, guidelines & definitions"):
    st.markdown("""
**If multiple approvers qualify, go lowest level first.**

**Purchase**  
- **Purchase (contract) agreements** — Contracts/POs/verbal commitments (incl. software). Approval based on **cumulative contract value**.  
- **(non) PO-purchases without a contract** — Use only when no contract exists.  
- **Capital/Capex** — Any spend capitalized under policy (machinery, vehicles, land, buildings).  

**Sales**  
- **Quotes & Customer Contracts** — Agreements defining commercial terms.  
- **Credit Limits / Shipment blocks / Credit notes** — Establishing/adjusting limits; significant one-offs.  

**Other**  
- **Stock corrections / counting differences / disposals** — Use thresholds per matrix.  
- **Manual journal posting review** — Threshold based on **EBITDA impact**.

**HR**  
- **Employment & Benefits** — Hiring, dismissal, transfers, comp/benefits changes, discretionary payments.
""")
