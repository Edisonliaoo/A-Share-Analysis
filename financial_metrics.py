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

    return "、".join(types) if types else "未分类"


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
        result['毛利润'] = (revenue - cost) / 1e8
        result['毛利率(%)'] = (revenue - cost).div(revenue) * 100

    # 四费
    for col in ['销售费用', '管理费用', '财务费用', '研发费用']:
        if col in df.columns:
            result[col] = df[col] / 1e8

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
        '经营活动产生的现金流量净额': '经营现金流净额',
        '投资活动产生的现金流量净额': '投资现金流净额',
        '筹资活动产生的现金流量净额': '筹资现金流净额',
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
