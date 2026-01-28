# Maintainer: Bernardo Kuri <bkuri@bkuri.com>
# Contributor: Your Name <your@email.com>

pkgname=python-village
pkgver=1.0.0
pkgrel=1
pkgdesc="CLI-native parallel development orchestrator"
url="https://github.com/bkuri/village"
license=("MIT")
arch=("any")
depends=("python" "python-hatchling")
makedepends=("python-build" "python-installer" "python-wheel")
source=("${pkgname}-${pkgver}.tar.gz")

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
