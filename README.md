# GTA 6 fan guide

I have built an unofficial new player fan guide as a static site.

It is not affiliated with Rockstar Games or Take-Two.

## Rebuild

```bash
python3 build/build.py
python3 build/test_site.py
```

The base URL defaults to https://e13ctr0n1c.github.io/gta6-guide/

```bash
python3 build/build.py --base-url https://example.com/gta6-guide/
```

Internal links stay relative, and they point at `index.html`, so the same files open on GitHub Pages and on raw.githack.

## Facts

Game facts come from `data/facts.json`. I do not add a figure that is not in that file. If the sources disagree, or if a number was never published, the page says so.

GitHub Pages is not enabled. This is a preview.
