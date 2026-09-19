# Tienda didáctica

Una tienda en línea pequeña para aprender un stack completo: **React + FastAPI + SQLAlchemy + PostgreSQL**.
Se construye por *checkpoints*, en orden; cada uno termina con un commit y un tag de Git. El plan
completo (requisitos, decisiones y guion de clase) está en [`PLAN.md`](PLAN.md).

> El código, los comentarios, los mensajes de commit y los textos de pantalla están en inglés.
> El castellano queda solo para este README y para `PLAN.md`.

## Requisitos

- Docker (con Compose)
- Python 3.12 o superior (solo para la opción B)
- Node.js 20.19 o superior, o 22.12 o superior (solo para la opción B; lo exige Vite)

## Arranque

Copia la plantilla de variables de entorno (el `.env` real no se sube a Git):

```bash
cp .env.example .env
```

### Opción A · Todo con Docker

Un solo comando construye y levanta la base de datos, el backend (que aplica las migraciones al
arrancar) y el frontend:

```bash
docker compose up --build
```

| Servicio | Dirección |
|---|---|
| Frontend | `http://localhost:5173` |
| Backend | `http://localhost:8000` (documentación interactiva en `/docs`) |
| PostgreSQL | `localhost:5432` |

Para parar todo: `docker compose down`. El código va dentro de las imágenes: tras cambiarlo hay que
repetir `docker compose up --build`. Para trabajar con recarga en caliente, usa la opción B.

#### Dónde están los datos de la base de datos

Los ficheros de PostgreSQL están en [`data/postgres/`](data), una carpeta de tu propio disco montada en
el contenedor (*bind mount*). Se puede abrir con el Explorador y no se sube a Git. Un volumen con
nombre estaría escondido dentro de la máquina virtual de Docker.

Consecuencia importante: **`docker compose down -v` ya no borra la base de datos**, porque `-v` solo
elimina volúmenes con nombre. Para empezar de cero (por ejemplo, para volver a aplicar todas las
migraciones desde la primera):

```bash
docker compose down
```

```bash
rm -rf data/postgres
```

```bash
docker compose up -d --build
```

### Opción B · Desarrollo local

Solo la base de datos en Docker (el esquema lo crea Alembic, no Docker). Atención: `docker compose up -d`
**sin** nombre de servicio levantaría también el backend y el frontend, y ocuparían los puertos 8000 y 5173:

```bash
docker compose up -d db
```

Backend, en `http://localhost:8000` (documentación interactiva en `/docs`):

```bash
cd backend && python -m venv .venv && .venv/Scripts/activate && pip install -r requirements.txt && alembic upgrade head && uvicorn app.main:app --reload
```

> En Linux o macOS el entorno virtual se activa con `source .venv/bin/activate`.

Frontend, en `http://localhost:5173`:

```bash
cd frontend && npm install && npm run dev
```

## Configuración

Todo lo que el backend lee del entorno está en [`backend/app/config.py`](backend/app/config.py). Se define
en `.env` (plantilla: `.env.example`) o en el entorno de quien lo ejecute:

| Variable | Para qué sirve | Si falta |
|---|---|---|
| `POSTGRES_PASSWORD` | Contraseña de PostgreSQL (la usa `docker-compose.yml`) | Compose se niega a arrancar |
| `DATABASE_URL` | Cadena de conexión a la base de datos | El backend no arranca. Con Docker no hace falta: Compose la fija apuntando al servicio `db` |
| `CORS_ORIGINS` | Páginas que pueden llamar a la API desde un navegador: orígenes separados por comas, sin ruta (`https://tienda.example.com,http://localhost:5173`) | `http://localhost:5173` |
| `IMAGES_DIR` | Carpeta con las imágenes de los productos, que la API sirve en `/images` | `data/images` de este repositorio. Con Docker no hace falta: Compose monta esa carpeta en `/app/images` y fija la variable |

**CORS** es una protección del *navegador*: una página servida desde un origen (esquema + dominio +
puerto) no puede leer las respuestas de otro origen a menos que ese otro servidor lo autorice con la
cabecera `Access-Control-Allow-Origin`. `localhost:5173` (frontend) y `localhost:8000` (API) son orígenes
distintos, así que la API tiene que nombrar al frontend. Para desplegar el frontend en otra dirección basta
con listarla en `CORS_ORIGINS`; no hay que tocar código. `curl` no aplica CORS: para comprobarlo hay que
enviar la cabecera `Origin` a mano:

```bash
curl -i "http://localhost:8000/products?limit=1" -H "Origin: http://localhost:5173"
```

## Imágenes de los productos

Las imágenes son ficheros estáticos que sirve la propia API, no algo que se guarde en la base de datos:

