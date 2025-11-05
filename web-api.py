import time
import logging
import threading
from flask import Flask, request, jsonify, render_template_string
from binance.client import Client

# ==============================
# 配置（请修改）
# ==============================
API_KEY = 'Gvt16Ehe8TH0O4iCTuPgedpvGhZz8t5omd9mwZCGcBjEaY1mup39R1B18LP3TyYN'
API_SECRET = 'OgfVjWYRTAlmAoCkvf8h3GQZFEJAHEnVNk1wzVF7NYAe0pynZuUVRXADtr8Fks6m'

CONFIG = {
    'take_profit': 1.0,
    'stop_loss': -1.0,
    'check_interval': 2,
    'symbols_whitelist': None
}
config_lock = threading.Lock()

# 日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
logger = logging.getLogger()

# Binance 客户端（用于后台交易）
trade_client = Client(API_KEY, API_SECRET, testnet=False)
# 再创建一个只读客户端（用于获取价格，避免 API 限频冲突）
price_client = Client(API_KEY, API_SECRET, testnet=False)

# ==============================
# 后台交易逻辑（不变）
# ==============================
def get_all_hedge_positions():
    try:
        all_positions = trade_client.futures_position_information()
        active = []
        for pos in all_positions:
            amt = float(pos['positionAmt'])
            side = pos['positionSide']
            if side in ['LONG', 'SHORT'] and abs(amt) > 0:
                symbol = pos['symbol']
                if CONFIG['symbols_whitelist'] is not None and symbol not in CONFIG['symbols_whitelist']:
                    continue
                active.append(pos)
        return active
    except Exception as e:
        logger.error(f"获取持仓失败: {e}")
        return []

def close_hedge_position(symbol, position_side, qty):
    side = "SELL" if position_side == "LONG" else "BUY"
    qty = abs(float(qty))
    try:
        exchange_info = trade_client.futures_exchange_info()
        symbol_info = next((s for s in exchange_info['symbols'] if s['symbol'] == symbol), None)
        if not symbol_info:
            raise ValueError(f"未找到 {symbol} 的交易规则")
        qty_precision = symbol_info['quantityPrecision']
        qty_str = f"{{:.{qty_precision}f}}".format(qty).rstrip('0').rstrip('.')
        if not qty_str:
            qty_str = "0"

        order = trade_client.futures_create_order(
            symbol=symbol,
            side=side,
            positionSide=position_side,
            type="MARKET",
            quantity=qty_str
        )
        logger.info(f"✅ 平仓成功 | {symbol} | {position_side} | 订单ID: {order['orderId']}")
        return True
    except Exception as e:
        logger.error(f"❌ 平仓失败 | {symbol} {position_side}: {e}")
        return False

def monitor_loop():
    logger.info("🚀 启动双向持仓监控（带 Web 仪表盘）")
    while True:
        try:
            with config_lock:
                take_profit = CONFIG['take_profit']
                stop_loss = CONFIG['stop_loss']
                interval = CONFIG['check_interval']

            positions = get_all_hedge_positions()
            for pos in positions:
                symbol = pos['symbol']
                position_side = pos['positionSide']
                qty = float(pos['positionAmt'])
                unrealized_pnl = float(pos['unRealizedProfit'])

                if unrealized_pnl >= take_profit:
                    logger.warning(f"🎯 {symbol} {position_side} 止盈触发 ({unrealized_pnl:.2f}U)")
                    close_hedge_position(symbol, position_side, qty)
                elif unrealized_pnl <= stop_loss:
                    logger.warning(f"⚠️ {symbol} {position_side} 止损触发 ({unrealized_pnl:.2f}U)")
                    close_hedge_position(symbol, position_side, qty)

            time.sleep(interval)
        except Exception as e:
            logger.error(f"监控异常: {e}")
            time.sleep(5)

