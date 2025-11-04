import ccxt
import time
import os
from decimal import Decimal

class BinanceAutoClose:
    def __init__(self):
        self.api_key = os.getenv('BINANCE_API_KEY')
        self.api_secret = os.getenv('BINANCE_API_SECRET')
        
        # 初始化币安交易所连接
        self.exchange = ccxt.binanceusdm({
            'apiKey': self.api_key,
            'secret': self.api_secret,
            'sandbox': True,  # 测试网模式，实盘请设为False
            'options': {
                'defaultType': 'future',
            }
        })
        
        self.profit_threshold = 1.0  # 1U止盈阈值
        self.check_interval = 3     # 检查间隔(秒)

    def get_usdm_account_balance(self):
        """获取U本位合约账户余额和未实现盈亏"""
        try:
            balance = self.exchange.fetch_balance()
            total_balance = float(balance['total']['USDT'])
            positions = self.exchange.fetch_positions()
            
            print(f"当前总余额: {total_balance:.2f} USDT")
            return total_balance, positions
        except Exception as e:
            print(f"获取账户信息失败: {e}")
            return None, None

    def calculate_unrealized_pnl(self, positions):
        """计算所有持仓的总未实现盈亏"""
        total_unrealized_pnl = 0.0
        open_positions = []
        
        for position in positions:
            symbol = position['symbol']
            unrealized_pnl = float(position['unrealizedPnl'])
            contracts = float(position['contracts'])
            
            if contracts != 0:  # 只统计有持仓的
                total_unrealized_pnl += unrealized_pnl
                open_positions.append({
                    'symbol': symbol,
                    'unrealized_pnl': unrealized_pnl,
                    'contracts': contracts,
                    'side': 'long' if contracts > 0 else 'short'
                })
                print(f"  {symbol}: {unrealized_pnl:.2f} USDT")
        
        return total_unrealized_pnl, open_positions

    def close_all_positions(self, positions):
        """一键平仓所有持仓"""
        print("开始执行一键平仓...")
        
        for position in positions:
            symbol = position['symbol']
            contracts = abs(position['contracts'])
            side = 'sell' if position['contracts'] > 0 else 'buy'  # 多仓平仓用sell，空仓平仓用buy
            
            try:
                # 市价平仓
                order = self.exchange.create_order(
                    symbol=symbol,
                    type='market',
                    side=side,
                    amount=contracts,
                    params={'reduceOnly': True}  # 只减仓标志
                )
                print(f"✅ 平仓成功: {symbol} {contracts}张, 方向: {side}")
                
            except Exception as e:
                print(f"❌ 平仓失败 {symbol}: {e}")

    def run(self):
        """主运行循环"""
        print(f"启动U本位合约自动止盈机器人")
        print(f"止盈阈值: {self.profit_threshold} USDT")
        print(f"检查间隔: {self.check_interval}秒")
        print("-" * 50)
        
        while True:
            try:
                # 获取账户信息
                total_balance, positions = self.get_usdm_account_balance()
                
                if positions is not None:
                    # 计算总未实现盈亏
                    total_unrealized_pnl, open_positions = self.calculate_unrealized_pnl(positions)
                    print(f"总未实现盈亏: {total_unrealized_pnl:.2f} USDT")
                    print("-" * 30)
                    
                    # 检查是否达到止盈阈值
                    if total_unrealized_pnl >= self.profit_threshold:
                        print(f"🎯 达到止盈条件! 未实现盈亏: {total_unrealized_pnl:.2f} USDT")
                        self.close_all_positions(open_positions)
                        print("✅ 所有仓位已平仓，程序继续运行...")
                
                # 等待下一次检查
                time.sleep(self.check_interval)
                
            except Exception as e:
                print(f"❌ 运行错误: {e}")
                time.sleep(self.check_interval)

# 使用示例
if __name__ == "__main__":
    # 设置环境变量
    os.environ['BINANCE_API_KEY'] = '你的API_KEY'
    os.environ['BINANCE_API_SECRET'] = '你的API_SECRET'
    
    bot = BinanceAutoClose()
    bot.run()