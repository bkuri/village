# Maintainer: Bernardo Kuri <bkuri@bkuri.com>
# Contributor: Your Name <your@email.com>

pkgname=python-village
pkgver=1.0.0
pkgrel=1
pkgdesc="CLI-native parallel development orchestrator"
url="https://github.com/bkuri/village"
license=("MIT")  # Check actual license in pyproject.toml
arch=("any")  # Pure Python package, architecture-independent
depends=("python" "python-hatchling")
makedepends=("python-build" "python-installer" "python-wheel")
source=("https://files.pythonhosted.org/packages/source/${pkgname}/${pkgname//-/_}/${pkgver}.tar.gz")

build() {
    cd "$srcdir/$_name-$pkgver"
    python -m build --wheel --no-isolation
}

package() {
    cd "$srcdir/$_name-$pkgver"
    python -m installer --destdir="$pkgdir" dist/*.whl
}

check() {
    cd "$srcdir/$_name-$pkgver"
    pytest
}
