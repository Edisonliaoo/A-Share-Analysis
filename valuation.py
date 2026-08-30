"""
估值分析模块 - DCF、DDM、P/B 估值模型
"""
import pandas as pd
import numpy as np


def calculate_wacc(balance_sheet, income_stmt, market_cap_yuan, beta, risk_free_rate_pct, equity_risk_premium=0.06):
    """
    计算WACC（加权平均资本成本）
    WACC = E/(E+D) × Ke + D/(E+D) × Kd × (1 - tax_rate)
    Ke = Rf + β × ERP (CAPM)
    """
    rf = risk_free_rate_pct / 100
    ke = rf + beta * equity_risk_premium

    total_debt = 0
    for col in ['短期借款', '长期借款', '应付债券']:
        val = balance_sheet.get(col)
        if val is not None and not val.empty:
            v = val.iloc[-1]
            if pd.notna(v):
                total_debt += v

    fin_expense = income_stmt.get('财务费用')
    if fin_expense is not None and not fin_expense.empty and total_debt > 0:
        kd = abs(fin_expense.iloc[-1]) / total_debt
    else:
        kd = 0.05

    pre_tax = income_stmt.get('利润总额')
    net_profit = income_stmt.get('净利润')
    tax_rate = 0.25
    if pre_tax is not None and not pre_tax.empty and net_profit is not None and not net_profit.empty:
        pt = pre_tax.iloc[-1]
        np_val = net_profit.iloc[-1]
        if pd.notna(pt) and pd.notna(np_val) and pt > 0:
            tax_rate = max(0, min(1 - np_val / pt, 0.4))

    E = market_cap_yuan if market_cap_yuan else 0
    D = total_debt
    V = E + D

    if V == 0:
        wacc = ke
    else:
        wacc = (E / V) * ke + (D / V) * kd * (1 - tax_rate)

    return {
        'wacc': wacc,
        'cost_of_equity': ke,
        'cost_of_debt': kd,
        'tax_rate': tax_rate,
        'equity_weight': E / V if V > 0 else 1,
        'debt_weight': D / V if V > 0 else 0,
        'market_cap': E,
        'total_debt': D,
        'beta': beta,
        'risk_free_rate': risk_free_rate_pct,
        'equity_risk_premium': equity_risk_premium,
    }


def dcf_valuation(cash_flow, income_stmt, balance_sheet,
                  growth_rate=0.10, terminal_growth=0.03,
                  discount_rate=0.10, forecast_years=5,
                  shares=None):
    """
    DCF现金流折现模型
    参数:
        growth_rate: 未来N年增长率
        terminal_growth: 永续增长率
        discount_rate: 折现率(WACC)
        forecast_years: 预测年数
        shares: 外部传入的股本数（当资产负债表缺少实收资本时使用）
    返回: dict with 'enterprise_value', 'equity_value', 'per_share_value', 'details'
    """
    from financial_metrics import calculate_fcf

    # 获取FCF历史数据
    fcf_series = calculate_fcf(cash_flow)
    if fcf_series.empty:
        return None

    # 使用近3年平均FCF作为基准（平滑波动，避免单年异常导致的偏差）
    recent_fcf = fcf_series.tail(3).dropna()
    if recent_fcf.empty:
        return None

    # 优先使用正FCF年份的平均值
    positive_fcf = recent_fcf[recent_fcf > 0]
    if not positive_fcf.empty:
        base_fcf = positive_fcf.mean()
    elif recent_fcf.iloc[-1] > 0:
        base_fcf = recent_fcf.iloc[-1]
    else:
        # 近3年FCF全为负，使用营收的3%作为保守估计
        revenue = income_stmt.get('营业总收入', income_stmt.get('营业收入'))
        if revenue is not None and not revenue.empty:
            base_fcf = revenue.iloc[-1] * 0.03
        else:
            return None

    latest_fcf = base_fcf

    # 预测未来FCF
    projected_fcfs = []
    current_fcf = base_fcf
    for year in range(1, forecast_years + 1):
        current_fcf = current_fcf * (1 + growth_rate)
        discounted = current_fcf / ((1 + discount_rate) ** year)
        projected_fcfs.append({
            'year': year,
            'fcf': current_fcf,
            'discount_factor': 1 / ((1 + discount_rate) ** year),
            'discounted_fcf': discounted,
        })

    # 终值
    terminal_fcf = projected_fcfs[-1]['fcf'] * (1 + terminal_growth)
    terminal_value = terminal_fcf / (discount_rate - terminal_growth)
    discounted_terminal = terminal_value / ((1 + discount_rate) ** forecast_years)

    # 企业价值
    enterprise_value = sum(p['discounted_fcf'] for p in projected_fcfs) + discounted_terminal

    # 净债务 = 有息负债 - 现金
    total_debt = 0
    for col in ['短期借款', '长期借款', '应付债券']:
        val = balance_sheet.get(col)
        if val is not None and not val.empty:
            v = val.iloc[-1]
            if pd.notna(v):
                total_debt += v

    monetary = balance_sheet.get('货币资金')
    net_debt = total_debt
    if monetary is not None and not monetary.empty:
        cash = monetary.iloc[-1]
        if pd.notna(cash):
            net_debt = total_debt - cash

    equity_value = enterprise_value - net_debt

    # 每股价值
    share_capital = balance_sheet.get('实收资本(或股本)')
    actual_shares = None
    if share_capital is not None and not share_capital.empty:
        sc_val = share_capital.iloc[-1]
        if pd.notna(sc_val) and sc_val > 0:
            actual_shares = sc_val

    if actual_shares is None or actual_shares <= 0:
        actual_shares = shares

    if actual_shares is None or actual_shares <= 0:
        return None

    per_share = equity_value / actual_shares

    return {
        'enterprise_value': enterprise_value,
        'equity_value': equity_value,
        'per_share_value': per_share,
        'net_debt': net_debt,
        'latest_fcf': latest_fcf,
        'projected_fcfs': projected_fcfs,
        'terminal_value': terminal_value,
        'discounted_terminal': discounted_terminal,
        'shares': actual_shares,
        'params': {
            'growth_rate': growth_rate,
            'terminal_growth': terminal_growth,
            'discount_rate': discount_rate,
            'forecast_years': forecast_years,
        }
    }


