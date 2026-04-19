# Maintainer: Bernardo Kuri <bkuri@bkuri.com>
# Contributor: Your Name <your@email.com>

pkgname=python-village
pkgver=2.1.0
pkgrel=1
pkgdesc="CLI-native parallel development orchestrator"
url="https://github.com/bkuri/village"
license=("MIT")
arch=("any")
depends=("python" "python-hatchling")
makedepends=("python-build" "python-installer" "python-wheel" "python-hatch-vcs" "git")
checkdepends=("git")
source=("${pkgname}-${pkgver}.tar.gz")

prepare() {
    cd "$srcdir/$_name-$pkgver"
    git describe --tags || true
}

build() {
    cd "$srcdir/$_name-$pkgver"
    export SETUPTOOLS_SCM_PRETEND_VERSION=$pkgver
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
