# Installation

## Via pip/uv

```bash
pip install village
# or
uv pip install village
# or
uvx village
```

## Via Arch Linux AUR

```bash
# Install from AUR (after PKGBUILD is uploaded)
paru -S python-village

# Or build manually
makepkg -f PKGBUILD
sudo pacman -U python-village-*.pkg.tar.zst
```

## Via system package manager

On Arch Linux: `pacman -S python-village`

## Verify Installation

```bash
village --help
village --version
```

**Output should show help and version.**
