import ccxt
import time
import os

class BinanceAutoCloseFixed:
    def __init__(self):
        self.api_key = os.getenv('BINANCE_API_KEY')
        self.api_secret = os.getenv('BINANCE_API_SECRET')
       
        # 初始化币安实盘连接
        self.exchange = ccxt.binance({
            'apiKey': self.api_key,
            'secret': self.api_secret,
            'options': {
                'defaultType': 'future',
            }
        })
       
        self.profit_threshold = 0.8  # 1U止盈阈值
        self.loss_threshold = -0.5   # 1U止损阈值
        self.check_interval = 5      # 检查间隔
       
        # 检查持仓模式并打印
        self.is_hedge_mode = self.check_position_mode()

    def check_position_mode(self):
        """检查持仓模式"""
        try:
            response = self.exchange.fapiPrivateGetPositionSideDual()
            is_hedge = response['dualSidePosition']  # True为Hedge，False为One-Way
            mode = "Hedge Mode" if is_hedge else "One-Way Mode"
            print(f"📋 当前持仓模式: {mode}")
            return is_hedge
        except Exception as e:
            print(f"❌ 检查模式失败: {e}")
            return None  # 默认假设One-Way

    def get_account_info(self):
        """获取账户信息"""
        try:
            # 获取余额
            balance = self.exchange.fetch_balance()
            total_balance = float(balance['total']['USDT'])
           
            # 获取持仓
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
                        'close_side': 'sell'
                    }
                else:
                    position_info = {
                        'symbol': symbol,
                        'unrealized_pnl': unrealized_pnl,
                        'contracts': abs(contracts),
                        'position_side': 'SHORT',
                        'close_side': 'buy'
                    }
               
                open_positions.append(position_info)
               
                # 显示持仓状态
                status = "🟢" if unrealized_pnl >= 0 else "🔴"
                print(f" {status} {symbol} {position_info['position_side']}: {unrealized_pnl:+.2f} USDT")
       
        return total_pnl, open_positions

    def close_position_safely(self, position):
        """安全平仓方法（优化版：移除timeInForce，修复symbol格式）"""
        symbol = position['symbol']
        amount = self.exchange.amount_to_precision(symbol, position['contracts'])  # 返回str，确保精度
        close_side = position['close_side']
        position_side = position['position_side']
        is_hedge = self.is_hedge_mode  # 使用初始化时检查的结果

        print(f"🚀 尝试平仓 {symbol} {position_side}: {amount}张 (模式: {'Hedge' if is_hedge else 'One-Way'})")

        # 基础参数：移除timeInForce，仅根据模式添加reduceOnly
        base_params = {}
        if not is_hedge:  # One-Way模式下添加reduceOnly
            base_params['reduceOnly'] = True

        try:
            # 方法1: Hedge模式专用（无timeInForce）
            if is_hedge:
                params = {**base_params, 'positionSide': position_side}
                order = self.exchange.create_order(
                    symbol=symbol,
                    type='market',
                    side=close_side,
                    amount=amount,
                    params=params
                )
                print(f"✅ {symbol} 平仓成功 (Hedge)")
                return True

            # 方法2: One-Way/通用（无timeInForce）
            else:
                params = base_params
                order = self.exchange.create_order(
                    symbol=symbol,
                    type='market',
                    side=close_side,
                    amount=amount,
                    params=params
                )
                print(f"✅ {symbol} 平仓成功 (One-Way)")
                return True

        except Exception as e:
            print(f"❌ 平仓失败 (详细: {str(e)})")
           
            try:
                # 方法3: 原生API备用（移除timeInForce，优化symbol和quantity格式）
                print("尝试方法3: 原生API")
                clean_symbol = symbol.replace('/', '')  # e.g., 'ETHUSDT'
                api_params = {
                    'symbol': clean_symbol,
                    'side': close_side.upper(),
                    'type': 'MARKET',
                    'quantity': str(amount),  # 确保为字符串
                }
                if is_hedge:
                    api_params['positionSide'] = position_side
                else:
                    api_params['reduceOnly'] = True  # One-Way下添加（ccxt处理为正确格式）
                response = self.exchange.fapiPrivatePostOrder(api_params)
                print(f"✅ {symbol} 平仓成功 (原生API)")
                return True
            except Exception as e3:
                print(f"❌ 原生API失败: {str(e3)}")
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
        print("🎯 启动币安自动止盈止损机器人 - 实盘模式")
        print(f"📈 止盈阈值: +{self.profit_threshold} USDT")
        print(f"📉 止损阈值: {self.loss_threshold} USDT")
        print(f"⏰ 检查间隔: {self.check_interval}秒")
        print("🚨 注意: 这是实盘交易，请谨慎操作！")
        print("=" * 60)
       
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
                else:
                    print("📭 当前无持仓")
               
                # 等待下次检查
                time.sleep(self.check_interval)
               
            except Exception as e:
                print(f"❌ 运行错误: {e}")
                time.sleep(10)  # 出错时等待时间长一些

