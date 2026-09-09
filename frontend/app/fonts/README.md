# Local interface fonts

The layout uses the WOFF2 files instead of the larger source TTFs. The
original Inter glyphs, character coverage, metrics, and four weights are retained;
no subsetting or external font host is used. See `INTER-LICENSE.txt` for the license.

The four WOFF2 files total 443,892 bytes, versus 1,302,640 bytes for the TTF sources
(66% smaller assets). Gzip totals are 442,386 versus 645,953 bytes, a 31.5%
reduction when comparing compressed delivery. Keep the TTFs as conversion sources.

To regenerate, use FontTools with its WOFF extra in a temporary tooling environment:

```python
from pathlib import Path
from fontTools.ttLib import TTFont

for source in Path("frontend/app/fonts").glob("*.ttf"):
    font = TTFont(source)
    font.flavor = "woff2"
    font.save(source.with_suffix(".woff2"))
```

After conversion, compare `getBestCmap()`, `getGlyphOrder()`, and `hmtx.metrics`
between source and output, then run the frontend production build. FontTools is
build-maintenance tooling only and is not a runtime application dependency.
