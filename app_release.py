"""Release contract shared by the launcher and the local HTTP server."""
APP_VERSION = '1.8.0'
FEATURES = ['interactive-chart', 'indicator-education', 'bot-history-replay', 'paper-perpetuals', 'strategy-source-import']
STATIC_PATHS = {
    '/': 'index.html', '/style.css': 'style.css', '/startup.js': 'startup.js',
    '/chart.js': 'chart.js', '/education.js': 'education.js', '/app.js': 'app.js',
    '/workspace.js': 'workspace.js', '/bot.js': 'bot.js',
}
