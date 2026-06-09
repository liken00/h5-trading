"""
选股模型
基于龙韵智趋战法的选股逻辑
"""

import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import akshare as ak
import baostock as bs


class SelectionModel:
    """龙韵智趋选股模型"""
    
    def __init__(self, dragon_model):
        self.dragon = dragon_model
    
    def get_today_zt_stocks(self) -> List[Dict]:
        """
        获取今日涨停股列表（增强版）
        包含封板时间、题材等信息
        """
        try:
            date = datetime.now().strftime('%Y%m%d')
            df = ak.stock_zt_pool_em(date=date)
            
            if df is None or df.empty:
                return []
            
            stocks = []
            for _, row in df.iterrows():
                # 解析涨停时间（如果有）
                seal_time = ''
                try:
                    # akshare的涨停池数据包含封板时间字段
                    seal_time = str(row.get('封板时间', ''))
                except:
                    pass
                
                stocks.append({
                    'code': str(row.get('代码', '')),
                    'name': str(row.get('名称', '')),
                    'boards': int(row.get('连板数', 0)),
                    'pct': float(row.get('涨幅', 0)),
                    'turnover': float(row.get('成交额', 0)) / 1e8,  # 亿
                    'reason': str(row.get('涨停统计[{}]'.format(date), row.get('所属行业', '题材'))),
                    'seal_time': seal_time,  # 封板时间
                    'board': str(row.get('所属行业', '')),  # 所属行业作为题材
                })
            
            # 按连板数排序
            stocks.sort(key=lambda x: x['boards'], reverse=True)
            return stocks
            
        except Exception as e:
            print(f"获取涨停股失败: {e}")
            return []
    
    def screen_mainlines(self) -> List[Dict]:
        """
        主线板块筛选
        规则：同板块≥2只同日2板 = 主线确认
        """
        stocks = self.get_today_zt_stocks()
        if not stocks:
            return []
        
        # 按板块分组
        sector_stocks = {}
        for stock in stocks:
            sector = stock.get('board', '未知')
            if sector not in sector_stocks:
                sector_stocks[sector] = []
            sector_stocks[sector].append(stock)
        
        # 筛选主线（≥2只2板以上）
        mainlines = []
        for sector, stock_list in sector_stocks.items():
            # 统计2板以上的股票
            above_2board = [s for s in stock_list if s.get('boards', 0) >= 2]
            if len(above_2board) >= 2:
                # 按封板时间排序
                above_2board.sort(key=lambda x: x.get('seal_time', '99:99:99'))
                mainlines.append({
                    'sector': sector,
                    'stocks': above_2board,
                    'count': len(above_2board),
                    'leader': above_2board[0] if above_2board else None,
                    'status': '主线确认' if len(above_2board) >= 2 else '观察中'
                })
        
        # 按涨停数量排序
        mainlines.sort(key=lambda x: x['count'], reverse=True)
        return mainlines
    
    def screen_leaders(self, min_boards: int = 3) -> List[Dict]:
        """
        龙头确认
        规则：三/四板封板时间最早
        
        min_boards: 最小连板数
        """
        stocks = self.get_today_zt_stocks()
        if not stocks:
            return []
        
        # 筛选高板位股票
        high_board_stocks = [s for s in stocks if s.get('boards', 0) >= min_boards]
        
        # 按封板时间排序（早封板优先）
        high_board_stocks.sort(key=lambda x: x.get('seal_time', '99:99:99'))
        
        leaders = []
        for i, stock in enumerate(high_board_stocks):
            boards = stock.get('boards', 0)
            
            # 计算仓位
            position = self._get_position(boards)
            
            # 风险等级
            risk_level = '高' if boards >= 5 else '中' if boards >= 4 else '低'
            
            leaders.append({
                'rank': i + 1,
                'code': stock.get('code'),
                'name': stock.get('name'),
                'boards': boards,
                'position': position,  # 仓位（成）
                'risk_level': risk_level,
                'seal_time': stock.get('seal_time', ''),
                'reason': stock.get('reason', ''),
                'turnover': stock.get('turnover', 0),
                'pct': stock.get('pct', 0)
            })
        
        return leaders
    
    def screen_wave2_candidates(self) -> List[Dict]:
        """
        二波候选筛选
        规则：连续两天首板≥5家
        """
        candidates = self.dragon.check_wave2_candidates(
            datetime.now().strftime('%Y%m%d'),
            days=10
        )
        
        result = []
        for cand in candidates:
            # 获取这两天涨停的首板股
            try:
                date1 = cand.get('date', '')
                date2 = cand.get('prev_date', '')
                
                zt_df1 = ak.stock_zt_pool_em(date=date1)
                zt_df2 = ak.stock_zt_pool_em(date=date2)
                
                if zt_df1 is not None and not zt_df1.empty:
                    wave2_stocks = zt_df1[zt_df1['连板数'] == 1].head(10)
                    for _, row in wave2_stocks.iterrows():
                        result.append({
                            'code': str(row.get('代码', '')),
                            'name': str(row.get('名称', '')),
                            'first_date': date1,
                            'second_date': date2,
                            'status': '二波候选'
                        })
                        
            except Exception as e:
                print(f"获取二波候选详情失败: {e}")
        
        return result
    
    def _get_position(self, boards: int) -> float:
        """
        根据连板数计算仓位
        规则：3板0.25成 / 4板0.35成 / 5板0.5成
        """
        position_map = {
            3: 0.25,
            4: 0.35,
            5: 0.50,
        }
        # 5板以上按5板处理
        return position_map.get(boards, position_map.get(5, 0.5))
    
    def get_selection_result(self) -> Dict:
        """
        获取完整选股结果
        包含主线、龙头、二波候选
        """
        return {
            'mainlines': self.screen_mainlines(),
            'leaders': self.screen_leaders(),
            'wave2_candidates': self.screen_wave2_candidates(),
            'timestamp': datetime.now().isoformat()
        }