# 实盘连接测试
def test_real_connection():
    """测试实盘连接"""
    print("🔍 测试实盘连接...")
   
    exchange = ccxt.binance({
        'apiKey': os.getenv('BINANCE_API_KEY'),
        'secret': os.getenv('BINANCE_API_SECRET'),
        'options': {'defaultType': 'future'},
    })
   
    try:
        # 测试获取余额
        balance = exchange.fetch_balance()
        usdt_balance = float(balance['total']['USDT'])
        print(f"✅ 实盘连接成功! 余额: {usdt_balance:.2f} USDT")
       
        # 测试获取持仓
        positions = exchange.fetch_positions()
        open_count = sum(1 for p in positions if float(p['contracts']) != 0)
        print(f"✅ 持仓获取成功! 当前有 {open_count} 个持仓")
       
        # 显示持仓详情
        for position in positions:
            contracts = float(position['contracts'])
            if contracts != 0:
                pnl = float(position['unrealizedPnl'])
                status = "盈利" if pnl >= 0 else "亏损"
                print(f" {position['symbol']}: {contracts} 张, {status} {pnl:.2f} USDT")
               
        return True
       
    except Exception as e:
        print(f"❌ 实盘连接失败: {e}")
        return False

# 紧急手动平仓
def emergency_close_all():
    """紧急平仓所有持仓 - 实盘版本（优化：移除timeInForce）"""
    print("🚨 执行紧急平仓 - 实盘！")
   
    exchange = ccxt.binance({
        'apiKey': os.getenv('BINANCE_API_KEY'),
        'secret': os.getenv('BINANCE_API_SECRET'),
        'options': {'defaultType': 'future'},
    })
   
    try:
        # 检查模式
        response = exchange.fapiPrivateGetPositionSideDual()
        is_hedge = response['dualSidePosition']
        print(f"持仓模式: {'Hedge' if is_hedge else 'One-Way'}")
       
        positions = exchange.fetch_positions()
        closed_count = 0
       
        for position in positions:
            contracts = float(position['contracts'])
            if contracts != 0:
                symbol = position['symbol']
               
                if contracts > 0:
                    side = 'sell'
                    action = "平多仓"
                    pos_side = 'LONG' if is_hedge else None
                else:
                    side = 'buy'
                    action = "平空仓"
                    pos_side = 'SHORT' if is_hedge else None
               
                amount = exchange.amount_to_precision(symbol, abs(contracts))
                print(f"{action} {symbol}: {amount}张")
               
                try:
                    params = {}
                    if not is_hedge:  # One-Way下添加reduceOnly
                        params['reduceOnly'] = True
                    if is_hedge and pos_side:
                        params['positionSide'] = pos_side
                   
                    order = exchange.create_order(
                        symbol=symbol,
                        type='market',
                        side=side,
                        amount=amount,
                        params=params
                    )
                    print(f"✅ {symbol} 平仓成功")
                    closed_count += 1
                    time.sleep(0.5)  # 避免频繁请求
                   
                except Exception as e:
                    print(f"❌ {symbol} 平仓失败: {e}")
       
        print(f"🎯 紧急平仓完成: 成功平仓 {closed_count} 个持仓")
                   
    except Exception as e:
        print(f"❌ 紧急平仓失败: {e}")

if __name__ == "__main__":
    # 设置环境变量（生产环境请使用实际密钥）
    os.environ['BINANCE_API_KEY'] = 'Gvt16Ehe8TH0O4iCTuPgedpvGhZz8t5omd9mwZCGcBjEaY1mup39R1B18LP3TyYN'
    os.environ['BINANCE_API_SECRET'] = 'OgfVjWYRTAlmAoCkvf8h3GQZFEJAHEnVNk1wzVF7NYAe0pynZuUVRXADtr8Fks6m'
   
    print("开始实盘连接测试...")
    if test_real_connection():
        print("\n" + "="*60)
        print("实盘测试通过，启动机器人...")
        print("="*60)
       
        # 确认用户是否要继续
        confirm = input("🚨 这是实盘交易！确认启动吗？(y/N): ")
        if confirm.lower() == 'y':
            bot = BinanceAutoCloseFixed()
            bot.run()
        else:
            print("已取消启动")
    else:
        print("❌ 实盘连接测试失败，请检查:")
        print(" 1. API密钥和秘钥是否正确")
        print(" 2. 是否开启了U本位合约交易权限")
        print(" 3. 网络连接是否正常")