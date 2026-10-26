# FichaManual — Android (MVP)

La versión de escritorio (Windows) es la entrega principal de hoy.
La app Android es un **MVP aparte**: misma idea (pegar texto → resumir → ver ficha), motor local simplificado.

## Estado actual

| Entregable | Estado |
|------------|--------|
| Código fuente en `android/` | Listo (scaffold + UI + resumen local) |
| APK instalable | **No generada en este PC** (falta JDK + Android SDK) |
| Envío al cliente | Cuando exista la APK, **aparte** del ZIP de Windows |

## Qué hace el MVP

- Pegar texto largo
- Pulsar **Crear ficha**
- Ver una ficha genérica breve (título, resumen, ideas clave, etc.)
- Copiar la ficha al portapapeles
- Funciona **offline** (sin servidor ni API)

No incluye aún: PDF, modo producto/electrodoméstico completo, ni API OpenAI.

## Cómo generar la APK (en un PC con Android Studio)

1. Instala [Android Studio](https://developer.android.com/studio) (incluye JDK y SDK).
2. Abre la carpeta `android/` como proyecto.
3. Espera a que Gradle sincronice.
4. Menú **Build → Build Bundle(s) / APK(s) → Build APK(s)**.
5. La APK debug quedará en:

   `android/app/build/outputs/apk/debug/app-debug.apk`

### Por línea de comandos (si ya tienes SDK/JDK)

Desde la carpeta `android/`:

```bat
gradlew.bat assembleDebug
```

O con el script del repo (desde la raíz):

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build_android_apk.ps1
```

## Cómo instalar la APK en el móvil del cliente

1. Copia `app-debug.apk` al teléfono (correo, Drive, USB, etc.).
2. En Android: **Ajustes → Seguridad** (o Aplicaciones) → permitir **instalar apps de orígenes desconocidos** para el explorador/archivo que uses.
3. Abre el archivo APK e instala.
4. Abre **FichaManual**, pega texto y pulsa **Crear ficha**.

> Nota: es una APK **debug** (prueba interna). Para Play Store haría falta firma release y más pulido.

## Relación con Windows

| | Windows | Android MVP |
|--|---------|-------------|
| Enviar hoy | `release\FichaManual-Setup.zip` | — |
| Motor | Completo (genérico + producto + API opcional) | Genérico local simplificado |
| Instrucciones cliente | `PARA_EL_CLIENTE.md` | Este archivo + APK aparte |
