import { api } from '../api.js';
import { formatPrice, formatPnl, formatNumber, signalBadge, truncate, showLoading, showError } from '../utils.js';
import { createDoughnutChart } from '../charts.js';
import { navigate } from '../router.js';

export async function render(container) {
    showLoading(container);

    try {
        const [status, analytics, markets] = await Promise.all([
            api.getStatus(),
            api.getAnalytics(),
            api.getMarkets(5, 0, false),
        ]);

        const hasErrors = status.migration_error || status.last_pipeline_error || status.db_error;
        const errorMsg = status.migration_error || status.last_pipeline_error || status.db_error || '';

        const buyCount = analytics.signal_distribution
            ? analytics.signal_distribution.filter(b => b.bucket >= 0.55).reduce((s, b) => s + b.count, 0) : 0;
        const sellCount = analytics.signal_distribution
            ? analytics.signal_distribution.filter(b => b.bucket < 0.35).reduce((s, b) => s + b.count, 0) : 0;
        const holdCount = analytics.signal_distribution
            ? analytics.signal_distribution.filter(b => b.bucket >= 0.35 && b.bucket < 0.55).reduce((s, b) => s + b.count, 0) : 0;

        container.innerHTML = `
            <div class="screen">
                <div class="screen-title">Dashboard</div>

                <div class="status-banner ${hasErrors ? 'error' : 'ok'}">
                    <span class="status-icon">${hasErrors ? '⚠️' : '✅'}</span>
                    <span class="status-text">
                        ${hasErrors ? 'Issues detected' : 'System running normally'}
                        ${hasErrors ? `<span class="status-detail">${_esc(errorMsg)}</span>` : ''}
                    </span>
                </div>

                <div class="kpi-strip">
                    <div class="kpi-card">
                        <div class="kpi-label">Markets</div>
                        <div class="kpi-value">${formatNumber(status.markets)}</div>
                    </div>
                    <div class="kpi-card">
                        <div class="kpi-label">Trades</div>
                        <div class="kpi-value">${formatNumber(status.trades)}</div>
                    </div>
                    <div class="kpi-card">
                        <div class="kpi-label">Total P&L</div>
                        <div class="kpi-value ${analytics.total_profit >= 0 ? 'positive' : 'negative'}">${formatPnl(analytics.total_profit)}</div>
                    </div>
                    <div class="kpi-card">
                        <div class="kpi-label">Avg Signal</div>
                        <div class="kpi-value">${(analytics.avg_prediction || 0).toFixed(2)}</div>
                    </div>
                </div>

                <div class="signal-summary">
                    <div class="signal-summary-item buy">
                        ${buyCount}<div class="signal-label">Buy</div>
                    </div>
                    <div class="signal-summary-item hold">
                        ${holdCount}<div class="signal-label">Hold</div>
                    </div>
                    <div class="signal-summary-item sell">
                        ${sellCount}<div class="signal-label">Sell</div>
                    </div>
                </div>

                ${(buyCount + sellCount + holdCount) > 0 ? `
                <div class="chart-card">
                    <div class="chart-card-title">Signal Distribution</div>
                    <div class="chart-container" style="height:180px">
                        <canvas id="home-donut"></canvas>
                    </div>
                </div>` : ''}

                <div class="section-header">
                    <span class="section-title">Top Markets</span>
                    <button class="section-action" id="btn-all-markets">View all →</button>
                </div>

                <div id="home-markets"></div>

                <div class="kpi-strip mt-16">
                    <div class="kpi-card">
                        <div class="kpi-label">Volume</div>
                        <div class="kpi-value">${formatNumber(analytics.total_volume)}</div>
                    </div>
                    <div class="kpi-card">
                        <div class="kpi-label">Signals</div>
                        <div class="kpi-value">${formatNumber(status.signals)}</div>
                    </div>
                    <div class="kpi-card">
                        <div class="kpi-label">News</div>
                        <div class="kpi-value">${formatNumber(status.news)}</div>
                    </div>
                    <div class="kpi-card">
                        <div class="kpi-label">Spread</div>
                        <div class="kpi-value">${(analytics.avg_spread_bps || 0).toFixed(0)} bps</div>
                    </div>
                </div>
            </div>
        `;

        const marketsEl = container.querySelector('#home-markets');
        const tradeStats = analytics.trade_stats || [];
        const top = tradeStats.slice(0, 3);

        if (top.length === 0) {
            const mItems = (markets.items || []).slice(0, 3);
            mItems.forEach(m => {
                marketsEl.appendChild(_marketCard(m.market_id, m.question, null, null, null));
            });
            if (mItems.length === 0) {
                marketsEl.innerHTML = '<div class="empty-state"><div class="empty-state-text">No markets yet</div></div>';
            }
        } else {
            top.forEach(t => {
                marketsEl.appendChild(_marketCard(t.market_id, t.question, t.avg_price, t.total_volume, null));
            });
        }

        container.querySelector('#btn-all-markets')?.addEventListener('click', () => navigate('markets'));

        if ((buyCount + sellCount + holdCount) > 0) {
            const canvas = container.querySelector('#home-donut');
            if (canvas) {
                createDoughnutChart(canvas, ['Buy', 'Hold', 'Sell'], [buyCount, holdCount, sellCount]);
            }
        }
    } catch (err) {
        showError(container, err.message);
    }
}

function _marketCard(id, question, price, volume, signalLabel) {
    const card = document.createElement('div');
    card.className = 'market-card';
    card.innerHTML = `
        <div class="market-card-body">
            <div class="market-card-question">${_esc(truncate(question || id, 80))}</div>
            <div class="market-card-meta">
                ${volume != null ? `<span>Vol: ${formatNumber(volume)}</span>` : ''}
                ${signalLabel ? signalBadge(signalLabel) : ''}
            </div>
        </div>
        <div class="market-card-right">
            ${price != null ? `<div class="market-card-price">${formatPrice(price)}</div>` : ''}
            <div class="card-chevron">›</div>
        </div>
    `;
    card.addEventListener('click', () => navigate(`market/${encodeURIComponent(id)}`));
    return card;
}

function _esc(s) {
    if (!s) return '';
    const d = document.createElement('div');
    d.textContent = s;
    return d.innerHTML;
}
