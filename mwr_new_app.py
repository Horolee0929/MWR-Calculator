import streamlit as st
import pandas as pd
import numpy as np
import datetime as dt
import requests
import datetime as dt
today = dt.date.today()

def get_historical_rate(date_str, base_currency, target_currency):
    url = f"https://api.exchangerate.host/{date_str}"
    params = {"base": base_currency, "symbols": target_currency}
    try:
        response = requests.get(url, params=params, timeout=5)
        response.raise_for_status()
        data = response.json()
        return data["rates"].get(target_currency, None)
    except:
        return None

st.set_page_config(page_title="MWR计算器", layout="centered")

st.title("💰 多币种 MWR（资金加权收益率）计算器")
st.markdown("""
请在下方表格中填写每一笔投资记录，包含：
- 日期
- 金额
- 币种（RMB / HKD / USD / CHF）
- 类型（流入：卖出或当前估值，流出：买入或转入）
- 股票信息（可选）：买了哪只股票、股数、每股价格
系统将自动识别你投入的资金流、实际买入的股票、当前估值并自动生成收益率。
""")

@st.cache_data
def get_empty_df():
    return pd.DataFrame({
        "日期": pd.Series(dtype="datetime64[ns]"),
        "买卖方向": pd.Series(dtype="str"),
        "股票代码": pd.Series(dtype="str"),
        "币种": pd.Series(dtype="str"),
        "价格": pd.Series(dtype="float"),
        "股数": pd.Series(dtype="float"),
        "汇率": pd.Series(dtype="float"),
        "目标币种": pd.Series(dtype="str"),
        "金额": pd.Series(dtype="float"),
    })

if "cashflow_df" not in st.session_state:
    st.session_state.cashflow_df = get_empty_df()

edited_df = st.session_state.cashflow_df.copy()

# 自动补汇率
for idx, row in edited_df.iterrows():
    if pd.notna(row["日期"]) and pd.notna(row["币种"]) and pd.notna(row["目标币种"]):
        if pd.isna(row["汇率"]):
            rate = get_historical_rate(str(row["日期"].date()), row["币种"], row["目标币种"])
            if rate is not None:
                edited_df.at[idx, "汇率"] = rate
            else:
                st.warning(f"⚠️ 无法获取 {row['日期'].date()} 从 {row['币种']} 到 {row['目标币种']} 的汇率，请手动输入。")

# 自动计算金额（以目标币种为计价）
for idx, row in edited_df.iterrows():
    if pd.isna(row["金额"]):
        if pd.notna(row["股数"]) and pd.notna(row["价格"]) and pd.notna(row["汇率"]):
            edited_df.at[idx, "金额"] = row["股数"] * row["价格"] * row["汇率"]

# 显示表格并可编辑除了金额列
st.data_editor(
    edited_df,
    num_rows="dynamic",
    use_container_width=True,
    key="cashflow_editor",
    column_config={
        "日期": st.column_config.DateColumn(format="YYYY-MM-DD"),
        "买卖方向": st.column_config.SelectboxColumn(options=["现金转入", "现金转出", "买入股票", "卖出股票"]),
        "股票代码": st.column_config.TextColumn(),
        "币种": st.column_config.SelectboxColumn(options=["RMB", "HKD", "USD", "CHF"]),
        "价格": st.column_config.NumberColumn(format="%.2f"),
        "股数": st.column_config.NumberColumn(format="%.2f"),
        "汇率": st.column_config.NumberColumn(format="%.4f"),
        "目标币种": st.column_config.SelectboxColumn(options=["RMB", "CHF"]),
        "金额": st.column_config.NumberColumn(format="%.2f"),
    }
)

disabled=["金额"] 

# 同步回 session_state
st.session_state.cashflow_df = edited_df
