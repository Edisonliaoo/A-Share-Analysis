"""
可视化模块 - 三张核心图表 + 辅助图表
按用户图片效果设计
"""
import plotly.graph_objects as go
import pandas as pd
import numpy as np
from plotly.subplots import make_subplots

# 颜色
C_BLUE = '#00A0E9'
C_RED = '#E60012'
C_DARK_RED = '#8B1A2B'
C_GREEN = '#16a34a'
C_PURPLE = '#7c3aed'
C_ORANGE = '#ea580c'


def plot_revenue_vs_market_cap(income_stmt, market_cap_yi=None, period='quarterly'):
    """
    图表1: 总营收(蓝色柱) vs 总市值(红色线) - 双轴柱线图
    income_stmt: 利润表DataFrame（含季度数据）
    market_cap_yi: 当前总市值（亿元），float
    period: 'quarterly' 或 'annual'
    """
    revenue_col = '营业总收入' if '营业总收入' in income_stmt.columns else '营业收入'
    if revenue_col not in income_stmt.columns:
        return None

    revenue = income_stmt[revenue_col].dropna()

    if period == 'annual':
        revenue = revenue[revenue.index.month == 12]

    # 构造X轴标签
    dates = revenue.index
    if period == 'quarterly':
        labels = [d.strftime('%Y-Q') + str((d.month - 1) // 3 + 1) for d in dates]
    else:
        labels = [str(d.year) for d in dates]

    fig = make_subplots(specs=[[{"secondary_y": True}]])

    # 总营收 - 蓝色柱状图（左轴）
    fig.add_trace(
        go.Bar(
            x=labels,
            y=[v / 1e8 for v in revenue.values],
            name='总营收',
            marker_color=C_BLUE,
            opacity=0.85,
        ),
        secondary_y=False,
    )

    # 总市值 - 红色线（右轴）
    if market_cap_yi and market_cap_yi > 0:
        fig.add_trace(
            go.Scatter(
                x=labels,
                y=[market_cap_yi] * len(labels),
                name=f'总市值(当前 {market_cap_yi:.0f}亿)',
                line=dict(color=C_RED, width=2),
                mode='lines+markers',
                marker=dict(size=6),
            ),
            secondary_y=True,
        )

    fig.update_xaxes(title_text="报告期", tickangle=-45)
    fig.update_yaxes(title_text="总营收 (亿元)", secondary_y=False)
    fig.update_yaxes(title_text="总市值 (亿元)", secondary_y=True)
    fig.update_layout(
        title="总营收与总市值趋势",
        hovermode='x unified',
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        height=450,
        barmode='group',
    )
    return fig


def plot_revenue_vs_cashflow(income_stmt, cash_flow, period='quarterly'):
    """
    图表2: 主营收(蓝色线) vs 主业现金流(红色线) - 双线图
    """
    revenue_col = '营业总收入' if '营业总收入' in income_stmt.columns else '营业收入'
    if revenue_col not in income_stmt.columns:
        return None

    revenue = income_stmt[revenue_col].dropna()
    ocf = cash_flow.get('经营活动产生的现金流量净额')
    if ocf is not None:
        ocf = ocf.dropna()

    if period == 'annual':
        revenue = revenue[revenue.index.month == 12]
        if ocf is not None:
            ocf = ocf[ocf.index.month == 12]

    dates = revenue.index
    if period == 'quarterly':
        labels = [d.strftime('%Y-Q') + str((d.month - 1) // 3 + 1) for d in dates]
    else:
        labels = [str(d.year) for d in dates]

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=labels,
        y=[v / 1e8 for v in revenue.values],
        name='主营收',
        line=dict(color=C_BLUE, width=2),
        mode='lines+markers',
    ))

    if ocf is not None and not ocf.empty:
        # 对齐index
        ocf_aligned = ocf.reindex(revenue.index)
        fig.add_trace(go.Scatter(
            x=labels,
            y=[v / 1e8 if pd.notna(v) else None for v in ocf_aligned.values],
            name='主业现金流',
            line=dict(color=C_DARK_RED, width=2),
            mode='lines+markers',
        ))

    fig.update_layout(
        title="主营收与主业现金流趋势",
        xaxis_title="报告期",
        yaxis_title="金额 (亿元)",
        hovermode='x unified',
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        height=400,
        xaxis_tickangle=-45,
    )
    return fig


def plot_balance_sheet_bar(balance_sheet, is_annual=True):
    """
    图表3: 资产负债表柱状图
    资产项蓝色, 负债项红色
    按用户图片中的项目显示
    """
    from data_fetcher import BS_ASSET_ITEMS, BS_LIAB_ITEMS

    if balance_sheet.empty:
        return None

    # 使用最新年度数据
    if is_annual:
        annual = balance_sheet[balance_sheet.index.month == 12]
        if annual.empty:
            annual = balance_sheet
        latest = annual.iloc[-1]
        date_label = str(annual.index[-1].year)
    else:
        latest = balance_sheet.iloc[-1]
        date_label = balance_sheet.index[-1].strftime('%Y-%m-%d')

    categories = []
    values = []
    colors = []

    # 资产项（蓝色）
    for label, col_name in BS_ASSET_ITEMS:
        if col_name is not None and col_name in latest.index:
            val = latest[col_name]
            if pd.notna(val) and val != 0:
                categories.append(label)
                values.append(abs(val) / 1e8)
                colors.append(C_BLUE)
        elif col_name is None:
            # 特殊处理：无形&商誉 = 无形资产 + 商誉
            val = 0
            if '无形资产' in latest.index and pd.notna(latest['无形资产']):
                val += abs(latest['无形资产'])
            if '商誉' in latest.index and pd.notna(latest['商誉']):
                val += abs(latest['商誉'])
            if val > 0:
                categories.append(label)
                values.append(val / 1e8)
                colors.append(C_BLUE)

    # 负债项（红色）
    for label, col_name in BS_LIAB_ITEMS:
        if col_name is not None and col_name in latest.index:
            val = latest[col_name]
            if pd.notna(val) and val != 0:
                categories.append(label)
                values.append(abs(val) / 1e8)
                colors.append(C_RED)
        elif col_name is None:
            # 特殊处理：薪酬&税 = 应付职工薪酬 + 应交税费
            val = 0
            if '应付职工薪酬' in latest.index and pd.notna(latest['应付职工薪酬']):
                val += abs(latest['应付职工薪酬'])
            if '应交税费' in latest.index and pd.notna(latest['应交税费']):
                val += abs(latest['应交税费'])
            if val > 0:
                categories.append(label)
                values.append(val / 1e8)
                colors.append(C_RED)

    fig = go.Figure(data=[
        go.Bar(
            x=categories,
            y=values,
            marker_color=colors,
            text=[f"{v:.2f}" for v in values],
            textposition='outside',
            textfont=dict(size=11),
        )
    ])
    fig.update_layout(
        title=f"资产负债表结构 ({date_label})",
        xaxis_title="项目",
        yaxis_title="金额 (亿元)",
        xaxis_tickangle=0,
        height=500,
        showlegend=False,
        margin=dict(b=120),
    )
    return fig


def plot_roe_trend(income_stmt, balance_sheet):
    """ROE趋势图（年度）"""
    annual_inc = income_stmt[income_stmt.index.month == 12]
    annual_bs = balance_sheet[balance_sheet.index.month == 12]

    net_profit = annual_inc.get('归属于母公司所有者的净利润', annual_inc.get('净利润'))
    equity = annual_bs.get('归属于母公司股东权益合计')

    if net_profit is None or equity is None:
        return None

    roe = net_profit.div(equity) * 100
    roe = roe.dropna()
    if roe.empty:
        return None

    years = [str(d.year) for d in roe.index]
    
    # 计算更宽阔的Y轴范围（减少视觉波动感）
    y_min, y_max = roe.min(), roe.max()
    y_range = y_max - y_min
    y_padding = max(y_range * 0.4, 5)  # 至少5个百分点的padding
    y_floor = max(y_min - y_padding, -20)
    y_ceil = y_max + y_padding
    
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=years, y=roe.values, name='ROE',
        marker_color=C_PURPLE,
        text=[f"{v:.2f}%" for v in roe.values],
        textposition='outside',
    ))
    fig.update_layout(
        title="ROE 趋势 (年度)",
        xaxis_title="年度", yaxis_title="ROE (%)",
        height=350,
        yaxis=dict(range=[y_floor, y_ceil]),
    )
    return fig


