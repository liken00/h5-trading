"""
Flask 后端 - 涨停复盘宝
提供股票数据 API 和 AI 智能问答
"""

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import json
import os
import datetime
import akshare as ak
import sqlite3
import pandas as pd
from concurrent.futures import ThreadPoolExecutor

# 导入龙韵智趋模型
import sys
sys.path.insert(0, os.path.dirname(__file__))
from models.dragon_model import DragonModel
from models.selection import SelectionModel
from models.entry import EntryModel

app = Flask(__name__, static_folder='../static')
CORS(app)

EXECUTOR = ThreadPoolExecutor(max_workers=5)

# 龙韵智趋模型实例
dragon_model = DragonModel()
selection_model = SelectionModel(dragon_model)
entry_model = EntryModel(dragon_model)

# ============================================================
# 股票数据缓存（避免频繁请求）
# ============================================================
CACHE = {
    'indices': {'data': None, 'time': None},
    'ztlist': {'data': None, 'time': None},
    'hot_sectors': {'data': None, 'time': None},
}
CACHE_TTL = 120  # 2分钟缓存


def get_cache(key):
    """检查缓存是否有效"""
    entry = CACHE.get(key)
    if entry and entry['time']:
        if (datetime.datetime.now() - entry['time']).seconds < CACHE_TTL:
            return entry['data']
    return None


def set_cache(key, data):
    CACHE[key] = {'data': data, 'time': datetime.datetime.now()}


# ============================================================
# 股票数据 API（akshare）
# ============================================================

@app.route('/api/indices', methods=['GET'])
def get_indices():
    """大盘指数（上证/深证/创业板/沪深300）"""
    cached = get_cache('indices')
    if cached:
        return jsonify({'code': 0, 'data': cached})

    def fetch():
        try:
            indices = [
                {'code': '000001', 'name': '上证指数', 'market': 'sh'},
                {'code': '399001', 'name': '深证成指', 'market': 'sz'},
                {'code': '399006', 'name': '创业板指', 'market': 'sz'},
                {'code': '000300', 'name': '沪深300', 'market': 'sh'},
            ]
            result = []
            for idx in indices:
                try:
                    df = ak.stock_zh_index_spot()
                    row = df[df['代码'] == idx['code']]
                    if not row.empty:
                        price = float(row['最新价'].values[0])
                        change = float(row['涨跌额'].values[0])
                        pct = float(row['涨跌幅'].values[0])
                        result.append({
                            'name': idx['name'],
                            'code': idx['code'],
                            'price': price,
                            'change': change,
                            'pct': pct,
                            'status': 'up' if change > 0 else 'down' if change < 0 else 'flat'
                        })
                except Exception:
                    pass
            return result
        except Exception as e:
            return []

    try:
        data = fetch()
        set_cache('indices', data)
        return jsonify({'code': 0, 'data': data})
    except Exception as e:
        return jsonify({'code': 1, 'msg': str(e)}), 500


@app.route('/api/ztlist', methods=['GET'])
def get_ztlist():
    """今日涨停板列表"""
    cached = get_cache('ztlist')
    if cached:
        return jsonify({'code': 0, 'data': cached})

    def fetch():
        try:
            # 获取今日涨停股
            df = ak.stock_zt_pool_em(date=datetime.datetime.now().strftime('%Y%m%d'))
            if df is None or df.empty:
                return []
            # 排序：按连板数降序
            df = df.sort_values('连板数', ascending=False)
            result = []
            for _, row in df.head(20).iterrows():
                result.append({
                    'code': str(row.get('代码', '')),
                    'name': str(row.get('名称', '')),
                    'reason': str(row.get('涨停统计[{}]'.format(datetime.datetime.now().strftime('%Y%m%d')), '题材')),  # 题材
                    'boards': int(row.get('连板数', 0)),
                    'pct': float(row.get('涨幅', 0)),
                    'turnover': float(row.get('成交额', 0)) / 1e8,  # 亿
                    'status': '二波' if int(row.get('连板数', 0)) == 0 and float(row.get('涨幅', 0)) >= 9 else '涨停',
                })
            return result
        except Exception as e:
            return []

    try:
        data = fetch()
        set_cache('ztlist', data)
        return jsonify({'code': 0, 'data': data})
    except Exception as e:
        return jsonify({'code': 1, 'msg': str(e)}), 500


