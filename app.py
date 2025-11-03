# app.py — Solidus Approver Finder (progressive filters)
import re, math, unicodedata
import streamlit as st
import pandas as pd
from PIL import Image

# ── Page / branding ────────────────────────────────────────────────────────────
st.set_page_config(page_title="Approver Finder — Solidus", page_icon="assets/solidus_favicon.png", layout="wide")
st.markdown("""
<style>
#MainMenu, footer {visibility:hidden}
.block-container{padding-top:2rem}
thead tr th{background:#0D4B6A;color:#fff!important}
tbody tr td{border-top:1px solid #E5E7EB!important}
.stButton>button{background:#0D4B6A;color:#fff;border:0;border-radius:10px;padding:.5rem 1rem}
.stButton>button:hover{filter:brightness(1.05)}
.small{color:#64748B;font-size:.9rem}
.badge{display:inline-block;padding:.15rem .5rem;border-radius:.5rem;background:#EEF2FF;color:#3730A3;font-size:.8rem}
</style>""", unsafe_allow_html=True)

h1, h2 = st.columns([1,6], vertical_alignment="center")
with h1:
    try: st.image("assets/solidus_logo.png", width=72)
    except Exception: pass
with h2:
    st.markdown(
        "<h1 style='margin:0;color:#0D4B6A'>Approver Finder</h1>"
        "<div class='small'>Choose an area and category. Extra fields (course of business, budget, amount) appear only if required.</div>",
        unsafe_allow_html=True,
    )
st.divider()

