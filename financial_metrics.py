"""
财务指标计算模块 - 只包含用户笔记中的核心指标
"""
import pandas as pd
import numpy as np


def safe_divide(num, den):
    if den is None or den == 0 or pd.isna(den):
        return np.nan
    return num / den


def calculate_fcf(cash_flow):
    """
    自由现金流(FCF) = 经营活动现金流净额 - 资本支出
    资本支出 = 购建固定资产、无形资产和其他长期资产所支付的现金
    若无CapEx数据则退化为只用CFO近似
    """
    ocf = cash_flow.get('经营活动产生的现金流量净额')
    if ocf is None:
        return pd.Series(dtype=float)

    capex = cash_flow.get('购建固定资产、无形资产和其他长期资产所支付的现金')
    if capex is not None:
        return ocf - capex

    return ocf


def calculate_gross_profit(income_stmt):
    """毛利润 = 营业总收入 - 营业总成本"""
    revenue = income_stmt.get('营业总收入', income_stmt.get('营业收入'))
    cost = income_stmt.get('营业总成本', income_stmt.get('营业成本'))
    if revenue is None or cost is None:
        return None
    return revenue - cost


def calculate_gross_margin(income_stmt):
    """毛利率 = 毛利润 / 营业总收入"""
    revenue = income_stmt.get('营业总收入', income_stmt.get('营业收入'))
    cost = income_stmt.get('营业总成本', income_stmt.get('营业成本'))
    if revenue is None or cost is None:
        return pd.Series(dtype=float)
    return (revenue - cost).div(revenue) * 100


def calculate_expense_ratio(income_stmt):
    """
    费用占毛利润比率 = (销售+管理+财务+研发) / 毛利润
    判断标准: < 70% 为优秀公司
    """
    gp = calculate_gross_profit(income_stmt)
    if gp is None:
        return pd.Series(dtype=float)

    expense_cols = ['销售费用', '管理费用', '财务费用', '研发费用']
    available = [c for c in expense_cols if c in income_stmt.columns]
    if not available:
        return pd.Series(dtype=float)

    total_expense = income_stmt[available].sum(axis=1)
    return total_expense.div(gp) * 100


def calculate_roe(income_stmt, balance_sheet):
    """ROE = 归母净利润 / 归属母公司股东权益"""
    np_col = '归属于母公司所有者的净利润' if '归属于母公司所有者的净利润' in income_stmt.columns else '净利润'
    eq_col = '归属于母公司股东权益合计' if '归属于母公司股东权益合计' in balance_sheet.columns else None

    net_profit = income_stmt.get(np_col)
    equity = balance_sheet.get(eq_col) if eq_col else None

    if net_profit is None or equity is None:
        return pd.Series(dtype=float)
    return net_profit.div(equity) * 100


def calculate_debt_ratio(balance_sheet):
    """资产负债率 = 负债合计 / 资产总计"""
    total_liab = balance_sheet.get('负债合计')
    total_assets = balance_sheet.get('资产总计')
    if total_liab is None or total_assets is None:
        return pd.Series(dtype=float)
    return total_liab.div(total_assets) * 100


def determine_business_type(income_stmt, balance_sheet):
    """判断商业类型"""
    types = []
    total_assets = balance_sheet.get('资产总计')
    fixed_asset = balance_sheet.get('固定资产净额')
    revenue = income_stmt.get('营业总收入', income_stmt.get('营业收入'))
    rd_expense = income_stmt.get('研发费用')
    total_liab = balance_sheet.get('负债合计')

    if total_assets is not None and fixed_asset is not None and not total_assets.empty:
        latest_fa_ratio = (fixed_asset.iloc[-1] / total_assets.iloc[-1]) * 100 if total_assets.iloc[-1] != 0 else 0
        if latest_fa_ratio > 30:
            types.append(f"重资产型（固定资产占比{latest_fa_ratio:.1f}%）")
        elif latest_fa_ratio < 15:
            types.append(f"轻资产型（固定资产占比{latest_fa_ratio:.1f}%）")

    if revenue is not None and rd_expense is not None and not revenue.empty:
        latest_rd_ratio = (rd_expense.iloc[-1] / revenue.iloc[-1]) * 100 if revenue.iloc[-1] != 0 else 0
        if latest_rd_ratio > 15:
            types.append(f"研发驱动型（研发占比{latest_rd_ratio:.1f}%）")

    if total_liab is not None and total_assets is not None and not total_assets.empty:
        latest_debt_ratio = (total_liab.iloc[-1] / total_assets.iloc[-1]) * 100 if total_assets.iloc[-1] != 0 else 0
        if latest_debt_ratio > 60:
            types.append(f"高杠杆型（资产负债率{latest_debt_ratio:.1f}%）")

    return types if types else ["未分类"]