def plot_gross_margin_trend(income_stmt):
    """毛利率趋势图（年度）"""
    annual = income_stmt[income_stmt.index.month == 12]
    revenue = annual.get('营业总收入', annual.get('营业收入'))
    cost = annual.get('营业总成本', annual.get('营业成本'))

    if revenue is None or cost is None:
        return None

    margin = (revenue - cost).div(revenue) * 100
    margin = margin.dropna()
    if margin.empty:
        return None

    years = [str(d.year) for d in margin.index]
    
    # 计算更宽阔的Y轴范围
    y_min, y_max = margin.min(), margin.max()
    y_range = y_max - y_min
    y_padding = max(y_range * 0.4, 5)
    y_floor = max(y_min - y_padding, -10)
    y_ceil = min(y_max + y_padding, 100)
    
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=years, y=margin.values, name='毛利率',
        marker_color=C_GREEN,
        text=[f"{v:.1f}%" for v in margin.values],
        textposition='outside',
    ))
    fig.update_layout(
        title="毛利率趋势 (年度)",
        xaxis_title="年度", yaxis_title="毛利率 (%)",
        height=350,
        yaxis=dict(range=[y_floor, y_ceil]),
    )
    return fig


def plot_expense_ratio_trend(income_stmt):
    """费用占毛利润比率趋势"""
    annual = income_stmt[income_stmt.index.month == 12]
    revenue = annual.get('营业总收入', annual.get('营业收入'))
    cost = annual.get('营业总成本', annual.get('营业成本'))

    if revenue is None or cost is None:
        return None

    gross_profit = revenue - cost

    expense_cols = ['销售费用', '管理费用', '财务费用', '研发费用']
    available = [c for c in expense_cols if c in annual.columns]
    if not available:
        return None

    total_expense = annual[available].sum(axis=1)
    ratio = total_expense.div(gross_profit) * 100
    ratio = ratio.replace([np.inf, -np.inf], np.nan).dropna()

    if ratio.empty:
        return None

    years = [str(d.year) for d in ratio.index]
    
    # 计算更宽阔的Y轴范围
    y_min, y_max = ratio.min(), ratio.max()
    y_range = y_max - y_min
    y_padding = max(y_range * 0.4, 10)
    y_floor = max(y_min - y_padding, -10)
    y_ceil = y_max + y_padding
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=years, y=ratio.values, name='费用占毛利润比率',
        line=dict(color=C_ORANGE, width=2),
        mode='lines+markers',
        text=[f"{v:.1f}%" for v in ratio.values],
        textposition='top center',
    ))
    # 70%基准线
    fig.add_hline(y=70, line_dash="dash", line_color="gray",
                  annotation_text="优秀线 70%")
    fig.update_layout(
        title="费用占毛利润比率趋势 (年度)",
        xaxis_title="年度", yaxis_title="比率 (%)",
        height=350,
        yaxis=dict(range=[y_floor, y_ceil]),
    )
    return fig


