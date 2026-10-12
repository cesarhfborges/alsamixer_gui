#!/usr/bin/env bash
# Gera o binário (PyInstaller) e o pacote .deb do Alsamixer GUI.
# Uso: ./scripts/build_deb.sh        (a partir da raiz do projeto, com o .venv criado)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PY="${PYTHON:-$ROOT/.venv/bin/python}"
APP=alsamixer-gui
ARCH="$(dpkg --print-architecture)"

# 1) Versão a partir do git (setuptools-scm / vcs-versioning) -> src/_version.py
PEP440_VERSION="$("$PY" -c 'from setuptools_scm import get_version; print(get_version(local_scheme="no-local-version", write_to="src/_version.py"))')"
# Debian: "~" ordena antes da versão final (0.1.dev9 -> 0.1~dev9, 1.0rc1 -> 1.0~rc1)
DEB_VERSION="$(echo "$PEP440_VERSION" | sed -E 's/\.dev/~dev/; s/(a|b|rc)([0-9]+)/~\1\2/')"
echo ">> Versão: $PEP440_VERSION (deb: $DEB_VERSION)"

# 2) Binário com PyInstaller (modo pasta: inicia rápido, ideal para o autostart)
"$PY" -m PyInstaller --noconfirm --clean --onedir --name "$APP" \
    --workpath build/pyinstaller --specpath build --distpath build/dist \
    --add-data "$ROOT/src/assets:assets" \
    --collect-data customtkinter \
    --hidden-import pystray._xorg --collect-submodules Xlib \
    --hidden-import PIL._tkinter_finder \
    main.py

# 3) Estrutura do pacote
PKG="build/deb/${APP}_${DEB_VERSION}_${ARCH}"
rm -rf "$PKG"
install -d "$PKG/DEBIAN" "$PKG/opt" "$PKG/usr/bin" "$PKG/usr/share/applications" \
           "$PKG/usr/share/icons/hicolor/scalable/apps"
cp -a "build/dist/$APP" "$PKG/opt/$APP"
ln -s "/opt/$APP/$APP" "$PKG/usr/bin/$APP"
install -m 644 packaging/alsamixer-gui.desktop "$PKG/usr/share/applications/$APP.desktop"
install -m 644 packaging/alsamixer-gui.svg "$PKG/usr/share/icons/hicolor/scalable/apps/$APP.svg"
install -m 755 packaging/postinst packaging/postrm "$PKG/DEBIAN/"
SIZE_KB="$(du -sk --exclude=DEBIAN "$PKG" | cut -f1)"
sed -e "s/@VERSION@/$DEB_VERSION/" -e "s/@ARCH@/$ARCH/" -e "s/@SIZE@/$SIZE_KB/" \
    packaging/control.in > "$PKG/DEBIAN/control"

# 4) .deb (arquivos pertencentes ao root dentro do pacote)
mkdir -p dist
dpkg-deb --build --root-owner-group "$PKG" "dist/${APP}_${DEB_VERSION}_${ARCH}.deb"
echo ">> Pacote: dist/${APP}_${DEB_VERSION}_${ARCH}.deb"
