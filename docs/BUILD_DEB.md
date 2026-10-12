# Como gerar o pacote .deb

Este guia gera o binário do Alsamixer GUI (PyInstaller) e o pacote instalável
`.deb` para Linux Mint / Ubuntu / Debian.

## 1. Pré-requisitos (uma vez)

```bash
sudo apt install python3-venv python3-tk dpkg-dev git
```

Na raiz do projeto, crie o ambiente virtual e instale as dependências do app e do build:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-build.txt     # pyinstaller, setuptools-scm, vcs-versioning
```

## 2. Versão (tags do git)

A versão vem do git via **setuptools-scm / vcs-versioning** (configurado no `pyproject.toml`).

| Situação | Versão do app | Arquivo gerado |
|---|---|---|
| Commit com tag `v1.2.0` | `1.2.0` | `alsamixer-gui_1.2.0_amd64.deb` |
| 3 commits após a tag `v1.2.0` | `1.2.1.dev3` | `alsamixer-gui_1.2.1~dev3_amd64.deb` |
| Sem nenhuma tag | `0.1.devN` | `alsamixer-gui_0.1~devN_amd64.deb` |

Padrão do nome: `nome_versão_arquitetura.deb`. O hash do commit e a data não entram
na versão (`local_scheme = "no-local-version"` no `pyproject.toml`).

Para publicar uma versão:

```bash
git add -A && git commit -m "Release 1.0.0"
git tag v1.0.0
```

Conferir a versão que será usada:

```bash
python -c "from setuptools_scm import get_version; print(get_version(local_scheme='no-local-version'))"
```

> O `~` no .deb faz versões de desenvolvimento (`1.0.0~dev3`) serem consideradas
> **anteriores** à versão final (`1.0.0`) pelo `apt`.

## 3. Gerar o .deb

```bash
./scripts/build_deb.sh
```

O script faz, em ordem:

1. **Versão:** `setuptools_scm.get_version(write_to="src/_version.py")` grava a versão embutida no binário.
2. **Binário:** `python -m PyInstaller --onedir ...` gera `build/dist/alsamixer-gui/`.
   - `--add-data src/assets:assets`: ícone (`audio-wave.svg`).
   - `--collect-data customtkinter`: temas e fontes do CustomTkinter.
   - `--hidden-import pystray._xorg --collect-submodules Xlib`: bandeja do sistema. O pystray escolhe o backend em tempo de execução, então o PyInstaller não o detecta sozinho.
   - `--onedir` (e não `--onefile`): inicia mais rápido, sem descompactar em `/tmp` a cada execução, o que é importante no início automático.
3. **Estrutura do pacote** em `build/deb/`:

   ```
   /opt/alsamixer-gui/                    binário + bibliotecas
   /usr/bin/alsamixer-gui                 link para o binário
   /usr/share/applications/alsamixer-gui.desktop     atalho no menu
   /usr/share/icons/hicolor/scalable/apps/alsamixer-gui.svg
   DEBIAN/control, postinst, postrm
   ```

4. **Pacote:** `dpkg-deb --build --root-owner-group build/deb/<pacote> dist/<pacote>.deb`.

Resultado: `dist/alsamixer-gui_<versão>_amd64.deb`.

Arquivos usados pelo build (em `packaging/`):

| Arquivo | Função |
|---|---|
| `control.in` | Metadados do pacote (versão, arquitetura e tamanho preenchidos pelo script) e dependências: `alsa-utils` (amixer), `x11-xserver-utils` (xrandr), `libglib2.0-bin` (gsettings) |
| `alsamixer-gui.desktop` | Atalho no menu do sistema |
| `alsamixer-gui.svg` | Ícone (cópia colorida de `src/assets/audio-wave.svg`) |
| `postinst` / `postrm` | Atualizam o cache de atalhos e ícones ao instalar/remover |

## 4. Conferir o pacote (opcional)

```bash
dpkg-deb -I dist/alsamixer-gui_*.deb      # metadados (versão, dependências)
dpkg-deb -c dist/alsamixer-gui_*.deb      # lista de arquivos
./build/dist/alsamixer-gui/alsamixer-gui  # roda o binário sem instalar
```

## 5. Instalar, atualizar e remover

```bash
sudo apt install ./dist/alsamixer-gui_*.deb   # instala (ou atualiza) e resolve dependências
alsamixer-gui                                  # ou: Menu → Som e vídeo → Alsamixer Control
sudo apt remove alsamixer-gui                  # remove
```

As configurações do usuário **não** são apagadas ao remover:
`~/.config/alsamixer-gui/` (settings.json, mixer-state.json).

## 6. Início automático com o sistema

O pacote **não** ativa o início automático: cada usuário decide em
**Configurações → Sistema → Iniciar com o sistema**. Isso grava
`~/.config/autostart/alsamixer-gui.desktop` com:

```ini
Exec=/usr/bin/alsamixer-gui --autostart
TryExec=/usr/bin/alsamixer-gui
X-GNOME-Autostart-Delay=5
```

- No login, o Cinnamon espera 5 s e abre o app só com o ícone na bandeja; o app reaplica o mudo salvo (ex.: S/PDIF) e continua vigiando.
- A entrada aparece em **Menu → Aplicativos de inicialização**. Se for desligada por lá, o app respeita a escolha.
- Se o app for desinstalado, o `TryExec` faz o Cinnamon ignorar a entrada.

Outros parâmetros do binário:

```bash
alsamixer-gui --autostart     # inicia escondido na bandeja (usado pelo início automático)
alsamixer-gui --apply-state   # só reaplica os estados de mudo salvos, sem interface, e encerra
```

## 7. Limpar os artefatos de build

```bash
rm -rf build/ dist/ src/_version.py
```