def ddm_valuation(income_stmt, balance_sheet,
                  dividend_growth_rate=0.05, discount_rate=0.08,
                  forecast_years=5, shares=None,
                  actual_payout_ratio=None, dividend_history=None):
    """
    DDM股利折现模型 (适用于分红稳定的公司)
    参数:
        actual_payout_ratio: 从现金流量表计算的实际派息率(0-1)
        dividend_history: 分红历史数据列表, 含 dividend_per_share 字段
    """
    np_col = '归属于母公司所有者的净利润' if '归属于母公司所有者的净利润' in income_stmt.columns else '净利润'
    net_profit = income_stmt.get(np_col)
    if net_profit is None or net_profit.empty:
        return None

    latest_profit = net_profit.iloc[-1]
    if pd.isna(latest_profit) or latest_profit <= 0:
        return None

    # 优先使用实际派息率，其次用分红历史推算，最后用默认30%
    if actual_payout_ratio is not None and not actual_payout_ratio.empty:
        recent_payout = actual_payout_ratio.tail(3).mean()
        if pd.notna(recent_payout) and recent_payout > 0:
            payout_ratio = min(max(recent_payout, 0.1), 0.9)
        else:
            payout_ratio = 0.30
    elif dividend_history:
        recent_divs = [d for d in dividend_history if d.get('dividend_per_share') and d['dividend_per_share'] > 0]
        if recent_divs:
            latest_div_data = recent_divs[-1]
            hist_payout = latest_div_data.get('payout_ratio')
            if hist_payout and hist_payout > 0:
                payout_ratio = min(max(hist_payout, 0.1), 0.9)
            else:
                payout_ratio = 0.30
        else:
            payout_ratio = 0.30
    else:
        payout_ratio = 0.30

    latest_dividend = latest_profit * payout_ratio

    # Gordon增长模型
    if discount_rate <= dividend_growth_rate:
        return None

    # 多阶段DDM
    projected_dividends = []
    current_div = latest_dividend
    for year in range(1, forecast_years + 1):
        current_div = current_div * (1 + dividend_growth_rate)
        discounted = current_div / ((1 + discount_rate) ** year)
        projected_dividends.append({
            'year': year,
            'dividend': current_div,
            'discounted': discounted,
        })

    terminal_div = projected_dividends[-1]['dividend'] * (1 + dividend_growth_rate)
    terminal_value = terminal_div / (discount_rate - dividend_growth_rate)
    discounted_terminal = terminal_value / ((1 + discount_rate) ** forecast_years)

    equity_value = sum(p['discounted'] for p in projected_dividends) + discounted_terminal

    share_capital = balance_sheet.get('实收资本(或股本)')
    actual_shares = None
    if share_capital is not None and not share_capital.empty:
        sc_val = share_capital.iloc[-1]
        if pd.notna(sc_val) and sc_val > 0:
            actual_shares = sc_val

    if actual_shares is None or actual_shares <= 0:
        actual_shares = shares

    if actual_shares is None or actual_shares <= 0:
        return None

    per_share = equity_value / actual_shares

    return {
        'equity_value': equity_value,
        'per_share_value': per_share,
        'latest_dividend': latest_dividend,
        'payout_ratio': payout_ratio,
        'projected_dividends': projected_dividends,
        'terminal_value': terminal_value,
        'params': {
            'dividend_growth_rate': dividend_growth_rate,
            'discount_rate': discount_rate,
            'forecast_years': forecast_years,
            'payout_ratio': payout_ratio,
        }
    }


