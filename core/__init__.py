"""finacial-invest 核心业务逻辑包。

从 scripts/ 影子迁移而来, 与 AI 编排层(.claude/)解耦:
- providers/   数据接入层(QuoteProvider 抽象)
- storage/     时序存储(Parquet + DuckDB)
- timeseries/  时序处理(对齐/复权/防穿越)
- factors/     因子库(模块化 + IC/IR)
- regime/      市场环境分层
- backtest/    回测引擎(walk-forward)
- portfolio/   组合/资金管理
- risk/        风控硬门
- forecasting/ 走势判断(概率路径)

对外接口: SDK (import core) + CLI (python -m core / core 命令)
"""
__version__ = "0.1.0"