# ==============================
# Web API 新增：获取实时持仓数据
# ==============================
def fetch_positions_for_dashboard():
    """获取用于仪表盘显示的持仓数据（含实时价格）"""
    try:
        positions = get_all_hedge_positions()
        result = []

        # 批量获取标记价格（更准）
        prices = {}
        if positions:
            symbols = [p['symbol'] for p in positions]
            mark_prices = price_client.futures_mark_price()
            prices = {item['symbol']: float(item['markPrice']) for item in mark_prices if item['symbol'] in symbols}

        for pos in positions:
            symbol = pos['symbol']
            side = pos['positionSide']
            qty = float(pos['positionAmt'])
            entry_price = float(pos['entryPrice'])
            pnl = float(pos['unRealizedProfit'])
            mark_price = prices.get(symbol, 0)

            result.append({
                'symbol': symbol,
                'side': side,
                'quantity': round(qty, 6),
                'entry_price': round(entry_price, 6),
                'mark_price': round(mark_price, 6),
                'unrealized_pnl': round(pnl, 4),
                'pnl_color': 'green' if pnl >= 0 else 'red'
            })
        return result
    except Exception as e:
        logger.error(f"仪表盘数据获取失败: {e}")
        return []

# ==============================
# Flask Web App
# ==============================
app = Flask(__name__)

DASHBOARD_HTML = '''
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>币安合约监控仪表盘</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
        body { background: #0f0f1b; color: #e0e0ff; padding: 20px; }
        .container { max-width: 1200px; margin: 0 auto; }
        header { text-align: center; margin-bottom: 30px; }
        h1 { font-size: 28px; margin-bottom: 10px; color: #4fc3f7; }
        .controls {
            display: flex; gap: 15px; margin-bottom: 25px; flex-wrap: wrap;
        }
        .control-group { flex: 1; min-width: 200px; }
        label { display: block; margin-bottom: 6px; font-size: 14px; color: #aaa; }
        input { width: 100%; padding: 10px; border-radius: 6px; border: 1px solid #444; background: #1a1a2e; color: white; }
        button {
            padding: 12px 20px; border: none; border-radius: 6px; cursor: pointer;
            font-weight: bold; margin-top: 22px;
        }
        #saveBtn { background: #4caf50; color: white; }
        #saveBtn:hover { background: #45a049; }
        #refreshBtn { background: #2196f3; color: white; }
        #refreshBtn:hover { background: #1e88e5; }

        .positions { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 20px; }
        .position-card {
            background: #16213e; border-radius: 12px; padding: 20px; box-shadow: 0 4px 12px rgba(0,0,0,0.3);
            border-left: 4px solid #6a5acd;
        }
        .position-card.long { border-left-color: #4caf50; }
        .position-card.short { border-left-color: #f44336; }
        .symbol { font-size: 20px; font-weight: bold; margin-bottom: 8px; }
        .side { display: inline-block; padding: 3px 8px; border-radius: 4px; font-size: 12px; }
        .side.LONG { background: #388e3c; color: white; }
        .side.SHORT { background: #d32f2f; color: white; }
        .info { margin: 10px 0; font-size: 15px; }
        .label { color: #888; }
        .value { color: white; }
        .pnl { font-size: 18px; font-weight: bold; margin-top: 10px; }
        .positive { color: #66bb6a; }
        .negative { color: #ef5350; }

        .status { margin-top: 20px; padding: 12px; background: #1e1e2f; border-radius: 6px; color: #ffd700; }
        .empty { text-align: center; color: #666; padding: 40px; }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>📊 币安合约实时监控仪表盘</h1>
            <p>双向持仓模式 · 自动止盈止损 · 实时数据刷新</p>
        </header>

        <div class="controls">
            <div class="control-group">
                <label>止盈目标 (USDT)</label>
                <input type="number" step="0.1" id="takeProfit" value="1.0">
            </div>
            <div class="control-group">
                <label>止损目标 (USDT)</label>
                <input type="number" step="0.1" id="stopLoss" value="-1.0">
            </div>
            <div class="control-group">
                <label>检查间隔 (秒)</label>
                <input type="number" step="1" min="1" max="30" id="interval" value="2">
            </div>
            <div style="display:flex; gap:10px; align-items:flex-end;">
                <button id="saveBtn">💾 保存设置</button>
                <button id="refreshBtn">🔄 刷新数据</button>
            </div>
        </div>

        <div id="status" class="status">就绪：等待加载数据...</div>

        <div id="positions-container" class="positions">
            <!-- 仓位卡片将通过 JS 动态插入 -->
        </div>
    </div>

    <script>
        let autoRefresh = true;

        function loadConfig() {
            fetch('/api/config')
                .then(r => r.json())
                .then(data => {
                    document.getElementById('takeProfit').value = data.take_profit;
                    document.getElementById('stopLoss').value = data.stop_loss;
                    document.getElementById('interval').value = data.check_interval;
                });
        }

        function saveConfig() {
            const tp = parseFloat(document.getElementById('takeProfit').value);
            const sl = parseFloat(document.getElementById('stopLoss').value);
            const iv = parseInt(document.getElementById('interval').value);
            fetch('/api/config', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ take_profit: tp, stop_loss: sl, check_interval: iv })
            })
            .then(r => r.json())
            .then(data => {
                document.getElementById('status').textContent = `✅ 配置已更新 | 止盈: ${tp}U, 止损: ${sl}U`;
                setTimeout(() => { if(autoRefresh) loadPositions(); }, 500);
            })
            .catch(err => {
                document.getElementById('status').textContent = '❌ 保存失败: ' + err;
            });
        }

        function loadPositions() {
            fetch('/api/positions')
                .then(r => r.json())
                .then(data => {
                    const container = document.getElementById('positions-container');
                    if (data.length === 0) {
                        container.innerHTML = '<div class="empty">暂无持仓</div>';
                        document.getElementById('status').textContent = '✅ 无活跃仓位';
                        return;
                    }
                    let html = '';
                    data.forEach(pos => {
                        const pnlClass = pos.unrealized_pnl >= 0 ? 'positive' : 'negative';
                        const sideClass = pos.side === 'LONG' ? 'LONG' : 'SHORT';
                        html += `
                            <div class="position-card ${pos.side.toLowerCase()}">
                                <div class="symbol">${pos.symbol}</div>
                                <span class="side ${sideClass}">${pos.side}</span>
                                <div class="info">
                                    <span class="label">持仓数量: </span>
                                    <span class="value">${pos.quantity}</span>
                                </div>
                                <div class="info">
                                    <span class="label">开仓价格: </span>
                                    <span class="value">${pos.entry_price}</span>
                                </div>
                                <div class="info">
                                    <span class="label">标记价格: </span>
                                    <span class="value">${pos.mark_price}</span>
                                </div>
                                <div class="pnl ${pnlClass}">
                                    浮动盈亏: ${pos.unrealized_pnl.toFixed(4)} USDT
                                </div>
                            </div>
                        `;
                    });
                    container.innerHTML = html;
                    document.getElementById('status').textContent = `✅ 已加载 ${data.length} 个仓位 | 自动刷新中...`;
                })
                .catch(err => {
                    document.getElementById('status').textContent = '❌ 加载仓位失败: ' + err;
                });
        }

        // 绑定按钮
        document.getElementById('saveBtn').onclick = saveConfig;
        document.getElementById('refreshBtn').onclick = () => { autoRefresh=false; loadPositions(); };

        // 自动刷新
        loadConfig();
        loadPositions();
        setInterval(() => { if(autoRefresh) loadPositions(); }, 3000);
    </script>
</body>
</html>
'''