def plot_cashflow_trend(cash_flow, period='annual'):
    """三大现金流趋势图"""
    if period == 'annual':
        cf = cash_flow[cash_flow.index.month == 12]
    else:
        cf = cash_flow

    ocf = cf.get('经营活动产生的现金流量净额')
    icf = cf.get('投资活动产生的现金流量净额')
    fcf = cf.get('筹资活动产生的现金流量净额')

    if ocf is None:
        return None

    if period == 'annual':
        labels = [str(d.year) for d in cf.index]
    else:
        labels = [d.strftime('%Y-Q') + str((d.month - 1) // 3 + 1) for d in cf.index]

    fig = go.Figure()
    fig.add_trace(go.Bar(x=labels, y=[v/1e8 if pd.notna(v) else 0 for v in ocf.values],
                         name='经营现金流', marker_color=C_BLUE))
    if icf is not None:
        fig.add_trace(go.Bar(x=labels, y=[v/1e8 if pd.notna(v) else 0 for v in icf.values],
                             name='投资现金流', marker_color=C_RED))
    if fcf is not None:
        fig.add_trace(go.Bar(x=labels, y=[v/1e8 if pd.notna(v) else 0 for v in fcf.values],
                             name='筹资现金流', marker_color=C_GREEN))

    fig.update_layout(
        title="三大现金流趋势",
        xaxis_title="报告期", yaxis_title="金额 (亿元)",
        barmode='group', height=350,
        xaxis_tickangle=-45,
    )
    return fig


# ====== 新增图表：业绩趋势分析 ======

def plot_revenue_marketcap_trend(income_stmt, historical_mc_df):
    """
    业绩趋势分析图表1: 公司总营收(年度柱) & 公司市值走势(月度线)
    使用datetime作为x轴，确保柱状图和折线图正确对齐
    """
    revenue_col = '营业总收入' if '营业总收入' in income_stmt.columns else '营业收入'
    if revenue_col not in income_stmt.columns:
        return None

    annual_inc = income_stmt[income_stmt.index.month == 12]
    revenue = annual_inc[revenue_col].dropna()

    # 取最近10年
    if len(revenue) > 10:
        revenue = revenue.iloc[-10:]

    if revenue.empty:
        return None

    # 使用datetime作为x轴（年终日期）
    bar_dates = revenue.index

    fig = make_subplots(specs=[[{"secondary_y": True}]])

    # 总营收 - 蓝色柱状图（左轴），使用实际日期
    fig.add_trace(
        go.Bar(
            x=bar_dates,
            y=[v / 1e8 for v in revenue.values],
            name='总营收',
            marker_color=C_BLUE,
            opacity=0.85,
            text=[f"{v/1e8:.0f}" for v in revenue.values],
            textposition='outside',
            width=200 * 24 * 3600 * 1000,  # 约200天宽度的柱
        ),
        secondary_y=False,
    )

    # 历史市值 - 红色线（右轴），使用实际日期
    if historical_mc_df is not None and not historical_mc_df.empty:
        mc_dates = pd.to_datetime(historical_mc_df['date'])
        mc_values = historical_mc_df['market_cap_yi']
        fig.add_trace(
            go.Scatter(
                x=mc_dates,
                y=mc_values,
                name='总市值',
                line=dict(color=C_RED, width=1.5),
                mode='lines',
            ),
            secondary_y=True,
        )
    else:
        # 如果没有历史市值数据，在图上标注说明
        fig.add_annotation(
            text="暂无历史市值数据",
            xref="paper", yref="paper",
            x=0.5, y=0.5,
            showarrow=False,
            font=dict(size=14, color="gray"),
        )

    fig.update_xaxes(title_text="年度", tickangle=-45, type='date',
                     dtick="M12", tickformat="%Y")
    fig.update_yaxes(title_text="总营收 (亿元)", secondary_y=False)
    fig.update_yaxes(title_text="总市值 (亿元)", secondary_y=True)
    fig.update_layout(
        title="公司总营收与总市值走势",
        hovermode='x unified',
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        height=450,
    )
    return fig


def plot_net_profit_cashflow(income_stmt, cash_flow):
    """
    业绩趋势分析图表2: 净利润 & 经营现金流净额趋势
    """
    np_col = '归属于母公司所有者的净利润' if '归属于母公司所有者的净利润' in income_stmt.columns else '净利润'
    if np_col not in income_stmt.columns:
        return None

    annual_inc = income_stmt[income_stmt.index.month == 12]
    annual_cf = cash_flow[cash_flow.index.month == 12]

    net_profit = annual_inc[np_col].dropna()
    ocf = annual_cf.get('经营活动产生的现金流量净额')
    if ocf is not None:
        ocf = ocf.dropna()

    # 取最近10年
    if len(net_profit) > 10:
        net_profit = net_profit.iloc[-10:]
    if ocf is not None and len(ocf) > 10:
        ocf = ocf.iloc[-10:]

    if net_profit.empty:
        return None

    years = [str(d.year) for d in net_profit.index]

    fig = go.Figure()

    # 净利润 - 蓝色线
    fig.add_trace(go.Scatter(
        x=years,
        y=[v / 1e8 for v in net_profit.values],
        name='净利润',
        line=dict(color=C_BLUE, width=2),
        mode='lines+markers',
    ))

    # 经营现金流净额 - 红色线
    if ocf is not None and not ocf.empty:
        ocf_aligned = ocf.reindex(net_profit.index)
        fig.add_trace(go.Scatter(
            x=years,
            y=[v / 1e8 if pd.notna(v) else None for v in ocf_aligned.values],
            name='经营现金流净额',
            line=dict(color=C_RED, width=2),
            mode='lines+markers',
        ))

    fig.update_layout(
        title="净利润与经营现金流净额趋势 (年度)",
        xaxis_title="年度",
        yaxis_title="金额 (亿元)",
        hovermode='x unified',
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        height=400,
        xaxis_tickangle=-45,
    )
    return fig


# ====== 新增图表：产品分析 ======

# 堆叠柱状图颜色方案
STACK_COLORS = ['#00A0E9', '#E60012', '#16a34a', '#7c3aed', '#ea580c',
                '#0EA5E9', '#F59E0B', '#EC4899', '#14B8A6', '#8B5CF6',
                '#F97316', '#06B6D4', '#84CC16', '#A855F7']


def plot_main_business_stacked(business_data, category_key, title_suffix):
    """
    主营构成堆叠柱状图：展示每个分类项的主营利润叠加
    每年可以有不同的产品/行业/地区构成，动态展示所有出现过的项
    business_data: list of dict, 每个含 report_year, item_name, profit, income
    category_key: 'by_industry', 'by_product', 'by_region'
    title_suffix: '行业', '产品', '地区'
    """
    if not business_data:
        return None

    df = pd.DataFrame(business_data)
    if df.empty or 'profit' not in df.columns:
        return None

    # 去重：同一年份+同一项目可能有多条记录（API重复），取利润最大的一条
    df['profit'] = pd.to_numeric(df['profit'], errors='coerce')
    df = df.sort_values('profit', ascending=False)
    df = df.drop_duplicates(subset=['report_year', 'item_name'], keep='first')

    # 获取所有年份
    years = sorted(df['report_year'].unique().tolist())
    if len(years) > 10:
        years = years[-10:]

    df = df[df['report_year'].isin(years)]

    # 收集所有年份中出现过的所有item名称
    # 按所有年份的利润总和排序（降序）
    item_total_profit = df.groupby('item_name')['profit'].sum().sort_values(ascending=False)
    item_names = item_total_profit.index.tolist()

    fig = go.Figure()

    for idx, item in enumerate(item_names):
        item_data = df[df['item_name'] == item].set_index('report_year')
        y_values = []
        for y in years:
            if y in item_data.index and pd.notna(item_data.loc[y, 'profit']):
                y_values.append(item_data.loc[y, 'profit'] / 1e8)
            else:
                y_values.append(0)

        color = STACK_COLORS[idx % len(STACK_COLORS)]
        # 只在非零年份显示文字标签
        text_labels = [f"{v:.1f}" if v > 0 else "" for v in y_values]
        fig.add_trace(go.Bar(
            x=years,
            y=y_values,
            name=item,
            marker_color=color,
            text=text_labels,
            textposition='inside',
            textfont=dict(size=9),
            hovertemplate=f"<b>{item}</b><br>年度: %{{x}}<br>利润: %{{y:.1f}} 亿元<extra></extra>",
        ))

    fig.update_layout(
        title=f"主营利润构成（按{title_suffix}）",
        xaxis_title="年度",
        yaxis_title="主营利润 (亿元)",
        barmode='stack',
        height=500,
        xaxis_tickangle=-45,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(b=100),
    )
    return fig


# ====== 新增图表：成本细节 ======

def plot_cost_gross_margin(income_stmt):
    """
    成本细节图表1: 毛利率 & 总营收 & 总营业成本
    双轴图：左轴柱状图(总营收 & 总营业成本)，右轴线图(毛利率)
    """
    annual = income_stmt[income_stmt.index.month == 12]
    revenue = annual.get('营业总收入', annual.get('营业收入'))
    cost = annual.get('营业总成本', annual.get('营业成本'))

    if revenue is None or cost is None:
        return None

    # 取最近10年
    if len(revenue) > 10:
        revenue = revenue.iloc[-10:]
        cost = cost.iloc[-10:]

    if revenue.empty:
        return None

    years = [str(d.year) for d in revenue.index]
    gross_margin = ((revenue - cost) / revenue * 100).values
    
    # 计算更宽阔的毛利率Y轴范围（右轴）
    gm_min, gm_max = np.nanmin(gross_margin), np.nanmax(gross_margin)
    gm_range = gm_max - gm_min
    gm_padding = max(gm_range * 0.4, 5)
    gm_floor = max(gm_min - gm_padding, -10)
    gm_ceil = min(gm_max + gm_padding, 100)

    fig = make_subplots(specs=[[{"secondary_y": True}]])

    # 总营收 - 蓝色柱
    fig.add_trace(
        go.Bar(x=years, y=[v / 1e8 for v in revenue.values],
               name='总营收', marker_color=C_BLUE, opacity=0.85),
        secondary_y=False,
    )

    # 总营业成本 - 红色柱
    fig.add_trace(
        go.Bar(x=years, y=[v / 1e8 for v in cost.values],
               name='总营业成本', marker_color=C_RED, opacity=0.85),
        secondary_y=False,
    )

    # 毛利率 - 绿色线
    fig.add_trace(
        go.Scatter(x=years, y=gross_margin, name='毛利率(%)',
                   line=dict(color=C_GREEN, width=2),
                   mode='lines+markers',
                   text=[f"{v:.1f}%" for v in gross_margin],
                   textposition='top center'),
        secondary_y=True,
    )

    fig.update_xaxes(title_text="年度", tickangle=-45)
    fig.update_yaxes(title_text="金额 (亿元)", secondary_y=False)
    fig.update_yaxes(title_text="毛利率 (%)", secondary_y=True,
                     range=[gm_floor, gm_ceil])
    fig.update_layout(
        title="毛利率、总营收与总营业成本",
        hovermode='x unified',
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        height=450,
        barmode='group',
    )
    return fig


def plot_cost_expenses(income_stmt):
    """
    成本细节图表2: 总营收 & 营销费用 & 管理费用 & 研发费用
    分组柱状图 + 总营收折线
    """
    annual = income_stmt[income_stmt.index.month == 12]

    revenue_col = '营业总收入' if '营业总收入' in annual.columns else '营业收入'
    revenue = annual.get(revenue_col)
    if revenue is None:
        return None

    expense_names = {'销售费用': '营销费用', '管理费用': '管理费用', '研发费用': '研发费用'}
    available_exp = {orig: display for orig, display in expense_names.items() if orig in annual.columns}

    if not available_exp:
        return None

    # 取最近10年
    if len(revenue) > 10:
        revenue = revenue.iloc[-10:]

    years = [str(d.year) for d in revenue.index]

    fig = make_subplots(specs=[[{"secondary_y": True}]])

    # 各项费用 - 分组柱状图（左轴）
    colors = [C_RED, C_PURPLE, C_ORANGE]
    for idx, (orig, display) in enumerate(available_exp.items()):
        exp_data = annual[orig].reindex(revenue.index)
        fig.add_trace(
            go.Bar(x=years, y=[v / 1e8 if pd.notna(v) else 0 for v in exp_data.values],
                   name=display, marker_color=colors[idx % len(colors)], opacity=0.85),
            secondary_y=False,
        )

    # 总营收 - 蓝色线（左轴，但用secondary_y=False的右轴概念）
    fig.add_trace(
        go.Scatter(x=years, y=[v / 1e8 for v in revenue.values],
                   name='总营收', line=dict(color=C_BLUE, width=2),
                   mode='lines+markers'),
        secondary_y=True,
    )

    fig.update_xaxes(title_text="年度", tickangle=-45)
    fig.update_yaxes(title_text="费用 (亿元)", secondary_y=False)
    fig.update_yaxes(title_text="总营收 (亿元)", secondary_y=True)
    fig.update_layout(
        title="总营收与各项费用",
        hovermode='x unified',
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        height=450,
        barmode='group',
    )
    return fig


# ====== 市盈率(P/E)趋势图 ======

def _calculate_ttm_eps(eps_series):
    """
    从累计每股收益计算滚动12个月(TTM)每股收益
    eps_series: pd.Series, index=DatetimeIndex, values=当年累计EPS
    返回: pd.Series, TTM EPS
    """
    ttm_data = {}

    for date in eps_series.index:
        year = date.year
        month = date.month

        if month == 12:
            ttm_data[date] = eps_series[date]
        else:
            last_year_dec = None
            for d in eps_series.index:
                if d.year == year - 1 and d.month == 12:
                    last_year_dec = d
                    break

            last_year_same = None
            for d in eps_series.index:
                if d.year == year - 1 and d.month == month:
                    last_year_same = d
                    break

            if last_year_dec is not None and last_year_same is not None:
                ttm_val = eps_series[last_year_dec] + eps_series[date] - eps_series[last_year_same]
                ttm_data[date] = ttm_val

    if not ttm_data:
        return None

    return pd.Series(ttm_data, dtype=float)


def plot_pe_trend(income_stmt, quarterly_prices):
    """
    市盈率(P/E)趋势图
    使用TTM每股收益和季度前复权收盘价计算历史P/E
    添加平均线和±1标准差参考线
    """
    if quarterly_prices is None or quarterly_prices.empty:
        return None

    eps_col = '基本每股收益'
    if eps_col not in income_stmt.columns:
        return None

    eps_series = income_stmt[eps_col].dropna()
    if eps_series.empty:
        return None

    ttm_eps = _calculate_ttm_eps(eps_series)
    if ttm_eps is None or ttm_eps.empty:
        return None

    # 用季度Period对齐价格和EPS
    prices_q = quarterly_prices.copy()
    prices_q.index = quarterly_prices.index.to_period('Q')

    eps_q = ttm_eps.copy()
    eps_q.index = ttm_eps.index.to_period('Q')

    aligned = pd.DataFrame({'price': prices_q, 'eps': eps_q}).dropna()

    # 过滤掉EPS<=0的数据点
    aligned = aligned[aligned['eps'] > 0]

    if len(aligned) < 2:
        return None

    pe_values = (aligned['price'] / aligned['eps']).values
    pe_dates = aligned.index.to_timestamp()

    pe_mean = np.mean(pe_values)
    pe_std = np.std(pe_values)
    pe_upper = pe_mean + pe_std
    pe_lower = max(pe_mean - pe_std, 0)

    labels = [f"{p.year}-Q{p.quarter}" for p in aligned.index]

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=labels, y=pe_values, name='P/E 市盈率',
        line=dict(color=C_BLUE, width=2),
        mode='lines+markers',
        text=[f"P/E: {v:.1f}" for v in pe_values],
        hovertemplate="季度: %{x}<br>P/E: %{y:.1f}<extra></extra>",
    ))

    fig.add_hline(y=pe_mean, line_dash="solid", line_color=C_GREEN,
                  annotation_text=f"平均PE: {pe_mean:.1f}",
                  annotation_position="top left")

    fig.add_hline(y=pe_upper, line_dash="dash", line_color=C_ORANGE,
                  annotation_text=f"+1σ: {pe_upper:.1f}",
                  annotation_position="top left")

    fig.add_hline(y=pe_lower, line_dash="dash", line_color=C_RED,
                  annotation_text=f"-1σ: {pe_lower:.1f}",
                  annotation_position="bottom left")

    fig.update_layout(
        title="市盈率(P/E)趋势 (TTM)",
        xaxis_title="季度",
        yaxis_title="P/E",
        height=450,
        xaxis_tickangle=-45,
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )

    return fig


