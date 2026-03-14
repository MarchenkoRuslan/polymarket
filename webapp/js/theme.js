export function applyTheme() {
    const tg = window.Telegram?.WebApp;
    const root = document.documentElement;

    const scheme = tg?.colorScheme || (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
    root.setAttribute('data-theme', scheme);

    const tp = tg?.themeParams || {};
    const map = {
        '--bg-primary':   tp.bg_color,
        '--bg-secondary': tp.secondary_bg_color,
        '--text-primary': tp.text_color,
        '--text-secondary': tp.hint_color,
        '--accent':       tp.button_color || tp.link_color,
        '--accent-text':  tp.button_text_color,
    };
    Object.entries(map).forEach(([prop, val]) => {
        if (val) root.style.setProperty(prop, val);
    });

    if (tp.bg_color && !tp.secondary_bg_color) {
        root.style.setProperty('--bg-secondary', adjustBrightness(tp.bg_color, scheme === 'dark' ? 12 : -5));
    }
    if (tp.bg_color) {
        root.style.setProperty('--bg-tertiary', adjustBrightness(tp.bg_color, scheme === 'dark' ? 24 : -10));
    }
}

function adjustBrightness(hex, amount) {
    hex = hex.replace('#', '');
    if (hex.length === 3) hex = hex.split('').map(c => c + c).join('');
    const num = parseInt(hex, 16);
    const r = Math.max(0, Math.min(255, ((num >> 16) & 0xff) + amount));
    const g = Math.max(0, Math.min(255, ((num >> 8) & 0xff) + amount));
    const b = Math.max(0, Math.min(255, (num & 0xff) + amount));
    return `#${((r << 16) | (g << 8) | b).toString(16).padStart(6, '0')}`;
}

export function getChartColors() {
    const cs = getComputedStyle(document.documentElement);
    return {
        text:      cs.getPropertyValue('--text-primary').trim(),
        secondary: cs.getPropertyValue('--text-secondary').trim(),
        grid:      cs.getPropertyValue('--border').trim(),
        accent:    cs.getPropertyValue('--accent').trim(),
        positive:  cs.getPropertyValue('--positive').trim(),
        negative:  cs.getPropertyValue('--negative').trim(),
        warning:   cs.getPropertyValue('--warning').trim(),
        bg:        cs.getPropertyValue('--bg-secondary').trim(),
    };
}