# ====== 财务质量深度指标 ======

def calculate_current_ratio(balance_sheet):
    """流动比率 = 流动资产合计 / 流动负债合计"""
    ca = balance_sheet.get('流动资产合计')
    cl = balance_sheet.get('流动负债合计')
    if ca is None or cl is None:
        return pd.Series(dtype=float)
    return ca.div(cl.replace(0, np.nan)) * 1


def calculate_quick_ratio(balance_sheet):
    """速动比率 = (流动资产合计 - 存货) / 流动负债合计"""
    ca = balance_sheet.get('流动资产合计')
    inv = balance_sheet.get('存货')
    cl = balance_sheet.get('流动负债合计')
    if ca is None or cl is None:
        return pd.Series(dtype=float)
    inv_val = inv if inv is not None else 0
    return (ca - inv_val).div(cl.replace(0, np.nan))


def calculate_receivable_turnover_days(income_stmt, balance_sheet):
    """应收账款周转天数 = 365 / (营收 / 平均应收账款)"""
    revenue = income_stmt.get('营业总收入', income_stmt.get('营业收入'))
    ar = balance_sheet.get('应收票据及应收账款')
    if revenue is None or ar is None:
        return pd.Series(dtype=float)
    annual_rev = revenue[revenue.index.month == 12]
    annual_ar = ar[ar.index.month == 12]
    if len(annual_ar) < 2:
        avg_ar = annual_ar
    else:
        avg_ar = (annual_ar + annual_ar.shift(1)) / 2
        avg_ar = avg_ar.dropna()
    turnover = annual_rev.reindex(avg_ar.index).div(avg_ar.replace(0, np.nan))
    return 365 / turnover


def calculate_inventory_turnover_days(income_stmt, balance_sheet):
    """存货周转天数 = 365 / (营业成本 / 平均存货)"""
    cost = income_stmt.get('营业总成本', income_stmt.get('营业成本'))
    inv = balance_sheet.get('存货')
    if cost is None or inv is None:
        return pd.Series(dtype=float)
    annual_cost = cost[cost.index.month == 12]
    annual_inv = inv[inv.index.month == 12]
    if len(annual_inv) < 2:
        avg_inv = annual_inv
    else:
        avg_inv = (annual_inv + annual_inv.shift(1)) / 2
        avg_inv = avg_inv.dropna()
    turnover = annual_cost.reindex(avg_inv.index).div(avg_inv.replace(0, np.nan))
    return 365 / turnover


def calculate_cashflow_to_profit_ratio(cash_flow, income_stmt):
    """经营现金流/净利润比 (盈利含金量)"""
    ocf = cash_flow.get('经营活动产生的现金流量净额')
    np_col = '归属于母公司所有者的净利润' if '归属于母公司所有者的净利润' in income_stmt.columns else '净利润'
    net_profit = income_stmt.get(np_col)
    if ocf is None or net_profit is None:
        return pd.Series(dtype=float)
    annual_ocf = ocf[ocf.index.month == 12]
    annual_np = net_profit[net_profit.index.month == 12]
    return annual_ocf.reindex(annual_np.index).div(annual_np.replace(0, np.nan))