# ====== 沪深300市盈率趋势图（主页市场情绪参考） ======

def plot_csi300_pe_trend(pe_data):
    """
    沪深300指数市盈率10年趋势图
    含平均线和±1标准差参考线
    """
    if pe_data is None or pe_data.empty:
        return None

    pe_col = '滚动市盈率'
    if pe_col not in pe_data.columns:
        return None

    dates = pe_data['日期']
    pe_series = pe_data[pe_col].dropna()
    if pe_series.empty:
        return None

    pe_mean = pe_series.mean()
    pe_std = pe_series.std()
    pe_upper = pe_mean + pe_std
    pe_lower = max(pe_mean - pe_std, 0)
    current_pe = pe_series.iloc[-1]
    percentile = (pe_series < current_pe).sum() / len(pe_series) * 100

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=dates, y=pe_series.values,
        name='沪深300 TTM P/E',
        line=dict(color=C_BLUE, width=1.5),
        hovertemplate="日期: %{x|%Y-%m-%d}<br>P/E: %{y:.2f}<extra></extra>",
    ))

    fig.add_hline(y=pe_mean, line_dash="solid", line_color=C_GREEN,
                  annotation_text=f"10年平均: {pe_mean:.1f}",
                  annotation_position="top left")

    fig.add_hline(y=pe_upper, line_dash="dash", line_color=C_ORANGE,
                  annotation_text=f"+1σ: {pe_upper:.1f}",
                  annotation_position="top left")

    fig.add_hline(y=pe_lower, line_dash="dash", line_color=C_RED,
                  annotation_text=f"-1σ: {pe_lower:.1f}",
                  annotation_position="bottom left")

    fig.update_layout(
        title=f"沪深300市盈率(TTM) 10年趋势 | 当前: {current_pe:.2f} ({percentile:.0f}%分位)",
        xaxis_title="日期",
        yaxis_title="P/E",
        height=450,
        hovermode='x unified',
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        margin=dict(l=60, r=60, t=80, b=60),
    )

    return fig


