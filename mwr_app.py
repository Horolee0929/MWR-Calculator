import streamlit as st
import pandas as pd
import numpy as np
import datetime as dt
import requests

st.set_page_config(page_title="MWR计算器", layout="centered")

st.title("💰 多币种 MWR（资金加权收益率）计算器")
st.markdown("""
此工具支持使用 **RMB / CHF / USD** 作为基准币种，输入你的交易记录（资金流入和流出），并计算每种币种下的 MWR。

请手动填写以下数据：
- 资金流（投入或取出）、币种、汇率
- 当前持有资产信息：股数、当前价格、买入日期等
""")

st.markdown("---")

# 初始化数据框架为空并指定列类型
def get_input_df():
    return pd.DataFrame({
        "日期": pd.Series(dtype="datetime64[ns]"),
        "金额": pd.Series(dtype="float"),
        "币种": pd.Series(dtype="str"),
        "类型": pd.Series(dtype="str"),
        "兑RMB": pd.Series(dtype="float"),
        "兑CHF": pd.Series(dtype="float"),
        "兑USD": pd.Series(dtype="float"),
    })

if "cashflow_df" not in st.session_state:
    st.session_state.cashflow_df = get_input_df()

edited_df = st.data_editor(
    st.session_state.cashflow_df,
    num_rows="dynamic",
    use_container_width=True,
    column_config={
        "日期": st.column_config.DateColumn(format="YYYY-MM-DD"),
        "金额": st.column_config.NumberColumn(step=100.0),
        "币种": st.column_config.SelectboxColumn(options=["RMB", "CHF", "USD", "HKD"]),
        "类型": st.column_config.SelectboxColumn(options=["流出", "流入"]),
        "兑RMB": st.column_config.NumberColumn(step=0.01),
        "兑CHF": st.column_config.NumberColumn(step=0.01),
        "兑USD": st.column_config.NumberColumn(step=0.01),
    },
    key="cashflow_editor"
)

# 腾讯持仓信息模块
st.markdown("---")
st.subheader("📘 当前持仓：腾讯控股")
is_adr = st.radio("持有形式：", ["港股（00700.HK）", "美股ADR（TCEHY）"])

# 手动输入买入信息
buy_date = st.date_input("买入日期：", dt.date(2023, 3, 1))
buy_price = st.number_input("买入价格（每股，港币）：", min_value=0.0, value=300.0)
buy_shares = st.number_input("买入股数：", min_value=0.0, value=50.0)

st.markdown(f"📝 你在 {buy_date} 买入了 {buy_shares} 股腾讯，每股 {buy_price} 港币，总成本约 {buy_price * buy_shares:.2f} 港币")

tx_shares = st.number_input("当前持有股数（可与买入不同）：", min_value=0.0, value=buy_shares)

# 汇率获取 API
@st.cache_data

def get_exchange_rates():
    url = "https://api.exchangerate.host/latest?base=HKD"
    r = requests.get(url)
    if r.status_code == 200:
        data = r.json()
        return {
            "HKD_RMB": data["rates"].get("CNY", 0.88),
            "HKD_CHF": data["rates"].get("CHF", 0.114),
            "HKD_USD": data["rates"].get("USD", 0.128)
        }
    return {"HKD_RMB": 0.88, "HKD_CHF": 0.114, "HKD_USD": 0.128}

rates = get_exchange_rates()
hkd_to_rmb = rates["HKD_RMB"]
hkd_to_usd = rates["HKD_USD"]
hkd_to_chf = rates["HKD_CHF"]

# 当前价格输入
if is_adr == "港股（00700.HK）":
    tx_price_hkd = st.number_input("当前腾讯股价（港币）：", value=320.0)
else:
    tx_price_hkd = st.number_input("当前腾讯 ADR 折算港币价格：", value=50.0 * 7.8)

current_hkd_value = tx_price_hkd * tx_shares

st.markdown(f"**当前持仓市值（港币）：{current_hkd_value:.2f} HKD**")
st.markdown(f"RMB：{current_hkd_value * hkd_to_rmb:.2f}，USD：{current_hkd_value * hkd_to_usd:.2f}，CHF：{current_hkd_value * hkd_to_chf:.2f}")

# 将当前市值加入现金流
edited_df = pd.concat([
    edited_df,
    pd.DataFrame.from_records([{
        "日期": dt.date.today(),
        "金额": current_hkd_value,
        "币种": "HKD",
        "类型": "流入",
        "兑RMB": hkd_to_rmb,
        "兑CHF": hkd_to_chf,
        "兑USD": hkd_to_usd
    }])
], ignore_index=True)

# 汇率换算 + MWR 计算函数
def calculate_xirr(cash_flows):
    def xnpv(rate):
        return sum(cf / (1 + rate) ** ((d - cash_flows[0][0]).days / 365) for d, cf in cash_flows)

    low, high = -0.99, 10.0
    while high - low > 1e-6:
        mid = (low + high) / 2
        if xnpv(mid) > 0:
            low = mid
        else:
            high = mid
    return mid

# 提交按钮
total_rows = edited_df.dropna()
if st.button("📈 计算各币种下的 MWR"):
    try:
        def build_cf(df, col):
            cf_list = []
            for _, row in df.iterrows():
                amt = row["金额"] * row[col]
                amt = abs(amt) if row["类型"] == "流入" else -abs(amt)
                cf_list.append((row["日期"], amt))
            return sorted(cf_list, key=lambda x: x[0])

        st.markdown("### 📊 计算过程与结果")

        for label, colname in zip(["RMB", "CHF", "USD"], ["兑RMB", "兑CHF", "兑USD"]):
            flows = build_cf(total_rows, colname)
            with st.expander(f"{label} 计价现金流"):
                df_show = pd.DataFrame(flows, columns=["日期", f"金额（{label}）"])
                st.dataframe(df_show, use_container_width=True)
                result = calculate_xirr(flows)
                st.success(f"MWR（{label} 计）：{result:.2%} 年化")

    except Exception as e:
        st.error(f"发生错误：{e}")
