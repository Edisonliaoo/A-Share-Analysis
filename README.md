# A股投资分析系统

基于 Streamlit 的 A股投资分析工具，提供公司财务分析、估值建模、行业对标和多股对比功能。

## 功能

- **公司财务分析**：资产负债表、利润表、现金流量表、杜邦分析、财务质量指标、成长性分析、股东结构
- **公司估值分析**：DCF 现金流折现模型（含敏感性分析）、DDM 股利折现模型、P/E 和 P/B 相对估值、WACC 自动计算、风险指标、机构一致预期
- **行业对标**：行业市盈率趋势、估值分布、同业对比排名
- **多股对比**：自选股横向对比、雷达图、分项对比

## 快速开始

```bash
# 1. 克隆仓库
git clone https://github.com/Edisonliaoo/A-Share-Analysis.git
cd A-Share-Analysis

# 2. 安装依赖
pip install -r requirements.txt

# 3. 启动应用
streamlit run app.py
```

应用将在 `http://localhost:8501` 启动。

## 环境变量（可选）

研报生成模块需要 LLM API 密钥。在项目根目录创建 `.env` 文件：

```
ARK_API_KEY=your_api_key_here
OPENAI_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
```

主应用（app.py）不需要任何 API 密钥，使用公开的东方财富/新浪财经数据接口。

## 项目结构

```
app.py                  # Streamlit 主应用
data_fetcher.py         # 数据获取（东方财富/Sina/akshare）
financial_metrics.py    # 财务指标计算
valuation.py            # 估值模型（DCF/DDM/PB/PE）
visualizations.py       # 可视化图表（Plotly）
.streamlit/config.toml  # Streamlit 主题配置
```

## 数据来源

- 东方财富（财务报表、行情、行业板块、股东数据）
- 新浪财经（行情数据）
- akshare（补充数据）

## 免责声明

本工具仅用于学习和研究目的，所有估值结果仅供参考，不构成投资建议。