@app.route('/api/hot-sectors', methods=['GET'])
def get_hot_sectors():
    """热门题材板块"""
    cached = get_cache('hot_sectors')
    if cached:
        return jsonify({'code': 0, 'data': cached})

    def fetch():
        try:
            df = ak.stock_board_industry_name_em()
            if df is None or df.empty:
                return []
            # 按涨跌幅排序，取前10
            df = df.sort_values('涨跌幅', ascending=False).head(10)
            result = []
            for _, row in df.iterrows():
                result.append({
                    'name': str(row.get('板块名称', '')),
                    'pct': float(row.get('涨跌幅', 0)),
                    'stock_count': int(row.get('总股票数', 0)),
                    'lead_stock': str(row.get('领涨股票', '')),
                    'status': 'up' if float(row.get('涨跌幅', 0)) > 0 else 'down',
                })
            return result
        except Exception as e:
            return []

    try:
        data = fetch()
        set_cache('hot_sectors', data)
        return jsonify({'code': 0, 'data': data})
    except Exception as e:
        return jsonify({'code': 1, 'msg': str(e)}), 500


@app.route('/api/stock/<code>', methods=['GET'])
def get_stock_detail(code):
    """个股详情（MA55、题材、资金流）"""
    try:
        # 获取个股K线数据
        df = ak.stock_zh_a_hist(symbol=code, period='daily', adjust='qfq')
        if df is None or df.empty:
            return jsonify({'code': 1, 'msg': '无数据'}), 404

        # 计算MA55
        df['MA55'] = df['收盘'].rolling(55).mean()
        latest = df.iloc[-1]
        ma55 = df['MA55'].iloc[-1] if not pd.isna(df['MA55'].iloc[-1]) else None

        return jsonify({
            'code': 0,
            'data': {
                'name': latest.get('股票代码', code),
                'price': float(latest.get('收盘', 0)),
                'pct': float(latest.get('涨跌幅', 0)),
                'ma55': float(ma55) if ma55 else None,
                'volume_ratio': float(latest.get('量比', 0)),
                'turnover': float(latest.get('成交额', 0)) / 1e8,
            }
        })
    except Exception as e:
        return jsonify({'code': 1, 'msg': str(e)}), 500


@app.route('/api/chat', methods=['POST'])
def chat():
    """AI 智能问答（通过 OpenClaw）"""
    data = request.get_json()
    message = data.get('message', '')
    if not message:
        return jsonify({'code': 1, 'msg': '消息不能为空'}), 400

    # TODO: 接入 OpenClaw
    # 暂时返回模拟回答
    return jsonify({
        'code': 0,
        'data': {
            'reply': f'收到您的问题：{message}。修哥交易系统七步法正在分析中...'
        }
    })


@app.route('/api/health', methods=['GET'])
def health():
    """健康检查"""
    return jsonify({'status': 'ok', 'time': datetime.datetime.now().isoformat()})


# ============================================================
# 龙韵智趋 API
# ============================================================

@app.route('/api/dragon/mainlines', methods=['GET'])
def get_mainlines():
    """主线板块筛选（同板块≥2只同日2板 = 主线确认）"""
    try:
        result = selection_model.screen_mainlines()
        return jsonify({'code': 0, 'data': result})
    except Exception as e:
        return jsonify({'code': 1, 'msg': str(e)}), 500


@app.route('/api/dragon/leaders', methods=['GET'])
def get_leaders():
    """龙头确认（三/四板封板时间最早）"""
    try:
        min_boards = int(request.args.get('min_boards', 3))
        result = selection_model.screen_leaders(min_boards=min_boards)
        return jsonify({'code': 0, 'data': result})
    except Exception as e:
        return jsonify({'code': 1, 'msg': str(e)}), 500


