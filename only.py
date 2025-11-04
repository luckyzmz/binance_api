import ccxt
import time
import os

class SimpleAutoClose:
    def __init__(self):
        self.api_key = os.getenv('BINANCE_API_KEY')
        self.api_secret = os.getenv('BINANCE_API_SECRET')
        
        # 最简单的配置
        self.exchange = ccxt.binance({
            'apiKey': self.api_key,
            'secret': self.api_secret,
        })
        
        self.profit_target = 1.0  # 盈利1U平仓
        self.loss_limit = -1.0    # 亏损1U平仓
        self.check_every = 5      # 5秒检查一次

    def get_positions(self):
        """获取当前持仓"""
        try:
            positions = self.exchange.fetch_balance()['info']['positions']
            open_positions = []
            
            for pos in positions:
                if float(pos['positionAmt']) != 0:
                    open_positions.append({
                        'symbol': pos['symbol'],
                        'amount': float(pos['positionAmt']),
                        'pnl': float(pos['unRealizedProfit'])
                    })
                    print(f"持仓: {pos['symbol']} {pos['positionAmt']}张, 盈亏: {pos['unRealizedProfit']} USDT")
            
            return open_positions
        except Exception as e:
            print(f"获取持仓失败: {e}")
            return []

    def close_position(self, symbol, amount):
        """平仓 - 最简单的方式"""
        try:
            # 判断平仓方向
            if amount > 0:
                # 多仓，用卖出平仓
                side = 'sell'
                print(f"平多仓: {symbol} {amount}张")
            else:
                # 空仓，用买入平仓  
                side = 'buy'
                print(f"平空仓: {symbol} {abs(amount)}张")
            
            # 最简单的下单方式
            order = self.exchange.create_market_order(
                symbol=symbol,
                side=side,
                amount=abs(amount)
            )
            
            print(f"✅ 平仓成功: {symbol}")
            return True
            
        except Exception as e:
            print(f"❌ 平仓失败 {symbol}: {e}")
            return False

    def run(self):
        """主循环"""
        print("🚀 启动极简自动平仓机器人")
        print(f"🎯 盈利目标: +{self.profit_target}U")
        print(f"🛑 止损限制: {self.loss_limit}U")
        
        while True:
            try:
                positions = self.get_positions()
                
                for pos in positions:
                    symbol = pos['symbol']
                    pnl = pos['pnl']
                    amount = pos['amount']
                    
                    print(f"检查 {symbol}: 盈亏={pnl:.2f}U")
                    
                    # 盈利平仓
                    if pnl >= self.profit_target:
                        print(f"🎉 {symbol} 达到盈利目标! +{pnl:.2f}U")
                        self.close_position(symbol, amount)
                    
                    # 止损平仓  
                    elif pnl <= self.loss_limit:
                        print(f"💸 {symbol} 触发止损! {pnl:.2f}U")
                        self.close_position(symbol, amount)
                
                time.sleep(self.check_every)
                
            except Exception as e:
                print(f"错误: {e}")
                time.sleep(10)

# 使用方式
if __name__ == "__main__":
    # 设置你的API密钥
    os.environ['BINANCE_API_KEY'] = 'Gvt16Ehe8TH0O4iCTuPgedpvGhZz8t5omd9mwZCGcBjEaY1mup39R1B18LP3TyYN'
    os.environ['BINANCE_API_SECRET'] = 'OgfVjWYRTAlmAoCkvf8h3GQZFEJAHEnVNk1wzVF7NYAe0pynZuUVRXADtr8Fks6m'
    
    bot = SimpleAutoClose()
    bot.run()