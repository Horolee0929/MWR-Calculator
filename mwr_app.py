import streamlit as st
import pandas as pd
import numpy as np
import datetime as dt

st.set_page_config(page_title="MWR计算器", layout="centered")

st.title("💰 多币种 MWR（资金加权收益率）计算器")
st.markdown("""
此工具支持使用 **RMB / CHF / USD** 作为基准币种，输入你的交易记录（资金流入和流出），并计算每种币种下的 MWR。

示例：
- 2023-01-01：你投入 1000 元人民币
- 2023-03-01：你用人民币买入了港币计价的腾讯
- 2025-04-12（今天）：你仍持有腾讯股票，估值为当前港币价格 × 汇率后填入 "流入"

请填入你的交易记录：
- 金额：交易金额（正数表示资金流入，负数表示资金流出）
- 币种：交易使用的币种（RMB, CHF, USD, HKD）
- 类型："流入" 表示账户收到资金（如资产变现或当前估值），"流出" 表示投入资金
- 汇率：将该币种换算到 RMB / CHF / USD 的对应汇率（系统不会自动拉汇率）
""")

st.markdown("---")

# 初始化数据框架

def get_input_df():
    return pd.DataFrame({
        "日期": [
            dt.date(2023, 1, 1),
            dt.date(2023, 3, 1),
            dt.date(2025, 4, 12)
        ],
        "金额": [
            -1000.0,  # 投入人民币
            -500.0,   # 用人民币买入港股腾讯
            2500.0    # 当前腾讯估值（港币）
        ],
        "币种": [
            "RMB",
            "RMB",
            "HKD"
        ],
        "类型": [
            "流出",
            "流出",
            "流入"
        ],
        "兑RMB": [
            1.0,
            1.0,
            0.88  # 当前港币兑人民币汇率
        ],
        "兑CHF": [
            0.13,
            0.13,
            0.114
        ],
        "兑USD": [
            0.14,
            0.14,
            0.128
        ]
    })

# 用户上传或编辑数据表
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

# 资产估值部分：输入腾讯股票估值币种
st.markdown("---")
st.subheader("📊 当前腾讯股票估值")
selected_currency = st.selectbox("请选择你想查看当前市值的币种：", ["港币 (HKD)", "人民币 (RMB)", "美元 (USD)", "瑞士法郎 (CHF)"])
current_hkd_value = 2500  # 示例值，可改为用户输入

# 汇率（可连接 API 自动获取）
hkd_to_rmb = 0.88
hkd_to_usd = 0.128
hkd_to_chf = 0.114

if selected_currency == "港币 (HKD)":
    st.info(f"当前持仓价值：{current_hkd_value} 港币")
elif selected_currency == "人民币 (RMB)":
    st.info(f"当前持仓价值：{current_hkd_value * hkd_to_rmb:.2f} 元人民币")
elif selected_currency == "美元 (USD)":
    st.info(f"当前持仓价值：{current_hkd_value * hkd_to_usd:.2f} 美元")
elif selected_currency == "瑞士法郎 (CHF)":
    st.info(f"当前持仓价值：{current_hkd_value * hkd_to_chf:.2f} 瑞郎")

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

        mwr_rmb = calculate_xirr(build_cf(total_rows, "兑RMB"))
        mwr_chf = calculate_xirr(build_cf(total_rows, "兑CHF"))
        mwr_usd = calculate_xirr(build_cf(total_rows, "兑USD"))

        st.success(f"MWR（RMB 计）：{mwr_rmb:.2%} 年化")
        st.success(f"MWR（CHF 计）：{mwr_chf:.2%} 年化")
        st.success(f"MWR（USD 计）：{mwr_usd:.2%} 年化")

    except Exception as e:
        st.error(f"发生错误：{e}")