# ====== 行业对标图表 ======

def plot_industry_pe_trend(pe_history_df, stock_pe=None, stock_name=""):
    """
    行业市盈率历史趋势图
    含平均线和±1标准差参考线，标注个股P/E
    """
    if pe_history_df is None or pe_history_df.empty:
        return None

    pe_series = pe_history_df['pe'].dropna()
    if pe_series.empty:
        return None

    dates = pe_history_df['date']

    pe_mean = pe_series.mean()
    pe_std = pe_series.std()
    pe_upper = pe_mean + pe_std
    pe_lower = max(pe_mean - pe_std, 0)
    current_pe = pe_series.iloc[-1]
    percentile = (pe_series < current_pe).sum() / len(pe_series) * 100

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=dates, y=pe_series.values,
        name='行业P/E (加权)',
        line=dict(color=C_BLUE, width=1.5),
        hovertemplate="日期: %{x|%Y-%m-%d}<br>P/E: %{y:.2f}<extra></extra>",
    ))

    fig.add_hline(y=pe_mean, line_dash="solid", line_color=C_GREEN,
                  annotation_text=f"平均: {pe_mean:.1f}",
                  annotation_position="top left")

    fig.add_hline(y=pe_upper, line_dash="dash", line_color=C_ORANGE,
                  annotation_text=f"+1σ: {pe_upper:.1f}",
                  annotation_position="top left")

    fig.add_hline(y=pe_lower, line_dash="dash", line_color=C_RED,
                  annotation_text=f"-1σ: {pe_lower:.1f}",
                  annotation_position="bottom left")

    if stock_pe is not None and stock_pe > 0:
        fig.add_hline(y=stock_pe, line_dash="dot", line_color=C_PURPLE,
                      annotation_text=f"{stock_name} P/E: {stock_pe:.1f}",
                      annotation_position="bottom right")

    title = f"行业市盈率趋势 | 当前: {current_pe:.2f} ({percentile:.0f}%分位)"
    if stock_name:
        title += f" | {stock_name}"

    fig.update_layout(
        title=title,
        xaxis_title="日期",
        yaxis_title="P/E",
        height=450,
        hovermode='x unified',
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        margin=dict(l=60, r=60, t=80, b=60),
    )

    return fig


def plot_industry_pe_distribution(peers_df, stock_code, stock_name, metric='pe'):
    """
    行业估值分布图
    显示同行业公司的PE或PB分布，标注当前个股位置
    """
    if peers_df is None or peers_df.empty:
        return None

    valid = peers_df[peers_df[metric] > 0]
    valid = valid[valid[metric] < 500]
    if valid.empty:
        return None

    labels_map = {'pe': '市盈率(P/E)', 'pb': '市净率(P/B)', 'roe': 'ROE(%)'}
    label = labels_map.get(metric, metric)

    stock_row = valid[valid['code'] == stock_code]
    stock_val = float(stock_row[metric].values[0]) if not stock_row.empty else None

    mean_val = valid[metric].mean()
    median_val = valid[metric].median()

    fig = go.Figure()

    fig.add_trace(go.Histogram(
        x=valid[metric],
        name=label,
        marker_color=C_BLUE,
        opacity=0.7,
        nbinsx=30,
        hovertemplate=f"{label}: %{{x:.1f}}<br>公司数: %{{y}}<extra></extra>",
    ))

    fig.add_vline(x=mean_val, line_dash="solid", line_color=C_GREEN,
                  annotation_text=f"均值: {mean_val:.1f}")

    fig.add_vline(x=median_val, line_dash="dash", line_color=C_ORANGE,
                  annotation_text=f"中位数: {median_val:.1f}")

    if stock_val is not None:
        fig.add_vline(x=stock_val, line_dash="dot", line_color=C_RED,
                      annotation_text=f"{stock_name}: {stock_val:.1f}")

    fig.update_layout(
        title=f"行业{label}分布 ({len(valid)}家公司)",
        xaxis_title=label,
        yaxis_title="公司数量",
        height=400,
        showlegend=False,
        margin=dict(l=60, r=60, t=60, b=60),
    )

    return fig


