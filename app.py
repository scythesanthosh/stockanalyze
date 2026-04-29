import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import warnings
warnings.filterwarnings('ignore')

st.set_page_config(
    page_title="Equity Intelligence Dashboard",
    layout="wide",
    initial_sidebar_state="expanded"
)


@st.cache_data(ttl=3600)
def fetch_stock_data(ticker: str) -> dict:
    try:
        ticker_obj = yf.Ticker(ticker)
        data = {
            'info': ticker_obj.info,
            'financials': ticker_obj.financials,
            'balance_sheet': ticker_obj.balance_sheet,
            'cashflow': ticker_obj.cashflow,
            'quarterly_financials': ticker_obj.quarterly_financials,
            'quarterly_balance_sheet': ticker_obj.quarterly_balance_sheet,
            'history': ticker_obj.history(period="5y", interval="1d")
        }
        return data
    except Exception as e:
        return None



def safe_get_row_value(df, row_name, col_idx=0, info=None):
    try:
        val = np.nan
        if df is not None and row_name in df.index:
            val = df.loc[row_name].iloc[col_idx]
            
        if pd.isna(val) and df is not None:
            alts = []
            if row_name == 'Net Income':
                alts = ['Net Income Common Stockholders', 'Net Income Continuous Operations']
            elif row_name == 'Total Revenue':
                alts = ['Operating Revenue']
            elif row_name == 'Gross Profit':
                if 'Total Revenue' in df.index and 'Cost Of Revenue' in df.index:
                    try:
                        val = df.loc['Total Revenue'].iloc[col_idx] - df.loc['Cost Of Revenue'].iloc[col_idx]
                    except: pass
            elif row_name == 'Operating Cash Flow':
                alts = ['Cash Flow From Continuing Operating Activities']
            elif row_name == 'Ordinary Shares Number':
                alts = ['Basic Average Shares', 'Diluted Average Shares', 'Share Issued']
            elif row_name == 'EBIT':
                alts = ['Operating Income', 'Net Income Continuous Operations']
            elif row_name == 'Free Cash Flow':
                if 'Operating Cash Flow' in df.index and 'Capital Expenditure' in df.index:
                    try:
                        cfo = df.loc['Operating Cash Flow'].iloc[col_idx]
                        capex = df.loc['Capital Expenditure'].iloc[col_idx]
                        if not pd.isna(cfo) and not pd.isna(capex):
                            val = cfo + capex
                    except: pass
            elif row_name == 'Current Assets':
                alts = ['Total Current Assets']
            elif row_name == 'Current Liabilities':
                alts = ['Total Current Liabilities']
            elif row_name == 'Total Debt':
                if 'Total Debt' not in df.index:
                    val_d = 0
                    if 'Current Debt' in df.index:
                        val_d += df.loc['Current Debt'].iloc[col_idx]
                    if 'Long Term Debt' in df.index:
                        val_d += df.loc['Long Term Debt'].iloc[col_idx]
                    if val_d > 0: val = val_d
            
            if pd.isna(val):
                for alt in alts:
                    if alt in df.index:
                        val = df.loc[alt].iloc[col_idx]
                        if not pd.isna(val):
                            break
                            
        # Info fallback for current period
        if pd.isna(val) and col_idx == 0 and info is not None:
            mapping = {
                'Net Income': 'netIncomeToCommon',
                'Total Revenue': 'totalRevenue',
                'Gross Profit': 'grossProfits',
                'Operating Cash Flow': 'operatingCashflow',
                'Free Cash Flow': 'freeCashflow',
                'Total Assets': 'totalAssets',
                'Total Debt': 'totalDebt',
                'Ordinary Shares Number': 'sharesOutstanding'
            }
            if row_name in mapping:
                val = info.get(mapping[row_name], np.nan)
            elif row_name == 'EBIT':
                val = info.get('ebitda', np.nan)
            
        return val
    except:
        return np.nan


