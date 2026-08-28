"""
数据获取模块 - 通过akshare(Sina)获取任意A股的季度+年度财报数据，实时行情
"""
import pandas as pd
import numpy as np
import requests
from datetime import datetime
from pathlib import Path

DATA_DIR = Path(__file__).parent / "download_financial_statement_files"
COMPANY_INFO_DIR = Path(__file__).parent / "company_info"

# ====== 资产负债表：用户图片中的项目 → Sina列名 ======
# 资产项(蓝色)
BS_ASSET_ITEMS = [
    ('现金', '货币资金'),
    ('应收款', '应收票据及应收账款'),
    ('预付款', '预付款项'),
    ('存货', '存货'),
    ('其它流动', '其他流动资产'),
    ('长期投资', '长期股权投资'),
    ('固定资产', '固定资产净额'),
    ('无形&商誉', None),  # 特殊处理：无形资产 + 商誉
    ('其它固定', '其他非流动资产'),
]
# 负债项(红色)
BS_LIAB_ITEMS = [
    ('短期借款', '短期借款'),
    ('应付款', '应付票据及应付账款'),
    ('预收款', '预收款项'),
    ('薪酬&税', None),  # 特殊处理：应付职工薪酬 + 应交税费
    ('其它流动', '其他应付款'),  # 用其他应付款代替
    ('长期借款', '长期借款'),
    ('其它非流动', '其他非流动负债'),
]

# ====== 利润表需要的列 ======
INCOME_COLS = [
    '营业总收入', '营业收入', '营业总成本', '营业成本',
    '销售费用', '管理费用', '财务费用', '研发费用',
    '营业利润', '利润总额', '净利润', '归属于母公司所有者的净利润',
    '基本每股收益',
]

# ====== 现金流量表需要的列 ======
CASHFLOW_COLS = [
    '经营活动产生的现金流量净额',
    '投资活动产生的现金流量净额',
    '筹资活动产生的现金流量净额',
    '购建固定资产、无形资产和其他长期资产所支付的现金',
    '分配股利、利润或偿付利息支付的现金',
]

# ====== 资产负债表所有需要的列 ======
BS_ALL_COLS = [
    '货币资金', '应收票据及应收账款', '预付款项', '存货',
    '其他流动资产', '长期股权投资', '固定资产净额',
    '无形资产', '商誉', '其他非流动资产',
    '短期借款', '应付票据及应付账款', '预收款项',
    '应付职工薪酬', '应交税费', '其他应付款',
    '长期借款', '应付债券', '其他非流动负债',
    '资产总计', '负债合计', '归属于母公司股东权益合计',
    '实收资本(或股本)',
    '流动资产合计', '流动负债合计',
]


def _to_sina_code(code, exchange):
    """转成Sina格式: sh688256 / sz000001"""
    ex = exchange.lower()
    return f"{ex}{code}"


def _parse_date(date_str):
    """解析Sina报告日: '20260630' -> datetime"""
    try:
        return datetime.strptime(str(date_str).strip(), '%Y%m%d')
    except (ValueError, TypeError):
        return None


STOCK_LIST_CACHE = Path(__file__).parent / "stock_list_cache.csv"


