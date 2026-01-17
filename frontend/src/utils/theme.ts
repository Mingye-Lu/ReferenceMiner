export type Theme = 'light' | 'dark' | 'system';

export function getStoredTheme(): Theme {
    return (localStorage.getItem('theme') as Theme) || 'system';
}

export function setTheme(theme: Theme) {
    localStorage.setItem('theme', theme);
    applyTheme(theme);
    // Dispatch a custom event so other components can react immediately
    window.dispatchEvent(new CustomEvent('themeChanged', { detail: theme }));
}

export function applyTheme(theme: Theme) {
    const html = document.documentElement;

    if (theme === 'dark') {
        html.setAttribute('data-theme', 'dark');
    } else if (theme === 'light') {
        html.setAttribute('data-theme', 'light');
    } else if (theme === 'system') {
        const systemDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
        html.setAttribute('data-theme', systemDark ? 'dark' : 'light');
    }
}

// Initialize theme on load
export function initTheme() {
    const theme = getStoredTheme();
    applyTheme(theme);

    // Listen for system preference changes
    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
        if (getStoredTheme() === 'system') {
            applyTheme('system');
        }
    });
}
