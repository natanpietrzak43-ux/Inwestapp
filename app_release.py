"""Release contract shared by the launcher and the local HTTP server."""
APP_VERSION = '2.2.0'
FEATURES = ['interactive-chart', 'indicator-education', 'bot-history-replay', 'paper-perpetuals', 'strategy-source-import', 'shared-execution-engine', 'okx-demo-executor', 'strategy-approvals', 'runtime-supervisor', 'local-api-security', 'release-integrity', 'expanded-crypto-catalog']
STATIC_PATHS = {
    '/': 'index.html', '/style.css': 'style.css', '/startup.js': 'startup.js',
    '/chart.js': 'chart.js', '/education.js': 'education.js', '/app.js': 'app.js',
    '/workspace.js': 'workspace.js', '/bot.js': 'bot.js', '/automation.js': 'automation.js',
    '/security.js': 'security.js', '/instruments.js': 'instruments.js',
    '/coingecko.js': 'coingecko.js',
}
FEATURES += ['coingecko-market-context']