def plot_industry_peer_bars(peers_df, stock_code, stock_name, metric='pe', top_n=15):
    """
    同业估值对比柱状图
    显示市值前N家公司的PE或PB，标注当前个股
    """
    if peers_df is None or peers_df.empty:
        return None

    valid = peers_df[peers_df[metric] > 0]
    valid = valid[valid[metric] < 500]
    if valid.empty:
        return None

    labels = {'pe': '市盈率(P/E)', 'pb': '市净率(P/B)', 'roe': 'ROE(%)'}
    label = labels.get(metric, metric)

    top = valid.nlargest(top_n, 'market_cap_yi').sort_values(metric, ascending=True)

    colors = []
    for _, row in top.iterrows():
        if row['code'] == stock_code:
            colors.append(C_RED)
        else:
            colors.append(C_BLUE)

    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=top[metric].values,
        y=top['name'].values,
        orientation='h',
        marker_color=colors,
        text=[f"{v:.1f}" for v in top[metric].values],
        textposition='outside',
        hovertemplate=f"<b>%{{y}}</b><br>{label}: %{{x:.1f}}<extra></extra>",
    ))

    fig.update_layout(
        title=f"同业{label}对比 (市值前{min(top_n, len(top))}家)",
        xaxis_title=label,
        yaxis_title="",
        height=max(400, len(top) * 30),
        showlegend=False,
        margin=dict(l=120, r=60, t=60, b=60),
    )

    return fig


def plot_industry_marketcap_trend(index_data, industry_name):
    """
    行业板块指数价格趋势图
    """
    if index_data is None or index_data.empty:
        return None

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=index_data['date'],
        y=index_data['close'],
        name=f'{industry_name}板块指数',
        line=dict(color=C_BLUE, width=1.5),
        hovertemplate="日期: %{x|%Y-%m-%d}<br>指数: %{y:.2f}<extra></extra>",
    ))

    current = index_data['close'].iloc[-1]
    first = index_data['close'].iloc[0]
    change_pct = (current - first) / first * 100 if first > 0 else 0

    fig.update_layout(
        title=f"{industry_name}行业指数走势 | 期间涨跌幅: {change_pct:+.1f}%",
        xaxis_title="日期",
        yaxis_title="指数",
        height=350,
        hovermode='x unified',
        margin=dict(l=60, r=60, t=60, b=60),
    )

    return fig


# ====== 财务质量深度指标图表 ======

def plot_debt_ratio_trend(balance_sheet):
    """资产负债率趋势图"""
    annual = balance_sheet[balance_sheet.index.month == 12]
    total_liab = annual.get('负债合计')
    total_assets = annual.get('资产总计')
    if total_liab is None or total_assets is None:
        return None
    ratio = total_liab.div(total_assets.replace(0, np.nan)) * 100
    ratio = ratio.dropna()
    if ratio.empty:
        return None

    years = [str(d.year) for d in ratio.index]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=years, y=ratio.values, name='资产负债率',
        marker_color=C_RED,
        text=[f"{v:.1f}%" for v in ratio.values],
        textposition='outside',
    ))
    fig.add_hline(y=60, line_dash="dash", line_color=C_ORANGE,
                  annotation_text="警戒线 60%")
    fig.add_hline(y=40, line_dash="dash", line_color=C_GREEN,
                  annotation_text="稳健线 40%")
    fig.update_layout(
        title="资产负债率趋势 (年度)",
        xaxis_title="年度", yaxis_title="资产负债率 (%)",
        height=350,
    )
    return fig


def plot_financial_quality_card(income_stmt, balance_sheet, cash_flow):
    """财务质量综合仪表板: 4个子图"""
    annual_inc = income_stmt[income_stmt.index.month == 12]
    annual_bs = balance_sheet[balance_sheet.index.month == 12]
    annual_cf = cash_flow[cash_flow.index.month == 12]

    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=('资产负债率(%)', '流动比率 & 速动比率',
                        '应收账款 & 存货周转天数', '现金流/净利润比'),
        vertical_spacing=0.15, horizontal_spacing=0.1,
    )

    # 1. 资产负债率
    total_liab = annual_bs.get('负债合计')
    total_assets = annual_bs.get('资产总计')
    if total_liab is not None and total_assets is not None:
        debt_ratio = total_liab.div(total_assets.replace(0, np.nan)) * 100
        debt_ratio = debt_ratio.dropna()
        if not debt_ratio.empty:
            years = [str(d.year) for d in debt_ratio.index]
            fig.add_trace(go.Bar(x=years, y=debt_ratio.values, name='资产负债率',
                                marker_color=C_RED, showlegend=False), row=1, col=1)

    # 2. 流动比率 & 速动比率
    ca = annual_bs.get('流动资产合计')
    cl = annual_bs.get('流动负债合计')
    inv = annual_bs.get('存货')
    if ca is not None and cl is not None:
        current_r = ca.div(cl.replace(0, np.nan))
        inv_val = inv if inv is not None else 0
        quick_r = (ca - inv_val).div(cl.replace(0, np.nan))
        common_idx = current_r.dropna().index.intersection(quick_r.dropna().index)
        if not common_idx.empty:
            years = [str(d.year) for d in common_idx]
            fig.add_trace(go.Scatter(x=years, y=current_r.loc[common_idx].values,
                                     name='流动比率', line=dict(color=C_BLUE, width=2),
                                     mode='lines+markers'), row=1, col=2)
            fig.add_trace(go.Scatter(x=years, y=quick_r.loc[common_idx].values,
                                     name='速动比率', line=dict(color=C_GREEN, width=2),
                                     mode='lines+markers'), row=1, col=2)

    # 3. 周转天数
    rev = annual_inc.get('营业总收入', annual_inc.get('营业收入'))
    ar = annual_bs.get('应收票据及应收账款')
    cost = annual_inc.get('营业总成本', annual_inc.get('营业成本'))
    if rev is not None and ar is not None and len(ar) >= 2:
        avg_ar = (ar + ar.shift(1)) / 2
        ar_turnover = 365 / (rev.reindex(avg_ar.index).div(avg_ar.replace(0, np.nan)))
        ar_turnover = ar_turnover.dropna()
        if not ar_turnover.empty:
            years = [str(d.year) for d in ar_turnover.index]
            fig.add_trace(go.Bar(x=years, y=ar_turnover.values, name='应收账款周转天数',
                                 marker_color=C_BLUE, showlegend=False), row=2, col=1)
    if cost is not None and inv is not None and len(inv) >= 2:
        avg_inv = (inv + inv.shift(1)) / 2
        inv_turnover = 365 / (cost.reindex(avg_inv.index).div(avg_inv.replace(0, np.nan)))
        inv_turnover = inv_turnover.dropna()
        if not inv_turnover.empty:
            years = [str(d.year) for d in inv_turnover.index]
            fig.add_trace(go.Bar(x=years, y=inv_turnover.values, name='存货周转天数',
                                 marker_color=C_ORANGE, showlegend=False), row=2, col=1)

    # 4. 现金流/净利润
    ocf = annual_cf.get('经营活动产生的现金流量净额')
    np_col = '归属于母公司所有者的净利润' if '归属于母公司所有者的净利润' in annual_inc.columns else '净利润'
    net_profit = annual_inc.get(np_col)
    if ocf is not None and net_profit is not None:
        ratio = ocf.reindex(net_profit.index).div(net_profit.replace(0, np.nan))
        ratio = ratio.dropna()
        if not ratio.empty:
            years = [str(d.year) for d in ratio.index]
            fig.add_trace(go.Bar(x=years, y=ratio.values, name='现金流/净利润',
                                 marker_color=C_GREEN, showlegend=False,
                                 text=[f"{v:.2f}" for v in ratio.values],
                                 textposition='outside'), row=2, col=2)
            fig.add_hline(y=1, line_dash="dash", line_color="gray",
                          annotation_text="健康线 1.0", row=2, col=2)

    fig.update_layout(height=700, showlegend=True,
                      legend=dict(orientation="h", yanchor="bottom", y=1.02))
    return fig


