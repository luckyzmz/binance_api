import ccxt
import time
import os
import json

class BinanceAutoCloseFixed:
    def __init__(self):
        self.api_key = os.getenv('BINANCE_API_KEY')
        self.api_secret = os.getenv('BINANCE_API_SECRET')
        
        # 初始化币安交易所连接 - 简化配置
        self.exchange = ccxt.binance({
            'apiKey': self.api_key,
            'secret': self.api_secret,
            'sandbox': False,  # 测试网模式
            'options': {
                'defaultType': 'future',
            }
        })
        
        self.profit_threshold = 0.66   # 1U止盈阈值
        self.loss_threshold = -0.10    # 1U止损阈值
        self.check_interval = 5       # 检查间隔

    def get_account_info(self):
        """获取账户信息"""
        try:
            # 获取余额
            balance = self.exchange.fetch_balance()
            total_balance = float(balance['total']['USDT'])
            
            # 获取持仓 - 使用正确的端点
            positions = self.exchange.fetch_positions()
            
            print(f"当前总余额: {total_balance:.2f} USDT")
            return total_balance, positions
            
        except Exception as e:
            print(f"❌ 获取账户信息失败: {e}")
            return None, None

    def analyze_positions(self, positions):
        """分析持仓情况"""
        open_positions = []
        total_pnl = 0.0
        
        for position in positions:
            symbol = position['symbol']
            unrealized_pnl = float(position['unrealizedPnl'])
            contracts = float(position['contracts'])
            
            if contracts != 0:  # 只处理有持仓的
                total_pnl += unrealized_pnl
                
                # 确定持仓方向
                if contracts > 0:
                    position_info = {
                        'symbol': symbol,
                        'unrealized_pnl': unrealized_pnl,
                        'contracts': contracts,
                        'position_side': 'LONG',
                        'close_side': 'SELL'
                    }
                else:
                    position_info = {
                        'symbol': symbol,
                        'unrealized_pnl': unrealized_pnl,
                        'contracts': abs(contracts),
                        'position_side': 'SHORT', 
                        'close_side': 'BUY'
                    }
                
                open_positions.append(position_info)
                
                # 显示持仓状态
                status = "🟢" if unrealized_pnl >= 0 else "🔴"
                print(f"  {status} {symbol} {position_info['position_side']}: {unrealized_pnl:+.2f} USDT")
        
        return total_pnl, open_positions

    def close_position_safely(self, position):
        """安全平仓方法"""
        symbol = position['symbol']
        amount = position['contracts']
        close_side = position['close_side']
        position_side = position['position_side']
        
        print(f"🚀 尝试平仓 {symbol} {position_side}: {amount}张")
        
        try:
            # 方法1: 使用create_order但不指定reduceOnly
            print("尝试方法1: 标准平仓")
            order = self.exchange.create_order(
                symbol=symbol,
                type='MARKET',
                side=close_side,
                amount=amount,
                params={
                    'positionSide': position_side
                }
            )
            print(f"✅ {symbol} 平仓成功")
            return True
            
        except Exception as e:
            print(f"❌ 方法1失败: {e}")
            
            try:
                # 方法2: 使用原生API调用
                print("尝试方法2: 原生API")
                clean_symbol = symbol.replace('/', '')
                params = {
                    'symbol': clean_symbol,
                    'side': close_side,
                    'type': 'MARKET',
                    'quantity': amount,
                    'positionSide': position_side
                }
                
                # 使用私密端点
                response = self.exchange.fapiPrivatePostOrder(params)
                print(f"✅ {symbol} 平仓成功 (原生API)")
                return True
                
            except Exception as e2:
                print(f"❌ 方法2失败: {e2}")
                
                try:
                    # 方法3: 极简方式 - 只传必要参数
                    print("尝试方法3: 极简方式")
                    order = self.exchange.create_order(
                        symbol=symbol,
                        type='MARKET', 
                        side=close_side,
                        amount=amount
                    )
                    print(f"✅ {symbol} 平仓成功 (极简方式)")
                    return True
                    
                except Exception as e3:
                    print(f"❌ 方法3失败: {e3}")
                    return False

    def check_trading_conditions(self, positions):
        """检查交易条件并执行平仓"""
        actions_taken = 0
        
        for position in positions:
            pnl = position['unrealized_pnl']
            symbol = position['symbol']
            
            # 止盈检查
            if pnl >= self.profit_threshold:
                print(f"🎯 {symbol} 达到止盈条件! 盈利: {pnl:.2f} USDT")
                if self.close_position_safely(position):
                    actions_taken += 1
                    print(f"💰 止盈成功，锁定盈利: {pnl:.2f} USDT")
                    time.sleep(1)  # 避免频繁请求
                    
            # 止损检查        
            elif pnl <= self.loss_threshold:
                print(f"🛑 {symbol} 达到止损条件! 亏损: {pnl:.2f} USDT")
                if self.close_position_safely(position):
                    actions_taken += 1
                    print(f"💸 止损成功，避免更大亏损")
                    time.sleep(1)  # 避免频繁请求
        
        return actions_taken

    def run(self):
        """主运行循环"""
        print("🎯 启动币安自动止盈止损机器人")
        print(f"📈 止盈阈值: +{self.profit_threshold} USDT")
        print(f"📉 止损阈值: {self.loss_threshold} USDT") 
        print(f"⏰ 检查间隔: {self.check_interval}秒")
        print("=" * 50)
        
        while True:
            try:
                # 获取账户信息
                balance, positions = self.get_account_info()
                
                if positions:
                    # 分析持仓
                    total_pnl, open_positions = self.analyze_positions(positions)
                    
                    print(f"📊 总未实现盈亏: {total_pnl:+.2f} USDT")
                    print(f"📋 持仓数量: {len(open_positions)} 个")
                    print("-" * 40)
                    
                    # 检查并执行平仓
                    actions = self.check_trading_conditions(open_positions)
                    
                    if actions > 0:
                        print(f"🎉 本次执行了 {actions} 个平仓操作")
                    else:
                        print("👀 监控中...")
                
                # 等待下次检查
                time.sleep(self.check_interval)
                
            except Exception as e:
                print(f"❌ 运行错误: {e}")
                time.sleep(10)  # 出错时等待时间长一些

