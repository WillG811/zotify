#! /usr/bin/env python3

"""
Zotify App
Interfaz web minima para usar Zotify desde el movil (Termux en Android).
Abre http://127.0.0.1:8080 en el navegador del telefono.
"""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HOST = '127.0.0.1'
PORT = 8080
MAX_LINES = 2000

SHARED_MUSIC = Path.home() / 'storage/shared/Music'
ROOT_PATH = (SHARED_MUSIC if SHARED_MUSIC.exists() else Path.home() / 'Music') / 'Zotify'
CREDENTIALS = Path.home() / '.local/share/zotify/credentials.json'

ANSI = re.compile(r'\x1b\[[0-9;?]*[A-Za-z]')
OAUTH = re.compile(r'OAUTH_URL (\S+)')


class Job:
    lock = threading.Lock()
    proc = None
    lines = []
    oauth_url = None

    @classmethod
    def running(cls):
        return cls.proc is not None and cls.proc.poll() is None

    @classmethod
    def log(cls, line):
        line = ANSI.sub('', line).strip()
        if not line or line.startswith('Open the link above'):
            return
        match = OAUTH.search(line)
        if match:
            cls.oauth_url = match.group(1)
            open_url(cls.oauth_url)
            line = 'Inicia sesion en Spotify con el boton de arriba.'
        with cls.lock:
            cls.lines.append(line)
            del cls.lines[:-MAX_LINES]

    @classmethod
    def start(cls, mode, urls, fmt, real_time):
        if cls.running():
            return 'Ya hay una descarga en curso.'

        cmd = [sys.executable, '-m', 'zotify',
               '--root-path', str(ROOT_PATH),
               '--download-format', fmt,
               '--download-real-time', str(real_time),
               '--skip-previously-downloaded', 'True',
               '--print-downloads', 'True',
               '--print-download-progress', 'False',
               '--print-splash', 'False']
        if mode == 'liked':
            cmd.append('-l')
        else:
            urls = [u for u in re.split(r'\s+', urls) if u.startswith('http')]
            if not urls:
                return 'Pega al menos un enlace de Spotify.'
            with tempfile.NamedTemporaryFile('w', suffix='.txt', delete=False, encoding='utf-8') as f:
                f.write('\n'.join(urls))
            cmd += ['-d', f.name]

        cls.lines = [f'Guardando en {ROOT_PATH}']
        cls.oauth_url = None
        env = dict(os.environ, PYTHONUNBUFFERED='1', PYTHONIOENCODING='utf-8')
        cls.proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT, env=env)
        threading.Thread(target=cls.read_output, args=(cls.proc,), daemon=True).start()
        return None

    @classmethod
    def read_output(cls, proc):
        wake_lock(True)
        buffer = ''
        while True:
            chunk = proc.stdout.read1(4096).decode('utf-8', 'replace')
            if not chunk:
                break
            buffer += chunk
            *done, buffer = re.split(r'[\r\n]', buffer)
            for line in done:
                cls.log(line)
        cls.log(buffer)
        proc.wait()
        cls.log('Terminado.' if proc.returncode == 0 else f'Se detuvo (codigo {proc.returncode}).')
        cls.oauth_url = None
        wake_lock(False)

    @classmethod
    def stop(cls):
        if cls.running():
            cls.proc.terminate()


def open_url(url):
    if shutil.which('termux-open-url'):
        subprocess.Popen(['termux-open-url', url])


def wake_lock(on):
    tool = 'termux-wake-lock' if on else 'termux-wake-unlock'
    if shutil.which(tool):
        subprocess.Popen([tool])