def get_stock_list():
    """
    获取所有A股股票列表（上交所+深交所+北交所）
    优先从本地缓存加载，否则从Sina API获取
    返回: DataFrame with columns [code, name, exchange]
    """
    # 1. 尝试从本地缓存加载
    if STOCK_LIST_CACHE.exists():
        try:
            df = pd.read_csv(STOCK_LIST_CACHE, dtype={'code': str})
            if not df.empty:
                return df
        except Exception:
            pass

    # 2. 从Sina Market Center API获取（绕过代理）
    import json
    session = requests.Session()
    session.trust_env = False
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)',
        'Referer': 'https://finance.sina.com.cn',
    })

    all_stocks = []
    page = 1
    max_pages = 80

    while page <= max_pages:
        url = 'http://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData'
        params = {'page': page, 'num': 100, 'node': 'hs_a', 'sort': 'symbol', 'asc': 1}
        try:
            r = session.get(url, params=params, timeout=15)
            data = json.loads(r.text)
            if not data:
                break
            for item in data:
                code = str(item.get('code', ''))
                name = str(item.get('name', '')).replace(' ', '')
                if not code or not name:
                    continue
                if code.startswith('6') or code.startswith('9'):
                    exchange = 'SH'
                elif code.startswith('0') or code.startswith('3') or code.startswith('2'):
                    exchange = 'SZ'
                elif code.startswith('8') or code.startswith('4'):
                    exchange = 'BJ'
                else:
                    exchange = 'SZ'
                all_stocks.append({'code': code, 'name': name, 'exchange': exchange})
            page += 1
        except Exception:
            page += 1

    # 3. 回退到akshare（如果Sina API失败）
    if not all_stocks:
        import akshare as ak
        import os
        saved = {}
        for k in ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy']:
            if k in os.environ:
                saved[k] = os.environ.pop(k)
        try:
            for board in ['主板A股', '科创板']:
                try:
                    df = ak.stock_info_sh_name_code(symbol=board)
                    for _, row in df.iterrows():
                        all_stocks.append({
                            'code': str(row['证券代码']).zfill(6),
                            'name': row['证券简称'],
                            'exchange': 'SH',
                        })
                except Exception:
                    pass
        finally:
            os.environ.update(saved)

    result = pd.DataFrame(all_stocks)
    if not result.empty:
        result = result.drop_duplicates(subset='code', keep='first')
        try:
            result.to_csv(STOCK_LIST_CACHE, index=False)
        except Exception:
            pass
    return result


def search_stocks(keyword, limit=20):
    """
    搜索股票：按代码或名称模糊匹配
    如果输入6位数字代码且不在列表中，自动创建条目
    """
    try:
        all_stocks = get_stock_list()
    except Exception:
        return pd.DataFrame(columns=['code', 'name', 'exchange', 'display'])

    keyword = keyword.strip()
    mask = (
        all_stocks['code'].str.contains(keyword, na=False) |
        all_stocks['name'].str.contains(keyword, na=False)
    )
    matched = all_stocks[mask].head(limit).copy()

    # 如果输入是6位数字代码且未找到，自动创建条目
    if len(keyword) == 6 and keyword.isdigit() and matched.empty:
        if keyword.startswith('6') or keyword.startswith('9'):
            exchange = 'SH'
        elif keyword.startswith('0') or keyword.startswith('3') or keyword.startswith('2'):
            exchange = 'SZ'
        elif keyword.startswith('8') or keyword.startswith('4'):
            exchange = 'BJ'
        else:
            exchange = 'SZ'
        matched = pd.DataFrame([{
            'code': keyword,
            'name': f'股票{keyword}',
            'exchange': exchange,
        }])

    if not matched.empty:
        matched['display'] = matched['name'] + ' (' + matched['exchange'] + matched['code'] + ')'
    return matched


def _fetch_sina_financial_with_retry(sina_code, symbol, max_retries=3):
    """
    带重试和代理绕过的Sina财报数据获取
    """
    import akshare as ak
    import time
    import os

    last_error = None
    for attempt in range(max_retries):
        # 每次尝试都清除代理环境变量
        saved = {}
        for k in ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy',
                   'ALL_PROXY', 'all_proxy']:
            if k in os.environ:
                saved[k] = os.environ.pop(k)
        try:
            df = ak.stock_financial_report_sina(stock=sina_code, symbol=symbol)
            return df
        except Exception as e:
            last_error = e
            time.sleep(1)
        finally:
            os.environ.update(saved)

    raise last_error


def fetch_balance_sheet(code, exchange):
    """
    从Sina获取资产负债表（含季度+年度）
    返回: DataFrame, index=datetime
    """
    sina_code = _to_sina_code(code, exchange)
    df = _fetch_sina_financial_with_retry(sina_code, '资产负债表')

    # 解析日期
    df['报告日'] = df['报告日'].apply(_parse_date)
    df = df.dropna(subset=['报告日'])
    df = df.sort_values('报告日')

    # 只保留需要的列
    available = [c for c in BS_ALL_COLS if c in df.columns]
    result = df[['报告日'] + available].copy()
    result = result.set_index('报告日')

    # 转为数值
    for col in result.columns:
        result[col] = pd.to_numeric(result[col], errors='coerce')

    return result


