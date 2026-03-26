import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go

st.set_page_config(page_title="Sommaire de la Valeur", layout="wide")
st.title("📊 Sommaire de la Valeur - V2 (avec Cash Flow & DCF)")

ticker_input = st.sidebar.text_input("Symbole (ex: NVMI, ABX.TO, GURU.V)", value="NVMI")
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

st.subheader(f"{info.get('longName', ticker_input)} ({ticker_input})")

# Résumé haut (comme l'image)
col1, col2, col3, col4 = st.columns(4)
with col1: st.metric("Revenus", f"{info.get('totalRevenue',0)/1e6:,.0f} M")
with col2: st.metric("Croissance estimée BPA (analystes)", f"{info.get('earningsGrowth',0)*100:.1f} %")
with col3: st.metric("Ratio P/B", f"{info.get('priceToBook', 'N/A'):.2f}")
with col4: st.metric("Année fiscale", str(info.get('fiscalYearEnds', 'N/A')))

# === Tabs ===
tab_rev, tab_val, tab_cash, tab_div, tab_ratios, tab_fcf = st.tabs([
    "Historique Revenus & Bénéfices", "Graphique Valeur + Juste Valeur", 
    "Disponibilités", "Dividends", "Ratios & PEG", "💰 Cash Flow & DCF"
])

with tab_rev:
    st.subheader("Historique des revenus et bénéfices (10 ans)")
    if not income.empty:
        rev = income.loc['Total Revenue']
        net = income.loc.get('Net Income Common Stockholders', income.loc['Net Income'])
        eps = net / info.get('sharesOutstanding', 1)
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=rev.index, y=rev/1e6, name="Revenus (M$)", line=dict(color="blue")))
        fig.add_trace(go.Scatter(x=eps.index, y=eps, name="BPA", line=dict(color="green"), yaxis="y2"))
        fig.update_layout(yaxis2=dict(overlaying="y", side="right"))
        st.plotly_chart(fig, use_container_width=True)

with tab_val:
    st.subheader("Graphique Valeur + Juste Valeur (ajustable)")
    if not history.empty:
        ma50 = history['Close'].rolling(50).mean()
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=history.index, y=history['Close'], name="Prix actuel"))
        fig.add_trace(go.Scatter(x=history.index, y=ma50, name="MA 50 jours"))
        st.plotly_chart(fig, use_container_width=True)

    # Juste valeur avec croissance ajustable
    st.subheader("Juste Valeur selon croissance EPS")
    growth_analyst = info.get('earningsGrowth', 0.15) * 100
    growth_slider = st.slider("Croissance EPS prévue (%)", 0, 40, int(growth_analyst))
    pe = info.get('forwardPE') or info.get('trailingPE', 20)
    juste_valeur = info.get('currentPrice', 100) * (1 + growth_slider/100)**5   # modèle simple 5 ans
    st.metric("Juste Valeur estimée (5 ans)", f"${juste_valeur:,.2f}", 
              f"{(juste_valeur/info.get('currentPrice',1)-1)*100:+.1f} %")

with tab_fcf:
    st.subheader("💰 Analyse Cash Flow + DCF complet")
    if not cashflow.empty:
        st.dataframe(cashflow.style.format("{:,.0f}"))
        ocf = cashflow.loc.get('Operating Cash Flow')
        capex = cashflow.loc.get('Capital Expenditure')
        if ocf is not None and capex is not None:
            fcf = ocf + capex
            st.subheader("Free Cash Flow")
            fig_fcf = go.Figure(go.Bar(x=fcf.index, y=fcf/1e6, name="FCF (M$)"))
            st.plotly_chart(fig_fcf, use_container_width=True)

            # DCF ajustable
            st.subheader("DCF 5 ans (ta propre évaluation)")
            g_fcf = st.slider("Croissance FCF (%)", 0, 40, 15)
            wacc = st.slider("WACC (%)", 6, 14, 10)
            tg = st.slider("Croissance perpétuelle (%)", 0, 5, 3)
            last_fcf = fcf.iloc[0]
            projected = [last_fcf * (1 + g_fcf/100)**i for i in range(1,6)]
            terminal = projected[-1] * (1 + tg/100) / (wacc/100 - tg/100)
            ev = sum(projected) + terminal
            equity = ev - info.get('totalDebt',0) + info.get('totalCash',0)
            per_share = equity / info.get('sharesOutstanding',1)
            st.metric("Valeur théorique par action (DCF)", f"${per_share:,.2f}")

with tab_ratios:
    st.subheader("Ratios & PEG")
    pe = info.get('trailingPE', 'N/A')
    peg = info.get('pegRatio')
    if peg is None and isinstance(pe, (int,float)) and growth_slider:
        peg = pe / growth_slider
    st.metric("PEG Ratio", f"{peg:.2f}" if isinstance(peg, (int,float)) else "N/A")
    st.caption("PEG < 1 = potentiellement sous-évalué (basé sur croissance EPS que tu as choisie)")

st.subheader("Données annuelles")
if not income.empty:
    df = pd.DataFrame({
        "Année": income.columns,
        "Revenus (M$)": (income.loc['Total Revenue']/1e6).round(0),
        "BPA": (income.loc.get('Net Income Common Stockholders', income.loc['Net Income']) / info.get('sharesOutstanding',1)).round(2)
    }).T
    st.dataframe(df)

st.caption("Données yfinance • 10 ans max • Cash Flow + DCF + PEG ajustable • Mis à jour en direct")
