import ccxt
import time
import os

class BinanceAutoCloseSingle:
    def __init__(self):
        self.api_key = os.getenv('BINANCE_API_KEY')
        self.api_secret = os.getenv('BINANCE_API_SECRET')
        
        self.exchange = ccxt.binanceusdm({
            'apiKey': self.api_key,
            'secret': self.api_secret,
            'sandbox': True,
            'options': {'defaultType': 'future'},
        })
        
        self.profit_threshold = 1.0  # 每个币种单独达到1U就平仓
        self.check_interval = 3

    def get_usdm_account_balance(self):
        """获取U本位合约账户余额和持仓"""
        try:
            balance = self.exchange.fetch_balance()
            total_balance = float(balance['total']['USDT'])
            positions = self.exchange.fetch_positions()
            
            print(f"当前总余额: {total_balance:.2f} USDT")
            return total_balance, positions
        except Exception as e:
            print(f"获取账户信息失败: {e}")
            return None, None

    def check_and_close_positions(self, positions):
        """检查每个持仓并单独平仓"""
        closed_any = False
        
        for position in positions:
            symbol = position['symbol']
            unrealized_pnl = float(position['unrealizedPnl'])
            contracts = float(position['contracts'])
            
            # 只处理有持仓的
            if contracts != 0:
                print(f"检查 {symbol}: 盈亏={unrealized_pnl:.2f} USDT, 持仓={contracts}张")
                
                # ⚠️ 关键修改：每个币种单独判断
                if unrealized_pnl >= self.profit_threshold:
                    print(f"🎯 {symbol} 达到止盈条件! 盈亏: {unrealized_pnl:.2f} USDT")
                    self.close_single_position(symbol, contracts)
                    closed_any = True
                elif unrealized_pnl <= -self.profit_threshold:  # 可选：亏损保护
                    print(f"⚠️ {symbol} 亏损达到阈值! 盈亏: {unrealized_pnl:.2f} USDT")
                    # self.close_single_position(symbol, contracts)  # 取消注释启用止损
        
        return closed_any

    def close_single_position(self, symbol, contracts):
        """平仓单个币种的持仓"""
        side = 'sell' if contracts > 0 else 'buy'
        close_amount = abs(contracts)
        
        try:
            order = self.exchange.create_order(
                symbol=symbol,
                type='market',
                side=side,
                amount=close_amount,
                params={'reduceOnly': True}
            )
            print(f"✅ {symbol} 平仓成功: {close_amount}张, 方向: {side}")
            return True
        except Exception as e:
            print(f"❌ {symbol} 平仓失败: {e}")
            return False

    def run_single_mode(self):
        """单个持仓监控模式"""
        print(f"启动单个持仓监控模式")
        print(f"每个币种止盈阈值: {self.profit_threshold} USDT")
        print(f"检查间隔: {self.check_interval}秒")
        print("-" * 50)
        
        while True:
            try:
                total_balance, positions = self.get_usdm_account_balance()
                
                if positions is not None:
                    # 检查并平仓达到阈值的单个持仓
                    closed_any = self.check_and_close_positions(positions)
                    
                    if closed_any:
                        print("✅ 已完成符合条件的平仓操作，继续监控...")
                    else:
                        print("📊 暂无持仓达到止盈条件，继续监控...")
                
                time.sleep(self.check_interval)
                
            except Exception as e:
                print(f"❌ 运行错误: {e}")
                time.sleep(self.check_interval)

# 使用示例
if __name__ == "__main__":
    # 设置环境变量
    os.environ['BINANCE_API_KEY'] = '你的API_KEY'
    os.environ['BINANCE_API_SECRET'] = '你的API_SECRET'
    
    # 选择模式：
    
    # 模式1：总余额监控（原代码）
    # bot = BinanceAutoClose()
    # bot.run()
    
    # 模式2：单个持仓监控（推荐用于套利）
    bot = BinanceAutoCloseSingle()
    bot.run_single_mode()