"""
A股投资分析软件 - Streamlit主应用
功能：公司财务分析（深度）+ 公司估值分析 + 行业对标分析
支持任意A股股票搜索（覆盖上交所+深交所+北交所）
"""
import streamlit as st
import pandas as pd
import numpy as np
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from data_fetcher import (
    search_stocks, fetch_all_data, get_company_info, get_csi300_pe_data,
    get_industry_board_name, get_industry_peers,
    get_industry_index_data, compute_industry_pe_history,
)
from financial_metrics import (
    calculate_gross_margin, calculate_expense_ratio, calculate_roe,
    calculate_debt_ratio, determine_business_type,
    build_income_table, build_cashflow_table, generate_annual_report_analysis,
    calculate_cagr, calculate_current_ratio, calculate_quick_ratio,
    calculate_cashflow_to_profit_ratio, calculate_goodwill_ratio,
    calculate_receivable_turnover_days, calculate_inventory_turnover_days,
    calculate_rd_ratio, build_financial_quality_table,
)
from valuation import dcf_valuation, ddm_valuation, pb_valuation, pe_valuation, calculate_wacc
from visualizations import (
    plot_balance_sheet_bar,
    plot_roe_trend, plot_gross_margin_trend, plot_expense_ratio_trend,
    plot_cashflow_trend,
    plot_revenue_marketcap_trend, plot_net_profit_cashflow,
    plot_main_business_stacked,
    plot_cost_gross_margin, plot_cost_expenses,
    plot_pe_trend, plot_csi300_pe_trend,
    plot_industry_pe_trend, plot_industry_pe_distribution,
    plot_industry_peer_bars, plot_industry_marketcap_trend,
    plot_debt_ratio_trend, plot_financial_quality_card,
    plot_growth_analysis, plot_rd_ratio_trend, plot_quarterly_growth,
)

