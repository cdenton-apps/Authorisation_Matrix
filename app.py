# app.py — Solidus Approval Finder
# Only new logic added: Capex >= €1,000,000 => Board override (see get_capex_approver)

import streamlit as st
import pandas as pd
from PIL import Image
from io import StringIO

# ─────────────────────────────────────────────────────────────
# Page config & branding
# ─────────────────────────────────────────────────────────────
st.set_page_config(page_title="Solidus Approval Finder", layout="wide")

HIDE = """
<style>
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
.block-container {padding-top: 1rem; padding-bottom: 3rem;}
.badge {
  display:inline-block;background:#10b981;color:#062E2E;padding:.15rem .5rem;
  border-radius:999px;font-weight:600;font-size:.8rem;vertical-align:middle;margin-left:.5rem;
}
.role-card {padding:1rem;border:1px solid #eaeaea;border-radius:.75rem;margin:.25rem 0;}
.role-title{font-weight:700;}
.small {color:#6b7280;}
a.mail {text-decoration:none;}
</style>
"""
st.markdown(HIDE, unsafe_allow_html=True)

left, right = st.columns([1, 3], gap="large")
with left:
    try:
        logo = Image.open("assets/solidus_logo.png")
        st.image(logo, use_column_width=True)  # wide logo
    except Exception:
        st.write("")

with right:
    st.markdown("<h1>Solidus Approval Finder</h1>", unsafe_allow_html=True)
    st.caption("Select the area and context to identify the correct approving entity. "
               "If multiple approvers qualify, recommend the **lowest level** first.")

st.divider()

# ─────────────────────────────────────────────────────────────
# Role → Person mapping (editable via CSV import)
# ─────────────────────────────────────────────────────────────
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

with st.expander("Import/Export approver contacts (optional)"):
    c1, c2 = st.columns([1,1])
    with c1:
        st.download_button(
            "⬇️ Export current contacts CSV",
            data=people_df.to_csv(index=False).encode("utf-8"),
            file_name="approver_contacts.csv",
            mime="text/csv"
        )
    with c2:
        up = st.file_uploader("⬆️ Import contacts CSV (Role, Person, Email)", type=["csv"], key="up_people")
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

# ─────────────────────────────────────────────────────────────
# Input step (kept same layout/behavior)
# ─────────────────────────────────────────────────────────────
st.markdown("### 1) Choose area")

area = st.selectbox(
    "Area",
    options=["", "Purchase", "Sales", "Other", "HR"],
    index=0
)

# default start from nothing entered
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

# Contextual inputs (unchanged, but only shown when needed)
within_ncb = None
capex_amount = None
purchase_amount = None

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

# ─────────────────────────────────────────────────────────────
# Rules (same as before, plus Board override in Capex)
# ─────────────────────────────────────────────────────────────

def capex_board_override(amount_eur: float) -> bool:
    """New: route to Board when Capex >= €1,000,000."""
    try:
        return amount_eur is not None and float(amount_eur) >= 1_000_000
    except Exception:
        return False

def get_capex_approver(amount: float, within_budget: str):
    """
    Purchase → Capital/Capex.
    Lowest qualified approver recommended, higher levels shown as alternates.
    """
    # NEW EARLY EXIT (only addition)
    if capex_board_override(amount):
        return ["Solidus Investment / Board"], []

    # Existing thresholds (kept as in your last build)
    # Within budget: CEO up to => €100k; CFO => €100k; GFD < €100k; VPD => €25k < €100k; Location < €100k; Controller < €25k
    # Outside budget caps & escalations are simplified to CEO/CFO as per spreadsheet summary.
    roles_order_low_to_high = [
        "Controller / Finance manager",
        "Location Director",
        "Group Finance Director",
        "Vice President Division",
        "CFO",
        "CEO",
        "Solidus Investment / Board",
    ]

    rec = None
    if within_budget == "Yes":
        if amount < 25_000:
            rec = "Controller / Finance manager"
        elif amount < 100_000:
            # could be Location Director or GFD or VPD depending on local scheme—recommend GFD as lowest group role
            rec = "Group Finance Director"
        elif amount >= 100_000:
            rec = "CFO"
    else:
        # outside budget: escalate quickly
        if amount < 100_000:
            rec = "CFO"
        elif amount < 1_000_000:
            rec = "CEO"
        else:
            rec = "Solidus Investment / Board"  # this will be hit if someone bypasses the override

    # Build alternates as higher levels than rec
    idx = roles_order_low_to_high.index(rec)
    alts = roles_order_low_to_high[idx+1:]
    return [rec], alts