# ── Matrix data (same content as before) ───────────────────────────────────────
ROWS = [
    {"Approver":"Shareholder","Purchase agreements":"N/A","Capex (SharePoint)":"Unlimited-subject to Capex committee review","Non-PO without contract":"N/A","Travel & Expenses":"N/A","Quotes & Customer Contracts":"N/A","Credit Limits / Shipment blocks / Credit notes":"N/A","Stock corrections / Counting / Disposals":"N/A","Manual Journal posting review":"N/A","Employment":"N/A"},
    {"Approver":"Board","Purchase agreements":"Outside normal course of business => €1.000k","Capex (SharePoint)":"=> €1.000k","Non-PO without contract":"N/A","Travel & Expenses":"CEO","Quotes & Customer Contracts":"N/A","Credit Limits / Shipment blocks / Credit notes":"Unlimited","Stock corrections / Counting / Disposals":"N/A","Manual Journal posting review":"N/A","Employment":"Board members"},
    {"Approver":"CEO","Purchase agreements":"Within normal course of business => €1.000k","Capex (SharePoint)":"- Within annual budget: => €100k ; - Outside annual budget: < €250k (individual) ; < €750k (group)","Non-PO without contract":"N/A","Travel & Expenses":"Direct reports","Quotes & Customer Contracts":"=> €1.000k","Credit Limits / Shipment blocks / Credit notes":"N/A","Stock corrections / Counting / Disposals":"=> €100k","Manual Journal posting review":"N/A","Employment":"signs yearly salary/ hiring costs => €125k ; signs bonus => €50k"},
    {"Approver":"CFO","Purchase agreements":"Within normal course of business => €1.000k","Capex (SharePoint)":"- Within annual budget: => €100k ; - Outside annual budget: < €250k (individual) ; < €750k (group)","Non-PO without contract":"=> €100k","Travel & Expenses":"Direct reports","Quotes & Customer Contracts":"N/A","Credit Limits / Shipment blocks / Credit notes":"=> €100k","Stock corrections / Counting / Disposals":"=> €50k < €100k","Manual Journal posting review":"N/A","Employment":"signs yearly salary/ hiring costs < €125k ; signs bonus < €50k"},
    {"Approver":"CHRO","Purchase agreements":"N/A","Capex (SharePoint)":"- Within annual budget: => €25k < €100k ; - Others follow approval scheme","Non-PO without contract":"N/A","Travel & Expenses":"Direct reports","Quotes & Customer Contracts":"N/A","Credit Limits / Shipment blocks / Credit notes":"N/A","Stock corrections / Counting / Disposals":"N/A","Manual Journal posting review":"N/A","Employment":"signs yearly salary/ hiring costs < €125k ; signs bonus < €50k"},
    {"Approver":"Group Finance Director","Purchase agreements":"< €100k","Capex (SharePoint)":"- Within annual budget: => €25k < €100k ; - Others follow approval scheme","Non-PO without contract":"N/A","Travel & Expenses":"Direct reports","Quotes & Customer Contracts":"N/A","Credit Limits / Shipment blocks / Credit notes":"N/A","Stock corrections / Counting / Disposals":"N/A","Manual Journal posting review":"=> €100k EBITDA Impact","Employment":"N/A"},
    {"Approver":"Strategy & Supply chain director","Purchase agreements":"=> €150k < €1.000k","Capex (SharePoint)":"Price / quality","Non-PO without contract":"N/A","Travel & Expenses":"Direct reports","Quotes & Customer Contracts":"N/A","Credit Limits / Shipment blocks / Credit notes":"N/A","Stock corrections / Counting / Disposals":"N/A","Manual Journal posting review":"N/A","Employment":"N/A"},
    {"Approver":"Group Legal","Purchase agreements":"Review Contract","Capex (SharePoint)":"N/A","Non-PO without contract":"N/A","Travel & Expenses":"N/A","Quotes & Customer Contracts":"N/A","Credit Limits / Shipment blocks / Credit notes":"N/A","Stock corrections / Counting / Disposals":"N/A","Manual Journal posting review":"N/A","Employment":"N/A"},
    {"Approver":"Vice President Division","Purchase agreements":"=> €100k < €150k","Capex (SharePoint)":"- Within annual budget: => €25k < €100k ; - Outside annual budget: < €25k ; - Others follow approval scheme","Non-PO without contract":"=> €25k < €100k","Travel & Expenses":"Direct reports","Quotes & Customer Contracts":"=> €25k < €1.000k","Credit Limits / Shipment blocks / Credit notes":"=> €25k < €100k","Stock corrections / Counting / Disposals":"=> €10k < €50k","Manual Journal posting review":"N/A","Employment":"signs yearly salary/ hiring costs < €125k ; signs bonus < €50k"},
    {"Approver":"Location Manager","Purchase agreements":"< €100k","Capex (SharePoint)":"- Within annual budget: => €25k < €100k ; - Others follow approval scheme","Non-PO without contract":"< €25k","Travel & Expenses":"Direct reports","Quotes & Customer Contracts":"< €25k","Credit Limits / Shipment blocks / Credit notes":"=> €10k < €25k","Stock corrections / Counting / Disposals":"=> €2.5k < €10k","Manual Journal posting review":"N/A","Employment":"N/A"},
    {"Approver":"Sales Director","Purchase agreements":"N/A","Capex (SharePoint)":"N/A","Non-PO without contract":"N/A","Travel & Expenses":"Direct reports","Quotes & Customer Contracts":"< €25k","Credit Limits / Shipment blocks / Credit notes":"< €10k","Stock corrections / Counting / Disposals":"N/A","Manual Journal posting review":"N/A","Employment":"N/A"},
    {"Approver":"Controller / Finance manager","Purchase agreements":"N/A","Capex (SharePoint)":"- Within annual budget: < €25k","Non-PO without contract":"N/A","Travel & Expenses":"Direct reports","Quotes & Customer Contracts":"N/A","Credit Limits / Shipment blocks / Credit notes":"N/A","Stock corrections / Counting / Disposals":"=> €2.5k < €10k","Manual Journal posting review":"< €100k EBITDA Impact","Employment":"N/A"},
]
GROUPS = {
    "Purchase": ["Purchase agreements","Capex (SharePoint)","Non-PO without contract","Travel & Expenses"],
    "Sales": ["Quotes & Customer Contracts","Credit Limits / Shipment blocks / Credit notes"],
    "Other": ["Stock corrections / Counting / Disposals","Manual Journal posting review"],
    "HR": ["Employment"],
}