```
data/images/product-1.jpg   ── volumen (bind mount, solo lectura) ──▶   /app/images en el contenedor
                                                                              │  StaticFiles
navegador  ──  GET http://localhost:8000/images/product-1.jpg  ◀────────────────┘
```

1. La base de datos guarda **dónde está** la imagen respecto al servidor: `products.image_url =
   '/images/product-1.jpg'`. No guarda un dominio, así que los mismos datos valen en `localhost` y en
   producción.
2. La API (`GET /products`) devuelve la dirección **completa**, construida con la dirección por la que
   llegó la petición: `"image_url": "http://localhost:8000/images/product-1.jpg"`. Es lo que hay que pedir.
3. El navegador hace un `GET` normal a esa dirección y `StaticFiles` (en `main.py`) lee el fichero de la
   carpeta y lo devuelve, con `ETag` para poder contestar `304` si no ha cambiado. No hay función de ruta ni
   consulta a la base de datos.

Como el frontend solo usa `product.image_url` como `src` de la etiqueta `<img>`, no sabe nada de todo esto.
Cargar una imagen de otro origen con `<img>` tampoco necesita CORS.

En `data/images/` hay dos juegos de imágenes: las fotografías `product-<id>.jpg`, que son las que se ven, y
las ilustraciones `product-<id>.svg` (color e icono por categoría) que se generaron primero y siguen ahí para
que el `downgrade` de la migración tenga a qué volver. Para cambiar una imagen, copia un fichero con el mismo
nombre en esa carpeta; se sirve al momento, sin reiniciar ni reconstruir nada.

La carpeta **sí** se sube a Git, porque es un dato de arranque igual que los productos de la migración
`001_products`: si no estuviera, quien clonara el repositorio vería las imágenes rotas, ya que la base de
datos nombra ficheros que no existirían. Por eso `.gitignore` ignora todo `data/` **menos** `data/images/`.
La carpeta de la base de datos, `data/postgres/`, sí se ignora.

> **Licencias.** Las fotografías proceden de Wikimedia Commons y Openverse, y varias son CC BY o CC BY-SA,
> que **exigen atribución visible**. La tabla con autor, licencia y origen de cada una está en
> [`data/images/CREDITS.md`](data/images/CREDITS.md); revísala antes de publicar la tienda en internet.

Dos revisiones mueven las imágenes, y ninguna cambia el esquema (solo los datos), así que las dos están
escritas a mano: autogenerate compara esquemas, no datos. Las dos tienen `downgrade`, así que se puede ir y
volver:

| Revisión | Deja `image_url` en |
|---|---|
| `001a_product_images` | `/images/product-<id>.svg`, en vez de las URLs externas de `picsum.photos` |
| `001b_product_images_jpg` | `/images/product-<id>.jpg`, las fotografías |

## Las categorías, en su propia tabla (EXPAND-CONTRACT)

Al principio la categoría era una columna de texto en `products`: el nombre `'laptops'` repetido en ocho
filas. Ahora es una tabla `categories` y `products.category_id` que la referencia. Así el nombre se guarda
una sola vez, renombrar una categoría es un `UPDATE`, y una errata no puede inventarse una categoría nueva
porque la clave foránea la rechaza.

El cambio se hace en **dos migraciones**, no en una, y esa es la lección:

| Revisión | Qué hace | ¿Rompe el código que ya está funcionando? |
|---|---|---|
| `001c_categories_expand` | Crea `categories`, la llena con los nombres que ya había y añade `products.category_id` **anulable** | **No.** La columna de texto sigue ahí y sigue siendo la que lee la aplicación |
| `001d_categories_contract` | Pone `category_id` como obligatoria y **borra** la columna de texto | **Sí.** Todo lo que aún leyera `products.category` deja de funcionar |

Entre las dos hay una parada: el hueco donde se despliega el código nuevo y se comprueba que nadie usa ya
la columna vieja. Si algo va mal, el `downgrade` de CONTRACT vuelve atrás **con los datos**, porque el
nombre se puede reconstruir siguiendo la clave foránea. Hacerlo en una sola migración obligaría a parar la
tienda. Se puede ver el esquema encoger y volver a crecer:

```bash
docker compose exec backend alembic downgrade 001c_categories_expand
```

```bash
docker compose exec backend alembic upgrade head
```

Dos cosas que `--autogenerate` **no** sabe hacer aquí, y que están corregidas a mano en las revisiones:

- **Mover los datos.** Compara esquemas, no datos, así que creó la tabla vacía y la columna llena de
  `NULL`. El traspaso está escrito a mano, y lee los nombres de los propios productos (`SELECT DISTINCT`)
  en vez de llevar una lista escrita, para que no se pueda olvidar ninguno.
