# FichaManual

**FichaManual** es una aplicación de escritorio para Windows que toma un manual largo (texto o PDF), lo resume y deja los datos importantes ordenados en una ficha clara.

Ideal para manuales de electrodomésticos u otros documentos técnicos: pegas el texto o abres el archivo y obtienes secciones como identificación, conexión, programas, uso, mantenimiento, averías y advertencias.

Repositorio: https://github.com/Juanki58/FichaManual

---

## Descargar

| Enlace | Uso |
|--------|-----|
| **[Página de descarga](https://juanki58.github.io/FichaManual/)** | Ideal para enviar al cliente |
| **[ZIP Windows (directo)](https://github.com/Juanki58/FichaManual/releases/latest/download/FichaManual-Setup.zip)** | Descarga estable del último Release |
| **[Releases en GitHub](https://github.com/Juanki58/FichaManual/releases)** | Historial de versiones |

**Android:** aún no hay APK publicada; solo Windows por ahora. Detalle: **[ANDROID.md](ANDROID.md)**.

### Activar GitHub Pages (si la web aún no carga)

1. En el repo: **Settings → Pages**.
2. **Source:** Deploy from a branch.
3. Branch: `master` (o `main`), carpeta `/docs` → **Save**.
4. En 1–2 minutos estará en: https://juanki58.github.io/FichaManual/

La página vive en `docs/index.html`.

---

## Para usuarios finales (sin Python)

Instrucciones ultra simples: ver **[PARA_EL_CLIENTE.md](PARA_EL_CLIENTE.md)**.

1. Descarga `FichaManual-Setup.zip` (enlace de arriba) o recibe el ZIP.
2. Descomprímelo.
3. Ejecuta **`FichaManual-Setup.bat`**.
4. La app se instala en `%LOCALAPPDATA%\FichaManual`, crea un acceso directo en el **Escritorio** y en el **Menú Inicio**.
5. Abre **FichaManual** desde el acceso directo → pega texto → **Crear ficha**.

Requisitos: Windows 10/11. No hace falta Python.

Para desinstalar: Menú Inicio → FichaManual → Desinstalar FichaManual.

> Instalador PowerShell/BAT (sin Inno Setup). No requiere permisos de administrador.

### Android

La app móvil es un MVP aparte (carpeta `android/`). No va en el ZIP de Windows.  
Detalle: **[ANDROID.md](ANDROID.md)**.

---

## Qué hace la app

- Pegar texto o abrir `.txt` / `.pdf`
- Generar una **ficha ordenada** con estas secciones:
  - Identificación
  - Conexión
  - Programas
  - Uso diario
  - Mantenimiento
  - Averías
  - Advertencias
- Corrección básica del texto de salida
- Copiar o guardar la ficha

### Motor de resumen

| Modo | Cuándo | Calidad |
|------|--------|---------|
| **API OpenAI** | Si existe la variable de entorno `OPENAI_API_KEY` y marcas «Usar API» | Mejor, entiende manuales desordenados |
| **Local (heurístico)** | Sin clave o si la API falla | Funciona offline; ordena por palabras clave |

Opcional:

```bat
setx OPENAI_API_KEY "sk-..."
setx FICHAMANUAL_MODEL "gpt-4o-mini"
```

Cierra y vuelve a abrir la app tras usar `setx`.

---

## Desarrollo (con Python)

Requisitos: Windows, Python 3.10+.

```bat
cd C:\Users\juanc\projects\FichaManual
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python scripts\generate_icon.py
python main.py
```

También puedes usar `run.bat`.

Estructura:

```
FichaManual/
  main.py
  run.bat
  requirements.txt
  FichaManual.spec
  PARA_EL_CLIENTE.md      # instrucciones simples para el cliente
  ANDROID.md              # estado y build de la app Android
  assets/                 # icono .ico / .png
  src/fichamanual/        # extractor, summarizer, corrector, gui
  android/                # MVP Android (Kotlin)
  scripts/                # icono, build exe, build instalador, APK
  installer/              # Setup.bat + Install/Uninstall.ps1
  examples/               # manual de ejemplo
```

---

## Generar el .exe y el instalador

Desde PowerShell en la raíz del proyecto:

```powershell
# Solo el ejecutable
powershell -ExecutionPolicy Bypass -File .\scripts\build_exe.ps1

# Ejecutable + carpeta/ZIP listos para enviar
powershell -ExecutionPolicy Bypass -File .\scripts\build_installer.ps1
```

Resultado:

- `dist\FichaManual\FichaManual.exe` — app empaquetada (PyInstaller)
- `release\FichaManual-Setup\` — **lo que envías a otro usuario** (incluye `app\FichaManual.exe`)
- `release\FichaManual-Setup.zip` — mismo contenido comprimido
- `installer\app\` — copia local del payload (generada por el build; no hace falta enviarla)

En el PC destino: descomprimir el ZIP y ejecutar `FichaManual-Setup.bat`. El `.exe` debe estar en `app\` junto al Setup.

El instalador usa el icono `assets\fichamanual.ico` en el `.exe` y en los accesos directos.

### Inno Setup / NSIS (opcional)

Si más adelante instalas [Inno Setup](https://jrsoftware.org/isinfo.php), puedes envolver `dist\FichaManual\` en un `.exe` de setup clásico. El flujo actual con `FichaManual-Setup.bat` ya cubre instalación + accesos directos sin herramientas extra.

---

## Licencia

Uso libre para el proyecto personal/equipo. Ajusta la licencia si lo publicas de forma formal.
