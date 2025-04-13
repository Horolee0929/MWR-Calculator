import streamlit as st
import pandas as pd
import numpy as np
import datetime as dt
import requests
import datetime as dt
today = dt.date.today()


st.set_page_config(page_title="MWR计算器", layout="centered")

st.title("💰 多币种 MWR（资金加权收益率）计算器")
st.markdown("""
请在下方表格中填写每一笔投资记录，包含：
- 日期
- 金额
- 币种（CNY / HKD / USD / CHF）
- 类型（流入：卖出或当前估值，流出：买入或转入）
- 股票信息（可选）：买了哪只股票、股数、每股价格
系统将自动识别你投入的资金流、实际买入的股票、当前估值并自动生成收益率。
""")

# 初始化表格
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

# ✅ 使用 Frankfurter API 获取历史汇率
def get_historical_rate(date_str, base_currency, target_currency):
    if base_currency == target_currency:
        return 1.0

    url = f"https://api.frankfurter.app/{date_str}"
    params = {"from": base_currency, "to": target_currency}
    try:
        response = requests.get(url, params=params, timeout=5)
        response.raise_for_status()
        data = response.json()
        rate = data["rates"].get(target_currency)
        if rate is None:
            st.warning(f"⚠️ Frankfurter 不支持 {base_currency} → {target_currency} 的汇率，请手动输入。")
        return rate
    except Exception as e:
        st.warning(f"❌ 无法获取汇率 {base_currency} → {target_currency}，请手动输入。错误信息：{e}")
        return None

# ✅ 自动更新汇率 & 金额
def update_cashflow_df(df):
    for idx, row in df.iterrows():
        try:
            direction = row["买卖方向"]
            base = row["币种"]
            target = row["目标币种"]
            price = float(row["价格"]) if pd.notna(row["价格"]) else None
            qty = float(row["股数"]) if pd.notna(row["股数"]) else None
            rate = float(row["汇率"]) if pd.notna(row["汇率"]) else None
            amount = row["金额"]

            # 自动补汇率
            if pd.notna(row["日期"]) and pd.notna(base) and pd.notna(target):
                if pd.isna(row["汇率"]) and base != target:
                    date_str = str(min(today, row["日期"].date()))
                    fetched_rate = get_historical_rate(date_str, base, target)
                    if fetched_rate is not None:
                        df.at[idx, "汇率"] = fetched_rate
                        rate = fetched_rate

            # 金额计算逻辑
            if direction in ["买入股票", "卖出股票"]:
                if price is not None and qty is not None and rate is not None:
                    df.at[idx, "金额"] = price * qty * rate

            elif direction in ["现金转入", "现金转出"]:
                if base == target:
                    if pd.notna(amount) and direction == "现金转出":
                        df.at[idx, "金额"] = -abs(float(amount))
                else:
                    if rate is not None and pd.notna(amount):
                        converted_amount = float(amount) * rate
                        if direction == "现金转出":
                            converted_amount = -abs(converted_amount)
                        df.at[idx, "金额"] = converted_amount
        except Exception as e:
            st.warning(f"第 {idx+1} 行金额处理失败：{e}")
    return df

# ✅ 显示可编辑表格
edited_df = st.data_editor(
    st.session_state.cashflow_df,
    num_rows="dynamic",
    use_container_width=True,
    key="cashflow_editor",
    column_config={
        "日期": st.column_config.DateColumn(format="YYYY-MM-DD"),
        "买卖方向": st.column_config.SelectboxColumn(options=["现金转入", "现金转出", "买入股票", "卖出股票"]),
        "股票代码": st.column_config.TextColumn(),
        "币种": st.column_config.SelectboxColumn(options=["CNY", "HKD", "USD", "CHF"]),
        "价格": st.column_config.NumberColumn(format="%.2f"),
        "股数": st.column_config.NumberColumn(format="%.2f"),
        "汇率": st.column_config.NumberColumn(format="%.4f"),
        "目标币种": st.column_config.SelectboxColumn(options=["CNY", "HKD", "USD", "CHF"]),
        "金额": st.column_config.NumberColumn(format="%.2f"),
    }
)

st.markdown("📌 如修改了汇率或价格，请点击下方按钮以重新计算金额。")


    
if st.button("🔄 重新计算金额"):
    updated_df = edited_df.copy()

    # ✅ 清空币种变化后的汇率
    for idx, row in updated_df.iterrows():
        if pd.notna(row["币种"]) and pd.notna(row["目标币种"]) and row["币种"] != row["目标币种"]:
            updated_df.at[idx, "汇率"] = None  # 强制重新抓汇率

    updated_df = update_cashflow_df(updated_df)
    st.session_state.cashflow_df = updated_df
    st.success("✅ 金额和汇率已重新计算，请查看上方表格。")

