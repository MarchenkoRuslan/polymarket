import { api } from '../api.js';
import { formatPrice, formatPnl, formatNumber, formatDate, signalBadge, showLoading, showError } from '../utils.js';
import { createLineChart, createBarChart } from '../charts.js';
import { getChartColors } from '../theme.js';

export async function render(container, marketId) {
    marketId = decodeURIComponent(marketId || '');
    showLoading(container);

    try {
        const [market, trades, signals, features, results] = await Promise.all([
            api.getMarket(marketId),
            api.getTrades(marketId, 200),
            api.getSignals(marketId, 100),
            api.getFeatures(marketId, 500),
            api.getResults(marketId, 200),
        ]);

        const tradeItems = (trades.items || []).slice().reverse();
        const signalItems = (signals.items || []).slice().reverse();

        const latestPrice = tradeItems.length > 0 ? tradeItems[tradeItems.length - 1].price : null;
        const firstPrice = tradeItems.length > 1 ? tradeItems[0].price : latestPrice;
        const priceChange = latestPrice != null && firstPrice != null && firstPrice !== 0
            ? ((latestPrice - firstPrice) / firstPrice * 100) : null;

        const latestSignal = signalItems.length > 0 ? signalItems[signalItems.length - 1] : null;
        const totalVolume = tradeItems.reduce((s, t) => s + (t.size || 0), 0);

        const featureMap = {};
        (features.items || []).forEach(f => {
            if (!featureMap[f.feature_name] || f.ts > featureMap[f.feature_name].ts) {
                featureMap[f.feature_name] = f;
            }
        });

        const resultItems = (results.items || []).slice();
        const totalProfit = resultItems.reduce((s, r) => s + (r.profit || 0), 0);

        container.innerHTML = `
            <div class="screen">
                <div class="detail-header">
                    <div class="detail-question">${_esc(market.question || market.market_id)}</div>
                    ${latestPrice != null ? `
                    <div class="detail-price-row">
                        <span class="detail-price">${formatPrice(latestPrice)}</span>
                        ${priceChange != null ? `<span class="detail-change ${priceChange >= 0 ? 'positive' : 'negative'}">${priceChange >= 0 ? '+' : ''}${priceChange.toFixed(1)}%</span>` : ''}
                    </div>` : ''}
                    <div class="detail-meta">
                        ${latestSignal ? `<span>Signal: ${signalBadge(latestSignal.signal_label)}</span>` : ''}
                        ${totalVolume ? `<span>Volume: ${formatNumber(totalVolume)}</span>` : ''}
                        <span>Trades: ${formatNumber(trades.total)}</span>
                    </div>
                </div>

                ${market.polymarket_url ? `<a class="detail-link" href="${market.polymarket_url}" target="_blank" rel="noopener">Trade on Polymarket ↗</a>` : ''}

                ${tradeItems.length > 2 ? `
                <div class="chart-card">
                    <div class="chart-card-title">Price & Volume</div>
                    <div class="chart-container tall"><canvas id="detail-price-chart"></canvas></div>
                </div>` : ''}

                ${_collapsible('trading-stats', 'Trading Stats', _tradingStatsHtml(tradeItems, totalVolume, totalProfit))}
                ${_collapsible('technicals', 'Technical Indicators', _techHtml(featureMap))}
                ${_collapsible('signal-history', 'Signal History', _signalHistoryHtml(signalItems))}
                ${resultItems.length > 0 ? _collapsible('pnl-detail', 'P&L History', `
                    <div class="chart-container" style="height:180px"><canvas id="detail-pnl-chart"></canvas></div>
                    <div style="text-align:center;font-size:14px;font-weight:600;margin-top:4px" class="${totalProfit >= 0 ? 'text-positive' : 'text-negative'}">Total: ${formatPnl(totalProfit)}</div>
                `) : ''}
            </div>`;

        _initCollapsibles(container);
        _renderPriceChart(container, tradeItems);
        _renderPnlChart(container, resultItems);
    } catch (err) {
        showError(container, err.message);
    }
}