def calculate_piotroski(data) -> dict:
    try:
        financials = data.get('financials')
        balance_sheet = data.get('balance_sheet')
        cashflow = data.get('cashflow')
        
        if financials is None or balance_sheet is None:
            result = {f'F{i}': 0 for i in range(1, 10)}
            result['total'] = 0
            result['label'] = 'Neutral'
            return result
        
        info = data.get('info', {})
        def get_row_value(df, row_name, col_idx=0):
            return safe_get_row_value(df, row_name, col_idx, info)
        
        net_income_y0 = get_row_value(financials, 'Net Income', 0)
        net_income_y1 = get_row_value(financials, 'Net Income', 1)
        revenue_y0 = get_row_value(financials, 'Total Revenue', 0)
        revenue_y1 = get_row_value(financials, 'Total Revenue', 1)
        gross_profit_y0 = get_row_value(financials, 'Gross Profit', 0)
        gross_profit_y1 = get_row_value(financials, 'Gross Profit', 1)
        
        total_assets_y0 = get_row_value(balance_sheet, 'Total Assets', 0)
        total_assets_y1 = get_row_value(balance_sheet, 'Total Assets', 1)
        total_debt_y0 = get_row_value(balance_sheet, 'Total Debt', 0)
        total_debt_y1 = get_row_value(balance_sheet, 'Total Debt', 1)
        current_assets_y0 = get_row_value(balance_sheet, 'Current Assets', 0)
        current_assets_y1 = get_row_value(balance_sheet, 'Current Assets', 1)
        current_liabilities_y0 = get_row_value(balance_sheet, 'Current Liabilities', 0)
        current_liabilities_y1 = get_row_value(balance_sheet, 'Current Liabilities', 1)
        shares_y0 = get_row_value(balance_sheet, 'Ordinary Shares Number', 0)
        shares_y1 = get_row_value(balance_sheet, 'Ordinary Shares Number', 1)
        
        cfo = get_row_value(cashflow, 'Operating Cash Flow', 0)
        
        roa_y0 = net_income_y0 / total_assets_y0 if (total_assets_y0 and not pd.isna(total_assets_y0) and total_assets_y0 != 0) else np.nan
        roa_y1 = net_income_y1 / total_assets_y1 if (total_assets_y1 and not pd.isna(total_assets_y1) and total_assets_y1 != 0) else np.nan
        
        f1 = 1 if (not pd.isna(roa_y0) and roa_y0 > 0) else 0
        
        f2 = 1 if (not pd.isna(cfo) and cfo > 0) else 0
        
        f3 = 1
        if not pd.isna(cfo) and not pd.isna(roa_y0) and total_assets_y0 and total_assets_y0 != 0:
            cfo_ratio = cfo / total_assets_y0
            if cfo_ratio > roa_y0:
                f3 = 1
            else:
                f3 = 0
        else:
            f3 = 0
        
        f4 = 1 if (not pd.isna(roa_y0) and not pd.isna(roa_y1) and roa_y0 > roa_y1) else 0
        
        leverage_y0 = total_debt_y0 / total_assets_y0 if (total_debt_y0 and total_assets_y0 and not pd.isna(total_debt_y0) and not pd.isna(total_assets_y0) and total_assets_y0 != 0) else np.nan
        leverage_y1 = total_debt_y1 / total_assets_y1 if (total_debt_y1 and total_assets_y1 and not pd.isna(total_debt_y1) and not pd.isna(total_assets_y1) and total_assets_y1 != 0) else np.nan
        f5 = 1 if (not pd.isna(leverage_y0) and not pd.isna(leverage_y1) and leverage_y0 < leverage_y1) else 0
        
        current_ratio_y0 = current_assets_y0 / current_liabilities_y0 if (current_assets_y0 and current_liabilities_y0 and not pd.isna(current_assets_y0) and not pd.isna(current_liabilities_y0) and current_liabilities_y0 != 0) else np.nan
        current_ratio_y1 = current_assets_y1 / current_liabilities_y1 if (current_assets_y1 and current_liabilities_y1 and not pd.isna(current_assets_y1) and not pd.isna(current_liabilities_y1) and current_liabilities_y1 != 0) else np.nan
        f6 = 1 if (not pd.isna(current_ratio_y0) and not pd.isna(current_ratio_y1) and current_ratio_y0 > current_ratio_y1) else 0
        
        f7 = 1 if (shares_y0 and shares_y1 and not pd.isna(shares_y0) and not pd.isna(shares_y1) and shares_y0 <= shares_y1) else 0
        
        gross_margin_y0 = gross_profit_y0 / revenue_y0 if (gross_profit_y0 and revenue_y0 and not pd.isna(gross_profit_y0) and not pd.isna(revenue_y0) and revenue_y0 != 0) else np.nan
        gross_margin_y1 = gross_profit_y1 / revenue_y1 if (gross_profit_y1 and revenue_y1 and not pd.isna(gross_profit_y1) and not pd.isna(revenue_y1) and revenue_y1 != 0) else np.nan
        f8 = 1 if (not pd.isna(gross_margin_y0) and not pd.isna(gross_margin_y1) and gross_margin_y0 > gross_margin_y1) else 0
        
        turnover_y0 = revenue_y0 / total_assets_y0 if (revenue_y0 and total_assets_y0 and not pd.isna(revenue_y0) and not pd.isna(total_assets_y0) and total_assets_y0 != 0) else np.nan
        turnover_y1 = revenue_y1 / total_assets_y1 if (revenue_y1 and total_assets_y1 and not pd.isna(revenue_y1) and not pd.isna(total_assets_y1) and total_assets_y1 != 0) else np.nan
        f9 = 1 if (not pd.isna(turnover_y0) and not pd.isna(turnover_y1) and turnover_y0 > turnover_y1) else 0
        
        total = f1 + f2 + f3 + f4 + f5 + f6 + f7 + f8 + f9
        
        if total >= 7:
            label = "Strong"
        elif total >= 4:
            label = "Neutral"
        else:
            label = "Weak"
        
        return {
            'F1': f1, 'F2': f2, 'F3': f3, 'F4': f4, 'F5': f5,
            'F6': f6, 'F7': f7, 'F8': f8, 'F9': f9,
            'total': total, 'label': label
        }
    except Exception as e:
        result = {f'F{i}': 0 for i in range(1, 10)}
        result['total'] = 0
        result['label'] = 'Neutral'
        return result