# ====== 成长性指标图表 ======

def plot_growth_analysis(income_stmt):
    """成长性分析: 营收 & 净利润年度增长 + CAGR"""
    annual = income_stmt[income_stmt.index.month == 12]
    revenue_col = '营业总收入' if '营业总收入' in annual.columns else '营业收入'
    np_col = '归属于母公司所有者的净利润' if '归属于母公司所有者的净利润' in annual.columns else '净利润'

    revenue = annual.get(revenue_col)
    net_profit = annual.get(np_col)
    if revenue is None:
        return None

    # 取最近10年
    if len(revenue) > 10:
        revenue = revenue.iloc[-10:]
    if net_profit is not None and len(net_profit) > 10:
        net_profit = net_profit.iloc[-10:]

    years = [str(d.year) for d in revenue.index]

    fig = make_subplots(specs=[[{"secondary_y": True}]])

    # 营收柱状图
    fig.add_trace(go.Bar(
        x=years, y=[v / 1e8 for v in revenue.values],
        name='营业总收入', marker_color=C_BLUE, opacity=0.8,
    ), secondary_y=False)

    # 净利润折线
    if net_profit is not None and not net_profit.empty:
        np_aligned = net_profit.reindex(revenue.index)
        fig.add_trace(go.Scatter(
            x=years, y=[v / 1e8 if pd.notna(v) else None for v in np_aligned.values],
            name='归母净利润', line=dict(color=C_RED, width=2),
            mode='lines+markers',
        ), secondary_y=False)

    # 同比增长率 (右轴)
    rev_yoy = revenue.pct_change() * 100
    fig.add_trace(go.Scatter(
        x=years, y=rev_yoy.values,
        name='营收同比增速(%)', line=dict(color=C_GREEN, width=1.5, dash='dot'),
        mode='lines+markers',
    ), secondary_y=True)

    if net_profit is not None:
        np_yoy = net_profit.pct_change() * 100
        np_aligned_yoy = np_yoy.reindex(revenue.index)
        fig.add_trace(go.Scatter(
            x=years, y=np_aligned_yoy.values,
            name='净利润同比增速(%)', line=dict(color=C_PURPLE, width=1.5, dash='dot'),
            mode='lines+markers',
        ), secondary_y=True)

    fig.update_xaxes(title_text="年度", tickangle=-45)
    fig.update_yaxes(title_text="金额 (亿元)", secondary_y=False)
    fig.update_yaxes(title_text="同比增长率 (%)", secondary_y=True)
    fig.update_layout(
        title="营收与净利润成长趋势",
        hovermode='x unified',
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        height=450,
        barmode='group',
    )
    return fig


def plot_rd_ratio_trend(income_stmt):
    """研发投入占比趋势图"""
    annual = income_stmt[income_stmt.index.month == 12]
    revenue = annual.get('营业总收入', annual.get('营业收入'))
    rd = annual.get('研发费用')
    if revenue is None or rd is None:
        return None

    ratio = rd.reindex(revenue.index).div(revenue.replace(0, np.nan)) * 100
    ratio = ratio.dropna()
    if ratio.empty:
        return None

    years = [str(d.year) for d in ratio.index]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=years, y=ratio.values, name='研发费用/营收',
        marker_color=C_PURPLE,
        text=[f"{v:.1f}%" for v in ratio.values],
        textposition='outside',
    ))
    fig.add_hline(y=5, line_dash="dash", line_color=C_ORANGE,
                  annotation_text="研发密集型 5%")
    fig.update_layout(
        title="研发投入占营收比趋势 (年度)",
        xaxis_title="年度", yaxis_title="占比 (%)",
        height=350,
    )
    return fig


def plot_quarterly_growth(income_stmt):
    """季度营收同比增长趋势"""
    from financial_metrics import calculate_quarterly_growth
    qg = calculate_quarterly_growth(income_stmt)
    if qg.empty:
        return None

    labels = [f"{d.year}-Q{((d.month-1)//3)+1}" for d in qg.index]

    fig = make_subplots(specs=[[{"secondary_y": True}]])

    fig.add_trace(go.Bar(
        x=labels, y=[v / 1e8 for v in qg['revenue'].values],
        name='单季营收', marker_color=C_BLUE, opacity=0.8,
    ), secondary_y=False)

    if 'yoy' in qg.columns:
        fig.add_trace(go.Scatter(
            x=labels, y=qg['yoy'].values,
            name='同比增速(%)', line=dict(color=C_GREEN, width=2),
            mode='lines+markers',
        ), secondary_y=True)

    if 'qoq' in qg.columns:
        fig.add_trace(go.Scatter(
            x=labels, y=qg['qoq'].values,
            name='环比增速(%)', line=dict(color=C_ORANGE, width=1.5, dash='dot'),
            mode='lines+markers',
        ), secondary_y=True)

    fig.update_xaxes(title_text="季度", tickangle=-45)
    fig.update_yaxes(title_text="单季营收 (亿元)", secondary_y=False)
    fig.update_yaxes(title_text="增长率 (%)", secondary_y=True)
    fig.update_layout(
        title="季度营收增长趋势 (近12季)",
        hovermode='x unified',
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        height=400,
    )
    return fig


# ====== 股息分析图表 ======