def fetch_income_statement(code, exchange):
    """
    从Sina获取利润表（含季度+年度）
    """
    sina_code = _to_sina_code(code, exchange)
    df = _fetch_sina_financial_with_retry(sina_code, '利润表')

    df['报告日'] = df['报告日'].apply(_parse_date)
    df = df.dropna(subset=['报告日'])
    df = df.sort_values('报告日')

    available = [c for c in INCOME_COLS if c in df.columns]
    result = df[['报告日'] + available].copy()
    result = result.set_index('报告日')

    for col in result.columns:
        result[col] = pd.to_numeric(result[col], errors='coerce')

    return result


def fetch_cash_flow(code, exchange):
    """
    从Sina获取现金流量表（含季度+年度）
    """
    sina_code = _to_sina_code(code, exchange)
    df = _fetch_sina_financial_with_retry(sina_code, '现金流量表')

    df['报告日'] = df['报告日'].apply(_parse_date)
    df = df.dropna(subset=['报告日'])
    df = df.sort_values('报告日')

    available = [c for c in CASHFLOW_COLS if c in df.columns]
    result = df[['报告日'] + available].copy()
    result = result.set_index('报告日')

    for col in result.columns:
        result[col] = pd.to_numeric(result[col], errors='coerce')

    return result


def get_current_price(code, exchange):
    """
    从Sina实时接口获取当前股价
    返回: float 或 None
    """
    sina_code = _to_sina_code(code, exchange)
    try:
        session = requests.Session()
        session.trust_env = False  # 绕过代理，直连Sina
        url = f'https://hq.sinajs.cn/list={sina_code}'
        headers = {'Referer': 'https://finance.sina.com.cn'}
        r = session.get(url, headers=headers, timeout=15)
        text = r.text.split('"')[1]
        parts = text.split(',')
        price = float(parts[3])
        if price == 0:
            price = float(parts[2])  # 用昨收价
        return price
    except Exception:
        return None


def get_market_cap(code, exchange, balance_sheet=None):
    """
    计算总市值 = 股本 × 当前股价
    balance_sheet: 可选，已获取的资产负债表（避免重复请求）
    返回: dict with 'price', 'shares', 'market_cap'(元), 'market_cap_yi'(亿元)
    """
    price = get_current_price(code, exchange)
    if price is None or price == 0:
        return None

    # 从资产负债表获取股本
    shares = None
    if balance_sheet is not None and '实收资本(或股本)' in balance_sheet.columns:
        shares = balance_sheet['实收资本(或股本)'].dropna()
        if not shares.empty:
            shares = float(shares.iloc[-1])

    # 回退：从东方财富push2 API获取总市值，反推股本
    if shares is None or shares == 0:
        try:
            em_prefix = '1' if code.startswith('6') or code.startswith('9') else '0'
            em_secid = f'{em_prefix}.{code}'
            session = requests.Session()
            session.trust_env = False
            session.headers.update({
                'User-Agent': 'Mozilla/5.0',
                'Referer': 'https://data.eastmoney.com',
            })
            url = 'https://push2.eastmoney.com/api/qt/stock/get'
            params = {'secid': em_secid, 'fields': 'f116,f117'}
            r = session.get(url, params=params, timeout=10)
            data = r.json()
            em_mc = data.get('data', {}).get('f116', 0)
            if em_mc and em_mc > 0 and price > 0:
                shares = em_mc / price
        except Exception:
            pass

    if shares is None or shares == 0:
        return None

    market_cap = price * shares
    return {
        'price': price,
        'shares': shares,
        'market_cap': market_cap,
        'market_cap_yi': market_cap / 1e8,
    }


def filter_annual(df):
    """从混合数据中筛选年度报告（12月31日）"""
    return df[df.index.month == 12]


def filter_quarterly(df):
    """获取所有季度报告（含年度）"""
    return df