def calculate_magic_formula(data) -> dict:
    try:
        financials = data.get('financials')
        balance_sheet = data.get('balance_sheet')
        info = data.get('info', {})
        
        info = data.get('info', {})
        def get_row_value(df, row_name, col_idx=0):
            return safe_get_row_value(df, row_name, col_idx, info)
        
        ebit = get_row_value(financials, 'EBIT', 0)
        if pd.isna(ebit):
            ebit = get_row_value(financials, 'Operating Income', 0)
        
        ev = info.get('enterpriseValue', np.nan)
        
        current_assets = get_row_value(balance_sheet, 'Current Assets', 0)
        current_liabilities = get_row_value(balance_sheet, 'Current Liabilities', 0)
        total_assets = get_row_value(balance_sheet, 'Total Assets', 0)
        
        nwc = current_assets - current_liabilities if (not pd.isna(current_assets) and not pd.isna(current_liabilities)) else 0
        
        intangible = 0
        try:
            if balance_sheet is not None and 'Intangible Assets' in balance_sheet.index:
                intangible = balance_sheet.loc['Intangible Assets'].iloc[0]
                if pd.isna(intangible):
                    intangible = 0
        except:
            intangible = 0
        
        cash = 0
        try:
            if balance_sheet is not None and 'Cash' in balance_sheet.index:
                cash = balance_sheet.loc['Cash'].iloc[0]
                if pd.isna(cash):
                    cash = 0
        except:
            cash = 0
        
        nfa = total_assets - current_assets - intangible - cash if (not pd.isna(total_assets) and not pd.isna(current_assets)) else 0
        
        invested_capital = nwc + nfa
        
        roic = ebit / invested_capital if (not pd.isna(ebit) and invested_capital != 0 and not pd.isna(invested_capital)) else np.nan
        earnings_yield = ebit / ev if (not pd.isna(ebit) and not pd.isna(ev) and ev != 0) else np.nan
        
        roic_pct = f"{roic * 100:.1f}%" if not pd.isna(roic) else "N/A"
        ey_pct = f"{earnings_yield * 100:.1f}%" if not pd.isna(earnings_yield) else "N/A"
        
        if not pd.isna(roic) and not pd.isna(earnings_yield) and roic > 0.15 and earnings_yield > 0.08:
            quality = "Magic Formula Candidate"
        elif not pd.isna(roic) and not pd.isna(earnings_yield) and (roic > 0.10 or earnings_yield > 0.05):
            quality = "Moderate"
        else:
            quality = "Below Threshold"
        
        return {
            'ebit': ebit, 'ev': ev, 'roic': roic, 'earnings_yield': earnings_yield,
            'roic_pct': roic_pct, 'ey_pct': ey_pct, 'quality': quality
        }
    except Exception as e:
        return {
            'ebit': np.nan, 'ev': np.nan, 'roic': np.nan, 'earnings_yield': np.nan,
            'roic_pct': "N/A", 'ey_pct': "N/A", 'quality': "Below Threshold"
        }


