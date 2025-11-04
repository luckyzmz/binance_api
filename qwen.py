import time
import logging
from binance.client import Client

# ====== 配置区（请修改）======
API_KEY = 'Gvt16Ehe8TH0O4iCTuPgedpvGhZz8t5omd9mwZCGcBjEaY1mup39R1B18LP3TyYN'
API_SECRET = 'OgfVjWYRTAlmAoCkvf8h3GQZFEJAHEnVNk1wzVF7NYAe0pynZuUVRXADtr8Fks6m'
PNL_TAKE_PROFIT = 1.0   # +1 USDT 止盈
PNL_STOP_LOSS = -0.25    # -1 USDT 止损
CHECK_INTERVAL = 3      # 检查间隔（秒）

# 日志配置
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    handlers=[
        logging.FileHandler("binance_hedge_pnl_bot.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger()

# 初始化客户端（实盘）
client = Client(API_KEY, API_SECRET, testnet=False)

def get_all_hedge_positions():
    """获取所有双向持仓中的非零仓位（LONG + SHORT）"""
    try:
        all_positions = client.futures_position_information()
        active = []
        for pos in all_positions:
            amt = float(pos['positionAmt'])
            side = pos['positionSide']
            # 双向模式下，LONG 和 SHORT 分开，且 amt 符号可能不直观，用 abs 判断是否持仓
            if side in ['LONG', 'SHORT'] and abs(amt) > 0:
                active.append(pos)
        return active
    except Exception as e:
        logger.error(f"❌ 获取持仓失败: {e}")
        return []

def close_hedge_position(symbol, position_side, qty):
    """
    平掉指定方向的仓位
    - LONG 仓位 → 用 SELL 平
    - SHORT 仓位 → 用 BUY 平
    """
    side = "SELL" if position_side == "LONG" else "BUY"
    qty = abs(float(qty))  # 确保为正数
    
    try:
        # 查询该 symbol 的数量精度（避免因精度错误被拒）
        exchange_info = client.futures_exchange_info()
        symbol_info = next((s for s in exchange_info['symbols'] if s['symbol'] == symbol), None)
        if not symbol_info:
            raise ValueError(f"未找到 {symbol} 的交易规则")
        
        # 获取数量精度（如 BTCUSDT 通常是 3 位小数）
        qty_precision = symbol_info['quantityPrecision']
        qty_str = f"{{:.{qty_precision}f}}".format(qty).rstrip('0').rstrip('.')
        if not qty_str:
            qty_str = "0"

        logger.info(f"准备平仓 | {symbol} | 方向: {position_side} | 数量: {qty_str}")

        order = client.futures_create_order(
            symbol=symbol,
            side=side,
            positionSide=position_side,  # 必须指定！
            type="MARKET",
            quantity=qty_str
        )
        logger.info(f"✅ 平仓成功 | {symbol} | {position_side} | 订单ID: {order['orderId']}")
        return True

    except Exception as e:
        logger.error(f"❌ 平仓失败 | {symbol} {position_side}: {e}")
        return False

def main():
    logger.info("🚀 启动【双向持仓】PnL 监控（止盈 +1U / 止损 -1U）")
    logger.info("📌 账户模式：Hedge Mode（双向持仓）| 实盘运行 | 小额测试建议")

    while True:
        try:
            positions = get_all_hedge_positions()
            if not positions:
                logger.debug("💤 无活跃仓位，继续监控...")
                time.sleep(CHECK_INTERVAL)
                continue

            for pos in positions:
                symbol = pos['symbol']
                position_side = pos['positionSide']  # 'LONG' 或 'SHORT'
                qty = float(pos['positionAmt'])
                unrealized_pnl = float(pos['unRealizedProfit'])

                logger.info(f"🔍 {symbol} | {position_side} | 仓位: {qty} | PnL: {unrealized_pnl:.4f} USDT")

                if unrealized_pnl >= PNL_TAKE_PROFIT:
                    logger.warning(f"🎯 {symbol} {position_side} 触发止盈（{unrealized_pnl:.2f} USDT）")
                    close_hedge_position(symbol, position_side, qty)

                elif unrealized_pnl <= PNL_STOP_LOSS:
                    logger.warning(f"⚠️ {symbol} {position_side} 触发止损（{-unrealized_pnl:.2f} USDT 亏损）")
                    close_hedge_position(symbol, position_side, qty)

            time.sleep(CHECK_INTERVAL)

        except KeyboardInterrupt:
            logger.info("🛑 用户终止程序")
            break
        except Exception as e:
            logger.error(f"💥 主循环异常: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()