def get_company_info(code, exchange):
    """
    从东方财富datacenter获取公司基本信息（直连，绕过代理）
    返回: dict
    """
    if exchange is None:
        exchange = 'SH' if code.startswith('6') else 'SZ'

    session = requests.Session()
    session.trust_env = False

    # 构造SECUCODE: 600519.SH / 000001.SZ
    secucode = f"{code}.{exchange.upper()}"
    url = 'https://datacenter.eastmoney.com/securities/api/data/v1/get'
    params = {
        'reportName': 'RPT_F10_BASIC_ORGINFO',
        'columns': 'ALL',
        'filter': f'(SECUCODE="{secucode}")',
        'pageNumber': 1,
        'pageSize': 1,
    }
    try:
        r = session.get(url, params=params, timeout=15)
        data = r.json()
        if data.get('result') and data['result'].get('data'):
            return data['result']['data'][0]
    except Exception:
        pass
    return None


def get_company_business(code, exchange=None):
    """
    获取公司主营业务信息（兼容接口，实际调用get_company_info）
    """
    if exchange is None:
        # 尝试从code推断exchange
        exchange = 'SH' if code.startswith('6') else 'SZ'
    return get_company_info(code, exchange)


def fetch_all_data(code, exchange):
    """
    一次性获取所有数据
    返回: dict with 'balance_sheet', 'income_statement', 'cash_flow',
          'balance_sheet_annual', 'income_statement_annual', 'cash_flow_annual',
          'market_cap', 'historical_market_cap', 'main_business'
    """
    bs = fetch_balance_sheet(code, exchange)
    inc = fetch_income_statement(code, exchange)
    cf = fetch_cash_flow(code, exchange)

    mc = get_market_cap(code, exchange, balance_sheet=bs)

    # 获取历史市值数据（每月月底收盘价 × 历史股本）
    historical_mc = None
    try:
        monthly_prices = get_historical_monthly_prices(code, exchange, years=10)
        share_capital = get_historical_share_capital(code)
        if not monthly_prices.empty and not share_capital.empty:
            historical_mc = calculate_historical_market_cap(monthly_prices, share_capital)
    except Exception:
        pass

    # 获取主营构成数据
    main_business = None
    try:
        main_business = get_main_business_composition(code, exchange, years=10)
    except Exception:
        pass

    # 获取季度收盘价（前复权）
    quarterly_prices = None
    try:
        quarterly_prices = get_quarterly_closing_prices(code, exchange, years=10)
    except Exception:
        pass

    # 获取beta和无风险利率（用于WACC计算）
    beta = None
    try:
        beta = get_beta(code, exchange, years=2)
    except Exception:
        pass

    risk_free_rate = None
    try:
        risk_free_rate = get_risk_free_rate()
    except Exception:
        pass

    return {
        'balance_sheet': bs,
        'income_statement': inc,
        'cash_flow': cf,
        'balance_sheet_annual': filter_annual(bs),
        'income_statement_annual': filter_annual(inc),
        'cash_flow_annual': filter_annual(cf),
        'market_cap': mc,
        'historical_market_cap': historical_mc,
        'main_business': main_business,
        'quarterly_prices': quarterly_prices,
        'beta': beta,
        'risk_free_rate': risk_free_rate,
    }


# ====== 历史市值 & 主营业务构成 ======

def get_historical_monthly_prices(code, exchange, years=10):
    """
    获取不复权的历史每月月底收盘价
    返回: pd.Series, index=日期, values=收盘价
    """
    import akshare as ak
    import os

    # 绕过代理
    saved = {}
    for k in ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy']:
        if k in os.environ:
            saved[k] = os.environ.pop(k)

    try:
        sina_code = _to_sina_code(code, exchange)
        end_date = datetime.now().strftime('%Y%m%d')
        start_year = datetime.now().year - years - 1
        start_date = f"{start_year}0101"

        df = ak.stock_zh_a_daily(
            symbol=sina_code,
            start_date=start_date,
            end_date=end_date,
            adjust=""  # 不复权
        )

        if df.empty:
            return pd.Series(dtype=float)

        df['date'] = pd.to_datetime(df['date'])
        df = df.set_index('date')
        # 每月月底收盘价
        monthly = df['close'].resample('ME').last().dropna()
        return monthly
    except Exception:
        return pd.Series(dtype=float)
    finally:
        os.environ.update(saved)


