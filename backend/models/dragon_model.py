"""
龙韵智趋核心战法模型
核心框架：蛰伏期 → 双二板定主线 → 三/四板定龙头 → ≥4板回调MA10 → 二波盈利

关键规则：
1. 龙头选股标准：≥4板 + 4板破板 + 回调MA10 + 二波 = 80%收益
2. 主线确认：同板块≥2只同日2板 = 主线确认
3. 买点信号：30分钟K线MA50 + 日K MA10±5% + 缩量承接
4. 仓位：3板0.25成 / 4板0.35成 / 5板0.5成
5. 止损：跌破日K MA10当日无法收回等次日拉涨平仓
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import akshare as ak
import baostock as bs


class DragonModel:
    """龙韵智趋核心战法模型"""
    
    # 战法常量
    BOARD_THRESHOLD = 2  # 主线确认：同板块≥2只同日2板
    WAVE2_DAYS = 2  # 二波候选：连续两天首板≥5家
    WAVE2_MIN_COUNT = 5  # 二波候选：每天首板≥5家
    
    # 仓位配置
    POSITION_CONFIG = {
        3: 0.25,  # 3板0.25成
        4: 0.35,  # 4板0.35成
        5: 0.50,  # 5板0.5成
    }
    
    # MA参数
    MA10_PERCENT = 0.05  # MA10±5%
    MIN30_MA50 = 50  # 30分钟MA50
    
    def __init__(self):
        self.stock_cache = {}  # 股票数据缓存
        self.zt_history = []  # 历史涨停数据
        
    def get_baostock_connection(self):
        """建立baostock连接"""
        lg = bs.login()
        return lg
    
    def close_baostock(self):
        """关闭baostock连接"""
        bs.logout()
    
    def get_historical_kline(self, symbol: str, days: int = 120) -> pd.DataFrame:
        """
        获取历史K线数据（不复权）
        symbol: 股票代码，如 '002354' 或 '600000'
        days: 获取天数
        """
        try:
            # 转换股票代码格式：6位 -> 9位 (sz.002354 或 sh.600000)
            if len(symbol) == 6:
                if symbol.startswith('6'):
                    symbol = f'sh.{symbol}'
                else:
                    symbol = f'sz.{symbol}'
            
            self.get_baostock_connection()
            rs = bs.query_history_k_data_plus(
                symbol,
                "date,code,open,high,low,close,volume,amount,turn",
                start_date=(datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d'),
                end_date=datetime.now().strftime('%Y-%m-%d'),
                frequency="d",
                adjustflag="3"  # 不复权
            )
            
            data_list = []
            while (rs.error_code == '0') & rs.next():
                data_list.append(rs.get_row_data())
            
            self.close_baostock()
            
            if not data_list:
                return pd.DataFrame()
            
            df = pd.DataFrame(data_list, columns=rs.fields)
            for col in ['open', 'high', 'low', 'close', 'volume', 'amount', 'turn']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            
            return df
        except Exception as e:
            print(f"获取K线失败 {symbol}: {e}")
            return pd.DataFrame()
    
    def calculate_ma(self, df: pd.DataFrame, periods: List[int]) -> pd.DataFrame:
        """计算移动平均线"""
        result = df.copy()
        for period in periods:
            result[f'ma{period}'] = result['close'].rolling(window=period).mean()
        return result
    
    def calculate_volume_ratio(self, df: pd.DataFrame, window: int = 5) -> pd.Series:
        """计算量比"""
        avg_volume = df['volume'].rolling(window=window).mean()
        current_volume = df['volume']
        return current_volume / avg_volume
    
    def identify_double_second_board(self, stocks: List[Dict], date: str) -> List[Dict]:
        """
        双二板识别算法
        识别同一板块内同日出现两只以上二板股的板块
        
        规则：同板块≥2只同日2板 = 主线确认
        """
        # 按板块分组
        sector_stocks = {}
        for stock in stocks:
            board = stock.get('board', '')
            boards_count = stock.get('boards_count', 0)
            if boards_count >= 2 and board:
                if board not in sector_stocks:
                    sector_stocks[board] = []
                sector_stocks[board].append(stock)
        
        # 筛选双二板板块
        mainlines = []
        for sector, stock_list in sector_stocks.items():
            if len(stock_list) >= self.BOARD_THRESHOLD:
                mainlines.append({
                    'sector': sector,
                    'stocks': stock_list,
                    'count': len(stock_list),
                    'date': date
                })
        
        return mainlines
    
    def identify_leader(self, stocks: List[Dict], min_boards: int = 3) -> List[Dict]:
        """
        龙头筛选算法（封板时间PK）
        
        规则：
        1. ≥4板首选
        2. 三/四板封板时间最早
        3. 回调MA10支撑
        
        返回按龙头潜力排序的股票列表
        """
        leaders = []
        
        for stock in stocks:
            boards = stock.get('boards', 0)
            if boards < min_boards:
                continue
            
            # 基础分
            score = boards * 10
            
            # 封板时间早加分
            seal_time = stock.get('seal_time', '')  # 格式: '09:30:00'
            if seal_time:
                try:
                    hour, minute = map(int, seal_time.split(':')[:2])
                    time_score = (10 - hour * 60 - minute) / 10  # 越早分数越高
                    score += max(0, time_score)
                except:
                    pass
            
            # 回调MA10支撑
            ma10_support = stock.get('ma10_support', 0)  # 0-100%支撑强度
            score += ma10_support * 0.5
            
            # 二波确认加分
            if stock.get('wave2_confirmed'):
                score += 20
            
            leaders.append({
                'code': stock.get('code'),
                'name': stock.get('name'),
                'boards': boards,
                'score': round(score, 2),
                'seal_time': stock.get('seal_time', ''),
                'ma10_support': ma10_support,
                'wave2_confirmed': stock.get('wave2_confirmed', False)
            })
        
        # 按分数降序排列
        leaders.sort(key=lambda x: x['score'], reverse=True)
        return leaders
    
    def verify_wave2(self, stock_history: List[Dict]) -> Tuple[bool, Dict]:
        """
        二波验证逻辑
        
        规则：连续两天首板≥5家 = 二波确认候选
        
        返回: (是否二波, 详细数据)
        """
        if len(stock_history) < 2:
            return False, {}
        
        consecutive_days = 0
        wave2_details = []
        
        for i in range(len(stock_history) - 1):
            day1 = stock_history[i]
            day2 = stock_history[i + 1]
            
            # 检查是否是首板（不是连续板）
            if day1.get('boards') == 1 and day2.get('boards') == 1:
                consecutive_days += 1
                wave2_details.append({
                    'date': day1.get('date'),
                    'count': 1
                })
            else:
                if consecutive_days >= self.WAVE2_DAYS:
                    break
                consecutive_days = 0
                wave2_details = []
        
        is_wave2 = consecutive_days >= self.WAVE2_DAYS
        
        return is_wave2, {
            'consecutive_days': consecutive_days,
            'details': wave2_details,
            'confirmed': is_wave2
        }
    
    def check_wave2_candidates(self, date: str, days: int = 5) -> List[Dict]:
        """
        二波候选筛选（连续两天首板≥5家）
        
        返回近期可能启动二波的股票列表
        """
        candidates = []
        
        try:
            # 获取近期涨停数据
            df = ak.stock_zt_pool_em(date=date)
            if df is None or df.empty:
                return candidates
            
            # 统计每日首板数量
            daily_counts = {}
            for _, row in df.iterrows():
                board_date = row.get('日期', '')
                boards = int(row.get('连板数', 0))
                if boards == 1:  # 首板
                    daily_counts[board_date] = daily_counts.get(board_date, 0) + 1
            
            # 筛选连续两天首板≥5家的日期
            sorted_dates = sorted(daily_counts.keys(), reverse=True)
            for i in range(len(sorted_dates) - 1):
                d1, d2 = sorted_dates[i], sorted_dates[i + 1]
                if daily_counts.get(d1, 0) >= self.WAVE2_MIN_COUNT and \
                   daily_counts.get(d2, 0) >= self.WAVE2_MIN_COUNT:
                    candidates.append({
                        'date': d1,
                        'prev_date': d2,
                        'count': daily_counts[d1],
                        'prev_count': daily_counts[d2]
                    })
                    
        except Exception as e:
            print(f"二波候选筛选失败: {e}")
        
        return candidates
    
    def calculate_ma10_support_strength(self, df: pd.DataFrame) -> float:
        """
        计算MA10支撑强度
        返回0-100的支撑强度百分比
        """
        if df is None or len(df) < 20:
            return 0
        
        df = self.calculate_ma(df, [10])
        latest = df.iloc[-1]
        
        current_price = latest.get('close', 0)
        ma10 = latest.get('ma10', 0)
        
        if ma10 == 0:
            return 0
        
        # 计算价格与MA10的距离
        distance_pct = abs(current_price - ma10) / ma10 * 100
        
        # 支撑强度：距离越近，支撑越强
        if distance_pct <= 1:
            return 100
        elif distance_pct <= 3:
            return 80
        elif distance_pct <= 5:
            return 60
        elif distance_pct <= 10:
            return 40
        else:
            return 20
    
    def get_stock_analysis(self, code: str) -> Dict:
        """
        获取个股龙韵分析
        包含：连板数、MA支撑、二波状态、买卖信号
        """
        # 获取K线数据
        kline_df = self.get_historical_kline(code, days=120)
        
        if kline_df.empty:
            return {'error': '无法获取数据'}
        
        # 计算MA
        kline_df = self.calculate_ma(kline_df, [10, 20, 30, 50, 60])
        
        # 计算量比
        kline_df['volume_ratio'] = self.calculate_volume_ratio(kline_df)
        
        latest = kline_df.iloc[-1]
        prev = kline_df.iloc[-2] if len(kline_df) > 1 else latest
        
        # MA10支撑强度
        ma10_support = self.calculate_ma10_support_strength(kline_df)
        
        # 当前价格状态
        current_price = latest.get('close', 0)
        ma10 = latest.get('ma10', 0)
        ma20 = latest.get('ma20', 0)
        
        # 判断是否在MA10支撑位附近
        near_ma10 = bool(abs(current_price - ma10) / ma10 * 100 <= 5) if ma10 > 0 else False
        
        # 获取涨停信息
        try:
            zt_date = datetime.now().strftime('%Y%m%d')
            zt_df = ak.stock_zt_pool_em(date=zt_date)
            zt_stock = zt_df[zt_df['代码'] == code] if zt_df is not None and not zt_df.empty else None
            boards = int(zt_stock['连板数'].values[0]) if zt_stock is not None and not zt_stock.empty else 0
        except:
            boards = 0
        
        return {
            'code': code,
            'name': latest.get('code', code),
            'price': float(current_price),
            'pct': float(latest.get('close', 0) / prev.get('close', 1) * 100 - 100) if prev.get('close', 0) > 0 else 0,
            'boards': boards,
            'ma10': float(ma10) if not pd.isna(ma10) else None,
            'ma20': float(ma20) if not pd.isna(ma20) else None,
            'ma10_support': round(ma10_support, 1),
            'near_ma10': near_ma10,
            'volume_ratio': float(latest.get('volume_ratio', 0)),
            'high': float(latest.get('high', 0)),
            'low': float(latest.get('low', 0)),
            'turn': float(latest.get('turn', 0)),
        }
    
    def get_min30_kline(self, code: str, date: str) -> pd.DataFrame:
        """
        获取30分钟K线数据（用于买点分析）
        """
        try:
            df = ak.stock_zh_a_hist(
                symbol=code,
                period='30',
                start_date=(datetime.now() - timedelta(days=5)).strftime('%Y%m%d'),
                end_date=date,
                adjustflag='3'
            )
            return df
        except Exception as e:
            print(f"获取30分钟K线失败: {e}")
            return pd.DataFrame()
    
    def check_entry_signal(self, code: str) -> Dict:
        """
        买点信号判断
        
        规则：
        1. 30分钟K线MA50支撑
        2. 日K MA10±5%
        3. 缩量承接
        """
        # 获取日K数据
        daily_df = self.get_historical_kline(code, days=60)
        if daily_df.empty:
            return {'signal': 'none', 'reason': '数据不足'}
        
        daily_df = self.calculate_ma(daily_df, [10, 20])
        latest = daily_df.iloc[-1]
        
        current_price = latest.get('close', 0)
        ma10 = latest.get('ma10', 0)
        
        # 检查日K MA10±5%
        ma10_check = False
        if ma10 > 0:
            distance = abs(current_price - ma10) / ma10 * 100
            ma10_check = distance <= 5
        
        # 检查量比（缩量承接）
        volume_ratio = self.calculate_volume_ratio(daily_df, window=5).iloc[-1]
        volume_check = 0.5 <= volume_ratio <= 1.5
        
        # 获取30分钟K线MA50
        min30_df = self.get_min30_kline(code, datetime.now().strftime('%Y%m%d'))
        if not min30_df.empty:
            min30_df['ma50'] = min30_df['收盘'].rolling(50).mean()
            min30_ma50 = min30_df['ma50'].iloc[-1]
            min30_check = min30_ma50 and abs(current_price - min30_ma50) / min30_ma50 * 100 <= 3
        else:
            min30_check = False
        
        # 综合判断
        signal = 'strong' if (ma10_check and volume_check and min30_check) else \
                 'watch' if (ma10_check and volume_check) else 'none'
        
        reasons = []
        if ma10_check:
            reasons.append('MA10支撑')
        if volume_check:
            reasons.append('缩量承接')
        if min30_check:
            reasons.append('30分钟MA50支撑')
        
        return {
            'signal': signal,
            'reasons': reasons,
            'ma10_distance': round(abs(current_price - ma10) / ma10 * 100, 2) if ma10 > 0 else None,
            'volume_ratio': round(float(volume_ratio), 2),
            'price': float(current_price),
            'ma10': float(ma10) if not pd.isna(ma10) else None
        }