function _renderPriceChart(container, trades) {
    const canvas = container.querySelector('#detail-price-chart');
    if (!canvas || trades.length < 3) return;
    const c = getChartColors();
    const labels = trades.map(t => formatDate(t.ts));
    const prices = trades.map(t => t.price);
    const volumes = trades.map(t => t.size || 0);
    createLineChart(canvas, labels, [
        { label: 'Price', data: prices, color: c.accent, fill: true, yAxisID: 'y' },
    ], {
        scales: {
            y: {
                position: 'left',
                ticks: { color: c.secondary, font: { size: 10 }, maxTicksLimit: 5 },
                grid: { color: c.grid },
                border: { display: false },
            },
            y1: {
                position: 'right',
                ticks: { display: false },
                grid: { display: false },
                border: { display: false },
            },
            x: {
                ticks: { color: c.secondary, font: { size: 10 }, maxTicksLimit: 5, maxRotation: 0 },
                grid: { display: false },
                border: { display: false },
            },
        },
    });

    if (volumes.some(v => v > 0)) {
        const barCanvas = document.createElement('canvas');
        barCanvas.style.cssText = 'width:100%;height:60px;margin-top:4px';
        canvas.parentElement.appendChild(barCanvas);
        createBarChart(barCanvas, labels, [
            { label: 'Volume', data: volumes, color: c.accent + '60' },
        ], {
            scales: {
                y: { display: false },
                x: { display: false },
            },
            plugins: { legend: { display: false }, tooltip: { enabled: false } },
        });
    }
}

function _renderPnlChart(container, results) {
    const canvas = container.querySelector('#detail-pnl-chart');
    if (!canvas || results.length === 0) return;
    const c = getChartColors();
    let cum = 0;
    const labels = results.map(r => formatDate(r.ts));
    const data = results.map(r => { cum += (r.profit || 0); return +cum.toFixed(4); });
    createLineChart(canvas, labels, [
        { label: 'Cumulative P&L', data, color: cum >= 0 ? c.positive : c.negative, fill: true },
    ]);
}

function _tradingStatsHtml(trades, volume, profit) {
    if (trades.length === 0) return '<div class="text-secondary" style="font-size:13px">No trade data</div>';
    const buys = trades.filter(t => t.side === 'buy').length;
    const sells = trades.filter(t => t.side === 'sell').length;
    const prices = trades.map(t => t.price).filter(p => p > 0);
    const minP = prices.length ? Math.min(...prices) : 0;
    const maxP = prices.length ? Math.max(...prices) : 0;
    return `
        <table class="data-table">
            <tr><td>Total trades</td><td class="text-right">${formatNumber(trades.length)}</td></tr>
            <tr><td>Buy / Sell</td><td class="text-right">${buys} / ${sells}</td></tr>
            <tr><td>Volume</td><td class="text-right">${formatNumber(volume)}</td></tr>
            <tr><td>Price range</td><td class="text-right">${formatPrice(minP)} – ${formatPrice(maxP)}</td></tr>
            <tr><td>P&L</td><td class="text-right ${profit >= 0 ? 'text-positive' : 'text-negative'}">${formatPnl(profit)}</td></tr>
        </table>`;
}

function _techHtml(featureMap) {
    const keys = Object.keys(featureMap);
    if (keys.length === 0) return '<div class="text-secondary" style="font-size:13px">No feature data</div>';
    const order = ['rsi', 'macd', 'ma_7', 'ma_30', 'volatility', 'spread', 'volume_ma'];
    const sorted = keys.sort((a, b) => {
        const ia = order.findIndex(o => a.toLowerCase().includes(o));
        const ib = order.findIndex(o => b.toLowerCase().includes(o));
        return (ia === -1 ? 99 : ia) - (ib === -1 ? 99 : ib);
    });
    return `
        <table class="data-table">
            ${sorted.map(k => `<tr><td>${_esc(k)}</td><td class="text-right font-mono">${featureMap[k].feature_value.toFixed(4)}</td></tr>`).join('')}
        </table>`;
}

function _signalHistoryHtml(signals) {
    if (signals.length === 0) return '<div class="text-secondary" style="font-size:13px">No signals yet</div>';
    const recent = signals.slice(-10);
    return `
        <table class="data-table">
            <thead><tr><th>Time</th><th>Prediction</th><th>Signal</th></tr></thead>
            <tbody>
                ${recent.map(s => `
                    <tr>
                        <td>${formatDate(s.ts)}</td>
                        <td class="font-mono">${s.prediction.toFixed(3)}</td>
                        <td>${signalBadge(s.signal_label)}</td>
                    </tr>`).join('')}
            </tbody>
        </table>`;
}

function _collapsible(id, title, bodyHtml) {
    return `
        <div class="collapsible" data-collapsible="${id}">
            <div class="collapsible-header">
                <span>${title}</span>
                <span class="collapsible-arrow">▼</span>
            </div>
            <div class="collapsible-body">${bodyHtml}</div>
        </div>`;
}

function _initCollapsibles(container) {
    container.querySelectorAll('.collapsible-header').forEach(hdr => {
        hdr.addEventListener('click', () => {
            hdr.parentElement.classList.toggle('open');
        });
    });
}

function _esc(s) {
    if (!s) return '';
    const d = document.createElement('div');
    d.textContent = s;
    return d.innerHTML;
}