def get_quarterly_closing_prices(code, exchange, years=10):
    """
    获取前复权的每季度末收盘价
    返回: pd.Series, index=季度末日期, values=收盘价
    """
    import akshare as ak
    import os

    saved = {}
    for k in ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy']:
        if k in os.environ:
            saved[k] = os.environ.pop(k)

    try:
        sina_code = _to_sina_code(code, exchange)
        end_date = datetime.now().strftime('%Y%m%d')
        start_year = datetime.now().year - years - 1
        start_date = f"{start_year}0101"

        df = ak.stock_zh_a_daily(
            symbol=sina_code,
            start_date=start_date,
            end_date=end_date,
            adjust="qfq"
        )

        if df.empty:
            return pd.Series(dtype=float)

        df['date'] = pd.to_datetime(df['date'])
        df = df.set_index('date')
        quarterly = df['close'].resample('QE').last().dropna()
        return quarterly
    except Exception:
        return pd.Series(dtype=float)
    finally:
        os.environ.update(saved)


def get_beta(code, exchange, years=2):
    """
    计算个股beta值（相对于沪深300指数）
    使用最近2年日收益率回归
    返回: float 或 None
    """
    import akshare as ak
    import os
    import numpy as np

    saved = {}
    for k in ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy']:
        if k in os.environ:
            saved[k] = os.environ.pop(k)

    try:
        sina_code = _to_sina_code(code, exchange)
        end_date = datetime.now().strftime('%Y%m%d')
        start_year = datetime.now().year - years
        start_date = f"{start_year}0101"

        stock_df = ak.stock_zh_a_daily(
            symbol=sina_code,
            start_date=start_date,
            end_date=end_date,
            adjust="qfq"
        )
        if stock_df.empty:
            return None

        index_df = ak.stock_zh_index_daily(symbol='sh000300')
        if index_df is None or index_df.empty:
            return None

        stock_df['date'] = pd.to_datetime(stock_df['date'])
        stock_df = stock_df.set_index('date').sort_index()

        index_df['date'] = pd.to_datetime(index_df['date'])
        index_df = index_df.set_index('date').sort_index()

        stock_returns = stock_df['close'].pct_change().dropna()
        index_returns = index_df['close'].pct_change().dropna()

        common_dates = stock_returns.index.intersection(index_returns.index)
        if len(common_dates) < 30:
            return None

        stock_r = stock_returns.loc[common_dates]
        index_r = index_returns.loc[common_dates]

        cov_matrix = np.cov(stock_r, index_r)
        beta = cov_matrix[0, 1] / cov_matrix[1, 1]

        if pd.isna(beta) or beta <= 0:
            return None

        return float(beta)
    except Exception:
        return None
    finally:
        os.environ.update(saved)


def get_risk_free_rate():
    """
    获取中国10年期国债收益率作为无风险利率
    返回: float (百分比，如1.68表示1.68%)
    """
    import akshare as ak
    import os

    saved = {}
    for k in ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy']:
        if k in os.environ:
            saved[k] = os.environ.pop(k)

    try:
        from datetime import datetime as dt
        start = f"{dt.now().year}0101"
        df = ak.bond_zh_us_rate(start_date=start)
        if df.empty:
            return 2.0

        latest = df.iloc[-1]
        rf = latest.get('中国国债收益率10年')
        if pd.isna(rf):
            return 2.0
        return float(rf)
    except Exception:
        return 2.0
    finally:
        os.environ.update(saved)


def get_csi300_pe_data(years=10):
    """
    获取沪深300指数市盈率历史数据（来自乐咕乐股）
    返回: pd.DataFrame, 包含日期/指数/滚动市盈率等列
    """
    import akshare as ak
    import os

    saved = {}
    for k in ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy']:
        if k in os.environ:
            saved[k] = os.environ.pop(k)

    try:
        df = ak.stock_index_pe_lg(symbol='沪深300')
        if df is None or df.empty:
            return pd.DataFrame()

        df['日期'] = pd.to_datetime(df['日期'])
        cutoff = pd.Timestamp.now() - pd.DateOffset(years=years)
        df = df[df['日期'] >= cutoff].sort_values('日期').reset_index(drop=True)
        return df
    except Exception:
        return pd.DataFrame()
    finally:
        os.environ.update(saved)