# 测试函数 - 先验证能否获取持仓
def test_connection():
    """测试连接和持仓获取"""
    print("🔍 测试连接...")
    
    exchange = ccxt.binance({
        'apiKey': os.getenv('BINANCE_API_KEY'),
        'secret': os.getenv('BINANCE_API_SECRET'),
        'sandbox': True,
        'options': {'defaultType': 'future'},
    })
    
    try:
        # 测试获取余额
        balance = exchange.fetch_balance()
        print(f"✅ 连接成功! 余额: {balance['total']['USDT']} USDT")
        
        # 测试获取持仓
        positions = exchange.fetch_positions()
        open_count = sum(1 for p in positions if float(p['contracts']) != 0)
        print(f"✅ 持仓获取成功! 当前有 {open_count} 个持仓")
        
        # 显示持仓详情
        for position in positions:
            contracts = float(position['contracts'])
            if contracts != 0:
                print(f"   {position['symbol']}: {contracts} 张, 盈亏: {position['unrealizedPnl']} USDT")
                
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False

if __name__ == "__main__":
    # 设置环境变量
    os.environ['BINANCE_API_KEY'] = 'Gvt16Ehe8TH0O4iCTuPgedpvGhZz8t5omd9mwZCGcBjEaY1mup39R1B18LP3TyYN'
    os.environ['BINANCE_API_SECRET'] = 'OgfVjWYRTAlmAoCkvf8h3GQZFEJAHEnVNk1wzVF7NYAe0pynZuUVRXADtr8Fks6m'
    
    print("开始测试连接...")
    if test_connection():
        print("\n" + "="*50)
        print("测试通过，启动机器人...")
        print("="*50)
        bot = BinanceAutoCloseFixed()
        bot.run()
    else:
        print("❌ 连接测试失败，请检查API密钥和网络连接")