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
            'sandbox': False,  # 测试网模式，实盘请设为False
            'options': {
                'defaultType': 'future',
            }
        })
        
        self.profit_threshold = 0.8  # 1U止盈阈值
        self.loss_threshold = -0.9  # 1U止损阈值
        self.check_interval = 5     # 检查间隔(秒)，避免频率限制
        
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
                
                # 用颜色标识盈亏状态
                status = "🟢" if unrealized_pnl >= 0 else "🔴"
                print(f"  {status} {symbol} {position_side}: {unrealized_pnl:+.2f} USDT, 持仓: {abs(contracts)}张")
        
        return total_unrealized_pnl, open_positions

    def close_single_position_dual(self, symbol, contracts, position_side, reason=""):
        """双向模式下平仓单个持仓 - 完全修复版"""
        close_side = 'sell' if position_side == 'LONG' else 'buy'
        close_amount = abs(contracts)
        
        # 修复符号问题
        clean_symbol = symbol.replace('/USDT:USDT', '/USDT').replace(':USDT', '/USDT')
        
        print(f"🚀 {reason}平仓 {clean_symbol} {position_side}: {close_amount}张")
        
        # 方法1：最简单的平仓，不使用reduceOnly
        try:
            order = self.exchange.create_order(
                symbol=clean_symbol,
                type='market',
                side=close_side,
                amount=close_amount,
                params={
                    'positionSide': position_side
                }
            )
            print(f"✅ {clean_symbol} {position_side} {reason}平仓成功")
            return True
            
        except Exception as e:
            print(f"❌ 方法1失败: {e}")
            
            # 方法2：使用币安原生API
            try:
                clean_symbol_base = symbol.replace('/USDT', '').replace(':USDT', '')
                
                params = {
                    'symbol': clean_symbol_base,
                    'side': close_side.upper(),
                    'type': 'MARKET',
                    'quantity': round(close_amount, 6),
                    'positionSide': position_side,
                }
                
                order = self.exchange.fapiPrivatePostOrder(params)
                print(f"✅ {clean_symbol_base} {position_side} {reason}平仓成功（原生API）")
                return True
                
            except Exception as e2:
                print(f"❌ 所有平仓方法都失败: {e2}")
                return False

    def check_and_close_individual_dual(self, positions):
        """双向模式下检查并平仓达到条件的持仓（止盈+止损）"""
        closed_any = False
        
        for position in positions:
            symbol = position['symbol']
            unrealized_pnl = position['unrealized_pnl']
            contracts = position['contracts']
            position_side = position['position_side']
            
            # 用颜色显示当前状态
            if unrealized_pnl >= self.profit_threshold:
                status = "🎯"
            elif unrealized_pnl <= self.loss_threshold:
                status = "⚠️ "
            else:
                status = "📊"
                
            print(f"{status} {symbol} {position_side}: 盈亏={unrealized_pnl:+.2f} USDT")
            
            # 止盈条件检查
            if unrealized_pnl >= self.profit_threshold:
                print(f"🎯 {symbol} {position_side} 达到止盈条件! 盈利: {unrealized_pnl:.2f} USDT")
                if self.close_single_position_dual(symbol, contracts, position_side, "止盈"):
                    closed_any = True
                    print(f"💰 已锁定盈利: {unrealized_pnl:.2f} USDT")
                    time.sleep(2)  # 平仓后稍作停顿
            
            # 止损条件检查
            elif unrealized_pnl <= self.loss_threshold:
                print(f"🛑 {symbol} {position_side} 达到止损条件! 亏损: {unrealized_pnl:.2f} USDT")
                if self.close_single_position_dual(symbol, contracts, position_side, "止损"):
                    closed_any = True
                    print(f"💸 已止损，避免更大亏损")
                    time.sleep(2)  # 平仓后稍作停顿
        
        return closed_any

    def get_trading_summary(self, positions):
        """获取交易摘要信息"""
        total_pnl = 0.0
        profit_count = 0
        loss_count = 0
        at_risk_count = 0
        
        for position in positions:
            pnl = position['unrealized_pnl']
            total_pnl += pnl
            
            if pnl >= self.profit_threshold:
                profit_count += 1
            elif pnl <= self.loss_threshold:
                loss_count += 1
            elif pnl < 0:  # 亏损但未达止损
                at_risk_count += 1
        
        return {
            'total_pnl': total_pnl,
            'profit_count': profit_count,
            'loss_count': loss_count,
            'at_risk_count': at_risk_count
        }

    def run(self):
        """单个持仓监控模式 - 止盈+止损"""
        print(f"🎯 启动双向持仓自动止盈止损机器人")
        print(f"📈 单个持仓止盈阈值: +{self.profit_threshold} USDT")
        print(f"📉 单个持仓止损阈值: {self.loss_threshold} USDT")
        print(f"⏰ 检查间隔: {self.check_interval}秒")
        print("=" * 60)
        
        while True:
            try:
                # 获取账户信息
                total_balance, positions = self.get_usdm_account_balance()
                
                if positions is not None:
                    # 计算总未实现盈亏和获取持仓详情
                    total_unrealized_pnl, open_positions = self.calculate_unrealized_pnl(positions)
                    
                    # 获取交易摘要
                    summary = self.get_trading_summary(open_positions)
                    
                    print(f"📊 持仓概览:")
                    print(f"   总未实现盈亏: {total_unrealized_pnl:+.2f} USDT")
                    print(f"   达到止盈条件: {summary['profit_count']} 个")
                    print(f"   达到止损条件: {summary['loss_count']} 个") 
                    print(f"   存在亏损风险: {summary['at_risk_count']} 个")
                    print("-" * 40)
                    
                    # 检查并平仓达到条件的持仓
                    closed_any = self.check_and_close_individual_dual(open_positions)
                    
                    if closed_any:
                        print("🎉 已完成平仓操作，继续监控...")
                    else:
                        if summary['profit_count'] > 0:
                            print("⏳ 有持仓达到止盈条件，等待平仓...")
                        elif summary['loss_count'] > 0:
                            print("⏳ 有持仓达到止损条件，等待平仓...")
                        else:
                            print("👀 监控中...")
                
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