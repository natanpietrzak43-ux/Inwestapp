"""Registered instruments, not an assertion that a venue lists every pair."""
CRYPTO = {
    'XRP': ('XRP', 1.8, '×'), 'XLM': ('Stellar', .24, 'S'),
    'BTC': ('Bitcoin', 65000, '₿'), 'ETH': ('Ethereum', 2500, 'Ξ'),
    'SOL': ('Solana', 150, '◎'), 'DOGE': ('Dogecoin', .15, 'Ð'),
    'ADA': ('Cardano', .4, 'A'), 'LINK': ('Chainlink', 15, 'L'),
    'AVAX': ('Avalanche', 25, 'A'), 'DOT': ('Polkadot', 4, '●'),
    'LTC': ('Litecoin', 80, 'Ł'), 'BCH': ('Bitcoin Cash', 350, 'B'),
    'UNI': ('Uniswap', 7, 'U'), 'ATOM': ('Cosmos', 5, '⚛'),
    'NEAR': ('NEAR Protocol', 4, 'N'), 'SUI': ('Sui', 2, 'S'),
}
INSTRUMENTS = {
    key: {'name': name, 'symbol': key + '-USD', 'kind': 'crypto',
          'description': key + ' / USD · rynek spot', 'demoPrice': price, 'icon': icon}
    for key, (name, price, icon) in CRYPTO.items()
}
INSTRUMENTS.update({
    'SILVER': {'name': 'Srebro', 'symbol': 'SI=F', 'kind': 'commodity', 'description': 'Silver futures · cena referencyjna', 'demoPrice': 30, 'icon': 'Ag'},
    'OIL': {'name': 'Ropa WTI', 'symbol': 'CL=F', 'kind': 'commodity', 'description': 'WTI futures · cena referencyjna', 'demoPrice': 68, 'icon': '◈'},
    'GOLD': {'name': 'Złoto', 'symbol': 'GC=F', 'kind': 'commodity', 'description': 'Gold futures · cena referencyjna', 'demoPrice': 2500, 'icon': 'Au'},
})