def calculate_goodwill_ratio(balance_sheet):
    """商誉占净资产比 = 商誉 / 归属于母公司股东权益合计"""
    gw = balance_sheet.get('商誉')
    eq = balance_sheet.get('归属于母公司股东权益合计')
    if gw is None or eq is None:
        return pd.Series(dtype=float)
    return gw.div(eq.replace(0, np.nan)) * 100


# ====== 成长性指标 ======

def calculate_cagr(series, years=3):
    """计算N年复合年增长率 (CAGR)
    series: pd.Series, 年度数据
    years: 回看年数
    返回: float 或 None
    """
    if series is None or len(series) < years + 1:
        return None
    start = series.iloc[-years - 1]
    end = series.iloc[-1]
    if pd.isna(start) or pd.isna(end) or start <= 0 or end <= 0:
        return None
    return ((end / start) ** (1.0 / years) - 1) * 100


def calculate_quarterly_growth(income_stmt):
    """计算季度营收环比增长率
    返回: pd.DataFrame with columns [quarter, revenue, yoy_growth, qoq_growth]
    """
    revenue_col = '营业总收入' if '营业总收入' in income_stmt.columns else '营业收入'
    if revenue_col not in income_stmt.columns:
        return pd.DataFrame()

    rev = income_stmt[revenue_col].dropna()
    # 累计值转单季值
    single_q = rev.copy()
    for i in range(len(single_q) - 1, 0, -1):
        curr = single_q.index[i]
        prev_idx = None
        for j in range(i - 1, -1, -1):
            if single_q.index[j].year == curr.year:
                prev_idx = j
                break
        if prev_idx is not None:
            single_q.iloc[i] = rev.iloc[i] - rev.iloc[prev_idx]

    # 同比增长率
    yoy = pd.Series(dtype=float, index=single_q.index)
    for i in range(len(single_q)):
        curr = single_q.index[i]
        for j in range(i - 1, -1, -1):
            prev = single_q.index[j]
            if prev.month == curr.month and prev.year == curr.year - 1:
                if single_q.iloc[j] != 0:
                    yoy.iloc[i] = (single_q.iloc[i] / single_q.iloc[j] - 1) * 100
                break

    # 环比增长率
    qoq = single_q.pct_change() * 100

    result = pd.DataFrame({
        'revenue': single_q,
        'yoy': yoy,
        'qoq': qoq,
    }).dropna(subset=['revenue'])

    return result.tail(12)


def calculate_rd_ratio(income_stmt):
    """研发投入占比 = 研发费用 / 营业总收入"""
    revenue = income_stmt.get('营业总收入', income_stmt.get('营业收入'))
    rd = income_stmt.get('研发费用')
    if revenue is None or rd is None:
        return pd.Series(dtype=float)
    annual_rev = revenue[revenue.index.month == 12]
    annual_rd = rd[rd.index.month == 12]
    return annual_rd.reindex(annual_rev.index).div(annual_rev.replace(0, np.nan)) * 100


