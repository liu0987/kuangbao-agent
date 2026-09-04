"""
Commodity Price MCP Server 测试
使用 pytest

注意：由于项目目录 'code' 与 Python 标准库模块 'code' 冲突，
需要使用 sys.path 来正确导入模块
"""
import sys
from pathlib import Path

# 确保项目根目录在 sys.path 中
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import pytest
from code.servers.commodity_price.sources.mock_source import MockPriceSource, BASE_PRICES


class TestMockPriceSource:
    """MockPriceSource 测试类"""

    def setup_method(self):
        """每个测试前初始化"""
        self.source = MockPriceSource()

    def test_get_price_latest(self):
        """测试获取最新价格"""
        result = self.source.get_price("lithium_carbonate")

        assert "price" in result
        assert "currency" in result
        assert "unit" in result
        assert result["commodity"] == "lithium_carbonate"
        assert result["price"] > 0
        assert result["currency"] == "CNY"
        assert result["unit"] == "元/吨"

    def test_get_price_specific_date(self):
        """测试获取指定日期价格"""
        result = self.source.get_price("copper", date="2026-01-01")

        assert "price" in result
        assert result["commodity"] == "copper"

    def test_get_price_unknown_commodity(self):
        """测试未知商品"""
        result = self.source.get_price("unknown_commodity")
        assert "error" in result

    def test_get_trend(self):
        """测试趋势查询"""
        result = self.source.get_trend("copper", days=30)

        assert "data_points" in result
        assert len(result["data_points"]) == 30
        assert "current" in result
        assert "high" in result
        assert "low" in result
        assert "avg" in result
        assert "trend" in result
        assert result["trend"] in ["上涨", "下跌", "震荡"]

    def test_get_trend_custom_days(self):
        """测试自定义天数趋势"""
        result = self.source.get_trend("gold", days=7)

        assert len(result["data_points"]) == 7

    def test_get_trend_price_consistency(self):
        """测试价格一致性：当前价格应在30日区间内"""
        result = self.source.get_trend("lithium_carbonate", days=30)

        current = result["current"]
        high = result["high"]
        low = result["low"]

        assert low <= current <= high, (
            f"当前价格 {current} 不在30日区间 [{low}, {high}] 内"
        )

    def test_infer_commodities_lithium(self):
        """测试锂矿商品推断"""
        commodities = MockPriceSource.infer_commodities("Pilbara lithium mine")

        assert isinstance(commodities, list)
        assert "lithium_carbonate" in commodities
        assert "lithium_spodumene" in commodities

    def test_infer_commodities_copper(self):
        """测试铜矿商品推断"""
        commodities = MockPriceSource.infer_commodities("copper project")

        assert "copper" in commodities

    def test_infer_commodities_unknown(self):
        """测试未知矿区推断"""
        commodities = MockPriceSource.infer_commodities("unknown mine")

        assert isinstance(commodities, list)
        assert len(commodities) > 0  # 默认返回锂相关

    def test_get_supported_commodities(self):
        """测试获取支持的商品列表"""
        commodities = MockPriceSource.get_supported_commodities()

        assert isinstance(commodities, list)
        assert "lithium_carbonate" in commodities
        assert "copper" in commodities
        assert "gold" in commodities

    def test_all_commodities_have_prices(self):
        """测试所有商品都有基础价格配置"""
        for commodity in MockPriceSource.get_supported_commodities():
            assert commodity in BASE_PRICES
            config = BASE_PRICES[commodity]
            assert "price" in config
            assert "currency" in config
            assert "unit" in config
            assert "source" in config