def calculate_dcf(data) -> dict:
    try:
        info = data.get('info', {})
        cashflow = data.get('cashflow')

        info = data.get('info', {})
        def get_row_value(df, row_name, col_idx=0):
            return safe_get_row_value(df, row_name, col_idx, info)

        # ✅ Get FCF from cashflow (primary source)
        fcf = get_row_value(cashflow, 'Free Cash Flow', 0)

        # ✅ Fallback: CFO - CapEx
        if pd.isna(fcf):
            cfo = get_row_value(cashflow, 'Operating Cash Flow', 0)
            capex = get_row_value(cashflow, 'Capital Expenditure', 0)

            if not pd.isna(cfo) and not pd.isna(capex):
                fcf = cfo + capex  # capex is negative in yfinance


        beta = info.get('beta', 1.0)
        if pd.isna(beta):
            beta = 1.0

        total_debt = info.get('totalDebt', 0)
        total_cash = info.get('totalCash', 0)
        shares = info.get('sharesOutstanding', np.nan)
        current_price = info.get('currentPrice') or info.get('regularMarketPrice')

        # ✅ Cost of capital (simple version)
        risk_free_rate = 0.07   # India adjusted
        equity_risk_premium = 0.06
        cost_of_equity = risk_free_rate + beta * equity_risk_premium
        wacc = cost_of_equity

        # 🚨 Guard clause
        if pd.isna(fcf) or pd.isna(shares) or shares <= 0:
            return {
                'fcf': fcf, 'wacc': wacc, 'intrinsic_value': np.nan,
                'current_price': current_price, 'margin_of_safety': np.nan,
                'upside': "Insufficient Data",
                'projected_fcfs': [], 'discounted_fcfs': [],
                'terminal_value': np.nan, 'years': list(range(1, 11))
            }

        # ✅ Growth assumptions
        growth_rate_stage1 = 0.10
        growth_rate_stage2 = 0.05
        terminal_growth = 0.025

        # ✅ FIX: don’t overwrite original FCF
        base_fcf = fcf
        projected_fcfs = []

        for i in range(10):
            if i < 5:
                growth = growth_rate_stage1
            else:
                growth = growth_rate_stage2

            base_fcf = base_fcf * (1 + growth)
            projected_fcfs.append(base_fcf)

        # Discounting
        discounted_fcfs = [
            f / ((1 + wacc) ** (i + 1))
            for i, f in enumerate(projected_fcfs)
        ]

        # Terminal value
        terminal_value = projected_fcfs[-1] * (1 + terminal_growth) / (wacc - terminal_growth)
        discounted_tv = terminal_value / ((1 + wacc) ** 10)

        # Equity value
        equity_value = sum(discounted_fcfs) + discounted_tv
        equity_value = equity_value + total_cash - total_debt

        intrinsic_per_share = equity_value / shares if shares > 0 else np.nan

        if intrinsic_per_share <= 0:
            mos = np.nan
            upside = "Negative Intrinsic Value"
        else:
            mos = ((intrinsic_per_share - current_price) / intrinsic_per_share * 100) \
                if (not pd.isna(intrinsic_per_share) and not pd.isna(current_price) and intrinsic_per_share != 0) else np.nan

            if not pd.isna(mos):
                if mos > 30:
                    upside = "Significantly Undervalued"
                elif mos > 0:
                    upside = "Undervalued"
                else:
                    upside = "Overvalued"
            else:
                upside = "N/A"

        return {
            'fcf': fcf,
            'wacc': wacc,
            'intrinsic_value': intrinsic_per_share,
            'current_price': current_price,
            'margin_of_safety': mos,
            'upside': upside,
            'projected_fcfs': projected_fcfs,
            'discounted_fcfs': discounted_fcfs,
            'terminal_value': discounted_tv,
            'years': list(range(1, 11))
        }

    except Exception as e:
        st.write("DCF ERROR:", e)
        return {
            'fcf': np.nan, 'wacc': np.nan, 'intrinsic_value': np.nan,
            'current_price': np.nan, 'margin_of_safety': np.nan,
            'upside': "Calculation Error",
            'projected_fcfs': [], 'discounted_fcfs': [],
            'terminal_value': np.nan, 'years': list(range(1, 11))
        }

def calculate_acquirers_multiple(data) -> dict:
    try:
        financials = data.get('financials')
        info = data.get('info', {})
        
        ev = info.get('enterpriseValue', np.nan)
        
        info = data.get('info', {})
        def get_row_value(df, row_name, col_idx=0):
            return safe_get_row_value(df, row_name, col_idx, info)
        
        ebit = get_row_value(financials, 'Operating Income', 0)
        
        am = ev / ebit if (not pd.isna(ev) and not pd.isna(ebit) and ebit > 0) else np.nan
        
        if not pd.isna(am):
            if am < 8:
                label = "Deep Value"
            elif am < 15:
                label = "Fair Value"
            else:
                label = "Expensive"
        else:
            label = "N/A"
        
        return {
            'ev': ev, 'ebit': ebit, 'acquirers_multiple': am,
            'label': label
        }
    except Exception as e:
        return {
            'ev': np.nan, 'ebit': np.nan, 'acquirers_multiple': np.nan,
            'label': "N/A"
        }