- **Deshacer CONTRACT.** Generó un `add_column` con `NOT NULL` y sin valor por defecto, que sobre una tabla
  con 36 filas PostgreSQL rechaza (*column "category" contains null values*). El `downgrade` correcto tiene
  tres pasos: añadir la columna anulable, rellenarla desde `categories`, y solo entonces exigir `NOT NULL`.

**La API no cambió.** `GET /products` sigue enviando `"category": "laptops"`, un nombre, que ahora se lee de
la fila relacionada. El contrato con el navegador es independiente del esquema. Lo que sí es nuevo es
`GET /categories`, que devuelve `[{"id": 1, "name": "laptops"}, …]`: antes el frontend llevaba la lista
escrita a mano y ahora la pide. Añade una fila a `categories` y aparecerá un botón más en la pantalla sin
tocar una línea de código.

```bash
curl -s "http://localhost:8000/categories"
```

## Checkpoints

| Tag | Revisión Alembic | Qué se enseña | Estado |
|---|---|---|---|
| `cp1-catalog` | de `001_products` a `001d_categories_contract` | Una tabla bien hecha, un endpoint paginado, un listado que carga más al hacer scroll | hecho |
| `cp2-cart` | `002_cart_and_orders` | Carrito (mutable, efímero) frente a pedido (inmutable, precio congelado) | pendiente |
| `cp3-users` | `003_users_and_addresses` | Usuario, dirección de envío y de facturación, registro y login | pendiente |
| `cp4-price-history` | `004_price_history` | Un histórico que la base de datos rellena sola con un trigger en el `UPDATE` | pendiente |

Para ver el código de un checkpoint concreto: `git checkout cp1-catalog` (y `git checkout main` para volver).

## Moverse entre checkpoints con Alembic

Alembic guarda en la tabla `alembic_version` qué revisión está aplicada. Es el `schema_migrations`
de la sesión 15, hecho por la herramienta de verdad. Los comandos se ejecutan en `backend/` con el
entorno virtual activado:

```bash
alembic current
```

```bash
alembic upgrade head
```

```bash
alembic downgrade 001_products
```

```bash
alembic downgrade base
```

El `--rev-id` legible es deliberado: permite mover la **base de datos** entre checkpoints sin tocar
Git, y en clase se ve el esquema crecer y encoger. Así se crea cada revisión (el mismo comando en los
cuatro checkpoints, cambiando el id y el mensaje):

```bash
alembic revision --autogenerate --rev-id 001_products -m "products"
```

Para mirar la base de datos no hace falta instalar `psql`; se usa el del contenedor:

```bash
docker compose exec db psql -U shop -d shop
```

## Guion de demo

### cp1 · Catálogo

1. Abrir [`backend/app/models.py`](backend/app/models.py) y
   [`backend/alembic/versions/001_products.py`](backend/alembic/versions/001_products.py) lado a lado:
   qué generó Alembic (la tabla, los `CHECK`, el índice) y qué se añadió a mano (los 36 productos:
   autogenerate compara esquemas, no datos).
2. `\d products` en psql: el DDL coincide con lo que dicen los modelos.
3. `GET /products?limit=5` dos veces, la segunda con el `next_cursor` de la primera; la última página
   devuelve `"next_cursor": null`:

   ```bash
   curl "http://localhost:8000/products?limit=5"
   ```

   ```bash
   curl "http://localhost:8000/products?limit=5&cursor=5"
   ```

4. `GET /products/999` devuelve `404` con `{"detail": "Product 999 not found"}`.
   La imagen: en psql `image_url` es una ruta relativa, en la API es una dirección completa, y esa
   dirección responde a un `GET` normal:

   ```bash
   curl -s "http://localhost:8000/products/1"
   ```

   ```bash
   curl -i "http://localhost:8000/images/product-1.jpg"
   ```
5. Navegador con la pestaña **Red** abierta: bajar y ver las **tres** peticiones a `/products`
   (`cursor=0`, `cursor=12`, `cursor=24`) y las imágenes llegando después. Son dos mecanismos distintos:
   `loading="lazy"` retrasa **las imágenes**; el `IntersectionObserver` retrasa **la petición de la
   página siguiente**. Si la ventana es muy alta, el final de la lista ya está a la vista y se cargan las
   tres páginas de golpe: reduce la altura de la ventana o amplía el zoom del navegador.

## Fuera de alcance

Se dejan fuera a propósito (no se implementan):

- Pasarela de pago (un pedido nace ya en estado `paid`)
- Roles y permisos
- Imágenes de producción (los contenedores de la aplicación arrancan los servidores de desarrollo)
- CI
- Observabilidad
- Tests automáticos
- Subir imágenes a través de la API (se colocan a mano en `data/images/`)