PAGE = '''<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Zotify</title>
<style>
  :root { color-scheme: dark; }
  body { margin: 0; padding: 16px; background: #121212; color: #eee; font: 16px system-ui, sans-serif; }
  h1 { color: #1db954; margin: 0 0 16px; }
  textarea { width: 100%; box-sizing: border-box; height: 140px; background: #222; color: #eee;
             border: 1px solid #333; border-radius: 8px; padding: 10px; font-size: 14px; }
  button, .btn { display: block; width: 100%; padding: 14px; margin: 10px 0; border: 0; border-radius: 24px;
                 font-size: 16px; font-weight: bold; background: #1db954; color: #000; text-align: center;
                 text-decoration: none; box-sizing: border-box; }
  button.alt { background: #333; color: #eee; }
  button:disabled { opacity: .4; }
  .row { display: flex; gap: 12px; align-items: center; margin: 8px 0; flex-wrap: wrap; }
  select { background: #222; color: #eee; border: 1px solid #333; border-radius: 6px; padding: 6px; }
  #login { display: none; background: #fff; }
  #log { background: #000; border-radius: 8px; padding: 10px; height: 45vh; overflow-y: auto;
         font: 12px monospace; white-space: pre-wrap; word-break: break-word; }
  .muted { color: #888; font-size: 13px; }
</style></head><body>
<h1>Zotify</h1>
<a id="login" class="btn" target="_blank">Iniciar sesion en Spotify</a>
<textarea id="urls" placeholder="Pega enlaces de Spotify (canciones, albumes, playlists, artistas), uno por linea"></textarea>
<div class="row">
  <label>Formato <select id="fmt"><option value="ogg">ogg (mejor calidad)</option><option>mp3</option><option>m4a</option></select></label>
  <label><input type="checkbox" id="rt" checked> Tiempo real (menos riesgo de ban)</label>
</div>
<button id="go" onclick="start('urls')">Descargar enlaces</button>
<button id="liked" class="alt" onclick="start('liked')">Descargar mis canciones que me gustan</button>
<button id="stop" class="alt" onclick="post('/api/stop')">Detener</button>
<div id="log"></div>
<p class="muted">Musica en: ROOT_PATH</p>
<button class="alt" onclick="if(confirm('Cerrar sesion de Spotify?')) post('/api/logout')">Cerrar sesion</button>
<script>
async function post(url, body) {
  const r = await fetch(url, {method: 'POST', body: JSON.stringify(body || {})});
  const j = await r.json();
  if (j.error) alert(j.error);
  poll();
}
function start(mode) {
  post('/api/start', {mode, urls: document.getElementById('urls').value,
    fmt: document.getElementById('fmt').value, real_time: document.getElementById('rt').checked});
}
async function poll() {
  const s = await (await fetch('/api/status')).json();
  const log = document.getElementById('log');
  const atBottom = log.scrollTop + log.clientHeight >= log.scrollHeight - 20;
  log.textContent = s.lines.join('\\n');
  if (atBottom) log.scrollTop = log.scrollHeight;
  const login = document.getElementById('login');
  login.style.display = s.oauth_url ? 'block' : 'none';
  if (s.oauth_url) login.href = s.oauth_url;
  document.getElementById('go').disabled = s.running;
  document.getElementById('liked').disabled = s.running;
  document.getElementById('stop').disabled = !s.running;
}
poll(); setInterval(poll, 1500);
</script></body></html>'''


class Handler(BaseHTTPRequestHandler):
    def send(self, code, body, kind='application/json'):
        data = body.encode('utf-8') if isinstance(body, str) else json.dumps(body).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', kind + '; charset=utf-8')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == '/':
            self.send(200, PAGE.replace('ROOT_PATH', str(ROOT_PATH)), 'text/html')
        elif self.path == '/api/status':
            with Job.lock:
                lines = list(Job.lines)
            self.send(200, {'running': Job.running(), 'lines': lines, 'oauth_url': Job.oauth_url})
        else:
            self.send(404, {'error': 'No encontrado'})

    def do_POST(self):
        length = int(self.headers.get('Content-Length', 0))
        try:
            body = json.loads(self.rfile.read(length) or b'{}')
        except json.JSONDecodeError:
            body = {}
        error = None
        if self.path == '/api/start':
            fmt = body.get('fmt') if body.get('fmt') in ('mp3', 'ogg', 'm4a') else 'ogg'
            error = Job.start(body.get('mode'), body.get('urls', ''), fmt, bool(body.get('real_time')))
        elif self.path == '/api/stop':
            Job.stop()
        elif self.path == '/api/logout':
            if Job.running():
                error = 'Deten la descarga primero.'
            else:
                CREDENTIALS.unlink(missing_ok=True)
                Job.lines = ['Sesion cerrada.']
        else:
            return self.send(404, {'error': 'No encontrado'})
        self.send(200, {'error': error})

    def log_message(self, format, *args):
        return


def main():
    ROOT_PATH.mkdir(parents=True, exist_ok=True)
    url = f'http://{HOST}:{PORT}'
    try:
        server = ThreadingHTTPServer((HOST, PORT), Handler)
    except OSError:
        # Ya esta abierta: solo mostrarla
        open_url(url)
        return
    print(f'Zotify App en {url}  (Ctrl+C para salir)')
    open_url(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        Job.stop()


if __name__ == '__main__':
    main()