def plot_dividend_trend(dividend_history, price=None):
    """
    分红历史趋势图: 每股股息(柱) + 派息率(线) + 股息率(线)
    """
    if not dividend_history:
        return None

    df = pd.DataFrame(dividend_history)
    if 'dividend_per_share' not in df.columns:
        return None

    df = df.dropna(subset=['dividend_per_share'])
    df = df[df['dividend_per_share'] > 0]
    if df.empty:
        return None

    years = df['report_year'].tolist()
    dps = df['dividend_per_share'].tolist()
    payout = df['payout_ratio'].fillna(0).tolist() if 'payout_ratio' in df.columns else [0] * len(years)
    div_yield = df['dividend_yield'].fillna(0).tolist() if 'dividend_yield' in df.columns else [0] * len(years)

    fig = make_subplots(specs=[[{"secondary_y": True}]])

    fig.add_trace(go.Bar(
        x=years, y=dps, name='每股股息(元)',
        marker_color=C_RED, opacity=0.85,
        text=[f"{v:.3f}" for v in dps],
        textposition='outside',
    ), secondary_y=False)

    if any(p > 0 for p in payout):
        fig.add_trace(go.Scatter(
            x=years, y=[p * 100 for p in payout],
            name='派息率(%)', line=dict(color=C_BLUE, width=2),
            mode='lines+markers',
        ), secondary_y=True)

    if any(d > 0 for d in div_yield):
        fig.add_trace(go.Scatter(
            x=years, y=[d * 100 for d in div_yield],
            name='股息率(%)', line=dict(color=C_GREEN, width=2, dash='dot'),
            mode='lines+markers',
        ), secondary_y=True)

    fig.update_xaxes(title_text="年度", tickangle=-45)
    fig.update_yaxes(title_text="每股股息 (元)", secondary_y=False)
    fig.update_yaxes(title_text="比率 (%)", secondary_y=True)
    fig.update_layout(
        title="分红历史趋势",
        hovermode='x unified',
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        height=400,
    )
    return fig


# ====== 风险指标图表 ======

def plot_risk_metrics(risk_metrics, stock_name=""):
    """
    风险指标可视化: 年化波动率、最大回撤、年化收益率、Sharpe比率
    """
    if not risk_metrics:
        return None

    metrics = ['年化收益率', '年化波动率', '最大回撤', 'Sharpe比率']
    values = [
        risk_metrics.get('annual_return', 0),
        risk_metrics.get('annualized_volatility', 0),
        risk_metrics.get('max_drawdown', 0),
        risk_metrics.get('sharpe_ratio', 0) or 0,
    ]
    colors = [C_GREEN, C_ORANGE, C_RED, C_BLUE]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=metrics, y=values,
        marker_color=colors,
        text=[f"{v:.2f}%" if i < 3 else f"{v:.2f}" for i, v in enumerate(values)],
        textposition='outside',
    ))

    title = "风险指标汇总 (近3年)"
    if stock_name:
        title += f" | {stock_name}"

    fig.update_layout(
        title=title,
        yaxis_title="数值",
        height=400,
        showlegend=False,
        margin=dict(l=60, r=60, t=60, b=60),
    )
    return fig


# ====== 多股票对比图表 ======

def plot_radar_chart(stock_summaries, current_code=None):
    """
    多股票雷达对比图
    维度: 估值吸引力(1/PE), 盈利能力(ROE), 成长性(涨跌幅), 安全性(1/PB), 流动性(换手率), 规模(市值)
    """
    if not stock_summaries or len(stock_summaries) < 2:
        return None

    categories = ['估值', '盈利', '动量', '安全', '流动', '规模']

    raw_data = []
    names = []
    for s in stock_summaries:
        if s is None:
            continue
        names.append(s.get('name', s.get('code', '')))
        raw_data.append({
            'pe': s.get('pe', 0),
            'roe': s.get('roe', 0),
            'change_pct': s.get('change_pct', 0),
            'pb': s.get('pb', 0),
            'turnover_rate': s.get('turnover_rate', 0),
            'market_cap_yi': s.get('market_cap_yi', 0),
        })

    if len(raw_data) < 2:
        return None

    # 归一化到0-1
    def normalize(values, higher_is_better=True):
        vals = [v if v > 0 else 0 for v in values]
        if not vals or max(vals) == 0:
            return [0.5] * len(vals)
        lo, hi = min(vals), max(vals)
        if hi == lo:
            return [0.5] * len(vals)
        norm = [(v - lo) / (hi - lo) for v in vals]
        if not higher_is_better:
            norm = [1 - n for n in norm]
        return norm

    fig = go.Figure()

    radar_colors = [C_BLUE, C_RED, C_GREEN, C_PURPLE, C_ORANGE]

    for idx, (name, data) in enumerate(zip(names, raw_data)):
        normalized = [
            normalize([d['pe'] for d in raw_data], higher_is_better=False)[idx],
            normalize([d['roe'] for d in raw_data])[idx],
            normalize([d['change_pct'] for d in raw_data])[idx],
            normalize([d['pb'] for d in raw_data], higher_is_better=False)[idx],
            normalize([d['turnover_rate'] for d in raw_data])[idx],
            normalize([d['market_cap_yi'] for d in raw_data])[idx],
        ]

        # 平滑处理，避免0值
        normalized = [max(n, 0.05) for n in normalized]

        color = radar_colors[idx % len(radar_colors)]
        fig.add_trace(go.Scatterpolar(
            r=normalized + [normalized[0]],
            theta=categories + [categories[0]],
            fill='toself',
            name=name,
            line=dict(color=color, width=2),
            fillcolor=color,
            opacity=0.15,
        ))

    fig.update_layout(
        polar=dict(
            radialaxis=dict(visible=True, range=[0, 1]),
        ),
        title="多股票雷达对比 (归一化)",
        height=500,
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    return fig


def plot_stock_comparison_bars(stock_summaries, metric='pe', current_code=None):
    """
    多股票对比柱状图
    """
    if not stock_summaries:
        return None

    labels_map = {
        'pe': '市盈率(P/E)',
        'pb': '市净率(P/B)',
        'roe': 'ROE(%)',
        'market_cap_yi': '总市值(亿)',
        'turnover_rate': '换手率(%)',
    }
    label = labels_map.get(metric, metric)

    valid = [s for s in stock_summaries if s and s.get(metric, 0) > 0]
    if len(valid) < 2:
        return None

    names = [s['name'] for s in valid]
    values = [s[metric] for s in valid]

    colors = [C_RED if s.get('code') == current_code else C_BLUE for s in valid]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=names, y=values,
        marker_color=colors,
        text=[f"{v:.2f}" for v in values],
        textposition='outside',
    ))

    fig.update_layout(
        title=f"多股票对比 - {label}",
        xaxis_title="", yaxis_title=label,
        height=400,
        showlegend=False,
        margin=dict(l=60, r=60, t=60, b=60),
    )
    return fig
