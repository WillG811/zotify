#!/data/data/com.termux/files/usr/bin/bash
# Instala Zotify App en Termux (Android).
# Uso: curl -sL https://raw.githubusercontent.com/WillG811/zotify/android-app/android/instalar.sh | bash
set -e

REPO="https://github.com/WillG811/zotify"
BRANCH="android-app"

echo "== Permiso de almacenamiento (acepta el aviso de Android) =="
termux-setup-storage || true
sleep 3

echo "== Paquetes de Termux =="
pkg update -y
yes | pkg upgrade -y -o Dpkg::Options::="--force-confnew"
pkg install -y python ffmpeg git python-pillow clang

echo "== Zotify =="
pip install --upgrade "git+$REPO@$BRANCH"

echo "== App =="
APP_DIR="$HOME/.zotify-app"
mkdir -p "$APP_DIR"
curl -sL "https://raw.githubusercontent.com/WillG811/zotify/$BRANCH/android/zotify_app.py" -o "$APP_DIR/zotify_app.py"

# Comando 'zotify-app' en Termux
cat > "$PREFIX/bin/zotify-app" <<EOF
#!/data/data/com.termux/files/usr/bin/bash
export PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python
exec python "$APP_DIR/zotify_app.py"
EOF
chmod +x "$PREFIX/bin/zotify-app"

# Icono en la pantalla de inicio (requiere la app Termux:Widget)
mkdir -p "$HOME/.shortcuts"
cat > "$HOME/.shortcuts/Zotify" <<EOF
#!/data/data/com.termux/files/usr/bin/bash
zotify-app
EOF
chmod +x "$HOME/.shortcuts/Zotify"

echo
echo "Listo. Escribe:  zotify-app"
echo "o anade el widget de Termux:Widget y toca 'Zotify'."
