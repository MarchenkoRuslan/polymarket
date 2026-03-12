# Polymarket Trading System - Run scripts
param([string]$Action = "help")

switch ($Action) {
    "collect"  { python -m services.collector.main }
    "features" { python -m services.feature_store.main }
    "ml"       { python -m services.ml_module.main }
    "backtest" { python -m services.backtester.main }
    "bot"      { python -m services.execution_bot.main }
    default {
        Write-Host "Usage: .\run.ps1 [collect|features|ml|backtest|bot]"
    }
}