def build_financial_quality_table(income_stmt, balance_sheet, cash_flow):
    """构建财务质量指标综合表（年度）"""
    annual_inc = income_stmt[income_stmt.index.month == 12]
    annual_bs = balance_sheet[balance_sheet.index.month == 12]
    annual_cf = cash_flow[cash_flow.index.month == 12]

    result = pd.DataFrame(index=annual_bs.index)

    # 资产负债率
    total_liab = annual_bs.get('负债合计')
    total_assets = annual_bs.get('资产总计')
    if total_liab is not None and total_assets is not None:
        result['资产负债率(%)'] = total_liab.div(total_assets.replace(0, np.nan)) * 100

    # 流动比率
    ca = annual_bs.get('流动资产合计')
    cl = annual_bs.get('流动负债合计')
    if ca is not None and cl is not None:
        result['流动比率(倍)'] = ca.div(cl.replace(0, np.nan))

    # 速动比率
    inv = annual_bs.get('存货')
    if ca is not None and cl is not None:
        inv_val = inv if inv is not None else 0
        result['速动比率(倍)'] = (ca - inv_val).div(cl.replace(0, np.nan))

    # 应收账款周转天数
    rev = annual_inc.get('营业总收入', annual_inc.get('营业收入'))
    ar = annual_bs.get('应收票据及应收账款')
    if rev is not None and ar is not None and len(ar) >= 2:
        avg_ar = (ar + ar.shift(1)) / 2
        avg_ar = avg_ar.dropna()
        turnover = rev.reindex(avg_ar.index).div(avg_ar.replace(0, np.nan))
        result['应收账款周转天数(天)'] = 365 / turnover

    # 存货周转天数
    cost = annual_inc.get('营业总成本', annual_inc.get('营业成本'))
    if cost is not None and inv is not None and len(inv) >= 2:
        avg_inv = (inv + inv.shift(1)) / 2
        avg_inv = avg_inv.dropna()
        turnover = cost.reindex(avg_inv.index).div(avg_inv.replace(0, np.nan))
        result['存货周转天数(天)'] = 365 / turnover

    # 现金流/净利润比
    ocf = annual_cf.get('经营活动产生的现金流量净额')
    np_col = '归属于母公司所有者的净利润' if '归属于母公司所有者的净利润' in annual_inc.columns else '净利润'
    net_profit = annual_inc.get(np_col)
    if ocf is not None and net_profit is not None:
        result['现金流/净利润(倍)'] = ocf.reindex(net_profit.index).div(net_profit.replace(0, np.nan))

    # 商誉占净资产比
    gw = annual_bs.get('商誉')
    eq = annual_bs.get('归属于母公司股东权益合计')
    if gw is not None and eq is not None:
        result['商誉/净资产(%)'] = gw.div(eq.replace(0, np.nan)) * 100

    result.index = [str(d.year) for d in result.index]
    result.index.name = '年度'
    return result


# ====== 股息分析指标 ======

def calculate_actual_payout_ratio(cash_flow, income_stmt):
    """
    从现金流量表计算实际派息率
    派息率 = 分配股利、利润或偿付利息支付的现金 / 归母净利润
    返回: pd.Series (年度), 值为派息率(0-1)
    """
    div_paid = cash_flow.get('分配股利、利润或偿付利息支付的现金')
    np_col = '归属于母公司所有者的净利润' if '归属于母公司所有者的净利润' in income_stmt.columns else '净利润'
    net_profit = income_stmt.get(np_col)

    if div_paid is None or net_profit is None:
        return pd.Series(dtype=float)

    annual_div = div_paid[div_paid.index.month == 12]
    annual_np = net_profit[net_profit.index.month == 12]

    payout = annual_div.reindex(annual_np.index).div(annual_np.replace(0, np.nan))
    payout = payout.clip(0, 2)
    return payout.dropna()


def build_dividend_table(dividend_history, cash_flow=None, income_stmt=None):
    """
    构建分红历史展示表
    返回: pd.DataFrame, index=年度
    """
    if not dividend_history:
        return pd.DataFrame()

    df = pd.DataFrame(dividend_history)
    df = df.set_index('report_year')

    display = pd.DataFrame(index=df.index)
    if 'dividend_per_share' in df.columns:
        display['每股股息(元)'] = df['dividend_per_share']
    if 'eps' in df.columns:
        display['每股收益(元)'] = df['eps']
    if 'payout_ratio' in df.columns:
        display['派息率(%)'] = df['payout_ratio'] * 100
    if 'dividend_yield' in df.columns:
        display['股息率(%)'] = df['dividend_yield'] * 100

    display.index.name = '年度'
    return display


