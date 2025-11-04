import ccxt
import time
import os

class BinanceDualModeAutoClose:
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
        
        # 验证是否为双向持仓模式
        self.verify_dual_mode()

    def verify_dual_mode(self):
        """验证并确认双向持仓模式"""
        try:
            response = self.exchange.fapiPrivateGetPositionSideDual()
            dual_mode = response.get('dualSidePosition', False)
            if dual_mode:
                print("✅ 当前为双向持仓模式")
            else:
                print("⚠️ 当前为单向持仓模式，建议在币安App中切换到双向持仓模式")
        except Exception as e:
            print(f"获取持仓模式失败: {e}")

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
        """计算所有持仓的未实现盈亏 - 双向模式专用"""
        total_unrealized_pnl = 0.0
        open_positions = []
        
        for position in positions:
            symbol = position['symbol']
            unrealized_pnl = float(position['unrealizedPnl'])
            contracts = float(position['contracts'])
            
            if contracts != 0:  # 只统计有持仓的
                total_unrealized_pnl += unrealized_pnl
                
                # 在双向模式下，需要明确获取持仓方向
                position_side = 'LONG' if contracts > 0 else 'SHORT'
                
                open_positions.append({
                    'symbol': symbol,
                    'unrealized_pnl': unrealized_pnl,
                    'contracts': contracts,
                    'side': 'long' if contracts > 0 else 'short',
                    'position_side': position_side  # 双向模式关键字段
                })
                print(f"  {symbol} {position_side}: {unrealized_pnl:.2f} USDT, 持仓: {abs(contracts)}张")
        
        return total_unrealized_pnl, open_positions

    def close_single_position_dual(self, symbol, contracts, position_side):
        """双向模式下平仓单个持仓 - 修复版"""
        close_side = 'sell' if position_side == 'LONG' else 'buy'
        close_amount = abs(contracts)
        
        print(f"平仓 {symbol} {position_side}: {close_amount}张")
        
        try:
            # 方法1：使用正确的reduceOnly参数格式
            order = self.exchange.create_order(
                symbol=symbol,
                type='market',
                side=close_side,
                amount=close_amount,
                params={
                    'reduceOnly': True,  # 使用布尔值而不是字符串
                    'positionSide': position_side
                }
            )
            print(f"✅ {symbol} {position_side} 平仓成功")
            return True
            
        except Exception as e:
            print(f"❌ 方法1平仓失败 {symbol} {position_side}: {e}")
            
            # 方法2：尝试不使用reduceOnly参数
            try:
                print(f"尝试方法2：不使用reduceOnly参数")
                order = self.exchange.create_order(
                    symbol=symbol,
                    type='market',
                    side=close_side,
                    amount=close_amount,
                    params={
                        'positionSide': position_side
                        # 移除reduceOnly参数
                    }
                )
                print(f"✅ {symbol} {position_side} 平仓成功（方法2）")
                return True
                
            except Exception as e2:
                print(f"❌ 方法2平仓失败 {symbol} {position_side}: {e2}")
                
                # 方法3：使用备选API端点
                return self.alternative_close_dual(symbol, close_amount, position_side, close_side)

    def alternative_close_dual(self, symbol, amount, position_side, close_side):
        """双向持仓模式备选平仓方法 - 修复版"""
        try:
            print(f"尝试备选方法平仓: {symbol} {position_side}")
            
            # 使用币安特定的API端点，正确的参数格式
            params = {
                'symbol': symbol.replace('/', ''),
                'side': close_side.upper(),
                'type': 'MARKET',
                'quantity': amount,
                'positionSide': position_side,
                # 移除reduceOnly参数或者使用正确格式
            }
            
            # 使用私密端点下单
            order = self.exchange.fapiPrivatePostOrder(params)
            print(f"✅ 备选方法平仓成功: {symbol} {position_side}")
            return True
            
        except Exception as e:
            print(f"❌ 备选方法也失败: {e}")
            
            # 最后尝试：使用不同的reduceOnly格式
            return self.final_close_attempt(symbol, amount, position_side, close_side)

    def final_close_attempt(self, symbol, amount, position_side, close_side):
        """最终平仓尝试"""
        try:
            print(f"最终尝试平仓: {symbol} {position_side}")
            
            # 尝试使用字符串格式的reduceOnly
            params = {
                'symbol': symbol.replace('/', ''),
                'side': close_side.upper(),
                'type': 'MARKET',
                'quantity': amount,
                'positionSide': position_side,
                'reduceOnly': 'true'  # 使用字符串格式
            }
            
            order = self.exchange.fapiPrivatePostOrder(params)
            print(f"✅ 最终方法平仓成功: {symbol} {position_side}")
            return True
            
        except Exception as e:
            print(f"❌ 所有平仓方法都失败: {e}")
            return False

    def check_and_close_individual_dual(self, positions):
        """双向模式下检查并平仓单个达到阈值的持仓"""
        closed_any = False
        
        for position in positions:
            symbol = position['symbol']
            unrealized_pnl = position['unrealized_pnl']
            contracts = position['contracts']
            position_side = position['position_side']
            
            print(f"检查 {symbol} {position_side}: 盈亏={unrealized_pnl:.2f} USDT")
            
            # 每个持仓单独判断
            if unrealized_pnl >= self.profit_threshold:
                print(f"🎯 {symbol} {position_side} 达到止盈条件! 盈亏: {unrealized_pnl:.2f} USDT")
                if self.close_single_position_dual(symbol, contracts, position_side):
                    closed_any = True
                    print(f"💰 已锁定盈利: {unrealized_pnl:.2f} USDT")
        
        return closed_any

    def run(self):
        """单个持仓监控模式 - 每个持仓独立判断"""
        print(f"启动双向持仓自动止盈机器人")
        print(f"单个持仓止盈阈值: {self.profit_threshold} USDT")
        print(f"检查间隔: {self.check_interval}秒")
        print("=" * 50)
        
        while True:
            try:
                # 获取账户信息
                total_balance, positions = self.get_usdm_account_balance()
                
                if positions is not None:
                    # 计算总未实现盈亏和获取持仓详情
                    total_unrealized_pnl, open_positions = self.calculate_unrealized_pnl(positions)
                    print(f"当前总未实现盈亏: {total_unrealized_pnl:.2f} USDT")
                    print("-" * 40)
                    
                    # 检查并平仓单个达到阈值的持仓
                    closed_any = self.check_and_close_individual_dual(open_positions)
                    
                    if closed_any:
                        print("🎉 已完成止盈平仓操作，继续监控...")
                    else:
                        print("⏳ 暂无持仓达到止盈条件，继续监控...")
                
                # 等待下一次检查
                time.sleep(self.check_interval)
                
            except Exception as e:
                print(f"❌ 运行错误: {e}")
                time.sleep(self.check_interval)

# 使用示例
if __name__ == "__main__":
    # 设置环境变量
    os.environ['BINANCE_API_KEY'] = 'Gvt16Ehe8TH0O4iCTuPgedpvGhZz8t5omd9mwZCGcBjEaY1mup39R1B18LP3TyYN'
    os.environ['BINANCE_API_SECRET'] = 'OgfVjWYRTAlmAoCkvf8h3GQZFEJAHEnVNk1wzVF7NYAe0pynZuUVRXADtr8Fks6m'
    
    # 创建并运行机器人
    bot = BinanceDualModeAutoClose()

    bot.run()