@app.route('/')
def dashboard():
    return render_template_string(DASHBOARD_HTML)

@app.route('/api/config', methods=['GET'])
def get_config():
    with config_lock:
        return jsonify({
            'take_profit': CONFIG['take_profit'],
            'stop_loss': CONFIG['stop_loss'],
            'check_interval': CONFIG['check_interval']
        })

@app.route('/api/config', methods=['POST'])
def set_config():
    data = request.get_json()
    try:
        with config_lock:
            CONFIG['take_profit'] = float(data['take_profit'])
            CONFIG['stop_loss'] = float(data['stop_loss'])
            CONFIG['check_interval'] = int(data['check_interval'])
        logger.info(f"🌐 配置更新: TP={CONFIG['take_profit']}, SL={CONFIG['stop_loss']}")
        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400

@app.route('/api/positions', methods=['GET'])
def api_positions():
    positions = fetch_positions_for_dashboard()
    return jsonify(positions)

# ==============================
# 启动程序
# ==============================
if __name__ == "__main__":
    logger.info("🌐 启动 Web 仪表盘（访问 http://服务器IP:5000）")
    
    # 启动 Flask（监听所有 IP，方便远程访问）
    flask_thread = threading.Thread(target=lambda: app.run(host='0.0.0.0', port=5000, debug=False))
    flask_thread.daemon = True
    flask_thread.start()

    # 启动交易监控
    try:
        monitor_loop()
    except KeyboardInterrupt:
        logger.info("🛑 程序已退出")