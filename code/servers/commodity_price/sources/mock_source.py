"""
模拟价格数据源（优化版）
提供更真实的模拟数据，支持趋势模拟
"""
import random
import math
from datetime import datetime, timedelta


# 基础价格配置（基于2026年真实市场数据）
BASE_PRICES = {
    "lithium_carbonate": {
        "price": 98500,
        "currency": "CNY",
        "unit": "元/吨",
        "source": "SMM",
        "volatility": 0.015,
        "trend": 0.001,
    },
    "lithium_hydroxide": {
        "price": 85000,
        "currency": "CNY",
        "unit": "元/吨",
        "source": "SMM",
        "volatility": 0.018,
        "trend": 0.0008,
    },
    "lithium_spodumene": {
        "price": 1200,
        "currency": "USD",
        "unit": "美元/吨",
        "source": "Fastmarkets",
        "volatility": 0.02,
        "trend": 0.0012,
    },
    "copper": {
        "price": 9200,
        "currency": "USD",
        "unit": "美元/吨",
        "source": "LME",
        "volatility": 0.012,
        "trend": 0.0005,
    },
    "nickel": {
        "price": 17500,
        "currency": "USD",
        "unit": "美元/吨",
        "source": "LME",
        "volatility": 0.018,
        "trend": -0.0003,
    },
    "zinc": {
        "price": 2800,
        "currency": "USD",
        "unit": "美元/吨",
        "source": "LME",
        "volatility": 0.015,
        "trend": 0.0002,
    },
    "iron_ore": {
        "price": 115,
        "currency": "USD",
        "unit": "美元/吨",
        "source": "SGX",
        "volatility": 0.018,
        "trend": -0.0005,
    },
    "gold": {
        "price": 2650,
        "currency": "USD",
        "unit": "美元/盎司",
        "source": "COMEX",
        "volatility": 0.008,
        "trend": 0.0003,
    },
    "silver": {
        "price": 31.5,
        "currency": "USD",
        "unit": "美元/盎司",
        "source": "COMEX",
        "volatility": 0.015,
        "trend": 0.0004,
    },
    "cobalt": {
        "price": 28000,
        "currency": "USD",
        "unit": "美元/吨",
        "source": "MB",
        "volatility": 0.02,
        "trend": -0.001,
    },
}

# 矿种到商品的映射（支持中英文关键词）
MINERAL_TO_COMMODITY = {
    # 英文关键词
    "lithium": ["lithium_carbonate", "lithium_hydroxide", "lithium_spodumene"],
    "copper": ["copper"],
    "nickel": ["nickel"],
    "zinc": ["zinc"],
    "iron": ["iron_ore"],
    "gold": ["gold"],
    "silver": ["silver"],
    "cobalt": ["cobalt"],
    "pilbara": ["lithium_carbonate", "lithium_spodumene"],
    "pilgangoora": ["lithium_carbonate", "lithium_spodumene"],
    # 中文关键词
    "锂": ["lithium_carbonate", "lithium_hydroxide", "lithium_spodumene"],
    "锂矿": ["lithium_carbonate", "lithium_hydroxide", "lithium_spodumene"],
    "碳酸锂": ["lithium_carbonate"],
    "氢氧化锂": ["lithium_hydroxide"],
    "锂辉石": ["lithium_spodumene"],
    "铜": ["copper"],
    "铜矿": ["copper"],
    "镍": ["nickel"],
    "镍矿": ["nickel"],
    "锌": ["zinc"],
    "锌矿": ["zinc"],
    "铁": ["iron_ore"],
    "铁矿": ["iron_ore"],
    "铁矿石": ["iron_ore"],
    "金": ["gold"],
    "金矿": ["gold"],
    "黄金": ["gold"],
    "银": ["silver"],
    "银矿": ["silver"],
    "白银": ["silver"],
    "钴": ["cobalt"],
    "钴矿": ["cobalt"],
}