_BOARD_LIST_CACHE = None


def _get_board_code(industry_name):
    """
    通过东方财富push2 API获取行业板块代码
    返回: (board_code, matched_name) 或 (None, None)
    """
    global _BOARD_LIST_CACHE

    session = requests.Session()
    session.trust_env = False
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)',
        'Referer': 'https://data.eastmoney.com',
    })

    if _BOARD_LIST_CACHE is None:
        url = 'https://push2.eastmoney.com/api/qt/clist/get'
        params = {
            'pn': 1, 'pz': 500,
            'po': 1, 'np': 1,
            'fltt': 2, 'invt': 2,
            'fs': 'm:90+t:2',
            'fields': 'f12,f14',
        }
        try:
            r = session.get(url, params=params, timeout=15)
            data = r.json()
            boards = data.get('data', {}).get('diff', [])
            _BOARD_LIST_CACHE = {b['f14']: b['f12'] for b in boards}
        except Exception:
            _BOARD_LIST_CACHE = {}

    if industry_name in _BOARD_LIST_CACHE:
        return _BOARD_LIST_CACHE[industry_name], industry_name

    for name, code in _BOARD_LIST_CACHE.items():
        if industry_name in name or name in industry_name:
            return code, name

    return None, None


def get_industry_board_name(industry_name):
    """
    匹配东方财富行业板块名称
    返回: str (板块名称) 或 None
    """
    _, matched_name = _get_board_code(industry_name)
    return matched_name if matched_name else None


def get_industry_peers(industry_name):
    """
    获取同行业公司列表及关键指标（来自东方财富push2 API）
    返回: DataFrame with columns [code, name, price, change_pct, pe, pb,
          market_cap_yi, circ_market_cap_yi, turnover_rate]
    """
    board_code, _ = _get_board_code(industry_name)
    if not board_code:
        return pd.DataFrame()

    session = requests.Session()
    session.trust_env = False
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)',
        'Referer': 'https://data.eastmoney.com',
    })

    url = 'https://push2.eastmoney.com/api/qt/clist/get'
    params = {
        'pn': 1, 'pz': 5000,
        'po': 1, 'np': 1,
        'fltt': 2, 'invt': 2,
        'fs': f'b:{board_code}',
        'fields': 'f2,f3,f8,f9,f12,f14,f20,f21,f23,f115',
    }
    try:
        r = session.get(url, params=params, timeout=15)
        data = r.json()
        stocks = data.get('data', {}).get('diff', [])

        if not stocks:
            return pd.DataFrame()

        df = pd.DataFrame(stocks)
        result = pd.DataFrame()
        result['code'] = df['f12'].astype(str)
        result['name'] = df['f14']
        result['price'] = pd.to_numeric(df.get('f2', 0), errors='coerce')
        result['change_pct'] = pd.to_numeric(df.get('f3', 0), errors='coerce')
        result['turnover_rate'] = pd.to_numeric(df.get('f8', 0), errors='coerce')
        result['pe'] = pd.to_numeric(df.get('f9', 0), errors='coerce')
        result['pb'] = pd.to_numeric(df.get('f23', 0), errors='coerce')
        result['roe'] = pd.to_numeric(df.get('f115', 0), errors='coerce')
        result['market_cap_yi'] = pd.to_numeric(df.get('f20', 0), errors='coerce') / 1e8
        result['circ_market_cap_yi'] = pd.to_numeric(df.get('f21', 0), errors='coerce') / 1e8

        return result
    except Exception:
        return pd.DataFrame()