def calculate_terry_smith(data) -> dict:
    try:
        financials = data.get('financials')
        balance_sheet = data.get('balance_sheet')
        cashflow = data.get('cashflow')
        
        info = data.get('info', {})
        def get_row_value(df, row_name, col_idx=0):
            return safe_get_row_value(df, row_name, col_idx, info)
        
        ebit = get_row_value(financials, 'EBIT', 0)
        total_assets = get_row_value(balance_sheet, 'Total Assets', 0)
        current_liabilities = get_row_value(balance_sheet, 'Current Liabilities', 0)
        capital_employed = total_assets - current_liabilities
        roce = (ebit / capital_employed * 100) if (not pd.isna(ebit) and not pd.isna(capital_employed) and capital_employed != 0) else np.nan
        
        gross_profit = get_row_value(financials, 'Gross Profit', 0)
        revenue = get_row_value(financials, 'Total Revenue', 0)
        net_income = get_row_value(financials, 'Net Income', 0)
        cfo = get_row_value(cashflow, 'Operating Cash Flow', 0)
        gross_margin = (gross_profit / revenue * 100) if (not pd.isna(gross_profit) and not pd.isna(revenue) and revenue != 0) else np.nan
        
        cash_conversion = ((cfo ) / net_income * 100) if (not pd.isna(cfo) and not pd.isna(net_income) and net_income > 0) else np.nan
        
        roce_pass = not pd.isna(roce) and roce > 15
        margin_pass = not pd.isna(gross_margin) and gross_margin > 40
        conversion_pass = not pd.isna(cash_conversion) and cash_conversion > 100
        
        quality_score = sum([roce_pass, margin_pass, conversion_pass])
        
        if quality_score == 3:
            label = "High Quality Compounder"
        elif quality_score == 2:
            label = "Good Quality"
        elif quality_score == 1:
            label = "Average"
        else:
            label = "Poor Quality"
        
        return {
            'roce': roce, 'gross_margin': gross_margin, 'cash_conversion': cash_conversion,
            'roce_pass': roce_pass, 'margin_pass': margin_pass, 'conversion_pass': conversion_pass,
            'quality_score': quality_score, 'label': label
        }
    except Exception as e:
        return {
            'roce': np.nan, 'gross_margin': np.nan, 'cash_conversion': np.nan,
            'roce_pass': False, 'margin_pass': False, 'conversion_pass': False,
            'quality_score': 0, 'label': "Poor Quality"
        }


def format_currency(value, ticker=""):
    sym = "₹" if ticker.endswith('.NS') or ticker.endswith('.BS') or ticker.endswith('.BO') else "$"
    if pd.isna(value) or value is None:
        return "N/A"
    if abs(value) >= 1e12:
        return f"{sym}{value/1e12:.2f}T"
    elif abs(value) >= 1e9:
        return f"{sym}{value/1e9:.2f}B"
    elif abs(value) >= 1e6:
        return f"{sym}{value/1e6:.1f}M"
    else:
        return f"{sym}{value:,.0f}"


def format_percent(value):
    if pd.isna(value) or value is None:
        return "N/A"
    return f"{value*100:.1f}%"


st.sidebar.title("\u2699\ufe0f Configuration")
ticker = st.sidebar.text_input("Stock Ticker", value="AAPL").upper().strip()
analyze_btn = st.sidebar.button("\U0001f50d Analyze", type="primary")
st.sidebar.markdown("---")
st.sidebar.markdown("**Model Legend**")
st.sidebar.markdown("\U0001f7e2 Strong signal | \U0001f7e1 Neutral | \U0001f7e3 Weak signal")