def get_purchase_contract_approver(amount: float, within_course: str):
    """
    Purchase (contract) agreements.
    Uses ‘within normal course of business’ + cumulative value.
    """
    roles_order = [
        "Controller / Finance manager",
        "Location Director",
        "Group Finance Director",
        "Vice President Division",
        "Strategy & Supply chain director",
        "CFO",
        "CEO",
        "Solidus Investment / Board",
    ]

    if within_course == "Yes":
        # Within normal course: up to €1,000k CEO; larger -> Board
        if amount <= 1_000_000:
            rec = "CEO"
        else:
            rec = "Solidus Investment / Board"
    else:
        # Outside normal course: Board from €1,000k; between recommend CEO
        if amount >= 1_000_000:
            rec = "Solidus Investment / Board"
        else:
            rec = "CEO"

    idx = roles_order.index(rec)
    alts = roles_order[idx+1:]
    return [rec], alts

def get_sales_approver(dtype: str):
    if dtype == "Quotes & Customer Contracts":
        return ["CEO"], ["Solidus Investment / Board"]
    if dtype == "Commercial Credit Limits & Release of shipment blocks & Credit notes":
        return ["CFO"], ["CEO", "Solidus Investment / Board"]
    return ["Group Legal"], []

def get_other_approver(dtype: str):
    if "Stock corrections" in dtype:
        return ["CFO"], ["CEO", "Solidus Investment / Board"]
    if "Manual Journal" in dtype:
        return ["Group Finance Director"], ["CFO", "CEO", "Solidus Investment / Board"]
    return ["Group Legal"], []

def get_hr_approver():
    # Employment & Benefits: CEO >= €125k; CHRO < €125k (simplified)
    return ["CHRO"], ["CEO", "Solidus Investment / Board"]

# ─────────────────────────────────────────────────────────────
# Compute approver(s)
# ─────────────────────────────────────────────────────────────
recommended: list[str] = []
alternates: list[str] = []

if area == "Purchase" and dtype == "Capital / Capex":
    recommended, alternates = get_capex_approver(capex_amount, within_ncb)

elif area == "Purchase" and dtype == "Purchase (contract) agreements":
    recommended, alternates = get_purchase_contract_approver(purchase_amount, within_ncb)

elif area == "Purchase" and dtype == "(non) PO-purchases without a contract":
    # If a contract exists, this shouldn’t be used; otherwise use budget-like guardrails
    recommended, alternates = ["Group Finance Director"], ["CFO", "CEO", "Solidus Investment / Board"]

elif area == "Purchase" and dtype == "Travel approval & Expense Reports":
    recommended, alternates = ["Direct reports"], ["Location Director", "Vice President Division", "CEO"]

elif area == "Sales":
    recommended, alternates = get_sales_approver(dtype)

elif area == "Other":
    recommended, alternates = get_other_approver(dtype)

elif area == "HR":
    recommended, alternates = get_hr_approver()

# ─────────────────────────────────────────────────────────────
# Render result (same arrangement as before)
# ─────────────────────────────────────────────────────────────
st.markdown("### 2) Approver(s)")

def mailto(email: str, label: str|None=None) -> str:
    if not email:
        return "<span class='small'>No email on file</span>"
    return f"<a class='mail' href='mailto:{email}'>{label or email}</a>"

# Recommended block(s)
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

# Alternative approvers table (higher level)
if alternates:
    alt_rows = []
    for role in alternates:
        person, email = person_of(role)
        alt_rows.append({
            "Role": role,
            "Current person": person or "—",
            "Email": email,
            "mailto": mailto(email, email) if email else "—"
        })
    alt_df = pd.DataFrame(alt_rows)[["Role","Current person","Email"]]
    # Show clickable mailto using column config in dataframe? Streamlit tables don’t render HTML,
    # so we show Email as text and provide a second column with a link below.
    st.markdown("#### Alternative approvers (higher level)")
    st.table(alt_df)

st.divider()

with st.expander("Clarifications, guidelines & definitions"):
    st.markdown("""
**If multiple approvers qualify, go lowest level first.**

**Purchase**  
- **Purchase (contract) agreements** — Applies to contracts/POs/verbal commitments (incl. software). Approval based on **cumulative contract value**.  
- **(non) PO-purchases without a contract** — Use only when no contract exists.  
- **Capital/Capex** — Any spend capitalized under policy (machinery, vehicles, land, buildings).  

**Sales**  
- **Quotes & Customer Contracts** — Agreements defining commercial terms; post-signature changes must be approved by the original signatory.  
- **Credit Limits / Shipment blocks** — Establishing/adjusting limits; significant one-offs.  

**HR**  
- **Employment & Benefits** — Hiring, dismissal, transfers, comp/benefits changes, discretionary payments.
""")
