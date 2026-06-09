"""
买点模型
基于龙韵智趋战法的买点信号判断
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional


class EntryModel:
    """龙韵智趋买点模型"""
    
    # 买点信号常量
    MA10_TOLERANCE = 0.05  # MA10±5%
    VOLUME_RATIO_LOW = 0.5  # 缩量下限
    VOLUME_RATIO_HIGH = 1.5  # 缩量上限
    
    def __init__(self, dragon_model):
        self.dragon = dragon_model
    
    def check_entry_signals(self, code: str) -> Dict:
        """
        综合买点信号检查
        
        规则：
        1. 30分钟K线MA50 + 日K MA10±5% + 缩量承接
        
        返回信号等级：
        - strong: 强买点（满足所有条件）
        - watch: 观察（满足部分条件）
        - none: 不满足
        """
        # 获取日K数据
        daily_df = self.dragon.get_historical_kline(code, days=60)
        if daily_df.empty:
            return {'signal': 'none', 'reason': '数据不足'}
        
        # 计算MA
        daily_df = self.dragon.calculate_ma(daily_df, [10, 20, 30])
        daily_df['volume_ratio'] = self.dragon.calculate_volume_ratio(daily_df, window=5)
        
        latest = daily_df.iloc[-1]
        current_price = latest.get('close', 0)
        ma10 = latest.get('ma10', 0)
        ma20 = latest.get('ma20', 0)
        ma30 = latest.get('ma30', 0)
        volume_ratio = latest.get('volume_ratio', 1)
        
        signals = {}
        reasons = []
        
        # 1. 检查MA10±5%
        ma10_check = False
        if ma10 > 0:
            distance = abs(current_price - ma10) / ma10 * 100
            ma10_check = distance <= 5
            signals['ma10_near'] = ma10_check
            if ma10_check:
                reasons.append(f'MA10接近({distance:.1f}%)')
        
        # 2. 检查缩量承接
        volume_check = self.VOLUME_RATIO_LOW <= volume_ratio <= self.VOLUME_RATIO_HIGH
        signals['volume_ok'] = volume_check
        if volume_check:
            reasons.append(f'量比健康({volume_ratio:.2f})')
        
        # 3. 检查30分钟MA50
        min30_ma50_check = self._check_min30_ma50(code)
        signals['min30_ma50'] = min30_ma50_check
        if min30_ma50_check:
            reasons.append('30分钟MA50支撑')
        
        # 4. 检查价格是否在MA均线之上
        price_above_ma = current_price > ma10 > 0
        signals['price_above_ma10'] = price_above_ma
        if price_above_ma:
            reasons.append('价格位于MA10上方')
        
        # 综合评分
        score = sum([
            signals.get('ma10_near', False) * 30,
            signals.get('volume_ok', False) * 30,
            signals.get('min30_ma50', False) * 20,
            signals.get('price_above_ma10', False) * 20,
        ])
        
        # 判断信号强度
        if score >= 80 and signals.get('ma10_near') and signals.get('volume_ok'):
            signal = 'strong'
        elif score >= 50 and (signals.get('ma10_near') or signals.get('volume_ok')):
            signal = 'watch'
        else:
            signal = 'none'
        
        return {
            'signal': signal,
            'score': score,
            'reasons': reasons,
            'details': signals,
            'price': float(current_price),
            'ma10': float(ma10) if not pd.isna(ma10) else None,
            'ma20': float(ma20) if not pd.isna(ma20) else None,
            'ma30': float(ma30) if not pd.isna(ma30) else None,
            'volume_ratio': float(volume_ratio),
            'timestamp': datetime.now().isoformat()
        }
    
    def _check_min30_ma50(self, code: str) -> bool:
        """
        检查30分钟K线MA50支撑
        """
        try:
            # 获取近5天的30分钟K线
            end_date = datetime.now().strftime('%Y%m%d')
            start_date = (datetime.now() - timedelta(days=5)).strftime('%Y%m%d')
            
            import akshare as ak
            df = ak.stock_zh_a_hist(
                symbol=code,
                period='30',
                start_date=start_date,
                end_date=end_date,
                adjustflag='3'
            )
            
            if df is None or df.empty:
                return False
            
            # 计算MA50
            df['ma50'] = df['收盘'].rolling(50).mean()
            if len(df) < 50:
                return False
            
            latest = df.iloc[-1]
            current_price = latest.get('收盘', 0)
            ma50 = latest.get('ma50', 0)
            
            if ma50 <= 0:
                return False
            
            # 检查价格是否在MA50附近3%
            distance = abs(current_price - ma50) / ma50 * 100
            return distance <= 3
            
        except Exception as e:
            print(f"30分钟MA50检查失败: {e}")
            return False
    
    def calculate_ma_support_strength(self, code: str) -> Dict:
        """
        计算MA支撑强度
        返回各周期MA的支撑状态
        """
        df = self.dragon.get_historical_kline(code, days=60)
        if df.empty:
            return {'error': '数据不足'}
        
        df = self.dragon.calculate_ma(df, [10, 20, 30, 60])
        latest = df.iloc[-1]
        current_price = latest.get('close', 0)
        
        supports = []
        for period in [10, 20, 30, 60]:
            ma = latest.get(f'ma{period}')
            if pd.isna(ma) or ma <= 0:
                continue
            
            distance = (current_price - ma) / ma * 100  # 正数表示在MA上方
            
            # 支撑强度判断
            if distance >= 5:
                strength = '强支撑'
            elif distance >= 0:
                strength = '支撑'
            elif distance >= -3:
                strength = '轻微跌破'
            else:
                strength = '跌破'
            
            supports.append({
                'period': period,
                'ma': float(ma),
                'distance': round(distance, 2),
                'strength': strength,
                'current_price': float(current_price)
            })
        
        return {
            'supports': supports,
            'timestamp': datetime.now().isoformat()
        }
    
    def get_batch_entry_check(self, codes: List[str]) -> List[Dict]:
        """
        批量检查买点信号
        """
        results = []
        for code in codes:
            result = self.check_entry_signals(code)
            result['code'] = code
            results.append(result)
        
        # 按信号强度排序
        signal_order = {'strong': 0, 'watch': 1, 'none': 2}
        results.sort(key=lambda x: (signal_order.get(x['signal'], 2), -x.get('score', 0)))
        
        return results