# ========== 页面配置 ==========
st.set_page_config(
    page_title="A股投资分析",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("📊 A股投资分析系统")
st.markdown("---")

# ========== 侧边栏：股票搜索 ==========
st.sidebar.header("🔍 股票搜索")

search_keyword = st.sidebar.text_input(
    "输入股票代码或名称",
    value="",
    placeholder="如：000001 或 平安银行",
)


@st.cache_data(ttl=3600)
def cached_search(keyword):
    return search_stocks(keyword, limit=30)


selected_stock = None

if search_keyword.strip():
    with st.spinner("搜索中..."):
        matched = cached_search(search_keyword.strip())

    if not matched.empty:
        display_list = matched['display'].tolist()
        selected_display = st.sidebar.selectbox("选择股票", display_list)
        selected_row = matched[matched['display'] == selected_display].iloc[0]
        selected_stock = {
            'code': selected_row['code'],
            'name': selected_row['name'],
            'exchange': selected_row['exchange'],
        }
    else:
        st.sidebar.warning("未找到匹配的股票，请尝试其他关键词")

if selected_stock:
    st.sidebar.markdown("---")
    st.sidebar.info(
        f"已选择: **{selected_stock['name']}** "
        f"({selected_stock['exchange']}{selected_stock['code']})"
    )

    if st.sidebar.button("📥 加载数据", type="primary"):
        st.session_state['selected_stock'] = selected_stock
        st.session_state['data_loaded'] = True
        st.rerun()


# ========== 数据加载 ==========
if 'selected_stock' in st.session_state and st.session_state.get('data_loaded'):
    stock = st.session_state['selected_stock']


    @st.cache_data(ttl=600, show_spinner=False)
    def load_all_data(code, exchange):
        return fetch_all_data(code, exchange)


    @st.cache_data(ttl=600, show_spinner=False)
    def fetch_company_info(code, exchange):
        return get_company_info(code, exchange)


    with st.spinner(f"正在加载 {stock['name']} 的财报数据，请稍候..."):
        data = load_all_data(stock['code'], stock['exchange'])
        company_info = fetch_company_info(stock['code'], stock['exchange'])

    balance_sheet = data.get('balance_sheet')
    income_stmt = data.get('income_statement')
    cash_flow = data.get('cash_flow')
    market_cap = data.get('market_cap')
    historical_mc = data.get('historical_market_cap')
    main_business = data.get('main_business')
    quarterly_prices = data.get('quarterly_prices')
    beta = data.get('beta')
    risk_free_rate = data.get('risk_free_rate')

    if balance_sheet is None or balance_sheet.empty:
        st.error("未能获取到财务数据，请检查股票代码或稍后重试")
        st.stop()

    # 侧边栏显示实时行情
    if market_cap:
        st.sidebar.markdown("---")
        st.sidebar.subheader("📈 实时行情")
        st.sidebar.metric("当前股价", f"{market_cap['price']:.2f} 元")
        st.sidebar.metric("总市值", f"{market_cap['market_cap_yi']:.2f} 亿元")
        st.sidebar.metric("总股本", f"{market_cap['shares'] / 1e4:.2f} 万股")

    # 侧边栏显示公司基本信息
    if company_info:
        st.sidebar.markdown("---")
        st.sidebar.subheader("🏢 公司信息")
        sidebar_fields = [
            ('SECURITY_NAME_ABBR', '股票简称'),
            ('EM2016', '行业'),
            ('LISTING_DATE', '上市时间'),
            ('REG_CAPITAL', '注册资本(万)'),
            ('EMP_NUM', '员工人数'),
        ]
        for eng_key, chn_label in sidebar_fields:
            if eng_key in company_info and company_info[eng_key]:
                val = str(company_info[eng_key]).split(' ')[0] if eng_key == 'LISTING_DATE' else str(company_info[eng_key])
                if len(val) > 30:
                    val = val[:30] + "..."
                st.sidebar.text(f"{chn_label}: {val}")

    # ========== 加载行业对标数据 ==========
    industry_name_raw = company_info.get('EM2016', '') if company_info else ''

    @st.cache_data(ttl=600, show_spinner=False)
    def load_industry_data(ind_name):
        if not ind_name:
            return None
        board = get_industry_board_name(ind_name)
        if not board:
            return None
        peers_df = get_industry_peers(board)
        idx_data = get_industry_index_data(board, years=10)
        pe_hist = compute_industry_pe_history(idx_data, peers_df)
        return {
            'board_name': board,
            'peers': peers_df,
            'index_data': idx_data,
            'pe_history': pe_hist,
        }

    industry_data = None
    if industry_name_raw:
        with st.spinner("正在加载行业对标数据..."):
            industry_data = load_industry_data(industry_name_raw)

    # ========== 主内容区 ==========
    tab1, tab2, tab3 = st.tabs(["🏢 公司财务分析", "💰 公司估值分析", "🏭 行业对标"])

    # ==================== Tab 1: 公司财务分析 ====================
    with tab1:
        # ======== 1. 公司与产品分析 ========
        st.header("1. 公司与产品分析")

        if company_info:
            col1, col2 = st.columns(2)
            with col1:
                st.subheader("公司基本信息")
                info_fields = [
                    ('ORG_NAME', '公司全称'),
                    ('ORG_NAME_EN', '英文名称'),
                    ('SECURITY_NAME_ABBR', '股票简称'),
                    ('EM2016', '行业分类'),
                    ('INDUSTRYCSRC1', '证监会行业'),
                    ('LISTING_DATE', '上市日期'),
                    ('FOUND_DATE', '成立日期'),
                    ('CHAIRMAN', '董事长'),
                    ('PRESIDENT', '总经理'),
                    ('LEGAL_PERSON', '法人代表'),
                    ('EMP_NUM', '员工人数'),
                    ('REG_CAPITAL', '注册资本(万元)'),
                    ('ADDRESS', '办公地址'),
                    ('REG_ADDRESS', '注册地址'),
                    ('ORG_WEB', '公司网址'),
                    ('ORG_TEL', '联系电话'),
                    ('ORG_EMAIL', '电子邮箱'),
                ]
                for eng_key, chn_label in info_fields:
                    if eng_key in company_info and company_info[eng_key]:
                        val = str(company_info[eng_key])
                        if eng_key in ('LISTING_DATE', 'FOUND_DATE'):
                            val = val.split(' ')[0]
                        if len(val) > 60:
                            val = val[:60] + "..."
                        st.text(f"{chn_label}: {val}")

            with col2:
                st.subheader("主营业务")
                main_biz = company_info.get('MAIN_BUSINESS', '')
                if main_biz:
                    st.write(main_biz)

                st.subheader("经营范围")
                scope = company_info.get('BUSINESS_SCOPE', '')
                if scope:
                    # 按分号拆分经营范围，逐行显示
                    scope_items = [s.strip() for s in scope.replace('；', ';').split(';') if s.strip()]
                    if len(scope_items) > 1:
                        for item in scope_items:
                            st.markdown(f"- {item}")
                    else:
                        st.write(scope[:500] + "..." if len(scope) > 500 else scope)

                st.subheader("公司愿景")
                profile = company_info.get('ORG_PROFILE', '')
                if profile:
                    st.write(profile.strip())
                else:
                    st.info("暂无公司简介信息")

            # --- 产品业务 ---
            st.markdown("---")
            st.subheader("产品业务")

            if main_business and (main_business.get('by_product') or main_business.get('by_industry')):
                # 提取最新年份的产品/行业构成
                latest_products = []
                latest_industries = []
                latest_regions = []

                for cat, target in [('by_product', 'latest_products'),
                                     ('by_industry', 'latest_industries'),
                                     ('by_region', 'latest_regions')]:
                    items = main_business.get(cat, [])
                    if items:
                        latest_year = max(item['report_year'] for item in items)
                        latest_items = [item for item in items if item['report_year'] == latest_year]
                        latest_items.sort(key=lambda x: x.get('income') or 0, reverse=True)
                        if target == 'latest_products':
                            latest_products = latest_items
                        elif target == 'latest_industries':
                            latest_industries = latest_items
                        else:
                            latest_regions = latest_items

                prod_col, ind_col, reg_col = st.columns(3)
                with prod_col:
                    st.markdown("**产品矩阵**")
                    if latest_products:
                        for item in latest_products:
                            income_yi = (item.get('income') or 0) / 1e8
                            st.text(f"  {item['item_name']}: {income_yi:.1f}亿元")
                    else:
                        st.text("  暂无数据")

                with ind_col:
                    st.markdown("**行业分布**")
                    if latest_industries:
                        for item in latest_industries:
                            income_yi = (item.get('income') or 0) / 1e8
                            st.text(f"  {item['item_name']}: {income_yi:.1f}亿元")
                    else:
                        st.text("  暂无数据")

                with reg_col:
                    st.markdown("**地区分布**")
                    if latest_regions:
                        for item in latest_regions:
                            income_yi = (item.get('income') or 0) / 1e8
                            st.text(f"  {item['item_name']}: {income_yi:.1f}亿元")
                    else:
                        st.text("  暂无数据")

                # 商业类型判断
                st.markdown("")
                st.markdown("**商业类型判断**")
                biz_types = determine_business_type(income_stmt, balance_sheet)
                if biz_types:
                    for bt in biz_types:
                        st.markdown(f"- {bt}")
                else:
                    st.text("  暂无足够数据判断")
            else:
                st.info("暂无产品业务构成数据")
        else:
            st.info("暂无公司基本信息")

        st.markdown("---")

        # ======== 2. 公司基本指标判断 ========
        st.header("2. 公司基本指标判断")

        # 图表1: 公司总营收与总市值走势
        st.subheader("📈 公司总营收与总市值走势")
        fig_rev_mc = plot_revenue_marketcap_trend(income_stmt, historical_mc)
        if fig_rev_mc:
            st.plotly_chart(fig_rev_mc, use_container_width=True)
        else:
            st.warning("暂无足够数据生成此图表")

        # 图表2: 净利润与经营现金流净额趋势
        st.subheader("📈 净利润与经营现金流净额趋势")
        fig_npc = plot_net_profit_cashflow(income_stmt, cash_flow)
        if fig_npc:
            st.plotly_chart(fig_npc, use_container_width=True)
        else:
            st.warning("暂无足够数据生成此图表")

        st.markdown("---")

        # ======== 3. 财务分析 ========
        st.header("3. 财务分析")

        # --- 资产负债表 ---
        st.subheader("📊 资产负债表")
        st.caption("🔵 蓝色 = 资产项 | 🔴 红色 = 负债项")
        fig_bs = plot_balance_sheet_bar(balance_sheet, is_annual=True)
        if fig_bs:
            st.plotly_chart(fig_bs, use_container_width=True)
        else:
            st.warning("无法生成图表，请检查数据")

        # --- 利润表 ---
        st.subheader("📊 利润表")

        # 成本细节图表1: 毛利率 & 总营收 & 总营业成本
        st.markdown("**毛利率、总营收与总营业成本**")
        fig_gm = plot_cost_gross_margin(income_stmt)
        if fig_gm:
            st.plotly_chart(fig_gm, use_container_width=True)
        else:
            st.warning("暂无足够数据生成此图表")

        # 成本细节图表2: 总营收 & 营销费用 & 管理费用 & 研发费用
        st.markdown("**总营收与各项费用**")
        fig_exp = plot_cost_expenses(income_stmt)
        if fig_exp:
            st.plotly_chart(fig_exp, use_container_width=True)
        else:
            st.warning("暂无足够数据生成此图表")

        # 利润表关键指标
        st.markdown("**利润表关键指标**")
        income_table = build_income_table(income_stmt, annual_only=True)
        if not income_table.empty:
            st.dataframe(income_table.style.format("{:.2f}"), use_container_width=True)
        else:
            st.info("暂无利润表数据")

        # 现金流量表关键指标
        st.markdown("**现金流量表关键指标**")
        cf_table = build_cashflow_table(cash_flow, annual_only=True)
        if not cf_table.empty:
            st.dataframe(cf_table.style.format("{:.2f}"), use_container_width=True)
        else:
            st.info("暂无现金流量表数据")

        st.markdown("---")

        # ======== 4. 产品分析（图表版本）========
        st.header("4. 产品分析")

        if main_business and (main_business.get('by_industry') or
                              main_business.get('by_product') or
                              main_business.get('by_region')):
            # 按行业
            st.subheader("📊 主营利润构成（按行业）")
            fig_ind = plot_main_business_stacked(
                main_business.get('by_industry', []),
                'by_industry', '行业'
            )
            if fig_ind:
                st.plotly_chart(fig_ind, use_container_width=True)
            else:
                st.info("暂无按行业分类的主营构成数据")

            # 按产品
            st.subheader("📊 主营利润构成（按产品）")
            fig_prod = plot_main_business_stacked(
                main_business.get('by_product', []),
                'by_product', '产品'
            )
            if fig_prod:
                st.plotly_chart(fig_prod, use_container_width=True)
            else:
                st.info("暂无按产品分类的主营构成数据")

            # 按地区
            st.subheader("📊 主营利润构成（按地区）")
            fig_reg = plot_main_business_stacked(
                main_business.get('by_region', []),
                'by_region', '地区'
            )
            if fig_reg:
                st.plotly_chart(fig_reg, use_container_width=True)
            else:
                st.info("暂无按地区分类的主营构成数据")
        else:
            st.info("暂无主营构成数据")

        st.markdown("---")

        # ======== 5. 年度报告分析 ========
        st.header("5. 年度报告分析")
        analyses = generate_annual_report_analysis(
            income_stmt, balance_sheet, cash_flow, market_cap
        )
        for section, text in analyses:
            st.subheader(f"📊 {section}")
            st.write(text)

        st.markdown("---")

        # ======== 6. 深度指标分析 ========
        st.header("6. 深度指标分析")

        col_chart1, col_chart2 = st.columns(2)
        with col_chart1:
            fig_roe = plot_roe_trend(income_stmt, balance_sheet)
            if fig_roe:
                st.plotly_chart(fig_roe, use_container_width=True)
        with col_chart2:
            fig_gm_trend = plot_gross_margin_trend(income_stmt)
            if fig_gm_trend:
                st.plotly_chart(fig_gm_trend, use_container_width=True)

        col_chart3, col_chart4 = st.columns(2)
        with col_chart3:
            fig_er = plot_expense_ratio_trend(income_stmt)
            if fig_er:
                st.plotly_chart(fig_er, use_container_width=True)
        with col_chart4:
            fig_cf = plot_cashflow_trend(cash_flow, period='annual')
            if fig_cf:
                st.plotly_chart(fig_cf, use_container_width=True)

        st.markdown("---")

        # ======== 7. 财务质量深度分析 ========
        st.header("7. 财务质量深度分析")
        st.caption("评估公司财务健康度：偿债能力、运营效率、盈利含金量、暴雷风险")

        # 资产负债率趋势
        st.subheader("📈 资产负债率趋势")
        fig_debt = plot_debt_ratio_trend(balance_sheet)
        if fig_debt:
            st.plotly_chart(fig_debt, use_container_width=True)
        else:
            st.warning("暂无足够数据")

        # 财务质量综合仪表板
        st.subheader("📈 财务质量综合仪表板")
        fig_quality = plot_financial_quality_card(income_stmt, balance_sheet, cash_flow)
        if fig_quality:
            st.plotly_chart(fig_quality, use_container_width=True)
        else:
            st.warning("暂无足够数据")

        # 财务质量指标表
        st.subheader("📊 财务质量指标表")
        quality_table = build_financial_quality_table(income_stmt, balance_sheet, cash_flow)
        if not quality_table.empty:
            st.dataframe(
                quality_table.style.format("{:.2f}"),
                use_container_width=True,
            )
            # 指标解读
            latest = quality_table.iloc[-1]
            st.markdown("**最新年度指标解读：**")
            interpretations = []
            if '资产负债率(%)' in latest.index and pd.notna(latest['资产负债率(%)']):
                dr = latest['资产负债率(%)']
                if dr < 40:
                    interpretations.append(f"✅ 资产负债率 {dr:.1f}%，财务结构稳健")
                elif dr < 60:
                    interpretations.append(f"⚠️ 资产负债率 {dr:.1f}%，财务结构适中")
                else:
                    interpretations.append(f"🔴 资产负债率 {dr:.1f}%，负债率较高，需关注偿债能力")
            if '流动比率' in latest.index and pd.notna(latest['流动比率']):
                cr = latest['流动比率']
                if cr >= 2:
                    interpretations.append(f"✅ 流动比率 {cr:.2f}，短期偿债能力强")
                elif cr >= 1:
                    interpretations.append(f"⚠️ 流动比率 {cr:.2f}，短期偿债能力一般")
                else:
                    interpretations.append(f"🔴 流动比率 {cr:.2f}，短期偿债能力不足")
            if '现金流/净利润' in latest.index and pd.notna(latest['现金流/净利润']):
                cr = latest['现金流/净利润']
                if cr >= 1:
                    interpretations.append(f"✅ 现金流/净利润 {cr:.2f}，盈利含金量高")
                elif cr >= 0.5:
                    interpretations.append(f"⚠️ 现金流/净利润 {cr:.2f}，盈利含金量一般")
                else:
                    interpretations.append(f"🔴 现金流/净利润 {cr:.2f}，盈利含金量低，需警惕")
            if '商誉/净资产(%)' in latest.index and pd.notna(latest['商誉/净资产(%)']):
                gr = latest['商誉/净资产(%)']
                if gr > 30:
                    interpretations.append(f"🔴 商誉占净资产 {gr:.1f}%，商誉减值风险较高")
                elif gr > 10:
                    interpretations.append(f"⚠️ 商誉占净资产 {gr:.1f}%，需关注减值风险")
            for interp in interpretations:
                st.markdown(f"- {interp}")
        else:
            st.info("暂无足够数据计算财务质量指标")

        st.markdown("---")

        # ======== 8. 成长性分析 ========
        st.header("8. 成长性分析")
        st.caption("评估公司成长能力：营收/净利润增长率、季度环比趋势、研发投入")

        # 成长性卡片
        annual_inc = income_stmt[income_stmt.index.month == 12]
        rev_col = '营业总收入' if '营业总收入' in annual_inc.columns else '营业收入'
        np_col = '归属于母公司所有者的净利润' if '归属于母公司所有者的净利润' in annual_inc.columns else '净利润'
        revenue_annual = annual_inc.get(rev_col)
        net_profit_annual = annual_inc.get(np_col)

        col_g1, col_g2, col_g3, col_g4 = st.columns(4)
        with col_g1:
            rev_cagr = calculate_cagr(revenue_annual, years=3) if revenue_annual is not None else None
            st.metric("营收3年CAGR", f"{rev_cagr:.1f}%" if rev_cagr is not None else "N/A")
        with col_g2:
            np_cagr = calculate_cagr(net_profit_annual, years=3) if net_profit_annual is not None else None
            st.metric("净利润3年CAGR", f"{np_cagr:.1f}%" if np_cagr is not None else "N/A")
        with col_g3:
            if revenue_annual is not None and len(revenue_annual) >= 2:
                rev_yoy = (revenue_annual.iloc[-1] / revenue_annual.iloc[-2] - 1) * 100 if revenue_annual.iloc[-2] != 0 else 0
                st.metric("营收同比增速", f"{rev_yoy:.1f}%")
            else:
                st.metric("营收同比增速", "N/A")
        with col_g4:
            if net_profit_annual is not None and len(net_profit_annual) >= 2 and net_profit_annual.iloc[-2] != 0:
                np_yoy = (net_profit_annual.iloc[-1] / net_profit_annual.iloc[-2] - 1) * 100
                st.metric("净利润同比增速", f"{np_yoy:.1f}%")
            else:
                st.metric("净利润同比增速", "N/A")

        # 营收与净利润成长趋势
        st.subheader("📈 营收与净利润成长趋势")
        fig_growth = plot_growth_analysis(income_stmt)
        if fig_growth:
            st.plotly_chart(fig_growth, use_container_width=True)
        else:
            st.warning("暂无足够数据")

        # 季度营收增长趋势
        st.subheader("📈 季度营收增长趋势")
        fig_qg = plot_quarterly_growth(income_stmt)
        if fig_qg:
            st.plotly_chart(fig_qg, use_container_width=True)
        else:
            st.warning("暂无足够数据生成季度增长图")

        # 研发投入占比趋势
        st.subheader("📈 研发投入占比趋势")
        fig_rd = plot_rd_ratio_trend(income_stmt)
        if fig_rd:
            st.plotly_chart(fig_rd, use_container_width=True)
        else:
            st.info("暂无研发费用数据")

    # ==================== Tab 2: 公司估值分析 ====================
    with tab2:
        st.header("💰 公司估值分析")

        # 当前股价/市值输入
        st.subheader("当前股价与市值")
        current_price_default = float(market_cap['price']) if market_cap else 0.0
        market_cap_default = float(market_cap['market_cap_yi']) if market_cap else 0.0

        col_input1, col_input2 = st.columns(2)
        with col_input1:
            current_price = st.number_input(
                "当前股价 (元)", min_value=0.0,
                value=current_price_default, step=0.1,
            )
        with col_input2:
            market_cap_yi_input = st.number_input(
                "当前总市值 (亿元)", min_value=0.0,
                value=market_cap_default, step=10.0,
            )

        mc_yuan = market_cap_yi_input * 1e8 if market_cap_yi_input > 0 else None

        # 年度数据（用于估值计算）
        annual_inc = income_stmt[income_stmt.index.month == 12]
        annual_bs = balance_sheet[balance_sheet.index.month == 12]
        annual_cf = cash_flow[cash_flow.index.month == 12]

        st.markdown("---")

        # ======== 相对估值法 ========
        st.header("相对估值法")

        # --- P/B 估值 ---
        st.subheader("📈 P/B 市净率估值")
        pb_result = pb_valuation(
            annual_bs, market_cap=mc_yuan,
            current_price=current_price if current_price > 0 else None,
            shares=market_cap['shares'] if market_cap else None,
        )
        if pb_result:
            col_pb1, col_pb2, col_pb3 = st.columns(3)
            with col_pb1:
                st.metric("每股净资产", f"{pb_result['bvps']:.2f} 元")
            with col_pb2:
                st.metric("净资产总额", f"{pb_result['total_equity'] / 1e8:.2f} 亿元")
            with col_pb3:
                if 'pb_ratio' in pb_result and not pd.isna(pb_result.get('pb_ratio')):
                    st.metric("P/B 市净率", f"{pb_result['pb_ratio']:.2f}")
                else:
                    st.metric("P/B 市净率", "请输入股价/市值")
        else:
            st.warning("无法计算P/B估值")

        # --- P/E 估值 ---
        st.subheader("📈 P/E 市盈率估值")
        pe_result = pe_valuation(
            annual_inc,
            current_price=current_price if current_price > 0 else None,
            market_cap=mc_yuan,
        )
        if pe_result:
            col_pe1, col_pe2, col_pe3 = st.columns(3)
            with col_pe1:
                st.metric("净利润", f"{pe_result['net_profit'] / 1e8:.2f} 亿元")
            with col_pe2:
                if 'eps' in pe_result and pe_result['eps'] is not None:
                    st.metric("每股收益(EPS)", f"{pe_result['eps']:.2f} 元")
                else:
                    st.metric("每股收益(EPS)", "N/A")
            with col_pe3:
                if 'pe_ratio' in pe_result and not pd.isna(pe_result.get('pe_ratio')):
                    st.metric("P/E 市盈率", f"{pe_result['pe_ratio']:.2f}")
                else:
                    st.metric("P/E 市盈率", "请输入股价/市值")
        else:
            st.warning("无法计算P/E估值")

        # P/E 趋势图
        st.markdown("**市盈率(P/E)历史趋势**")
        fig_pe_trend = plot_pe_trend(income_stmt, quarterly_prices)
        if fig_pe_trend:
            st.plotly_chart(fig_pe_trend, use_container_width=True)
        else:
            st.warning("暂无足够数据生成P/E趋势图")

        st.markdown("---")

        # ======== 绝对估值法 ========
        st.header("绝对估值法")

        # 估值参数设置
        st.subheader("估值参数设置")

        # WACC自动计算
        wacc_data = None
        mc_for_wacc = mc_yuan
        if mc_for_wacc is None and market_cap:
            mc_for_wacc = market_cap['market_cap_yi'] * 1e8
        if beta is not None and risk_free_rate is not None and mc_for_wacc:
            wacc_data = calculate_wacc(annual_bs, annual_inc, mc_for_wacc, beta, risk_free_rate)

        col_p1, col_p2, col_p3, col_p4 = st.columns(4)
        with col_p1:
            dcf_growth = st.slider("DCF - 未来增长率 (%)", 0, 30, 10) / 100
        with col_p2:
            dcf_terminal = st.slider("DCF - 永续增长率 (%)", 0, 8, 3) / 100
        with col_p3:
            if wacc_data:
                default_wacc = max(3, min(25, int(round(wacc_data['wacc'] * 100))))
                dcf_discount = st.slider(
                    "DCF - 折现率/WACC (%)", 3, 25,
                    value=default_wacc,
                    help=f"自动计算WACC: {wacc_data['wacc']*100:.2f}%"
                ) / 100
            else:
                dcf_discount = st.slider("DCF - 折现率 (%)", 5, 20, 10) / 100
        with col_p4:
            dcf_years = st.slider("DCF - 预测年数", 3, 10, 5)

        ddm_growth = st.slider("DDM - 股利增长率 (%)", 0, 15, 5) / 100
        ddm_discount = st.slider("DDM - 折现率 (%)", 5, 15, 8) / 100

        # WACC明细
        if wacc_data:
            with st.expander("查看WACC计算明细"):
                col_w1, col_w2, col_w3, col_w4 = st.columns(4)
                with col_w1:
                    st.metric("Beta (β)", f"{wacc_data['beta']:.2f}")
                    st.metric("无风险利率(Rf)", f"{wacc_data['risk_free_rate']:.2f}%")
                with col_w2:
                    st.metric("股权风险溢价", f"{wacc_data['equity_risk_premium']*100:.1f}%")
                    st.metric("股权成本(Ke)", f"{wacc_data['cost_of_equity']*100:.2f}%")
                with col_w3:
                    st.metric("债务成本(Kd)", f"{wacc_data['cost_of_debt']*100:.2f}%")
                    st.metric("税率", f"{wacc_data['tax_rate']*100:.1f}%")
                with col_w4:
                    st.metric("股权权重", f"{wacc_data['equity_weight']*100:.1f}%")
                    st.metric("债权权重", f"{wacc_data['debt_weight']*100:.1f}%")
                st.markdown(f"**WACC = {wacc_data['wacc']*100:.2f}%**")
                st.caption("Ke = Rf + β × ERP (CAPM) | WACC = E/(E+D)×Ke + D/(E+D)×Kd×(1-t)")

        st.markdown("---")

        # --- DCF 估值 ---
        st.subheader("📈 DCF 现金流折现模型")

        # 检测金融类公司（银行/保险/证券），FCF模型不适用
        industry_str = ''
        if company_info:
            industry_str = str(company_info.get('EM2016', '')) + str(company_info.get('INDUSTRYCSRC1', ''))
        is_financial = any(kw in industry_str for kw in ['银行', '保险', '证券', '金融'])

        if is_financial:
            st.warning(
                "⚠️ 该公司属于金融行业（银行/保险/证券），DCF现金流模型不适用。"
                "金融类公司的\"经营现金流\"包含存贷款变动，无法反映真实自由现金流。"
                "建议参考下方 **DDM股利折现模型** 和 **P/B市净率估值**。"
            )
        else:
            dcf_result = dcf_valuation(
                annual_cf, annual_inc, annual_bs,
                growth_rate=dcf_growth, terminal_growth=dcf_terminal,
                discount_rate=dcf_discount, forecast_years=dcf_years,
                shares=market_cap['shares'] if market_cap else None,
            )
            if dcf_result:
                col_d1, col_d2, col_d3 = st.columns(3)
                with col_d1:
                    st.metric("企业价值", f"{dcf_result['enterprise_value'] / 1e8:.2f} 亿元")
                with col_d2:
                    st.metric("股权价值", f"{dcf_result['equity_value'] / 1e8:.2f} 亿元")
                with col_d3:
                    st.metric("每股价值", f"{dcf_result['per_share_value']:.2f} 元")

                with st.expander("查看DCF预测明细"):
                    st.write(f"**基准FCF（近3年正FCF均值）**: {dcf_result['latest_fcf'] / 1e8:.2f} 亿元")
                    ocf_val = annual_cf.get('经营活动产生的现金流量净额')
                    capex_val = annual_cf.get('购建固定资产、无形资产和其他长期资产所支付的现金')
                    if ocf_val is not None and not ocf_val.empty:
                        st.write(f"  - 最近年度经营现金流(CFO): {ocf_val.iloc[-1] / 1e8:.2f} 亿元")
                    if capex_val is not None and not capex_val.empty:
                        st.write(f"  - 最近年度资本支出(CapEx): {capex_val.iloc[-1] / 1e8:.2f} 亿元")

                    proj_df = pd.DataFrame(dcf_result['projected_fcfs'])
                    proj_df['fcf'] = proj_df['fcf'] / 1e8
                    proj_df['discounted_fcf'] = proj_df['discounted_fcf'] / 1e8
                    proj_df.columns = ['年份', '预测FCF(亿)', '折现因子', '折现后FCF(亿)']
                    st.dataframe(
                        proj_df.style.format({
                            '预测FCF(亿)': '{:.2f}',
                            '折现因子': '{:.4f}',
                            '折现后FCF(亿)': '{:.2f}',
                        }),
                        use_container_width=True, hide_index=True,
                    )
                    st.write(f"**终值**: {dcf_result['terminal_value'] / 1e8:.2f} 亿元")
                    st.write(f"**折现终值**: {dcf_result['discounted_terminal'] / 1e8:.2f} 亿元")
                    st.write(f"**净债务(有息负债-现金)**: {dcf_result['net_debt'] / 1e8:.2f} 亿元")

                if current_price > 0:
                    upside = (dcf_result['per_share_value'] - current_price) / current_price * 100
                    ratio = dcf_result['per_share_value'] / current_price
                    st.metric(
                        "估值空间", f"{upside:+.1f}%",
                        delta=f"DCF估值 {dcf_result['per_share_value']:.2f} vs 现价 {current_price:.2f}",
                    )
                    if ratio > 3:
                        st.warning(
                            f"⚠️ DCF估值是当前股价的 {ratio:.1f} 倍，偏差较大，"
                            "可能原因：① 增长率假设过高 ② 近年FCF异常偏高 ③ 公司处于周期高点。"
                            "建议调低增长率或折现率后重新评估。"
                        )
                    elif ratio < 0.2:
                        st.info(
                            "DCF估值远低于当前股价，可能公司处于高成长期，"
                            "市场给予了较高的成长溢价。"
                        )
            else:
                st.warning("无法计算DCF估值，请检查数据")

        st.markdown("---")

        # --- DDM 估值 ---
        st.subheader("📈 DDM 股利折现模型")
        ddm_result = ddm_valuation(
            annual_inc, annual_bs,
            dividend_growth_rate=ddm_growth, discount_rate=ddm_discount,
            shares=market_cap['shares'] if market_cap else None,
        )
        if ddm_result:
            col_dd1, col_dd2 = st.columns(2)
            with col_dd1:
                st.metric("股权价值", f"{ddm_result['equity_value'] / 1e8:.2f} 亿元")
            with col_dd2:
                st.metric("每股价值", f"{ddm_result['per_share_value']:.2f} 元")

            with st.expander("查看DDM预测明细"):
                proj_df = pd.DataFrame(ddm_result['projected_dividends'])
                proj_df['dividend'] = proj_df['dividend'] / 1e8
                proj_df['discounted'] = proj_df['discounted'] / 1e8
                proj_df.columns = ['年份', '预测股利(亿)', '折现后(亿)']
                st.dataframe(
                    proj_df.style.format({
                        '预测股利(亿)': '{:.2f}',
                        '折现后(亿)': '{:.2f}',
                    }),
                    use_container_width=True, hide_index=True,
                )
                st.write(f"**假设分红率**: {ddm_result['payout_ratio'] * 100:.0f}%")
                st.write(f"**最新年度预测分红**: {ddm_result['latest_dividend'] / 1e8:.2f} 亿元")
        else:
            st.warning("该公司净利润为负或不适用DDM模型，建议参考DCF估值")

        st.markdown("---")
        st.caption("⚠️ 免责声明: 本工具仅用于学习和研究目的，所有估值结果仅供参考，不构成投资建议。")

    # ==================== Tab 3: 行业对标 ====================
    with tab3:
        st.header("🏭 行业对标分析")

        if not industry_data:
            st.warning(f"无法获取行业「{industry_name_raw}」的板块数据，可能该行业分类无对应板块")
            st.stop()

        board_name = industry_data['board_name']
        peers = industry_data['peers']
        idx_data = industry_data['index_data']
        pe_history = industry_data['pe_history']

        if peers is None or peers.empty:
            st.warning("无法获取同行业公司数据")
            st.stop()

        stock_code = stock['code']
        stock_name = stock['name']
        stock_in_peers = peers[peers['code'] == stock_code]

        # ======== 1. 行业概况 ========
        st.subheader("1. 行业概况")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("所属行业板块", board_name)
        with col2:
            st.metric("同业公司数", f"{len(peers)} 家")
        with col3:
            st.metric("行业总市值", f"{peers['market_cap_yi'].sum():.0f} 亿元")
        with col4:
            if not stock_in_peers.empty:
                mc_rank = (peers['market_cap_yi'] > float(stock_in_peers.iloc[0]['market_cap_yi'])).sum() + 1
                st.metric("个股市值排名", f"第 {mc_rank} / {len(peers)}")
            else:
                st.metric("个股市值排名", "N/A")

        st.markdown("---")

        # ======== 2. 行业市盈率趋势 ========
        st.subheader("2. 行业市盈率趋势")
        st.caption("基于行业指数价格与当前加权P/E推算，近似反映行业估值变化趋势")

        if pe_history is not None and not pe_history.empty:
            stock_pe = None
            if not stock_in_peers.empty and float(stock_in_peers.iloc[0]['pe']) > 0:
                stock_pe = float(stock_in_peers.iloc[0]['pe'])

            fig_pe = plot_industry_pe_trend(pe_history, stock_pe, stock_name)
            if fig_pe:
                st.plotly_chart(fig_pe, use_container_width=True)

            current_pe = pe_history['pe'].iloc[-1]
            pe_mean = pe_history['pe'].mean()
            pe_percentile = (pe_history['pe'] < current_pe).sum() / len(pe_history) * 100

            col_m1, col_m2, col_m3 = st.columns(3)
            with col_m1:
                st.metric("行业当前P/E", f"{current_pe:.2f}")
            with col_m2:
                st.metric("10年平均P/E", f"{pe_mean:.2f}")
            with col_m3:
                st.metric("当前历史分位", f"{pe_percentile:.0f}%")

            if pe_percentile < 25:
                st.success("行业估值处于历史低位")
            elif pe_percentile > 75:
                st.warning("行业估值处于历史高位")
            else:
                st.info("行业估值处于历史中等水平")
        else:
            st.warning("暂无足够数据生成行业P/E趋势图")

        st.markdown("---")

        # ======== 3. 行业指数走势 ========
        st.subheader("3. 行业指数走势")
        if idx_data is not None and not idx_data.empty:
            fig_idx = plot_industry_marketcap_trend(idx_data, board_name)
            if fig_idx:
                st.plotly_chart(fig_idx, use_container_width=True)
        else:
            st.warning("暂无行业指数数据")

        st.markdown("---")

        # ======== 4. 行业估值分布 ========
        st.subheader("4. 行业估值分布")
        col_pe, col_pb = st.columns(2)
        with col_pe:
            fig_dist_pe = plot_industry_pe_distribution(peers, stock_code, stock_name, 'pe')
            if fig_dist_pe:
                st.plotly_chart(fig_dist_pe, use_container_width=True)
            else:
                st.warning("暂无P/E分布数据")
        with col_pb:
            fig_dist_pb = plot_industry_pe_distribution(peers, stock_code, stock_name, 'pb')
            if fig_dist_pb:
                st.plotly_chart(fig_dist_pb, use_container_width=True)
            else:
                st.warning("暂无P/B分布数据")

        st.markdown("---")

        # ======== 5. 同业估值对比 ========
        st.subheader("5. 同业估值对比")
        col_bars1, col_bars2, col_bars3 = st.columns(3)
        with col_bars1:
            fig_bars_pe = plot_industry_peer_bars(peers, stock_code, stock_name, 'pe', top_n=15)
            if fig_bars_pe:
                st.plotly_chart(fig_bars_pe, use_container_width=True)
        with col_bars2:
            fig_bars_pb = plot_industry_peer_bars(peers, stock_code, stock_name, 'pb', top_n=15)
            if fig_bars_pb:
                st.plotly_chart(fig_bars_pb, use_container_width=True)
        with col_bars3:
            fig_bars_roe = plot_industry_peer_bars(peers, stock_code, stock_name, 'roe', top_n=15)
            if fig_bars_roe:
                st.plotly_chart(fig_bars_roe, use_container_width=True)

        st.markdown("---")

        # ======== 6. 同业对比表 ========
        st.subheader("6. 同业对比表")
        display_df = peers.copy()
        display_df.columns = [
            '代码', '名称', '最新价', '涨跌幅(%)', 'PE(动态)', 'PB', 'ROE(%)',
            '总市值(亿)', '流通市值(亿)', '换手率(%)',
        ]
        display_df = display_df.sort_values('总市值(亿)', ascending=False)
        st.dataframe(
            display_df.style.format({
                '最新价': '{:.2f}',
                '涨跌幅(%)': '{:.2f}',
                'PE(动态)': '{:.1f}',
                'PB': '{:.2f}',
                'ROE(%)': '{:.2f}',
                '总市值(亿)': '{:.1f}',
                '流通市值(亿)': '{:.1f}',
                '换手率(%)': '{:.2f}',
            }),
            use_container_width=True,
            hide_index=True,
        )

        # 行业平均指标
        st.markdown("**行业平均指标**")
        valid_pe = peers[peers['pe'] > 0]
        valid_pb = peers[peers['pb'] > 0]
        valid_roe = peers[peers['roe'] > 0]
        avg_cols = st.columns(4)
        with avg_cols[0]:
            st.metric("行业平均PE", f"{valid_pe['pe'].mean():.1f}" if not valid_pe.empty else "N/A")
        with avg_cols[1]:
            st.metric("行业平均PB", f"{valid_pb['pb'].mean():.2f}" if not valid_pb.empty else "N/A")
        with avg_cols[2]:
            st.metric("行业平均ROE", f"{valid_roe['roe'].mean():.2f}%" if not valid_roe.empty else "N/A")
        with avg_cols[3]:
            st.metric("行业总市值", f"{peers['market_cap_yi'].sum():.0f} 亿元")

        st.markdown("---")

        # ======== 7. 个股行业排名 ========
        st.subheader("7. 个股行业排名")

        if not stock_in_peers.empty:
            stock_row = stock_in_peers.iloc[0]

            valid_pe = peers[peers['pe'] > 0]
            valid_pb = peers[peers['pb'] > 0]
            valid_roe = peers[peers['roe'] > 0]

            rank_cols = st.columns(4)
            with rank_cols[0]:
                if stock_row['pe'] > 0 and not valid_pe.empty:
                    pe_rank = int((valid_pe['pe'] < stock_row['pe']).sum()) + 1
                    st.metric("P/E 排名", f"第 {pe_rank} / {len(valid_pe)}",
                              f"当前: {stock_row['pe']:.1f}")
                else:
                    st.metric("P/E 排名", "N/A")

            with rank_cols[1]:
                if stock_row['pb'] > 0 and not valid_pb.empty:
                    pb_rank = int((valid_pb['pb'] < stock_row['pb']).sum()) + 1
                    st.metric("P/B 排名", f"第 {pb_rank} / {len(valid_pb)}",
                              f"当前: {stock_row['pb']:.2f}")
                else:
                    st.metric("P/B 排名", "N/A")

            with rank_cols[2]:
                if stock_row['roe'] > 0 and not valid_roe.empty:
                    roe_rank = int((valid_roe['roe'] > stock_row['roe']).sum()) + 1
                    st.metric("ROE 排名", f"第 {roe_rank} / {len(valid_roe)}",
                              f"当前: {stock_row['roe']:.2f}%")
                else:
                    st.metric("ROE 排名", "N/A")

            with rank_cols[3]:
                mc_rank = int((peers['market_cap_yi'] > stock_row['market_cap_yi']).sum()) + 1
                st.metric("总市值排名", f"第 {mc_rank} / {len(peers)}",
                          f"当前: {stock_row['market_cap_yi']:.1f}亿")

            st.markdown("")
            st.markdown("**排名说明**: P/E和P/B排名中，排名越靠前表示估值越低（越便宜）。"
                        "ROE排名中，排名越靠前表示盈利能力越强。"
                        "总市值排名反映公司在行业中的规模地位。")
        else:
            st.warning("当前个股不在同业板块成分股列表中，无法计算排名")

        st.caption("⚠️ 数据来源: 东方财富行业板块。P/E趋势为基于指数价格的近似推算，仅供参考。")

else:
    st.info("👈 请在左侧搜索并选择一只股票，然后点击「加载数据」开始分析")
    st.markdown("### 使用说明")
    st.markdown(
        "1. 在左侧搜索框输入**股票代码**（如 `000001`）或**股票名称**（如 `平安银行`）\n"
        "2. 从下拉列表中选择目标股票\n"
        "3. 点击 **📥 加载数据** 按钮\n"
        "4. 系统将自动获取该股票的**季度+年度财报数据**、**历史市值**和**主营构成**\n"
        "5. 在三个标签页中查看**财务分析**、**估值分析**和**行业对标**"
    )

    st.markdown("---")
    st.header("📊 市场情绪参考 — 沪深300市盈率")

    @st.cache_data(ttl=3600, show_spinner="正在获取沪深300市盈率数据...")
    def load_csi300_pe():
        return get_csi300_pe_data(years=10)

    csi300_pe = load_csi300_pe()

    if not csi300_pe.empty:
        fig_csi300 = plot_csi300_pe_trend(csi300_pe)
        if fig_csi300:
            st.plotly_chart(fig_csi300, use_container_width=True)

        current_pe = csi300_pe['滚动市盈率'].iloc[-1]
        pe_10y = csi300_pe['滚动市盈率'].dropna()
        percentile = (pe_10y < current_pe).sum() / len(pe_10y) * 100

        col_m1, col_m2, col_m3 = st.columns(3)
        with col_m1:
            st.metric("沪深300 当前P/E", f"{current_pe:.2f}")
        with col_m2:
            st.metric("10年平均P/E", f"{pe_10y.mean():.2f}")
        with col_m3:
            st.metric("当前历史分位", f"{percentile:.0f}%")

        if percentile < 25:
            st.success("当前估值处于历史低位，市场情绪偏保守")
        elif percentile > 75:
            st.warning("当前估值处于历史高位，市场情绪偏乐观")
        else:
            st.info("当前估值处于历史中等水平")
    else:
        st.warning("暂无法获取沪深300市盈率数据")