def build_income_table(income_stmt, annual_only=True):
    """
    构建利润表展示表（只含用户关心的指标）
    毛利润、毛利率、销售费用、管理费用、财务费用、研发费用、费用占毛利润比率
    """
    df = income_stmt.copy()
    if annual_only:
        df = df[df.index.month == 12]

    result = pd.DataFrame(index=df.index)

    # 毛利润
    revenue = df.get('营业总收入', df.get('营业收入'))
    cost = df.get('营业总成本', df.get('营业成本'))
    if revenue is not None and cost is not None:
        result['毛利润(亿元)'] = (revenue - cost) / 1e8
        result['毛利率(%)'] = (revenue - cost).div(revenue) * 100

    # 四费
    for col in ['销售费用', '管理费用', '财务费用', '研发费用']:
        if col in df.columns:
            result[f'{col}(亿元)'] = df[col] / 1e8

    # 费用占毛利润比率
    if revenue is not None and cost is not None:
        gp = revenue - cost
        expense_cols = [c for c in ['销售费用', '管理费用', '财务费用', '研发费用'] if c in df.columns]
        if expense_cols:
            total_exp = df[expense_cols].sum(axis=1)
            result['费用占毛利润比(%)'] = total_exp.div(gp) * 100

    result.index = [str(d.year) for d in result.index]
    result.index.name = '年度'
    return result


def build_cashflow_table(cash_flow, annual_only=True):
    """
    构建现金流量表展示表（只含用户关心的指标）
    经营现金流净额、投资现金流净额、筹资现金流净额
    """
    df = cash_flow.copy()
    if annual_only:
        df = df[df.index.month == 12]

    result = pd.DataFrame(index=df.index)

    col_map = {
        '经营活动产生的现金流量净额': '经营现金流净额(亿元)',
        '投资活动产生的现金流量净额': '投资现金流净额(亿元)',
        '筹资活动产生的现金流量净额': '筹资现金流净额(亿元)',
    }

    for orig, display in col_map.items():
        if orig in df.columns:
            result[display] = df[orig] / 1e8

    result.index = [str(d.year) for d in result.index]
    result.index.name = '年度'
    return result