def get_industry_index_data(industry_name, years=10):
    """
    获取行业板块指数历史数据（来自东方财富push2his API）
    返回: DataFrame with columns [date, close, volume, change_pct]
    """
    board_code, matched_name = _get_board_code(industry_name)
    if not board_code:
        return pd.DataFrame()

    session = requests.Session()
    session.trust_env = False
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)',
        'Referer': 'https://data.eastmoney.com',
    })

    end_date = datetime.now().strftime('%Y%m%d')
    start_year = datetime.now().year - years
    start_date = f"{start_year}0101"

    url = 'https://push2his.eastmoney.com/api/qt/stock/kline/get'
    params = {
        'secid': f'90.{board_code}',
        'klt': '101',
        'fqt': '0',
        'beg': start_date,
        'end': end_date,
        'fields1': 'f1,f2,f3,f4,f5,f6',
        'fields2': 'f51,f52,f53,f54,f55,f56,f57,f58',
    }
    try:
        r = session.get(url, params=params, timeout=15)
        data = r.json()
        klines = data.get('data', {}).get('klines', [])

        if not klines:
            return pd.DataFrame()

        records = []
        for line in klines:
            parts = line.split(',')
            if len(parts) >= 8:
                records.append({
                    'date': pd.to_datetime(parts[0]),
                    'close': float(parts[2]),
                    'volume': float(parts[5]),
                    'change_pct': float(parts[7]),
                })

        result = pd.DataFrame(records)
        return result.sort_values('date').reset_index(drop=True)
    except Exception:
        return pd.DataFrame()


def compute_industry_pe_history(index_data, peers_df):
    """
    计算行业市盈率历史趋势（近似值）
    使用行业指数价格和当前成分股加权P/E推算

    注：此方法假设成分股盈利不变，仅反映价格变动对P/E的影响
    """
    if index_data is None or index_data.empty or peers_df is None or peers_df.empty:
        return pd.DataFrame()

    valid = peers_df[(peers_df['pe'] > 0) & (peers_df['pe'] < 500)]
    if valid.empty:
        return pd.DataFrame()

    total_mc = valid['market_cap_yi'].sum()
    total_earnings = (valid['market_cap_yi'] / valid['pe']).sum()

    if total_earnings <= 0 or total_mc <= 0:
        return pd.DataFrame()

    current_pe = total_mc / total_earnings

    current_index = index_data['close'].iloc[-1]
    if current_index <= 0:
        return pd.DataFrame()

    result = index_data[['date', 'close']].copy()
    result['pe'] = current_pe * (result['close'] / current_index)

    return result


def get_historical_share_capital(code):
    """
    获取历史股本结构变化数据（来自东方财富）
    返回: pd.DataFrame, columns=[变更日期, 总股本], 按日期升序
    """
    import akshare as ak
    import os

    saved = {}
    for k in ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy']:
        if k in os.environ:
            saved[k] = os.environ.pop(k)

    try:
        df = ak.stock_zh_a_gbjg_em(symbol=code)
        if df is None or df.empty:
            return pd.DataFrame()

        # 只需要变更日期和总股本
        result = df[['变更日期', '总股本']].copy()
        result['变更日期'] = pd.to_datetime(result['变更日期'])
        result['总股本'] = pd.to_numeric(result['总股本'], errors='coerce')
        result = result.dropna(subset=['总股本'])
        result = result.sort_values('变更日期')
        result = result.drop_duplicates(subset='变更日期', keep='last')
        return result
    except Exception:
        return pd.DataFrame()
    finally:
        os.environ.update(saved)


def calculate_historical_market_cap(weekly_prices, share_capital_df):
    """
    计算历史总市值 = 每周五收盘价 × 当时对应的总股本
    weekly_prices: pd.Series, index=日期, values=收盘价
    share_capital_df: pd.DataFrame, columns=[变更日期, 总股本]
    返回: pd.DataFrame, columns=[date, close, shares, market_cap_yi]
    """
    if weekly_prices.empty or share_capital_df.empty:
        return pd.DataFrame()

    caps = share_capital_df.set_index('变更日期')['总股本']

    results = []
    for date, price in weekly_prices.items():
        # 找到该日期时点对应的最新股本
        applicable = caps[caps.index <= date]
        if applicable.empty:
            continue
        shares = float(applicable.iloc[-1])
        market_cap = price * shares
        results.append({
            'date': date,
            'close': price,
            'shares': shares,
            'market_cap_yi': market_cap / 1e8,
        })

    return pd.DataFrame(results)