# ── Role → people (from your list) + emails ───────────────────────────────────
DEFAULT_PEOPLE = {
    "Shareholder":"",
    "Board":"Solidus Investment / Board",
    "CEO":"Niels Flierman",
    "CFO":"David Kubala",
    "CHRO":"Erik van Mierlo",
    "Strategy & Supply chain director":"Robert Egging/Ignacio Aguado",
    "Group Finance Director":"Hielke Bremer",
    "Group Legal":"David Kubala",
    "Vice President Division":"Jan-Willem Kleppers",
    "Location Manager":"MD (Vacant)",
    "Sales Director":"Paul Garstang",
    "Controller / Finance manager":"Tony Noble",
}
def strip_accents(s:str)->str:
    return ''.join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))
def name_to_email(name:str)->str|None:
    n=strip_accents(name.strip())
    if not n or "vacant" in n.lower(): return None
    n=n.replace("'", "")
    parts=[p for p in re.split(r"\s+", n) if p]
    if len(parts)<2: return None
    first=re.sub(r"[^a-z0-9\-]","", parts[0].lower())
    last=re.sub(r"[^a-z0-9\-]","", parts[-1].lower())
    return f"{first}.{last}@solidus.com" if first and last else None
def names_to_emails(field:str)->list[str]:
    if not field: return []
    out=[]
    for chunk in [c.strip() for c in re.split(r"[/,&]", field) if c.strip()]:
        e=name_to_email(chunk)
        if e: out.append(e)
    return out
st.sidebar.markdown("### Role → Person (editable)")
PEOPLE={}
for role, default in DEFAULT_PEOPLE.items():
    PEOPLE[role]=st.sidebar.text_input(role, value=default, placeholder="Name(s)")
st.sidebar.caption("Use '/' for multiple names. Emails generated as firstname.lastname@solidus.com.")

# ── Helpers: parse rules into facets (CoB, Budget, Ranges) ────────────────────
DF = pd.DataFrame(ROWS)

def euro_to_number(s:str)->float|None:
    s=s.strip().replace("€","").replace(" ","")
    if not s: return None
    mult=1.0
    if s.lower().endswith("k"): mult=1000.0; s=s[:-1]
    s=s.replace(".", "").replace(",", ".")
    try: return float(s)*mult
    except: return None

R_PAT = [
    re.compile(r"[>]=?\s*€?([\d\.,kK]+)\s*<\s*€?([\d\.,kK]+)"), # => x < y
    re.compile(r"<\s*€?([\d\.,kK]+)"),                         # < y
    re.compile(r"[>]=?\s*€?([\d\.,kK]+)"),                     # => y (we treat as threshold)
]

def extract_ranges(text:str)->list[tuple[float|None,float|None]]:
    if not text or text.upper()=="N/A": return []
    text=text.replace("=>","≥")  # normalize sign for readability (optional)
    out=[]
    for part in re.split(r"[;\n•]+", text):
        p=part.strip()
        if not p: continue
        if "Unlimited" in p: out.append((None,None)); continue
        m=R_PAT[0].search(p)
        if m:
            lo=euro_to_number(m.group(1)); hi=euro_to_number(m.group(2)); out.append((lo,hi)); continue
        m=R_PAT[1].search(p)
        if m:
            hi=euro_to_number(m.group(1)); out.append((None,hi)); continue
        m=R_PAT[2].search(p)
        if m:
            # threshold only; keep as (None, value) meaning "≤ value" (policy texts typically mean up to)
            hi=euro_to_number(m.group(1)); out.append((None,hi)); continue
    return out

def tokenize_facets(text:str)->dict:
    t=(text or "").lower()
    return {
        "cob": "Within normal" if "within normal course of business" in t
               else "Outside normal" if "outside normal course of business" in t
               else None,
        "budget": "Within annual budget" if "within annual budget" in t
                  else "Outside annual budget" if "outside annual budget" in t
                  else "Price / quality" if "price / quality" in t
                  else None,
        "ranges": extract_ranges(text or ""),
        "raw": text or "",
    }

def amount_matches(ranges:list[tuple[float|None,float|None]], amount:float|None)->bool:
    if amount is None:
        return len(ranges)>0 or True   # if no amount given, don't block match
    if not ranges: return False
    for lo,hi in ranges:
        if lo is None and hi is None: return True
        if lo is None and hi is not None and amount <= hi+1e-6: return True
        if lo is not None and hi is not None and (lo-1e-6) <= amount <= (hi+1e-6): return True
    return False

