import re

with open('app.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace format_currency
old_format = '''def format_currency(value):
    if pd.isna(value) or value is None:
        return "N/A"
    if abs(value) >= 1e12:
        return f"${value/1e12:.2f}T"
    elif abs(value) >= 1e9:
        return f"${value/1e9:.2f}B"
    elif abs(value) >= 1e6:
        return f"${value/1e6:.1f}M"
    else:
        return f"${value:,.0f}"'''

new_format = '''def format_currency(value, ticker=""):
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
        return f"{sym}{value:,.0f}"'''

content = content.replace(old_format, new_format)

# Find all calls to format_currency and replace them with format_currency(value, ticker)
content = content.replace("format_currency(info.get('marketCap', np.nan))", "format_currency(info.get('marketCap', np.nan), ticker)")
content = content.replace("format_currency(am['ev'])", "format_currency(am['ev'], ticker)")
content = content.replace("format_currency(am['ebit'])", "format_currency(am['ebit'], ticker)")

# Find hardcoded dollar signs
# 600: yaxis_title="Price ($)",
old_yaxis_price = 'yaxis_title="Price ($)",'
new_yaxis_price = 'yaxis_title=f"Price ({\'₹\' if ticker.endswith(\'.NS\') or ticker.endswith(\'.BS\') or ticker.endswith(\'.BO\') else \'$\'})",'
content = content.replace(old_yaxis_price, new_yaxis_price)

# 716: f"${iv_val:.2f}" if not pd.isna(iv_val) else "N/A"
old_iv = 'f"${iv_val:.2f}" if not pd.isna(iv_val) else "N/A"'
new_iv = 'f"{\'₹\' if ticker.endswith(\'.NS\') or ticker.endswith(\'.BS\') or ticker.endswith(\'.BO\') else \'$\'}{iv_val:.2f}" if not pd.isna(iv_val) else "N/A"'
content = content.replace(old_iv, new_iv)

# 721: f"${cp_val:.2f}" if not pd.isna(cp_val) else "N/A"
old_cp = 'f"${cp_val:.2f}" if not pd.isna(cp_val) else "N/A"'
new_cp = 'f"{\'₹\' if ticker.endswith(\'.NS\') or ticker.endswith(\'.BS\') or ticker.endswith(\'.BO\') else \'$\'}{cp_val:.2f}" if not pd.isna(cp_val) else "N/A"'
content = content.replace(old_cp, new_cp)

# 752: yaxis_title="Cash Flow ($)",
old_yaxis_cf = 'yaxis_title="Cash Flow ($)",'
new_yaxis_cf = 'yaxis_title=f"Cash Flow ({\'₹\' if ticker.endswith(\'.NS\') or ticker.endswith(\'.BS\') or ticker.endswith(\'.BO\') else \'$\'})",'
content = content.replace(old_yaxis_cf, new_yaxis_cf)

with open('app.py', 'w', encoding='utf-8') as f:
    f.write(content)
