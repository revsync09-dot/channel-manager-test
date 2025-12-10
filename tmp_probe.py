from pathlib import Path
text = Path('src/bot.py').read_text(encoding='utf-8')
idx = text.index('plugin_fn = (')
print(text[idx:idx+1000])
