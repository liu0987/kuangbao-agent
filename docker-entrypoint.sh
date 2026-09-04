#!/bin/bash
set -e

# 根据 SERVICE_TYPE 启动不同服务
case "${SERVICE_TYPE}" in
  mining-news)
    echo "Starting Mining News MCP Server..."
    exec python -m code.servers.mining_news.server
    ;;
  mineral-pdf)
    echo "Starting Mineral PDF MCP Server..."
    exec python -m code.servers.mineral_pdf.server
    ;;
  commodity-price)
    echo "Starting Commodity Price MCP Server..."
    exec python -m code.servers.commodity_price.server
    ;;
  agent)
    echo "Starting Agent..."
    exec python -m code.agent.main "${@}"
    ;;
  *)
    echo "Unknown SERVICE_TYPE: ${SERVICE_TYPE}"
    echo "Valid options: mining-news, mineral-pdf, commodity-price, agent"
    exit 1
    ;;
esac
