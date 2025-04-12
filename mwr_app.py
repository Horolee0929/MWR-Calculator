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

系统将自动识别你投入的资金流、实际买入的股票、当前估值并自动生成收益率。
""")

@st.cache_data
def get_empty_df():
    return pd.DataFrame({
        "买卖方向": pd.Series(dtype="str"),
        "日期": pd.Series(dtype="datetime64[ns]"),
        "金额": pd.Series(dtype="float"),
        "币种": pd.Series(dtype="str"),
        
        "股票代码": pd.Series(dtype="str"),
        "市场": pd.Series(dtype="str"),
        "股数": pd.Series(dtype="float"),
        "价格": pd.Series(dtype="float")
    })

if "cashflow_df" not in st.session_state:
    st.session_state.cashflow_df = get_empty_df()

edited_df = st.data_editor(
    st.session_state.cashflow_df,
    num_rows="dynamic",
    use_container_width=True,
    column_config={
        "买卖方向": st.column_config.SelectboxColumn(options=["现金转入", "现金转出", "买入股票", "卖出股票"]),
        "日期": st.column_config.DateColumn(format="YYYY-MM-DD"),
        "金额": st.column_config.NumberColumn(format="%.2f"),
        "币种": st.column_config.SelectboxColumn(options=["RMB", "HKD", "USD", "CHF"]),
        
        "股票代码": st.column_config.TextColumn(),
        "市场": st.column_config.SelectboxColumn(options=["港股", "美股", "A股", "其他"]),
        "股数": st.column_config.NumberColumn(format="%.2f"),
        "价格": st.column_config.NumberColumn(format="%.2f"),
    },
    key="cashflow_editor"
)



# 自动补金额或买入价格，并自动设置币种与市场一致，金额正负依类型/买卖方向确定
类型映射 = {"现金转入": 1, "卖出股票": 1, "现金转出": -1, "买入股票": -1}

for idx, row in edited_df.iterrows():

    # 自动填写金额（买入或卖出）
    if pd.isna(row["金额"]):
        if pd.notna(row["股数"]) and pd.notna(row["价格"]):
            edited_df.at[idx, "金额"] = row["股数"] * row["价格"]

    # 自动填写价格（当金额已知）
    elif pd.isna(row["价格"]):
        if pd.notna(row["股数"]) and pd.notna(row["金额"]):
            try:
                edited_df.at[idx, "价格"] = row["金额"] / row["股数"]
            except ZeroDivisionError:
                pass

    # 自动设置币种 = 市场（港股→HKD, 美股→USD, A股→RMB）
    if pd.isna(row["币种"]) and pd.notna(row["市场"]):
        if row["市场"] == "港股":
            edited_df.at[idx, "币种"] = "HKD"
        elif row["市场"] == "美股":
            edited_df.at[idx, "币种"] = "USD"
        elif row["市场"] == "A股":
            edited_df.at[idx, "币种"] = "RMB"

    # 自动修正金额符号（流入为正，流出为负）
    if pd.notna(row["金额"]):
        amt = abs(row["金额"])
        if 类型映射.get(row["买卖方向"], 0) == -1:
            edited_df.at[idx, "金额"] = -amt
        elif 类型映射.get(row["买卖方向"], 0) == 1:
            edited_df.at[idx, "金额"] = amt

# 将自定义类型映射为逻辑流向
类型映射 = {"现金转入": 1, "卖出股票": 1, "现金转出": -1, "买入股票": -1}

# 校验股数
incomplete_rows = edited_df[(edited_df["买卖方向"].isin(["买入股票", "现金转出"])) & ((edited_df["股数"].isna()) | (edited_df["股数"] == 0))]
if not incomplete_rows.empty:
    st.error("⚠️ 有投资记录缺少股数，请补全股数后再计算。")
    st.stop()

# 自动生成当前估值记录（使用实时股价 API 或手动输入）
holdings = edited_df[(edited_df["买卖方向"] == "买入股票") & (edited_df["股数"] > 0)]

if not holdings.empty:
    st.markdown("---")
    st.subheader("📘 当前持仓估值输入（自动获取或手动填入价格）")

    estimated_cashflows = []
    grouped = holdings.groupby(["股票代码", "市场", "币种"])["股数"].sum().reset_index()

    for _, row in grouped.iterrows():
        stock_code = row["股票代码"]
        market = row["市场"]
        base_currency = row["币种"]
        shares = row["股数"]

        # 根据市场构建查询代码（这里只处理港股）
        if market == "港股":
            ticker = f"{stock_code}.HK"
        elif market == "美股":
            ticker = "AAPL" if stock_code.upper() == "APPL" else stock_code.upper()
        else:
            ticker = stock_code

        # 默认失败 fallback
        price = None

        # 查询雅虎财经 + 容错机制
        try:
            yurl = f"https://query1.finance.yahoo.com/v7/finance/quote?symbols={ticker}"
            r = requests.get(yurl)
            r.raise_for_status()
            data = r.json()
            results = data.get("quoteResponse", {}).get("result", [])
            if results and "regularMarketPrice" in results[0]:
                price = results[0]["regularMarketPrice"]
            else:
                st.warning(f"⚠️ 无法从返回数据中获取 {ticker} 的收盘价，请手动填写。")
        except Exception as e:
            st.warning(f"⚠️ 获取 {ticker} 的实时价格失败，请手动填写。错误：{e}")
        except:
            st.warning(f"⚠️ 无法获取 {ticker} 的实时股价，请手动填写。")

        final_price = st.number_input(
            f"{stock_code} 当前价格（单位：{base_currency}）",
            min_value=0.0,
            value=price if price is not None else 0.0
        )

        market_value = final_price * shares
        estimated_cashflows.append({
            "日期": dt.date.today(),
            "金额": market_value,
            "币种": base_currency,
            "买卖方向": "卖出股票", # 模拟持仓估值流入，用于计算 XIRR
            "股票代码": stock_code,
            "市场": market,
            "股数": shares,
            "价格": final_price  
        })

    if estimated_cashflows:
        edited_df = pd.concat([edited_df, pd.DataFrame(estimated_cashflows)], ignore_index=True)

# 计算函数

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

# 汇总信息展示

# 🧮 自动计算当前持仓股数 × 当前输入价格
if not edited_df.empty:
    net_positions = edited_df.copy()
    net_positions = net_positions[~(
        (net_positions["买卖方向"] == "卖出股票") &
        (net_positions["金额"].notna()) &
        (net_positions["日期"] == dt.date.today())
    )]
    net_positions["方向"] = net_positions["买卖方向"].map(类型映射).fillna(0)
    net_positions["调整股数"] = net_positions["股数"] * net_positions["方向"]
    stock_summary = net_positions.groupby(["股票代码", "市场", "币种"])["调整股数"].sum().reset_index().rename(columns={"调整股数": "当前持仓"})
    


    st.markdown("---")
    st.subheader("📦 当前股票净持仓（含 previous close price 和持有资产价值）")
    if not stock_summary.empty:
        # 匹配估值价格并计算市值
        market_prices = {
            (row["股票代码"], row["市场"]): row["价格"]
            for row in estimated_cashflows
            if row.get("股票代码") and row.get("市场")
        } if "estimated_cashflows" in locals() else {}
        def get_price_label(row):
            ccy = row["币种"]
            return f"previous close price ({ccy})"

        stock_summary["价格列名"] = stock_summary.apply(get_price_label, axis=1)
        stock_summary["previous close price"] = stock_summary.apply(lambda x: market_prices.get((x["股票代码"], x["市场"]), 0.0), axis=1)
        stock_summary["持有资产价值"] = stock_summary["当前持仓"] * stock_summary["previous close price"]
        stock_summary["持有资产价值列名"] = stock_summary["价格列名"].str.replace("previous close price", "持有资产价值")
        display_df = stock_summary[["股票代码", "市场", "当前持仓", "previous close price", "持有资产价值"]].copy()
        display_df.columns = ["股票代码", "市场", "当前持仓", stock_summary["价格列名"].iloc[0], stock_summary["持有资产价值列名"].iloc[0]]

        st.dataframe(display_df, use_container_width=True)
    else:
        st.info("当前没有任何持仓。")


st.markdown("---")
st.subheader("📊 投资现金流汇总")

summary_df = edited_df[["日期", "金额", "币种", "买卖方向"]].dropna()
summary_df = summary_df.sort_values("日期")
st.dataframe(summary_df, use_container_width=True)

# 计算入口
if st.button("📊 计算 MWR（多币种分别计算）"):
    try:
        cf_df = edited_df.copy()
        cf_df_sorted = cf_df.sort_values("日期")
        currency_groups = cf_df_sorted.groupby("币种")

        st.subheader("📈 各币种计价的 MWR 年化收益率")
        for currency, group in currency_groups:
            group = group.copy()
            cash_flows = []
            for _, row in group.iterrows():
                amt = abs(row["金额"]) if 类型映射.get(row["买卖方向"], 0) == 1 else -abs(row["金额"])
                cash_flows.append((row["日期"], amt))
            try:
                result = calculate_xirr(cash_flows)
                st.markdown(f"**{currency}：{result:.2%}**")
                with st.expander(f"📋 {currency} 现金流明细"):
                    st.dataframe(group[["日期", "金额", "币种", "买卖方向", "股票代码", "市场"]], use_container_width=True)
            except Exception as calc_error:
                st.warning(f"{currency} 计算失败：{calc_error}")

    except Exception as e:
        st.error(f"计算出错：{e}")
