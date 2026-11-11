# Zotify App para Android

Interfaz sencilla para descargar música en masa desde el móvil.

## Instalación (una sola vez)

1. Instala **Termux** desde F-Droid (la versión de Play Store está desactualizada).
   Opcional: instala también **Termux:Widget** para tener un icono en la pantalla de inicio.
2. Abre Termux y pega:

   ```bash
   curl -sL https://raw.githubusercontent.com/WillG811/zotify/android-app/android/instalar.sh | bash
   ```

   Acepta el permiso de almacenamiento cuando Android lo pida.

## Uso

1. En Termux escribe `zotify-app` (o toca el widget **Zotify**). Se abre la app en el navegador.
2. Pega enlaces de Spotify (canciones, álbumes, playlists o artistas), uno por línea, y pulsa
   **Descargar enlaces**. O pulsa **Descargar mis canciones que me gustan**.
3. La primera vez aparece el botón **Iniciar sesión en Spotify**: inicia sesión y vuelve a la app.
   La sesión queda guardada.

La música se guarda en `Música/Zotify` del almacenamiento del teléfono. Las canciones ya
descargadas se saltan, así que puedes repetir una descarga interrumpida sin duplicar nada.

Deja Termux abierto mientras descarga (la app mantiene el móvil despierto con `termux-wake-lock`).
La opción **Tiempo real** descarga a velocidad de reproducción: más lento, pero reduce el riesgo
de que Spotify bloquee la cuenta.