@app.route('/api/dragon/wave2', methods=['GET'])
def get_wave2():
    """二波候选筛选（连续两天首板≥5家）"""
    try:
        result = selection_model.screen_wave2_candidates()
        return jsonify({'code': 0, 'data': result})
    except Exception as e:
        return jsonify({'code': 1, 'msg': str(e)}), 500


@app.route('/api/dragon/selection', methods=['GET'])
def get_dragon_selection():
    """获取完整选股结果（主线+龙头+二波候选）"""
    try:
        result = selection_model.get_selection_result()
        return jsonify({'code': 0, 'data': result})
    except Exception as e:
        return jsonify({'code': 1, 'msg': str(e)}), 500


@app.route('/api/dragon/entry/<code>', methods=['GET'])
def get_entry_signal(code):
    """个股买点信号检查（30分钟MA50 + 日K MA10±5% + 缩量承接）"""
    try:
        result = entry_model.check_entry_signals(code)
        return jsonify({'code': 0, 'data': result})
    except Exception as e:
        return jsonify({'code': 1, 'msg': str(e)}), 500


@app.route('/api/dragon/analysis/<code>', methods=['GET'])
def get_stock_analysis(code):
    """个股龙韵分析（连板数、MA支撑、二波状态）"""
    try:
        result = dragon_model.get_stock_analysis(code)
        return jsonify({'code': 0, 'data': result})
    except Exception as e:
        return jsonify({'code': 1, 'msg': str(e)}), 500


@app.route('/api/dragon/ma-support/<code>', methods=['GET'])
def get_ma_support(code):
    """MA支撑强度分析"""
    try:
        result = entry_model.calculate_ma_support_strength(code)
        return jsonify({'code': 0, 'data': result})
    except Exception as e:
        return jsonify({'code': 1, 'msg': str(e)}), 500


@app.route('/api/dragon/batch-entry', methods=['POST'])
def batch_entry_check():
    """批量检查买点信号"""
    try:
        data = request.get_json()
        codes = data.get('codes', [])
        if not codes:
            return jsonify({'code': 1, 'msg': '股票代码列表不能为空'}), 400
        result = entry_model.get_batch_entry_check(codes)
        return jsonify({'code': 0, 'data': result})
    except Exception as e:
        return jsonify({'code': 1, 'msg': str(e)}), 500


@app.route('/api/dragon/zt-today', methods=['GET'])
def get_today_zt():
    """获取今日涨停股列表（增强版，含封板时间、题材）"""
    try:
        result = selection_model.get_today_zt_stocks()
        return jsonify({'code': 0, 'data': result})
    except Exception as e:
        return jsonify({'code': 1, 'msg': str(e)}), 500


# ============================================================
# 短信宝 Auth 认证系统
# ============================================================
import random
import hashlib
import time as time_module

AUTH_DB = os.path.join(os.path.dirname(__file__), 'auth.db')