if analyze_btn or 'data' in st.session_state:
    if analyze_btn:
        with st.spinner(f"Fetching data for {ticker}..."):
            data = fetch_stock_data(ticker)
            st.session_state['data'] = data
            st.session_state['ticker'] = ticker
    else:
        data = st.session_state.get('data')
        ticker = st.session_state.get('ticker', ticker)
    
    if data is None:
        st.error(f"Could not fetch data for {ticker}. Check the ticker symbol.")
        st.stop()
    
    piotroski = calculate_piotroski(data)
    magic = calculate_magic_formula(data)
    dcf = calculate_dcf(data)
    am = calculate_acquirers_multiple(data)
    terry = calculate_terry_smith(data)
    
    info = data.get('info', {})
    
    tabs = st.tabs(["\U0001f4ca Overview", "\U0001f3c6 Piotroski F-Score", "\U0001f9c4 Magic Formula & AM", "\U0001f4b0 DCF Valuation", "\u2728 Quality Filters"])
    
    with tabs[0]:
        col1, col2, col3 = st.columns([2, 1, 1])
        
        with col1:
            st.subheader(f"\U0001f4bc {info.get('shortName', ticker)}")
            st.markdown(f"**Sector:** {info.get('sector', 'N/A')}")
            st.markdown(f"**Industry:** {info.get('industry', 'N/A')}")
            st.markdown(f"**Market Cap:** {format_currency(info.get('marketCap', np.nan), ticker)}")
            st.markdown(f"**P/E Ratio:** {info.get('trailingPE', 'N/A'):.2f}" if info.get('trailingPE') else "**P/E Ratio:** N/A")
            st.markdown(f"**P/B Ratio:** {info.get('priceToBook', 'N/A'):.2f}" if info.get('priceToBook') else "**P/B Ratio:** N/A")
            st.markdown(f"**EV/EBITDA:** {info.get('evToEbitda', 'N/A'):.2f}" if info.get('evToEbitda') else "**EV/EBITDA:** N/A")
        
        with col2:
            score_color = "green" if piotroski['total'] >= 7 else "red" if piotroski['total'] < 4 else "gray"
            st.metric(
                "Piotroski F-Score",
                f"{piotroski['total']}/9",
                delta=piotroski['label'],
                delta_color="normal" if piotroski['total'] >= 7 else "inverse" if piotroski['total'] < 4 else "off"
            )
        
        with col3:
            st.metric("Magic Formula", magic['quality'], delta="")
        
        st.markdown("---")
        
        col_score1, col_score2, col_score3, col_score4, col_score5 = st.columns(5)
        
        with col_score1:
            st.metric(
                "F-Score",
                f"{piotroski['total']}/9",
                delta="PASS" if piotroski['total'] >= 7 else "FAIL",
                delta_color="normal" if piotroski['total'] >= 7 else "inverse"
            )
        
        with col_score2:
            st.metric("ROIC", magic['roic_pct'])
        
        with col_score3:
            mos_val = dcf['margin_of_safety']
            mos_str = f"{mos_val:.1f}%" if not pd.isna(mos_val) else "N/A"
            st.metric("DCF MoS", mos_str)
        
        with col_score4:
            am_val = am['acquirers_multiple']
            am_str = f"{am_val:.1f}x" if not pd.isna(am_val) else "N/A"
            st.metric("Acq. Multiple", am_str)
        
        with col_score5:
            st.metric("Quality Score", f"{terry['quality_score']}/3", delta=terry['label'])
        
        st.markdown("---")
        
        history = data.get('history')
        if history is not None and not history.empty:
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=history.index,
                y=history['Close'],
                mode='lines',
                name='Price',
                line=dict(color='#00CED1', width=2)
            ))
            fig.update_layout(
                template="plotly_dark",
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                title=f"{ticker} - 5 Year Price History",
                xaxis_title="Date",
                yaxis_title=f"Price ({'₹' if ticker.endswith('.NS') or ticker.endswith('.BS') or ticker.endswith('.BO') else '$'})",
                height=400,
                margin=dict(t=50, r=20, b=40, l=60)
)
            st.plotly_chart(fig, width="stretch")
        
        with tabs[1]:
            st.metric("Total F-Score", f"{piotroski['total']}/9", delta=piotroski['label'])
            
            f_labels = [
                "ROA Positive", "CFO Positive", "Accruals Quality", "ΔRoA",
                "ΔLeverage", "ΔLiquidity", "No Dilution", "ΔGross Margin", "ΔAsset Turnover"
            ]
            f_values = [piotroski['F1'], piotroski['F2'], piotroski['F3'], piotroski['F4'],
                        piotroski['F5'], piotroski['F6'], piotroski['F7'], piotroski['F8'], piotroski['F9']]
            
            colors = ['#00CED1' if v == 1 else '#FF6B6B' for v in f_values]
            
            fig = go.Figure(go.Bar(
                x=f_values,
                y=f_labels,
                orientation='h',
                marker_color=colors,
                text=f_values,
                textposition='outside'
            ))
            fig.update_layout(
                template="plotly_dark",
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                title="Piotroski F-Score Components",
                xaxis_title="Score (0 or 1)",
                xaxis=dict(range=[0, 1.5]),
                height=500,
                margin=dict(t=50, r=100, b=40, l=150)
            )
            st.plotly_chart(fig, width="stretch")
            
            interpretation = {
                'Strong': "This stock scores 7+ on the Piotroski F-Score, indicating **strong fundamental quality**. It shows positive profitability, improving leverage, and operational efficiency gains.",
                'Neutral': "This stock scores 4-6 on the Piotroski F-Score, indicating **mixed fundamentals**. Some positive signals offset concerns in other areas.",
                'Weak': "This stock scores below 4 on the Piotroski F-Score, indicating **weak fundamental quality**. Multiple red flags suggest caution."
            }
            st.markdown(f"**Interpretation:** {interpretation.get(piotroski['label'], '')}")
        
        with tabs[2]:
            col_left, col_right = st.columns(2)
            
            with col_left:
                st.subheader("\U0001f9c4 Magic Formula (Greenblatt)")
                st.markdown(f"**ROIC:** {magic['roic_pct']}")
                st.markdown(f"**Earnings Yield:** {magic['ey_pct']}")
                st.markdown(f"**Status:** {magic['quality']}")
                st.markdown("---")
                st.markdown("""
                **Magic Formula** looks for stocks with:
                - High Return on Invested Capital (ROIC) - indicates efficient capital use
                - High Earnings Yield (EY) - indicates cheap relative to earnings
                
                Target: ROIC > 15% AND EY > 8%
                """)
                
                fig_gauge = go.Figure(go.Indicator(
                    mode="gauge+number",
                    value=magic['roic'] * 100 if not pd.isna(magic['roic']) else 0,
                    number={'suffix': "%", 'font': {'size': 24}},
                    gauge=dict(
                        axis=dict(range=[0, 30], tickwidth=1),
                        bar=dict(color="darkblue"),
                        steps=[
                            {'range': [0, 15], 'color': 'red'},
                            {'range': [15, 30], 'color': 'green'}
                        ],
                        threshold=dict(line=dict(color="cyan", width=3), value=15)
                    ),
                    domain={'x': [0, 1], 'y': [0, 1]},
                    title={'text': 'ROIC %', 'font': {'color': 'white'}}
                ))
                fig_gauge.update_layout(
                    template="plotly_dark",
                    paper_bgcolor='rgba(0,0,0,0)',
                    height=350,
                    margin=dict(t=50, r=40, b=80, l=40)
                )
                st.plotly_chart(fig_gauge, width="stretch")
            
            with col_right:
                st.subheader("\U0001f9c6 Acquirer's Multiple")
                ev_val = format_currency(am['ev'], ticker) if not pd.isna(am['ev']) else "N/A"
                ebit_val = format_currency(am['ebit'], ticker) if not pd.isna(am['ebit']) else "N/A"
                am_val = f"{am['acquirers_multiple']:.1f}x" if not pd.isna(am['acquirers_multiple']) else "N/A"
                
                st.markdown(f"**Enterprise Value:** {ev_val}")
                st.markdown(f"**EBIT:** {ebit_val}")
                st.markdown(f"**Acquirer's Multiple:** {am_val}")
                st.markdown(f"**Status:** {am['label']}")
                st.markdown("---")
                st.markdown("""
                **Acquirer's Multiple** (Carlisle): EV / EBIT
                - < 8x: Deep Value - potentially mispriced
                - 8-15x: Fair Value - reasonable price
                - > 15x: Expensive - limited margin of safety
                """)
        
        st.markdown("---")
        st.markdown("**Combined View:** Look for stocks that pass both Magic Formula AND Acquirer's Multiple for maximum conviction.")
    
    with tabs[3]:
        iv_val = dcf['intrinsic_value']
        cp_val = dcf['current_price']
        mos_val = dcf['margin_of_safety']
        
        col_iv1, col_iv2, col_iv3, col_iv4 = st.columns(4)
        with col_iv1:
            st.metric(
                "Intrinsic Value/Share",
                f"{'₹' if ticker.endswith('.NS') or ticker.endswith('.BS') or ticker.endswith('.BO') else '$'}{iv_val:.2f}" if not pd.isna(iv_val) else "N/A"
            )
        with col_iv2:
            st.metric(
                "Current Price",
                f"{'₹' if ticker.endswith('.NS') or ticker.endswith('.BS') or ticker.endswith('.BO') else '$'}{cp_val:.2f}" if not pd.isna(cp_val) else "N/A"
            )
        with col_iv3:
            mos_str = f"{mos_val:.1f}%" if not pd.isna(mos_val) else "N/A"
            st.metric("Margin of Safety", mos_str)
        with col_iv4:
            st.metric("WACC", f"{dcf['wacc']*100:.2f}%")
        
        st.markdown("---")
        st.subheader("DCF Projections")
        
        if dcf['projected_fcfs']:
            fig_dcf = go.Figure()
            fig_dcf.add_trace(go.Bar(
                name='Projected FCF',
                x=dcf['years'],
                y=dcf['projected_fcfs'],
                marker_color='#00CED1'
            ))
            fig_dcf.add_trace(go.Bar(
                name='Discounted FCF',
                x=dcf['years'],
                y=dcf['discounted_fcfs'],
                marker_color='#FF6B6B'
            ))
            fig_dcf.update_layout(
                template="plotly_dark",
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                title="FCF Projections vs Discounted Values",
                xaxis_title="Year",
                yaxis_title=f"Cash Flow ({'₹' if ticker.endswith('.NS') or ticker.endswith('.BS') or ticker.endswith('.BO') else '$'})",
                barmode='group',
                height=400,
                margin=dict(t=50, r=20, b=40, l=60)
            )
            st.plotly_chart(fig_dcf, width="stretch")
        
        st.markdown("---")
        st.subheader("Sensitivity Analysis")
        
        if not pd.isna(iv_val) and not pd.isna(cp_val) and not pd.isna(dcf['wacc']):
            base_wacc = dcf['wacc']
            base_tg = 0.025
            
            wacc_range = [round(base_wacc - 0.02 + i * 0.005, 3) for i in range(9)]
            tg_range = [round(base_tg - 0.01 + i * 0.005, 3) for i in range(5)]
            
            sensitivity_data = []
            for wacc in wacc_range:
                row = []
                for tg in tg_range:
                    if wacc > tg:
                        iv_adj = iv_val * (base_wacc - tg) / (wacc - tg)
                        row.append(iv_adj)
                    else:
                        row.append(np.nan)
                sensitivity_data.append(row)
            
            sensitivity_df = pd.DataFrame(
                sensitivity_data,
                index=[f"{w*100:.1f}%" for w in wacc_range],
                columns=[f"{t*100:.1f}%" for t in tg_range]
            )
            sensitivity_df.index.name = 'WACC \\ TG'
            
            def color_cells(val):
                if pd.isna(val) or val is None:
                    return 'background-color: gray; color: white'
                if val > cp_val:
                    return 'background-color: green; color: white'
                else:
                    return 'background-color: red; color: white'
            
            st.dataframe(
                sensitivity_df.style.map(color_cells).format("{:.2f}"),
                width="stretch"
            )
            st.caption("Green = above current price | Red = below current price")
        
        st.markdown("---")
        st.subheader("Value Summary")
        tv_pv = dcf['terminal_value']
        fcf_sum = sum(dcf['discounted_fcfs'])
        iv_total = fcf_sum + tv_pv if not pd.isna(tv_pv) else fcf_sum
        
        fig_waterfall = go.Figure(go.Waterfall(
            name="DCF",
            orientation="h",
            measure=["relative", "relative", "total"],
            x=[fcf_sum, tv_pv, iv_total],
            text=["FCF PV Sum", "Terminal Value PV", "Total IV"],
            textposition="outside"
        ))
        fig_waterfall.update_layout(
            template="plotly_dark",
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            title="DCF Value Build-Up",
            height=300,
            margin=dict(t=50, r=20, b=40, l=60)
        )
        st.plotly_chart(fig_waterfall, width="stretch")
    
    with tabs[4]:
        roce_val = terry['roce']
        gm_val = terry['gross_margin']
        cc_val = terry['cash_conversion']
        
        st.subheader("\u2728 Terry Smith Quality Filters")
        
        col_t1, col_t2, col_t3 = st.columns(3)
        
        with col_t1:
            roce_str = f"{roce_val:.1f}%" if not pd.isna(roce_val) else "N/A"
            st.metric(
                "ROCE",
                roce_str,
                delta="PASS (>15%)" if terry['roce_pass'] else "FAIL (<15%)",
                delta_color="normal" if terry['roce_pass'] else "inverse"
            )
            st.markdown("\U0001f7e2" if terry['roce_pass'] else "\U0001f7e3")
        
        with col_t2:
            gm_str = f"{gm_val:.1f}%" if not pd.isna(gm_val) else "N/A"
            st.metric(
                "Gross Margin",
                gm_str,
                delta="PASS (>40%)" if terry['margin_pass'] else "FAIL (<40%)",
                delta_color="normal" if terry['margin_pass'] else "inverse"
            )
            st.markdown("\U0001f7e2" if terry['margin_pass'] else "\U0001f7e3")
        
        with col_t3:
            cc_str = f"{cc_val:.1f}%" if not pd.isna(cc_val) else "N/A"
            st.metric(
                "Cash Conversion",
                cc_str,
                delta="PASS (>100%)" if terry['conversion_pass'] else "FAIL (<100%)",
                delta_color="normal" if terry['conversion_pass'] else "inverse"
            )
            st.markdown("\U0001f7e2" if terry['conversion_pass'] else "\U0001f7e3")
        
        st.markdown("---")
        
        score = terry['quality_score']
        st.subheader(f"Quality Score: {score}/3")
        st.progress(score / 3, text=terry['label'])
        
        st.markdown("---")
        st.markdown("""
        **Terry Smith Quality Filters:**
        1. **ROCE > 15%**: Return on Capital Employed - measure of operational efficiency
        2. **Gross Margin > 40%**: Pricing power and operational efficiency
        3. **Cash Conversion > 100%**: Earnings quality - cash matches reported profits
        
        All three passing = High Quality Compounder (rare, quality businesses)
        """)
    
    st.markdown("---")
    st.caption(f"Data refreshed for {st.session_state.get('ticker', ticker)} | All models use cached data (TTL: 1 hour)")

else:
    st.title("\U0001f4c8 Multi-Factor Equity Intelligence Dashboard")
    st.info("Enter a ticker in the sidebar and click **Analyze** to begin.")
    st.markdown("""
    **Models included:**
    - \U0001f3c6 Piotroski F-Score (9-point fundamental quality test)
    - \U0001f9c4 Magic Formula (Greenblatt ROIC + Earnings Yield)
    - \U0001f9c6 Acquirer's Multiple (Carlisle deep value EV/EBIT)
    - \U0001f4b0 Automated DCF (intrinsic value with sensitivity analysis)
    - \u2728 Terry Smith Quality Filter (ROCE, margins, cash conversion)
    """)