def _generate_price_series(commodity: str, days: int = 30) -> list[dict]:
    """
    生成价格时间序列（确保一致性）

    Args:
        commodity: 商品名称
        days: 天数

    Returns:
        价格数据点列表
    """
    config = BASE_PRICES[commodity]
    base_price = config["price"]
    volatility = config["volatility"]
    trend = config.get("trend", 0)

    # 使用固定的随机种子确保可重复性
    seed = hash(commodity + str(datetime.now().date())) % 100000
    random.seed(seed)

    data_points = []
    current_date = datetime.now() - timedelta(days=days)
    price = base_price * (1 - trend * days * 0.5)  # 起始价格

    for i in range(days):
        date_str = current_date.strftime("%Y-%m-%d")

        # 使用正弦波 + 趋势 + 随机游走
        cycle_factor = math.sin(i * 0.15) * 0.015
        daily_change = random.gauss(trend, volatility)
        price = price * (1 + daily_change + cycle_factor * 0.1)
        price = max(price * 0.5, min(price * 2, price))  # 限制波动范围

        data_points.append({
            "date": date_str,
            "price": round(price, 2)
        })
        current_date += timedelta(days=1)

    random.seed()  # 重置随机种子
    return data_points


class MockPriceSource:
    """模拟价格数据源（优化版）"""

    def get_price(self, commodity: str, date: str = "latest") -> dict:
        """
        获取商品价格（使用与趋势一致的计算）

        Args:
            commodity: 商品名称
            date: 日期，"latest" 或 "YYYY-MM-DD"

        Returns:
            价格数据
        """
        if commodity not in BASE_PRICES:
            return {"error": f"Unknown commodity: {commodity}", "commodity": commodity}

        config = BASE_PRICES[commodity]

        # 生成30天价格序列
        data_points = _generate_price_series(commodity, 30)

        if date == "latest":
            # 使用最新的价格
            current = data_points[-1]["price"]
            yesterday = data_points[-2]["price"] if len(data_points) > 1 else current
            change_pct = ((current - yesterday) / yesterday) * 100
        else:
            # 查找指定日期的价格
            matching = [p for p in data_points if p["date"] == date]
            if matching:
                current = matching[0]["price"]
                idx = data_points.index(matching[0])
                yesterday = data_points[idx - 1]["price"] if idx > 0 else current
                change_pct = ((current - yesterday) / yesterday) * 100
            else:
                # 如果没有找到，使用最新价格
                current = data_points[-1]["price"]
                change_pct = 0

        return {
            "commodity": commodity,
            "price": round(current, 2),
            "currency": config["currency"],
            "unit": config["unit"],
            "date": date if date != "latest" else datetime.now().strftime("%Y-%m-%d"),
            "source": config["source"],
            "change_pct": round(change_pct, 2),
        }

    def get_trend(self, commodity: str, days: int = 30) -> dict:
        """
        获取价格趋势

        Args:
            commodity: 商品名称
            days: 天数

        Returns:
            趋势数据
        """
        if commodity not in BASE_PRICES:
            return {"error": f"Unknown commodity: {commodity}", "commodity": commodity}

        config = BASE_PRICES[commodity]

        # 生成价格序列
        data_points = _generate_price_series(commodity, days)

        # 计算统计值
        prices = [p["price"] for p in data_points]
        current = data_points[-1]["price"]
        high = max(prices)
        low = min(prices)
        avg = sum(prices) / len(prices)

        # 计算涨跌幅
        start_price = data_points[0]["price"]
        change_pct = ((current - start_price) / start_price) * 100

        # 判断趋势
        if change_pct > 2:
            trend_desc = "上涨"
        elif change_pct < -2:
            trend_desc = "下跌"
        else:
            trend_desc = "震荡"

        return {
            "commodity": commodity,
            "currency": config["currency"],
            "unit": config["unit"],
            "source": config["source"],
            "period": f"{days}d",
            "current": round(current, 2),
            "high": round(high, 2),
            "low": round(low, 2),
            "avg": round(avg, 2),
            "change_pct": round(change_pct, 2),
            "trend": trend_desc,
            "data_points": data_points,
        }

    @staticmethod
    def get_supported_commodities() -> list[str]:
        """获取支持的商品列表"""
        return list(BASE_PRICES.keys())

    @staticmethod
    def infer_commodities(target: str) -> list[str]:
        """
        根据目标矿区/公司推断相关商品

        Args:
            target: 矿区/公司名称

        Returns:
            相关商品列表
        """
        target_lower = target.lower()
        commodities = []

        for keyword, comms in MINERAL_TO_COMMODITY.items():
            if keyword in target_lower:
                commodities.extend(comms)

        # 去重
        commodities = list(set(commodities))

        # 如果没有匹配到，默认返回锂相关
        if not commodities:
            commodities = ["lithium_carbonate"]

        return commodities
