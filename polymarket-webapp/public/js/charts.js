import { getChartColors } from './theme.js';

const active = [];

export function destroyAllCharts() {
    active.forEach(c => c.destroy());
    active.length = 0;
}

function baseOpts(colors) {
    return {
        responsive: true,
        maintainAspectRatio: false,
        animation: { duration: 400 },
        plugins: {
            legend: { display: false },
            tooltip: {
                backgroundColor: colors.bg,
                titleColor: colors.text,
                bodyColor: colors.secondary,
                borderColor: colors.grid,
                borderWidth: 1,
                cornerRadius: 8,
                padding: 10,
                titleFont: { weight: '600' },
            },
        },
        scales: {
            x: {
                ticks: { color: colors.secondary, font: { size: 10 }, maxTicksLimit: 6, maxRotation: 0 },
                grid: { display: false },
                border: { display: false },
            },
            y: {
                ticks: { color: colors.secondary, font: { size: 10 }, maxTicksLimit: 5 },
                grid: { color: colors.grid },
                border: { display: false },
            },
        },
    };
}

export function createLineChart(canvas, labels, datasets, extraOpts = {}) {
    const c = getChartColors();
    const dsets = datasets.map(ds => ({
        borderColor: ds.color || c.accent,
        backgroundColor: (ds.color || c.accent) + '18',
        borderWidth: 2,
        pointRadius: 0,
        pointHitRadius: 8,
        tension: 0.3,
        fill: ds.fill !== false,
        ...ds,
    }));
    const chart = new Chart(canvas, {
        type: 'line',
        data: { labels, datasets: dsets },
        options: { ...baseOpts(c), ...extraOpts },
    });
    active.push(chart);
    return chart;
}

export function createBarChart(canvas, labels, datasets, extraOpts = {}) {
    const c = getChartColors();
    const dsets = datasets.map(ds => ({
        backgroundColor: ds.color || c.accent,
        borderRadius: 4,
        maxBarThickness: 32,
        ...ds,
    }));
    const chart = new Chart(canvas, {
        type: 'bar',
        data: { labels, datasets: dsets },
        options: { ...baseOpts(c), ...extraOpts },
    });
    active.push(chart);
    return chart;
}

export function createDoughnutChart(canvas, labels, data, colors) {
    const c = getChartColors();
    const chart = new Chart(canvas, {
        type: 'doughnut',
        data: {
            labels,
            datasets: [{ data, backgroundColor: colors || [c.positive, c.warning, c.negative], borderWidth: 0 }],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            cutout: '65%',
            animation: { duration: 400 },
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: { color: c.text, padding: 12, usePointStyle: true, pointStyleWidth: 8, font: { size: 12 } },
                },
                tooltip: {
                    backgroundColor: c.bg,
                    titleColor: c.text,
                    bodyColor: c.secondary,
                    borderColor: c.grid,
                    borderWidth: 1,
                    cornerRadius: 8,
                },
            },
        },
    });
    active.push(chart);
    return chart;
}