def generate_annual_report_analysis(income_stmt, balance_sheet, cash_flow, market_cap=None):
    """
    基于财报数据生成年度报告分析
    返回: list of (section_title, analysis_text)
    """
    analyses = []
    annual_inc = income_stmt[income_stmt.index.month == 12]
    annual_bs = balance_sheet[balance_sheet.index.month == 12]
    annual_cf = cash_flow[cash_flow.index.month == 12]

    if annual_inc.empty:
        return [("提示", "暂无足够的年度报告数据进行分析")]

    latest_year = annual_inc.index[-1].year
    revenue = annual_inc.get('营业总收入', annual_inc.get('营业收入'))
    net_profit = annual_inc.get('归属于母公司所有者的净利润', annual_inc.get('净利润'))
    cost = annual_inc.get('营业总成本', annual_inc.get('营业成本'))

    # 1. 营收分析
    if revenue is not None and not revenue.empty:
        latest_rev = revenue.iloc[-1]
        rev_text = f"{latest_year}年度营业总收入为 {latest_rev/1e8:.2f} 亿元。"
        if len(revenue) >= 2:
            growth = (revenue.iloc[-1] / revenue.iloc[-2] - 1) * 100 if revenue.iloc[-2] != 0 else 0
            rev_text += f" 同比增长 {growth:.1f}%。"
            if len(revenue) >= 3:
                cagr = ((revenue.iloc[-1] / revenue.iloc[0]) ** (1/(len(revenue)-1)) - 1) * 100 if revenue.iloc[0] != 0 else 0
                rev_text += f" 过去{len(revenue)}年复合增长率约 {cagr:.1f}%。"
        analyses.append(("营收分析", rev_text))

    # 2. 盈利能力
    if revenue is not None and cost is not None:
        gp = revenue.iloc[-1] - cost.iloc[-1]
        gm = gp / revenue.iloc[-1] * 100 if revenue.iloc[-1] != 0 else 0
        profit_text = f"{latest_year}年度毛利润为 {gp/1e8:.2f} 亿元，毛利率为 {gm:.1f}%。"
        if net_profit is not None and not net_profit.empty:
            latest_np = net_profit.iloc[-1]
            npm = latest_np / revenue.iloc[-1] * 100 if revenue.iloc[-1] != 0 else 0
            profit_text += f" 归母净利润为 {latest_np/1e8:.2f} 亿元，净利率为 {npm:.1f}%。"
            if latest_np > 0:
                profit_text += " 公司实现盈利。"
            else:
                profit_text += " 公司处于亏损状态。"
        analyses.append(("盈利能力", profit_text))

    # 3. 费用管控
    expense_cols = ['销售费用', '管理费用', '财务费用', '研发费用']
    available_exp = [c for c in expense_cols if c in annual_inc.columns]
    if available_exp and revenue is not None and cost is not None:
        total_exp = annual_inc[available_exp].iloc[-1].sum()
        gp_latest = revenue.iloc[-1] - cost.iloc[-1]
        exp_ratio = total_exp / gp_latest * 100 if gp_latest != 0 else 0
        exp_text = f"{latest_year}年度四费合计 {total_exp/1e8:.2f} 亿元，占毛利润比率为 {exp_ratio:.1f}%。"
        if exp_ratio < 70:
            exp_text += " 该比率低于70%，属于优秀水平，说明公司费用管控能力较强。"
        else:
            exp_text += " 该比率超过70%，费用管控有待改善。"
        if '研发费用' in annual_inc.columns:
            rd = annual_inc['研发费用'].iloc[-1]
            rd_ratio = rd / revenue.iloc[-1] * 100 if revenue.iloc[-1] != 0 else 0
            exp_text += f" 研发费用占营收比率为 {rd_ratio:.1f}%。"
        analyses.append(("费用管控", exp_text))

    # 4. 资产负债
    total_assets = annual_bs.get('资产总计')
    total_liab = annual_bs.get('负债合计')
    if total_assets is not None and total_liab is not None:
        latest_ta = total_assets.iloc[-1]
        latest_tl = total_liab.iloc[-1]
        debt_ratio = latest_tl / latest_ta * 100 if latest_ta != 0 else 0
        equity = latest_ta - latest_tl
        bs_text = f"{latest_year}年度末总资产 {latest_ta/1e8:.2f} 亿元，总负债 {latest_tl/1e8:.2f} 亿元，"
        bs_text += f"资产负债率 {debt_ratio:.1f}%，净资产 {equity/1e8:.2f} 亿元。"
        if debt_ratio < 40:
            bs_text += " 财务结构稳健。"
        elif debt_ratio < 60:
            bs_text += " 财务结构适中。"
        else:
            bs_text += " 负债率较高，需关注偿债能力。"
        analyses.append(("资产负债", bs_text))

    # 5. 现金流质量
    ocf = annual_cf.get('经营活动产生的现金流量净额')
    if ocf is not None and not ocf.empty:
        latest_ocf = ocf.iloc[-1]
        cf_text = f"{latest_year}年度经营活动现金流净额为 {latest_ocf/1e8:.2f} 亿元。"
        if net_profit is not None and not net_profit.empty:
            latest_np = net_profit.iloc[-1]
            if latest_np > 0:
                if latest_ocf > latest_np:
                    cf_text += " 经营现金流大于净利润，盈利质量较高。"
                else:
                    cf_text += " 经营现金流小于净利润，需关注应收账款回收情况。"
            else:
                if latest_ocf > 0:
                    cf_text += " 虽然亏损但经营现金流为正，说明主业造血能力尚可。"
                else:
                    cf_text += " 经营现金流为负，主业造血能力较弱。"
        analyses.append(("现金流质量", cf_text))

    # 6. 估值参考
    if market_cap:
        mc_yi = market_cap.get('market_cap_yi', 0)
        if revenue is not None and not revenue.empty and mc_yi > 0:
            ps = mc_yi / (revenue.iloc[-1] / 1e8) if revenue.iloc[-1] != 0 else 0
            val_text = f"当前总市值约 {mc_yi:.0f} 亿元，市销率(PS)约 {ps:.1f} 倍。"
            if net_profit is not None and not net_profit.empty and net_profit.iloc[-1] > 0:
                pe = mc_yi / (net_profit.iloc[-1] / 1e8)
                val_text += f" 市盈率(PE)约 {pe:.1f} 倍。"
            else:
                val_text += " 公司处于亏损状态，无法计算市盈率。"
            analyses.append(("估值参考", val_text))

    return analyses


