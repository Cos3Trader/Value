import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go

st.set_page_config(page_title="Sommaire de la Valeur", layout="wide")
st.title("📊 Sommaire de la Valeur - V2.3 (Style Recognia)")

# ====================== FONCTIONS HELPER (en haut !) ======================
def clean_financial_df(df):
    if df is None or df.empty:
        return pd.DataFrame()
    valid_cols = [col for col in df.columns 
                  if hasattr(col, 'year') and col.year >= 2010]
    if not valid_cols:
        return df
    return df[valid_cols].sort_index(axis=1, ascending=True)

def get_net_income(income_df):
    keys = ['Net Income Common Stockholders', 'Net Income', 
            'Net Income From Continuing Operations', 
            'Net Income Applicable To Common Shares']
    for key in keys:
        if key in income_df.index:
            return income_df.loc[key]
    return pd.Series([0] * len(income_df.columns), index=income_df.columns)

# ====================== SIDEBAR ======================
ticker_input = st.sidebar.text_input("Symbole (ex: NVMI, TSLA, ABX.TO, GURU.V)", value="NVMI")
period_options = st.sidebar.selectbox("Historique", ["10y", "5y", "max"], index=0)

if st.sidebar.button("🚀 Analyser"):
    ticker = yf.Ticker(ticker_input.upper())
else:
    ticker = yf.Ticker("NVMI")

info = ticker.info
income = ticker.income_stmt
balance = ticker.balance_sheet
cashflow = ticker.cashflow
history = ticker.history(period=period_options)

income_clean = clean_financial_df(income)
balance_clean = clean_financial_df(balance)
cashflow_clean = clean_financial_df(cashflow)

st.subheader(f"{info.get('longName', ticker_input)} ({ticker_input})")
st.caption(info.get('longBusinessSummary', '')[:700] + "...")

# ====================== RÉSUMÉ HAUT ======================
col1, col2, col3, col4 = st.columns(4)
with col1:
    rev = info.get('totalRevenue', 0)
    if rev >= 1e9:
        st.metric("Revenus", f"{rev/1e9:,.1f} B USD")
    else:
        st.metric("Revenus", f"{rev/1e6:,.0f} M USD")
with col2:
    st.metric("Croissance estimée BPA", f"{info.get('earningsGrowth', 0)*100:.1f} %")
with col3:
    st.metric("Ratio P/B", f"{info.get('priceToBook', 'N/A'):.2f}")
with col4:
    st.metric("Année fiscale", str(info.get('fiscalYearEnds', 'N/A')))

# ====================== TABS ======================
tab_rev, tab_val, tab_cash, tab_ratios, tab_fcf = st.tabs([
    "📈 Historique Revenus & Bénéfices", 
    "📊 Graphique Valeur + Juste Valeur", 
    "💰 Disponibilités", 
    "Ratios & PEG", 
    "💰 Cash Flow & DCF"
])

with tab_rev:
    st.subheader("Historique des revenus et bénéfices")
    if not income_clean.empty:
        rev = income_clean.loc['Total Revenue'] / 1e6
        net = get_net_income(income_clean)
        shares = info.get('sharesOutstanding', 1)
        eps = net / shares

        fig = go.Figure()
        fig.add_trace(go.Scatter(x=rev.index, y=rev, name="Revenus (M USD)", line=dict(color="blue")))
        fig.add_trace(go.Scatter(x=eps.index, y=eps, name="BPA", line=dict(color="green"), yaxis="y2"))
        fig.update_layout(yaxis2=dict(overlaying="y", side="right"))
        st.plotly_chart(fig, use_container_width=True)

with tab_val:
    st.subheader("Graphique Valeur + Juste Valeur")
    if not history.empty:
        ma50 = history['Close'].rolling(50).mean()
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=history.index, y=history['Close'], name="Prix actuel"))
        fig.add_trace(go.Scatter(x=history.index, y=ma50, name="MA 50 jours"))
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("Juste Valeur selon croissance EPS")
    growth_analyst = info.get('earningsGrowth', 0.15) * 100
    growth_slider = st.slider("Croissance EPS prévue (%)", 0, 40, int(growth_analyst))
    current_price = info.get('currentPrice', 100)
    juste_valeur = current_price * (1 + growth_slider/100)**5
    st.metric("Juste Valeur estimée (5 ans)", f"${juste_valeur:,.2f}", 
              f"{(juste_valeur/current_price-1)*100:+.1f} %")

with tab_cash:
    st.subheader("Disponibilités et comptes assimilés")
    if not balance_clean.empty and 'Cash And Cash Equivalents' in balance_clean.index:
        cash = balance_clean.loc['Cash And Cash Equivalents'] / 1e6
        st.bar_chart(cash)

with tab_ratios:
    st.subheader("Ratios & PEG")
    pe = info.get('trailingPE', info.get('forwardPE', 'N/A'))
    peg = info.get('pegRatio')
    if peg is None and isinstance(pe, (int, float)) and growth_analyst > 0:
        peg = pe / growth_analyst
    st.metric("PEG Ratio", f"{peg:.2f}" if isinstance(peg, (int,float)) else "N/A")
    st.caption("PEG < 1 = potentiellement sous-évalué")

with tab_fcf:
    st.subheader("Analyse Cash Flow")
    if not cashflow_clean.empty:
        st.dataframe(cashflow_clean.style.format("{:,.0f}"))

# ====================== TABLEAU ANNUEL (dernière année en haut) ======================
st.subheader("📋 Données annuelles sur la compagnie (dernière année en haut)")

if not income_clean.empty:
    income_calc = income_clean.sort_index(axis=1, ascending=True)
    rev = income_calc.loc['Total Revenue'] / 1e6
    net = get_net_income(income_calc)
    shares = info.get('sharesOutstanding', 1)
    eps = net / shares

    rev_yoy = rev.pct_change() * 100
    eps_yoy = eps.pct_change() * 100

    # Dette / Fonds propres
    de_ratio = pd.Series([None] * len(rev))
    if 'Total Debt' in balance_clean.index and 'Stockholders Equity' in balance_clean.index:
        debt = balance_clean.loc['Total Debt']
        equity = balance_clean.loc['Stockholders Equity']
        de_ratio = (debt / equity).reindex(rev.index, method='nearest')

    # Encaisse
    cash = pd.Series([None] * len(rev))
    if 'Cash And Cash Equivalents' in balance_clean.index:
        cash = balance_clean.loc['Cash And Cash Equivalents'] / 1e6

    df_annual = pd.DataFrame({
        "Année fiscale": rev.index.year,
        "Revenus (M USD)": rev.round(0),
        "Croiss. Rev. (%)": rev_yoy.round(1),
        "BPA": eps.round(2),
        "Croiss. BPA (%)": eps_yoy.round(1),
        "Dette / Fonds propres": de_ratio.round(2),
        "Encaisse (M USD)": cash.round(0),
        "Actions (M)": round(shares / 1e6, 1)
    })

    df_annual = df_annual.sort_values("Année fiscale", ascending=False)
    df_annual = df_annual.set_index("Année fiscale")
    df_annual = df_annual.fillna("-").replace([0, -0.0], "-")

    st.dataframe(df_annual.style.format("{:,.1f}"), use_container_width=True)

st.caption("✅ Dernière année en haut • Unités claires • Croissances % • Dilution visible • Données nettoyées")