def pb_valuation(balance_sheet, market_cap=None, current_price=None, shares=None):
    """
    P/B 市净率估值
    """
    equity = balance_sheet.get('归属于母公司股东权益合计', balance_sheet.get('所有者权益合计'))
    share_capital = balance_sheet.get('实收资本(或股本)')

    if equity is None or equity.empty:
        return None

    latest_equity = equity.iloc[-1]

    actual_shares = None
    if share_capital is not None and not share_capital.empty:
        sc_val = share_capital.iloc[-1]
        if pd.notna(sc_val) and sc_val > 0:
            actual_shares = sc_val

    if actual_shares is None or actual_shares <= 0:
        actual_shares = shares

    if actual_shares is None or actual_shares <= 0:
        return None

    bvps = latest_equity / actual_shares if actual_shares > 0 else 0  # 每股净资产

    result = {
        'total_equity': latest_equity,
        'shares': actual_shares,
        'bvps': bvps,  # 每股净资产
        'book_value': latest_equity,
    }

    if current_price and current_price > 0:
        result['current_price'] = current_price
        result['pb_ratio'] = current_price / bvps if bvps > 0 else np.nan

    if market_cap and market_cap > 0:
        result['market_cap'] = market_cap
        result['pb_ratio'] = market_cap / latest_equity if latest_equity > 0 else np.nan

    return result


def pe_valuation(income_stmt, current_price=None, market_cap=None):
    """
    P/E 市盈率估值
    """
    np_col = '归属于母公司所有者的净利润' if '归属于母公司所有者的净利润' in income_stmt.columns else '净利润'
    net_profit = income_stmt.get(np_col)
    share_capital_idx = None  # Need balance sheet for shares
    eps = income_stmt.get('基本每股收益')

    if net_profit is None or net_profit.empty:
        return None

    latest_profit = net_profit.iloc[-1]
    if pd.isna(latest_profit):
        return None

    result = {
        'net_profit': latest_profit,
    }

    if eps is not None and not eps.empty:
        latest_eps = eps.iloc[-1]
        result['eps'] = latest_eps
        if current_price and current_price > 0 and latest_eps and latest_eps > 0:
            result['pe_ratio'] = current_price / latest_eps

    if market_cap and market_cap > 0 and latest_profit and latest_profit > 0:
        result['market_cap'] = market_cap
        result['pe_ratio'] = market_cap / latest_profit

    return result


def dcf_sensitivity(cash_flow, income_stmt, balance_sheet,
                     growth_rates=None, discount_rates=None,
                     terminal_growth=0.03, forecast_years=5,
                     shares=None):
    """
    DCF敏感性分析: 不同增长率×折现率组合下的每股估值
    返回: dict with 'matrix' (pd.DataFrame), 'growth_rates', 'discount_rates'
    """
    if growth_rates is None:
        growth_rates = [0.03, 0.05, 0.08, 0.10, 0.12, 0.15, 0.20]
    if discount_rates is None:
        discount_rates = [0.06, 0.08, 0.10, 0.12, 0.15, 0.18]

    matrix = pd.DataFrame(index=[f"{g*100:.0f}%" for g in growth_rates],
                         columns=[f"{d*100:.0f}%" for d in discount_rates],
                         dtype=float)

    for g in growth_rates:
        for d in discount_rates:
            if d <= terminal_growth:
                matrix.loc[f"{g*100:.0f}%", f"{d*100:.0f}%"] = np.nan
                continue
            result = dcf_valuation(
                cash_flow, income_stmt, balance_sheet,
                growth_rate=g, terminal_growth=terminal_growth,
                discount_rate=d, forecast_years=forecast_years,
                shares=shares,
            )
            if result and result.get('per_share_value') is not None:
                matrix.loc[f"{g*100:.0f}%", f"{d*100:.0f}%"] = result['per_share_value']
            else:
                matrix.loc[f"{g*100:.0f}%", f"{d*100:.0f}%"] = np.nan

    matrix.index.name = '增长率'
    matrix.columns.name = '折现率'

    return {
        'matrix': matrix,
        'growth_rates': growth_rates,
        'discount_rates': discount_rates,
    }