# ── Step 1/2: Area → Category ────────────────────────────────────────────────
cA,cB = st.columns([1.2,1.8])
with cA:
    area = st.selectbox("Area", list(GROUPS.keys()), index=0)
with cB:
    categories = GROUPS[area]
    category  = st.selectbox("Category", categories, index=0)

col_rules = DF[category].tolist()

# ── Scan selected category to decide which extra inputs are needed ────────────
need_cob     = any("course of business" in str(x).lower() for x in col_rules)
need_budget  = any(("annual budget" in str(x).lower()) or ("price / quality" in str(x).lower()) for x in col_rules)
need_amount  = any(len(extract_ranges(str(x)))>0 for x in col_rules)

# Build option lists based on what actually appears
cob_opts=set()
budget_opts=set()
for txt in col_rules:
    f=tokenize_facets(str(txt))
    if f["cob"]: cob_opts.add(f["cob"])
    if f["budget"]: budget_opts.add(f["budget"])

cob_list    = ["(Any)"] + sorted(cob_opts) if cob_opts else ["(Any)"]
budget_list = ["(Any)"] + sorted(budget_opts) if budget_opts else ["(Any)"]

st.markdown("")

ux1, ux2, ux3 = st.columns(3)
with ux1:
    cob_sel = st.selectbox("Course of business", cob_list, index=0) if need_cob else "(Any)"
with ux2:
    budget_sel = st.selectbox("Budget context", budget_list, index=0) if need_budget else "(Any)"
with ux3:
    amount = None
    if need_amount:
        amount_eur = st.number_input("Amount (€)", min_value=0.0, value=0.0, step=1000.0, format="%.2f")
        amount = None if amount_eur==0.0 else amount_eur

st.divider()

# ── Match rows ────────────────────────────────────────────────────────────────
matches=[]
for _, row in DF.iterrows():
    cell = str(row[category] or "").strip()
    if not cell or cell.upper()=="N/A": continue
    f = tokenize_facets(cell)
    if cob_sel!="(Any)" and f["cob"]!=cob_sel: continue
    if budget_sel!="(Any)" and f["budget"]!=budget_sel: continue
    if need_amount and not amount_matches(f["ranges"], amount): continue

    role = row["Approver"]
    name_field = PEOPLE.get(role,"")
    emails = names_to_emails(name_field)
    matches.append({
        "Approving Entity": role,
        "Person(s)": name_field,
        "Email(s)": ", ".join(emails),
        "Rule Text": cell
    })

seniority = ["Shareholder","Board","CEO","CFO","CHRO","Group Finance Director",
             "Strategy & Supply chain director","Group Legal","Vice President Division",
             "Location Manager","Sales Director","Controller / Finance manager"]
order_map = {r:i for i,r in enumerate(seniority)}
matches.sort(key=lambda r: order_map.get(r["Approving Entity"], math.inf))

# ── Output ────────────────────────────────────────────────────────────────────
st.markdown(f"### Results for **{area} → {category}**")
if not matches:
    msg = "No approver found. "
    hints=[]
    if need_cob: hints.append("course of business")
    if need_budget: hints.append("budget context")
    if need_amount: hints.append("amount")
    if hints:
        msg += "Try adjusting " + ", ".join(hints) + "."
    st.info(msg)
else:
    out = pd.DataFrame(matches)
    st.markdown(f"<span class='badge'>{len(out)} match(es)</span>", unsafe_allow_html=True)
    st.dataframe(out, use_container_width=True)

    best = matches[0]
    st.markdown("#### Recommended Approver")
    email_note  = f" — {best['Email(s)']}" if best["Email(s)"] else ""
    person_note = f" ({best['Person(s)']})"  if best["Person(s)"] else ""
    st.success(f"**{best['Approving Entity']}**{person_note}{email_note}\n\nPolicy match: _{best['Rule Text']}_")

st.markdown("<hr/>", unsafe_allow_html=True)
st.markdown("<div class='small'>© Solidus — Internal tool. Policy owners: Finance & Legal.</div>", unsafe_allow_html=True)
