import { api } from '../api.js';
import { formatPnl, formatNumber, showLoading, showEmpty, showError } from '../utils.js';
import { createLineChart, createBarChart } from '../charts.js';
import { getChartColors } from '../theme.js';

export async function render(container) {
    showLoading(container);

    try {
        const analytics = await api.getAnalytics();

        const pnl = analytics.pnl_timeline || [];
        const tradeStats = analytics.trade_stats || [];
        const spreadTimeline = analytics.spread_timeline || [];

        if (pnl.length === 0 && tradeStats.length === 0) {
            showEmpty(container, '📈', 'No Performance Data', 'Results will appear after backtesting');
            return;
        }

        const totalProfit = analytics.total_profit || 0;
        const profitByMarket = {};
        pnl.forEach(p => {
            profitByMarket[p.market_id] = (profitByMarket[p.market_id] || 0) + p.profit;
        });
        const marketProfits = Object.entries(profitByMarket).sort((a, b) => b[1] - a[1]);
        const bestMarket = marketProfits.length > 0 ? marketProfits[0] : null;
        const worstMarket = marketProfits.length > 0 ? marketProfits[marketProfits.length - 1] : null;
        const winCount = marketProfits.filter(([, p]) => p > 0).length;
        const lossCount = marketProfits.filter(([, p]) => p < 0).length;

        container.innerHTML = `
            <div class="screen">
                <div class="screen-title">Performance</div>

                <div class="kpi-strip">
                    <div class="kpi-card">
                        <div class="kpi-label">Total P&L</div>
                        <div class="kpi-value ${totalProfit >= 0 ? 'positive' : 'negative'}">${formatPnl(totalProfit)}</div>
                    </div>
                    <div class="kpi-card">
                        <div class="kpi-label">Volume</div>
                        <div class="kpi-value">${formatNumber(analytics.total_volume)}</div>
                    </div>
                    <div class="kpi-card">
                        <div class="kpi-label">Win / Loss</div>
                        <div class="kpi-value">${winCount} / ${lossCount}</div>
                    </div>
                    <div class="kpi-card">
                        <div class="kpi-label">Spread</div>
                        <div class="kpi-value">${(analytics.avg_spread_bps || 0).toFixed(0)} bps</div>
                    </div>
                </div>

                ${pnl.length > 1 ? `
                <div class="chart-card">
                    <div class="chart-card-title">Cumulative P&L</div>
                    <div class="chart-container tall"><canvas id="perf-pnl"></canvas></div>
                </div>` : ''}

                ${marketProfits.length > 0 ? `
                <div class="chart-card">
                    <div class="chart-card-title">Profit by Market</div>
                    <div class="chart-container tall"><canvas id="perf-by-market"></canvas></div>
                </div>` : ''}

                ${spreadTimeline.length > 1 ? `
                <div class="chart-card">
                    <div class="chart-card-title">Spread Over Time (bps)</div>
                    <div class="chart-container"><canvas id="perf-spread"></canvas></div>
                </div>` : ''}

                ${bestMarket || worstMarket ? `
                <div class="card">
                    <div class="card-title" style="margin-bottom:12px">Summary</div>
                    <table class="data-table">
                        <tr><td>Total trades</td><td class="text-right">${formatNumber(analytics.total_trades)}</td></tr>
                        ${bestMarket ? `<tr><td>Best market</td><td class="text-right text-positive">${_truncId(bestMarket[0])} (${formatPnl(bestMarket[1])})</td></tr>` : ''}
                        ${worstMarket ? `<tr><td>Worst market</td><td class="text-right text-negative">${_truncId(worstMarket[0])} (${formatPnl(worstMarket[1])})</td></tr>` : ''}
                        <tr><td>Avg prediction</td><td class="text-right">${(analytics.avg_prediction || 0).toFixed(3)}</td></tr>
                    </table>
                </div>` : ''}
            </div>`;

        const c = getChartColors();

        if (pnl.length > 1) {
            const canvas = container.querySelector('#perf-pnl');
            if (canvas) {
                const labels = pnl.map(p => _shortTs(p.ts));
                const data = pnl.map(p => p.cumulative);
                const clr = data[data.length - 1] >= 0 ? c.positive : c.negative;
                createLineChart(canvas, labels, [
                    { label: 'Cumulative P&L', data, color: clr, fill: true },
                ]);
            }
        }

        if (marketProfits.length > 0) {
            const canvas = container.querySelector('#perf-by-market');
            if (canvas) {
                const sorted = marketProfits.slice(0, 15);
                const labels = sorted.map(([id]) => _truncId(id));
                const data = sorted.map(([, p]) => +p.toFixed(4));
                const colors = sorted.map(([, p]) => p >= 0 ? c.positive : c.negative);
                createBarChart(canvas, labels, [{ label: 'Profit', data, backgroundColor: colors }], {
                    indexAxis: 'y',
                    scales: {
                        x: {
                            ticks: { color: c.secondary, font: { size: 10 } },
                            grid: { color: c.grid },
                            border: { display: false },
                        },
                        y: {
                            ticks: { color: c.secondary, font: { size: 10 } },
                            grid: { display: false },
                            border: { display: false },
                        },
                    },
                });
            }
        }

        if (spreadTimeline.length > 1) {
            const canvas = container.querySelector('#perf-spread');
            if (canvas) {
                const reversed = spreadTimeline.slice().reverse();
                const labels = reversed.map(s => _shortTs(s.ts));
                const data = reversed.map(s => s.spread_bps);
                createLineChart(canvas, labels, [
                    { label: 'Spread (bps)', data, color: c.warning, fill: true },
                ]);
            }
        }
    } catch (err) {
        showError(container, err.message);
    }
}

function _shortTs(ts) {
    if (!ts) return '';
    const d = new Date(typeof ts === 'number' ? ts * 1000 : ts);
    if (isNaN(d.getTime())) return String(ts).slice(0, 10);
    return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

function _truncId(id) {
    if (!id) return '';
    return id.length > 12 ? id.slice(0, 10) + '…' : id;
}

function _esc(s) {
    if (!s) return '';
    const d = document.createElement('div');
    d.textContent = s;
    return d.innerHTML;
}