def get_auth_db():
    conn = sqlite3.connect(AUTH_DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_auth_db():
    conn = get_auth_db()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        phone TEXT UNIQUE NOT NULL,
        nickname TEXT,
        avatar TEXT,
        created_at TEXT,
        last_login TEXT,
        auto_token TEXT,
        auto_token_expires INTEGER
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS debug_codes (
        phone TEXT PRIMARY KEY,
        code TEXT NOT NULL,
        expires_at INTEGER NOT NULL
    )''')
    conn.commit()
    conn.close()

init_auth_db()

def generate_code():
    return str(random.randint(100000, 999999))

def send_sms(phone, code):
    """短信宝发送验证码"""
    import urllib.request
    import urllib.parse
    params = urllib.parse.urlencode({
        'u': 'kenli',
        'p': 'ef5d6a1e7c9a4beba829bbf01dc247f7',
        'm': phone,
        'c': f'【复盘宝】您的验证码为{code}，5分钟内有效。如非本人操作，请忽略。'
    })
    try:
        resp = urllib.request.urlopen(f'http://api.smsbao.com/sms?{params}', timeout=10)
        result = resp.read().decode('utf-8')
        return result == '0'
    except Exception as e:
        print(f'SMS send error: {e}')
        return False

@app.route('/api/auth/send_code', methods=['POST'])
def send_code():
    data = request.get_json() or {}
    phone = data.get('phone', '').strip()
    if not phone or len(phone) != 11:
        return jsonify({'code': 1, 'msg': '手机号格式错误'})
    code = generate_code()
    expires_at = int(time_module.time()) + 300
    conn = get_auth_db()
    conn.execute('INSERT OR REPLACE INTO debug_codes (phone, code, expires_at) VALUES (?, ?, ?)',
                 (phone, code, expires_at))
    conn.commit()
    conn.close()
    sms_ok = send_sms(phone, code)
    return jsonify({
        'code': 0,
        'debug_code': code,
        'msg': '发送成功' if sms_ok else '发送成功（调试模式）'
    })

@app.route('/api/auth/verify_code', methods=['POST'])
def verify_code():
    data = request.get_json() or {}
    phone = data.get('phone', '').strip()
    code = data.get('code', '').strip()
    if not phone or not code:
        return jsonify({'code': 1, 'msg': '参数不完整'})
    now = int(time_module.time())
    conn = get_auth_db()
    row = conn.execute('SELECT code, expires_at FROM debug_codes WHERE phone=?', (phone,)).fetchone()
    if not row or str(row['code']) != code or row['expires_at'] < now:
        conn.close()
        return jsonify({'code': 1, 'msg': '验证码错误或已过期'})
    conn.execute('DELETE FROM debug_codes WHERE phone=?', (phone,))
    user = conn.execute('SELECT * FROM users WHERE phone=?', (phone,)).fetchone()
    if not user:
        conn.execute('INSERT INTO users (phone, nickname, created_at, last_login) VALUES (?, ?, ?, ?)',
                     (phone, f'用户{phone[-4:]}', datetime.datetime.now().isoformat(), datetime.datetime.now().isoformat()))
    else:
        auto_token = 'at_' + hashlib.sha256(f'{phone}{code}{now}'.encode()).hexdigest()[:32]
        auto_token_expires = now + 30 * 24 * 3600
        conn.execute('UPDATE users SET last_login=?, auto_token=?, auto_token_expires=? WHERE phone=?',
                     (datetime.datetime.now().isoformat(), auto_token, auto_token_expires, phone))
        user = conn.execute('SELECT * FROM users WHERE phone=?', (phone,)).fetchone()
    conn.commit()
    conn.close()
    user_dict = dict(user)
    del user_dict['auto_token']
    del user_dict['auto_token_expires']
    return jsonify({'code': 0, 'msg': '登录成功', 'data': user_dict})

@app.route('/api/auth/check_session', methods=['GET'])
def check_session():
    auto_token = request.headers.get('Authorization', '').replace('Bearer ', '')
    if not auto_token:
        return jsonify({'code': 1, 'msg': '未登录'})
    conn = get_auth_db()
    user = conn.execute('SELECT * FROM users WHERE auto_token=? AND auto_token_expires>?',
                       (auto_token, int(time_module.time()))).fetchone()
    conn.close()
    if not user:
        return jsonify({'code': 1, 'msg': '登录已过期'})
    user_dict = dict(user)
    del user_dict['auto_token']
    del user_dict['auto_token_expires']
    return jsonify({'code': 0, 'data': user_dict})

@app.route('/api/auth/logout', methods=['POST'])
def logout():
    auto_token = request.headers.get('Authorization', '').replace('Bearer ', '')
    if auto_token:
        conn = get_auth_db()
        conn.execute('UPDATE users SET auto_token=NULL WHERE auto_token=?', (auto_token,))
        conn.commit()
        conn.close()
    return jsonify({'code': 0, 'msg': '已退出'})


# ============================================================
# 静态文件
# ============================================================
@app.route('/')
def index():
    return send_from_directory('.', 'index.html')


@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory('../static', filename)


# ============================================================
# 启动
# ============================================================
if __name__ == '__main__':
    print('🚀 涨停复盘宝后端启动中...')
    print(f'   时间: {datetime.datetime.now()}')
    print(f'   服务: http://0.0.0.0:5000')
    app.run(host='0.0.0.0', port=5000, debug=False)