def get_main_business_composition(code, exchange, years=10):
    """
    获取主营构成数据（来自东方财富API）
    返回: dict with keys 'by_industry', 'by_product', 'by_region'
    每个 value 是 list of dict:
        {report_date, report_name, item_name, income, cost, profit, gross_profit_ratio, mbi_ratio}
    """
    import json

    secucode = f"{code}.{exchange.upper()}"
    session = requests.Session()
    session.trust_env = False
    session.headers.update({
        'User-Agent': 'Mozilla/5.0',
        'Referer': 'https://data.eastmoney.com',
    })

    all_records = []
    page = 1
    while True:
        url = 'https://datacenter.eastmoney.com/securities/api/data/v1/get'
        params = {
            'reportName': 'RPT_F10_FN_MAINOP',
            'columns': 'ALL',
            'filter': f'(SECUCODE="{secucode}")',
            'pageNumber': page,
            'pageSize': 100,
            'sortColumns': 'REPORT_DATE',
            'sortTypes': '-1',
        }
        try:
            r = session.get(url, params=params, timeout=15)
            data = r.json()
            if not data.get('result') or not data['result'].get('data'):
                break
            page_data = data['result']['data']
            all_records.extend(page_data)
            if len(page_data) < 100:
                break
            page += 1
        except Exception:
            break

    if not all_records:
        return {'by_industry': [], 'by_product': [], 'by_region': []}

    # MAINOP_TYPE: "1"=按行业, "2"=按产品, "3"=按地区
    type_map = {'1': 'by_industry', '2': 'by_product', '3': 'by_region'}

    result = {'by_industry': [], 'by_product': [], 'by_region': []}

    # 只保留年度报告（12月31日）
    cutoff_year = datetime.now().year - years

    for rec in all_records:
        report_date_str = rec.get('REPORT_DATE', '')
        if not report_date_str:
            continue
        try:
            report_date = pd.to_datetime(report_date_str)
        except Exception:
            continue

        # 只保留年报
        if report_date.month != 12:
            continue
        if report_date.year < cutoff_year:
            continue

        mainop_type = str(rec.get('MAINOP_TYPE', ''))
        category = type_map.get(mainop_type)
        if not category:
            continue

        item_name = rec.get('ITEM_NAME', '').strip()
        if not item_name:
            continue

        income = rec.get('MAIN_BUSINESS_INCOME')
        cost = rec.get('MAIN_BUSINESS_COST')
        profit = rec.get('MAIN_BUSINESS_RPOFIT')  # API中拼写为RPOFIT
        gross_ratio = rec.get('GROSS_RPOFIT_RATIO')
        mbi_ratio = rec.get('MBI_RATIO')

        result[category].append({
            'report_date': report_date,
            'report_year': str(report_date.year),
            'item_name': item_name,
            'income': float(income) if income is not None else None,
            'cost': float(cost) if cost is not None else None,
            'profit': float(profit) if profit is not None else None,
            'gross_profit_ratio': float(gross_ratio) * 100 if gross_ratio is not None else None,
            'income_ratio': float(mbi_ratio) * 100 if mbi_ratio is not None else None,
        })

    return result


# ====== 本地CSV兼容（向后兼容）======
def list_local_companies():
    """列出本地CSV中有的公司"""
    import glob
    import re
    csv_files = glob.glob(str(DATA_DIR / "*_balance_sheet_年度.csv"))
    companies = []
    for f in csv_files:
        basename = Path(f).name
        match = re.match(r'(.+?)_(A|HK)_(SH|SZ|HK)(\d+)_balance_sheet', basename)
        if match:
            name = match.group(1)
            exchange = match.group(3)
            code = match.group(4)
            companies.append({
                'name': name,
                'exchange': exchange,
                'code': code,
                'display': f"{name} ({exchange}{code})",
            })
    return companies


def load_local_company_info(prefix):
    """加载本地公司信息"""
    path = COMPANY_INFO_DIR / f"{prefix}_info.txt"
    if path.exists():
        df = pd.read_csv(path, sep=r'\s+', engine='python')
        df.columns = df.columns.str.strip()
        return df
    return None