def build_dupont_table(income_stmt, balance_sheet):
    """
    杜邦分析: ROE = 净利率 × 总资产周转率 × 权益乘数
    返回: pd.DataFrame, 列 = [年度, 净利率(%), 总资产周转率(次), 权益乘数(倍), ROE(%)]
    """
    annual_inc = income_stmt[income_stmt.index.month == 12]
    annual_bs = balance_sheet[balance_sheet.index.month == 12]

    np_col = '归属于母公司所有者的净利润' if '归属于母公司所有者的净利润' in annual_inc.columns else '净利润'
    rev_col = '营业总收入' if '营业总收入' in annual_inc.columns else '营业收入'

    net_profit = annual_inc.get(np_col)
    revenue = annual_inc.get(rev_col)
    total_assets = annual_bs.get('资产总计')
    eq_col = '归属于母公司股东权益合计' if '归属于母公司股东权益合计' in annual_bs.columns else None
    equity = annual_bs.get(eq_col) if eq_col else None

    if net_profit is None or revenue is None or total_assets is None or equity is None:
        return pd.DataFrame()

    common_idx = net_profit.dropna().index.intersection(revenue.dropna().index) \
                               .intersection(total_assets.dropna().index) \
                               .intersection(equity.dropna().index)
    if len(common_idx) < 2:
        return pd.DataFrame()

    np_s = net_profit.reindex(common_idx)
    rev_s = revenue.reindex(common_idx)
    ta_s = total_assets.reindex(common_idx)
    eq_s = equity.reindex(common_idx)

    avg_ta = (ta_s + ta_s.shift(1)) / 2
    avg_eq = (eq_s + eq_s.shift(1)) / 2
    avg_ta = avg_ta.dropna()
    avg_eq = avg_eq.dropna()
    np_s = np_s.reindex(avg_ta.index)
    rev_s = rev_s.reindex(avg_ta.index)
    avg_eq = avg_eq.reindex(avg_ta.index)

    net_margin = np_s.div(rev_s.replace(0, np.nan)) * 100
    asset_turnover = rev_s.div(avg_ta.replace(0, np.nan))
    equity_multiplier = avg_ta.div(avg_eq.replace(0, np.nan))
    roe = np_s.div(avg_eq.replace(0, np.nan)) * 100

    result = pd.DataFrame({
        '净利率(%)': net_margin.round(2),
        '总资产周转率(次)': asset_turnover.round(3),
        '权益乘数(倍)': equity_multiplier.round(3),
        'ROE(%)': roe.round(2),
    }, index=avg_ta.index)

    result.index.name = '年度'
    return result


def calculate_roe_decomposition_trend(income_stmt, balance_sheet, years=5):
    """
    计算ROE分解各因子的年度变化率，用于判断驱动因素
    返回: dict with 'net_margin', 'asset_turnover', 'equity_multiplier', 'roe' 的变化趋势
    """
    dupont = build_dupont_table(income_stmt, balance_sheet)
    if dupont.empty or len(dupont) < 2:
        return None

    latest = dupont.iloc[-1]
    prev = dupont.iloc[-2]

    return {
        'latest': latest.to_dict(),
        'prev': prev.to_dict(),
        'changes': {
            '净利率': latest['净利率(%)'] - prev['净利率(%)'],
            '总资产周转率': latest['总资产周转率(次)'] - prev['总资产周转率(次)'],
            '权益乘数': latest['权益乘数(倍)'] - prev['权益乘数(倍)'],
            'ROE': latest['ROE(%)'] - prev['ROE(%)'],
        },
        'table': dupont.tail(years),
    }
