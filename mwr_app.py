import streamlit as st
import pandas as pd
import numpy as np
import datetime as dt
import requests

st.set_page_config(page_title="MWR计算器", layout="centered")

st.title("💰 多币种 MWR（资金加权收益率）计算器")
st.markdown("""
请在下方表格中填写每一笔投资记录，包含：
- 日期
- 金额
- 币种（RMB / HKD / USD / CHF）
- 类型（流入：卖出或当前估值，流出：买入或转入）
- 股票信息（可选）：买了哪只股票（港股/美股/A股）、股数、每股价格

系统将根据你输入的总持仓数量 × 当前实时价格 × 实时汇率，自动计算以不同币种计价的 MWR（资金加权收益率）。
""")

# 初始化空表格结构
@st.cache_data

def get_empty_df():
    return pd.DataFrame({
        "日期": pd.Series(dtype="datetime64[ns]"),
        "金额": pd.Series(dtype="float"),
        "币种": pd.Series(dtype="str"),
        "类型": pd.Series(dtype="str"),
        "股票代码": pd.Series(dtype="str"),
        "市场": pd.Series(dtype="str"),
        "股数": pd.Series(dtype="float"),
        "买入价格": pd.Series(dtype="float")
    })

if "cashflow_df" not in st.session_state:
    st.session_state.cashflow_df = get_empty_df()

edited_df = st.data_editor(
    st.session_state.cashflow_df,
    num_rows="dynamic",
    use_container_width=True,
    column_config={
        "日期": st.column_config.DateColumn(format="YYYY-MM-DD"),
        "金额": st.column_config.NumberColumn(format="%.2f"),
        "币种": st.column_config.SelectboxColumn(options=["RMB", "HKD", "USD", "CHF"]),
        "类型": st.column_config.SelectboxColumn(options=["流入", "流出"]),
        "股票代码": st.column_config.TextColumn(),
        "市场": st.column_config.SelectboxColumn(options=["港股", "美股", "A股", "其他"]),
        "股数": st.column_config.NumberColumn(format="%.2f"),
        "买入价格": st.column_config.NumberColumn(format="%.2f"),
    },
    key="cashflow_editor"
)


# 汇率获取函数（以 HKD 为基准）
def get_hkd_rates():
    url = "https://api.exchangerate.host/latest?base=HKD"
    try:
        r = requests.get(url, timeout=5)
        r.raise_for_status()
        data = r.json()
        if "rates" in data:
            return {
                "HKD_RMB": data["rates"].get("CNY", None),
                "HKD_CHF": data["rates"].get("CHF", None),
                "HKD_USD": data["rates"].get("USD", None)
            }
    except Exception as e:
        st.warning(f"⚠️ 无法获取实时汇率数据，请手动输入。原因：{e}")
        return None

rates = get_hkd_rates()

if rates is None or any(v is None for v in rates.values()):
    st.error("请手动输入当前汇率：")
    hkd_to_rmb = st.number_input("HKD兑RMB：", value=0.88, step=0.01)
    hkd_to_usd = st.number_input("HKD兑USD：", value=0.128, step=0.001)
    hkd_to_chf = st.number_input("HKD兑CHF：", value=0.114, step=0.001)
else:
    hkd_to_rmb = rates["HKD_RMB"]
    hkd_to_usd = rates["HKD_USD"]
    hkd_to_chf = rates["HKD_CHF"]

# 识别当前持仓（流出总股数）
holdings = edited_df[edited_df["类型"] == "流出"]
if not holdings.empty and all(col in holdings.columns for col in ["股数", "股票代码", "市场"]):
    grouped = holdings.groupby(["股票代码", "市场"])["股数"].sum().reset_index()
    st.markdown("---")
    st.subheader("📘 当前持仓信息")
    for _, row in grouped.iterrows():
        st.markdown(f"- 股票：{row['股票代码']}（{row['市场']}），当前持仓约：{row['股数']} 股")

    if "00700" in grouped["股票代码"].values:
        tx_shares = float(grouped[grouped["股票代码"] == "00700"]["股数"].values[0])
        st.markdown("---")
        st.subheader("📈 实时市值输入：腾讯控股（00700.HK）")
        tx_price = st.number_input("请输入当前每股价格（港币）", value=320.0)
        market_value_hkd = tx_shares * tx_price
        st.markdown(f"当前市值：{market_value_hkd:.2f} 港币 | 折合：RMB {market_value_hkd * hkd_to_rmb:.2f} | USD {market_value_hkd * hkd_to_usd:.2f} | CHF {market_value_hkd * hkd_to_chf:.2f}")
        # 添加为今日现金流
        edited_df = pd.concat([
            edited_df,
            pd.DataFrame.from_records([{
                "日期": dt.date.today(),
                "金额": market_value_hkd,
                "币种": "HKD",
                "类型": "流入",
                "股票代码": "00700",
                "市场": "港股",
                "股数": tx_shares,
                "买入价格": None
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

# MWR计算入口
if st.button("📊 计算 MWR（按不同币种）"):
    try:
        def convert(df, to_currency):
            rate_map = {"RMB": 1.0, "HKD": hkd_to_rmb, "USD": hkd_to_usd, "CHF": hkd_to_chf}
            return df.apply(
                lambda row: row["金额"] * rate_map.get(row["币种"], 1.0)
                if to_currency == "RMB" else
                row["金额"] * (rate_map.get(row["币种"], 1.0) / rate_map[to_currency]), axis=1)

        for ccy in ["RMB", "USD", "CHF"]:
            cf_df = edited_df.copy()
            cf_df["金额转换"] = convert(cf_df, ccy)
            cf_df_sorted = cf_df.sort_values("日期")
            cash_flows = list(zip(cf_df_sorted["日期"], cf_df_sorted["金额转换"]))
            result = calculate_xirr(cash_flows)
            with st.expander(f"{ccy} 计价 MWR 计算明细"):
                st.dataframe(cf_df_sorted[["日期", "金额", "币种", "类型", "股票代码", "市场", "金额转换"]], use_container_width=True)
                st.success(f"📈 MWR（{ccy}）年化收益率：{result:.2%}")
    except Exception as e:
        st.error(f"计算出错：{e}")
