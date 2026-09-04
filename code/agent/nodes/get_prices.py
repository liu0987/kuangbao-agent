"""
价格查询节点
查询相关商品价格和趋势
优化：改进商品推断，支持更多矿种
"""
from ..state import AgentState, PriceData
from .. import mcp_client
from ..logger import get_logger


async def get_prices_node(state: AgentState) -> dict:
    """
    价格查询节点

    1. 根据目标矿区/公司推断相关商品
    2. 查询价格和趋势
    """
    logger = get_logger()
    logger.start_stage("获取价格", "查询相关商品价格和趋势数据")

    target = state.get("target", "")
    query = state.get("query", "")
    warnings = list(state.get("warnings", []))

    # 1. 推断相关商品
    logger.log_mcp_call("commodity-price-mcp", "infer_commodities")
    infer_result = await mcp_client.call(
        "commodity-price-mcp",
        "infer_commodities",
        {"target": target + " " + query}
    )

    if isinstance(infer_result, dict) and "error" in infer_result:
        logger.warning(f"商品推断失败: {infer_result['error']}")
        warnings.append(f"商品推断失败: {infer_result['error']}")
        logger.end_stage("failed", infer_result['error'])
        return {"prices": [], "warnings": warnings}

    commodities = infer_result.get("commodities", []) if isinstance(infer_result, dict) else []

    if not commodities:
        commodities = ["lithium_carbonate"]  # 默认查询碳酸锂
        logger.add_stage_detail("→ 使用默认商品: 碳酸锂")
    else:
        logger.add_stage_detail(f"→ 推断相关商品: {', '.join(commodities[:3])}")

    # 2. 查询价格和趋势（最多查询3个商品，避免过长）
    prices = []
    for comm in commodities[:3]:
        try:
            # 查询当前价格
            logger.log_mcp_call("commodity-price-mcp", "get_price")
            price_result = await mcp_client.call(
                "commodity-price-mcp",
                "get_price",
                {"commodity": comm}
            )

            if isinstance(price_result, dict) and "error" in price_result:
                logger.warning(f"{comm} 价格查询失败: {price_result['error']}")
                warnings.append(f"{comm} 价格查询失败: {price_result['error']}")
                continue

            # 查询趋势
            logger.log_mcp_call("commodity-price-mcp", "get_trend")
            trend_result = await mcp_client.call(
                "commodity-price-mcp",
                "get_trend",
                {"commodity": comm, "days": 30}
            )

            trend = trend_result if isinstance(trend_result, dict) else {}

            # 记录价格
            price = price_result.get("price", 0)
            currency = price_result.get("currency", "")
            logger.log_price(comm, price, currency)

            prices.append(PriceData(
                commodity=comm,
                price=price,
                currency=currency,
                unit=price_result.get("unit", ""),
                change_pct=price_result.get("change_pct", 0),
                trend=trend,
            ))

        except Exception as e:
            logger.warning(f"{comm} 价格数据暂不可用: {str(e)}")
            warnings.append(f"{comm} 价格数据暂不可用: {str(e)}")

    logger.end_stage("success")
    return {"prices": prices, "warnings": warnings}
