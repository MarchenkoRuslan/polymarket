import { api } from '../api.js';
import { formatPrice, signalBadge, truncate, showLoading, showEmpty, showError } from '../utils.js';
import { createBarChart, createDoughnutChart } from '../charts.js';
import { getChartColors } from '../theme.js';
import { navigate } from '../router.js';

export async function render(container) {
    showLoading(container);

    try {
        const [analytics, signalsData] = await Promise.all([
            api.getAnalytics(),
            api.getSignals(undefined, 500),
        ]);

        const signals = signalsData.items || [];
        if (signals.length === 0) {
            showEmpty(container, '📡', 'No Signals Yet', 'ML signals will appear after model training');
            return;
        }

        const latestByMarket = {};
        signals.forEach(s => {
            if (!latestByMarket[s.market_id] || s.ts > latestByMarket[s.market_id].ts) {
                latestByMarket[s.market_id] = s;
            }
        });

        const marketSignals = Object.values(latestByMarket);
        const buyCount = marketSignals.filter(s => s.signal_label === 'buy').length;
        const sellCount = marketSignals.filter(s => s.signal_label === 'sell').length;
        const holdCount = marketSignals.filter(s => s.signal_label === 'hold').length;

        const sortedMarkets = marketSignals.sort((a, b) => b.prediction - a.prediction);

        const distribution = analytics.signal_distribution || [];

        container.innerHTML = `
            <div class="screen">
                <div class="screen-title">Signals</div>
                <div class="screen-subtitle">ML predictions across markets</div>

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

                <div class="chart-card">
                    <div class="chart-card-title">Signal by Market</div>
                    <div class="chart-container tall"><canvas id="signals-bar"></canvas></div>
                </div>

                ${distribution.length > 0 ? `
                <div class="chart-card">
                    <div class="chart-card-title">Distribution</div>
                    <div class="chart-container"><canvas id="signals-dist"></canvas></div>
                </div>` : ''}

                <div class="section-header">
                    <span class="section-title">All Signals</span>
                </div>
                <div id="signals-list"></div>
            </div>`;

        const c = getChartColors();

        if (sortedMarkets.length > 0) {
            const labels = sortedMarkets.map(s => truncate(s.market_id, 16));
            const data = sortedMarkets.map(s => s.prediction);
            const colors = sortedMarkets.map(s =>
                s.signal_label === 'buy' ? c.positive : s.signal_label === 'sell' ? c.negative : c.warning
            );
            const canvas = container.querySelector('#signals-bar');
            if (canvas) {
                createBarChart(canvas, labels, [{ label: 'Prediction', data, backgroundColor: colors }], {
                    indexAxis: 'y',
                    scales: {
                        x: {
                            min: 0, max: 1,
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

        if (distribution.length > 0) {
            const canvas = container.querySelector('#signals-dist');
            if (canvas) {
                const distLabels = distribution.map(d => d.bucket.toFixed(1));
                const distData = distribution.map(d => d.count);
                const distColors = distribution.map(d =>
                    d.bucket >= 0.55 ? c.positive : d.bucket < 0.35 ? c.negative : c.warning
                );
                createBarChart(canvas, distLabels, [{ label: 'Count', data: distData, backgroundColor: distColors }]);
            }
        }

        const listEl = container.querySelector('#signals-list');
        sortedMarkets.forEach(s => {
            const card = document.createElement('div');
            card.className = 'market-card';
            card.innerHTML = `
                <div class="market-card-body">
                    <div class="market-card-question">${_esc(truncate(s.market_id, 50))}</div>
                    <div class="market-card-meta">
                        <span class="font-mono">${s.prediction.toFixed(3)}</span>
                    </div>
                </div>
                <div class="market-card-right">
                    ${signalBadge(s.signal_label)}
                </div>`;
            card.addEventListener('click', () => navigate(`market/${encodeURIComponent(s.market_id)}`));
            listEl.appendChild(card);
        });
    } catch (err) {
        showError(container, err.message);
    }
}

function _esc(s) {
    if (!s) return '';
    const d = document.createElement('div');
    d.textContent = s;
    return d.innerHTML;
}
