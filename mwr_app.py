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

# 初始化数据框架为空
def get_input_df():
    return pd.DataFrame({
        "日期": [],
        "金额": [],
        "币种": [],
        "类型": [],
        "兑RMB": [],
        "兑CHF": [],
        "兑USD": []
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

# 以下持仓模块和计算过程代码保持不变...
