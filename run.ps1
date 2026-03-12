# Polymarket Trading System - Run scripts
param([string]$Action = "help")

switch ($Action) {
    "init"     { python scripts/init_local.py }
    "seed"     { python scripts/seed_demo.py }
    "warmup"   { python scripts/warmup.py --runs 15 --interval 20 }
    "collect"  { python -m services.collector.main }
    "news"     { python -m services.news_collector.main }
    "features" { python -m services.feature_store.main }
    "ml"       { python -m services.ml_module.main }
    "backtest" { python -m services.backtester.main }
    "bot"      { python -m services.execution_bot.main }
    default {
        Write-Host "Usage: .\run.ps1 [init|collect|news|features|ml|backtest|bot]"
        Write-Host "  init     - create SQLite DB (for local run without Docker)"
        Write-Host "  seed     - insert demo data (2 markets, 350 trades)"
        Write-Host "  warmup   - run collect 15x (20s) to build real price history (~5 min)"
        Write-Host "  collect  - collector (markets, trades)"
        Write-Host "  news     - RSS news collector"
        Write-Host "  features - feature store"
        Write-Host "  ml       - ML signals"
        Write-Host "  backtest - backtester"
        Write-Host "  bot      - execution bot"
    }
}
