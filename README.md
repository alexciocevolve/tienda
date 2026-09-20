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

> **Ojo con `/docs`:** es una página que carga Swagger UI desde un CDN, así que sin
> conexión a internet no pinta nada aunque `/openapi.json` siga contestando perfectamente.

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

## Integración continua

`.github/workflows/ci.yml` ejecuta en cada push y en cada pull request **todo lo que antes se
comprobaba a mano**: las tres suites de tests y las dos reglas de estilo del proyecto (ni clases
en `frontend/src`, ni castellano en el código), que hasta ahora eran dos `grep` que había que
acordarse de teclear antes de cada tag.

Cuatro trabajos, y el orden no es casual — es la pirámide de tests gastada como dinero:

```
rules  ─┐
frontend ├──→ e2e
backend ─┘
```

Lo barato va primero y a la vez; **e2e solo arranca si lo demás estaba verde**, porque construye
tres contenedores y espera a sus healthchecks. Un test unitario en rojo no debería costar tres
minutos de Docker.

Dos cosas que el pipeline sí comprueba y una sesión de desarrollo normal no:

- **El tipado.** `npm run build` es `tsc --noEmit && vite build`. Vitest transpila **sin comprobar
  tipos**, así que un error de tipos puede vivir tranquilamente dentro de una suite en verde.
- **La versión de Python.** CI usa **3.12**, la del `Dockerfile`, no la del portátil. Es la
  comprobación de que el proyecto no ha empezado a depender de una versión que producción no tiene.

## Desplegar en Render

`render.yaml` describe la tienda entera como **tres recursos que no son tres cosas iguales** — y esa es
la primera lección de sacar de un portátil algo que allí eran tres contenedores:

| Recurso | Qué es | Plan gratis |
|---|---|---|
| `tienda-db` | Una base de datos gestionada | 1 GB · **caduca a los 30 días** |
| `tienda-api` | Un proceso que escucha en un puerto | Se duerme a los 15 min sin tráfico |
| `tienda-web` | **Una carpeta de ficheros.** Tras `vite build` no hay proceso | — |

Se despliega con **New → Blueprint** en Render, apuntando a este repositorio. Pide dos valores que no
se pueden deducir solos (`CORS_ORIGINS` y `VITE_API_URL`), porque cada servicio necesita la URL del
otro y esas URLs no existen hasta que se crean los servicios.

**Ojo con `VITE_API_URL`:** Vite la **incrusta en el JavaScript al construir**. Cambiarla en el panel
no hace nada hasta que el sitio se **vuelve a construir**. Configuración de construcción y
configuración de arranque se parecen mucho en un panel y no se comportan igual.

Y cuatro cosas del código existen por esto:

- **Las imágenes viajan dentro de la imagen de Docker** (`COPY data/images`), por lo que el backend se
  construye con la raíz del repositorio como contexto. Sin ellas la API **ni arranca**: `StaticFiles`
  rechaza un directorio que no existe. En el plan gratuito no hay discos persistentes.
- **El puerto** sale de `${PORT:-8000}`: lo elige el host.
- **`DATABASE_URL`** llega como `postgresql://…` y `app/config.py` le pone el driver (`with_driver`).
- **La migración sigue en el arranque.** Render solo ofrece `preDeployCommand` en planes de pago, y en
  gratis hay exactamente una instancia, así que la comodidad que `PLAN.md` señalaba es aquí la única
  opción. El fichero deja anotado qué descomentar el día que deje de serlo.

## El contrato de la API (`openapi.json`)

FastAPI **genera** el documento OpenAPI a partir del código: recorre las rutas y lee las firmas, los
modelos Pydantic y los decoradores. No existe un fichero que se edite para cambiar el contrato — el
contrato es el código. Lo sirve en `/openapi.json`, y `/docs` y `/redoc` solo lo pintan.

Eso tiene una consecuencia que conviene conocer: **lee declaraciones, nunca el cuerpo de las
funciones**. Todo lo que se lanza con `raise HTTPException(...)` es invisible para el generador, así que
hasta que se declararon con `responses=` en cada ruta, las decisiones más pensadas de esta API —404 en
vez de 403 para el pedido de otro, 404 en vez de lista vacía para un producto que no existe, 409 en vez
de 400 cuando una regla dice que no— **no aparecían en su propia documentación**.

El contrato está además **versionado en el repositorio**, para que un cambio llegue como un diff que
alguien tiene que aprobar en vez de cambiar solo:

```bash
cd backend && .venv/Scripts/python export_openapi.py
```

| Rompe esto | Tiene que fallar |
|---|---|
| Cambiar cualquier cosa que un cliente vea (una ruta, un parámetro, un código de estado) sin reexportar | `test_the_committed_contract_still_matches_the_code`, con el diff exacto |
| Quitar el `responses=` de `POST /orders` o de `GET /orders/{id}` | también `test_the_failures_this_api_chose_are_in_its_documentation`, que dice **qué promesa** se ha perdido |

## Tests

Los tests del backend se ejecutan contra una base de datos **aparte**, `shop_test`, que se crea sola la
primera vez y se construye **ejecutando las migraciones de verdad**. Nunca tocan la base de desarrollo,
así que no pueden llevarse por delante los datos de la clase.

```bash
cd backend && .venv/Scripts/activate && pip install -r requirements-dev.txt && pytest
```

Cada test corre dentro de una transacción que se deshace al terminar, así que todos empiezan con los
mismos 36 productos y sin usuarios. No hay que borrar nada a mano.

**Cómo saber si un test sirve para algo:** rompe a propósito la regla que vigila y comprueba que falla.

| Rompe esto en `services.py` | Debe fallar |
|---|---|
| Quitar `joinedload(Product.category)` | El test que cuenta consultas (el N+1) |
| Poner `price_cents=0` en el `OrderItem` | Los dos tests del precio congelado |
| Quitar `Order.user_id == user.id` del `WHERE` | El test de que un pedido solo lo lee su dueño |
| Hacer que `save_address` modifique la fila | Los tests del histórico de direcciones |
| Quitar `with_for_update()` de `create_order` | El test de concurrencia: *«both buyers got through»* |
| Devolver `403` en vez de `404` en un pedido ajeno | El test que comprueba que no se confirma su existencia |
| Añadir `password_hash` a la respuesta de un usuario | Los dos tests que revisan lo que sale por la API |
| Cambiar un modelo sin escribir la migración | El test de deriva, que es el único que dice **por qué** |

Un test que no falla al romper lo que vigila no vigila nada.

### Los tres tipos de test, y por qué son distintos

| Fichero | Cómo se aísla |
|---|---|
| `test_security.py` | No toca la base de datos: una función, un argumento, una respuesta |
| `test_*.py` (servicios) y `test_api_*.py` | Una transacción que se deshace al terminar |
| `test_concurrency.py` | **Confirma de verdad**, porque dos transacciones que no se ven no compiten por nada. Crea su propio producto en vez de tocar el stock de los 36 de siempre, y limpia con SQL a pelo para que un fallo no deje filas confirmadas detrás |
| `test_migrations.py` | **Su propia base de datos**, que crea y destruye, porque la vacía entera |

Los de la API van contra el `TestClient` de FastAPI, no contra un servidor levantado: prueban las rutas,
las dependencias, la validación y los códigos de estado, sin que nadie tenga que arrancar nada.

### Frontend

```bash
cd frontend && npm install && npm test
```

Con `vitest` y Testing Library, sobre `jsdom`. **Ninguno toca la red**: cada test dice lo que responde la
API, así que un fallo siempre habla de este código y nunca de que la tienda esté caída, lenta o con datos
de otra persona.

Son pocos y elegidos. Se prueba comportamiento, nunca la forma: no hay tests de `formatPrice` ni del
`Header`, porque no tienen forma de romperse en silencio.

| Rompe esto | Debe fallar |
|---|---|
| Hacer controlado el campo de contraseña | Los dos tests de que la contraseña no acaba en el HTML |
| `setItems(page.items)` en vez de concatenar | El test de que cada página se **añade** a las anteriores |
| Quitar la comprobación de `generation` | El test de la respuesta que llega tarde |
| Quitar `!user || !shippingAddress` del botón | Los dos tests del botón de comprar bloqueado |

El primero existe porque **ese fallo fue real**: con un `<input value={...}>` controlado, React escribe el
texto en el **atributo** `value`, y entonces cualquier cosa que serialice el DOM se lleva la contraseña en
claro.

> `jsdom` no tiene maquetación, así que no sabe qué se ve y no trae `IntersectionObserver`. El doble está
> en [`src/setupTests.ts`](frontend/src/setupTests.ts) y avisa de «visible» en cuanto se observa algo, que
> es lo que hace un navegador de verdad cuando el elemento ya está a la vista. Por eso, en los tests, el
> catálogo se comporta como en una pantalla alta: sigue pidiendo páginas hasta que el servidor dice que no
> hay más.

### De extremo a extremo

Con la tienda levantada, desde `e2e/`:

```bash
docker compose up -d
```

```bash
cd e2e && ../backend/.venv/Scripts/python -m pytest
```

Si la tienda no está arrancada, se saltan con un mensaje que lo dice, en vez de fallar quince veces.

Son **15 y hablan solo HTTP y SQL**: no hay navegador. La regla que los define está en
[`e2e/conftest.py`](e2e/conftest.py) y conviene leerla antes que los tests:

> **Ninguno importa la aplicación.** Ni un solo `from app import ...`.

Un test que importa el código que prueba puede pasar mientras los contenedores están mal conectados, las
migraciones no se han ejecutado, el CORS apunta a otro sitio o las imágenes no se están sirviendo. Eso es
justo lo que esta capa existe para cazar.

**Prueba de que sirven:** con `CORS_ORIGINS` apuntando a una dirección equivocada, los 152 tests de backend
y frontend pasan igual y **estos dos fallan**. Con el contenedor del frontend parado, falla el que comprueba
que se está sirviendo. La tienda estaría rota en cualquier navegador y nada más se habría enterado.

**Escriben en la base de datos de verdad**, porque es la que usa la tienda en marcha. Por eso traen **su
propio producto y su propio cliente** y se los llevan al terminar: los 36 productos de siempre no se tocan y
el stock no queda cambiado. Comprobado ejecutándolos dos veces seguidas: la base queda idéntica.

### Por qué tan pocos de cada capa

| Capa | Cuántos | Qué prueba | Coste de un fallo |
|---|---|---|---|
| Backend | 128 | Las reglas: stock, precios, propiedad, migraciones | Rápido y señala la línea |
| Frontend | 24 | Tres comportamientos que se rompen en silencio | Rápido |
| Extremo a extremo | 15 | Que las piezas están conectadas | Lento, y dice «algo falla» sin decir dónde |

Cuantos más se suba en la tabla, más lentos y más vagos son los mensajes. Por eso arriba hay quince y no
doscientos: aquí solo va lo que **no se puede comprobar de ninguna otra forma**.

## Checkpoints

| Tag | Revisión Alembic | Qué se enseña | Estado |
|---|---|---|---|
| `cp1-catalog` | de `001_products` a `001d_categories_contract` | Una tabla bien hecha, un endpoint paginado, un listado que carga más al hacer scroll | hecho |
| `cp2-cart` | `002_cart_and_orders` | Carrito (mutable, efímero) frente a pedido (inmutable, precio congelado) | hecho |
| `cp3-users` | de `003_users` a `003c_orders_user` | Registro, acceso, sesiones, direcciones, y el pedido con dueño y destino | en curso |
| `cp4-tests` | ninguna | Convertir en tests todo lo que hasta ahora se comprobaba a mano | pendiente |
| `cp5-price-history` | `004_price_history` | Un histórico que la base de datos rellena sola con un trigger en el `UPDATE` | pendiente |

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
5. Pinchar en cualquier parte de una tarjeta: se abre el detalle con la imagen, la descripción, el
   precio y si queda stock. Se cierra pinchando fuera, con `Esc` o con la `×`. En la pestaña **Red**
   se ve lo interesante: **no hay ninguna petición nueva**. La descripción ya venía en el listado, así
   que el detalle no le pide nada al servidor.
6. Navegador con la pestaña **Red** abierta: bajar y ver las **tres** peticiones a `/products`
   (`cursor=0`, `cursor=12`, `cursor=24`) y las imágenes llegando después. Son dos mecanismos distintos:
   `loading="lazy"` retrasa **las imágenes**; el `IntersectionObserver` retrasa **la petición de la
   página siguiente**. Si la ventana es muy alta, el final de la lista ya está a la vista y se cargan las
   tres páginas de golpe: reduce la altura de la ventana o amplía el zoom del navegador.

### cp2 · Carrito y pedido

1. Abrir `cart_items` y `order_items` lado a lado en [`models.py`](backend/app/models.py). **Esa es la
   sesión**: `cart_items` **no** tiene columna de precio y `order_items` **sí**. Un carrito enseña el precio
   de hoy, leído de `products`; un pedido guarda el precio al que se compró.
2. El recorrido completo por curl. El token del carrito viaja en una cabecera, nunca en la dirección:

   ```bash
   curl -s -X POST http://localhost:8000/cart
   ```

   ```bash
   curl -s -X PUT http://localhost:8000/cart/items/1 -H "X-Cart-Token: TOKEN" -H "Content-Type: application/json" -d '{"quantity":2}'
   ```

   Repetir ese mismo `PUT` deja el carrito igual: **fija** la cantidad, no suma. Por eso reintentarlo tras
   un corte de red es inofensivo. `DELETE` quita la línea: cada verbo hace lo que dice su nombre.
3. La demostración del precio congelado. Hacer el pedido, cambiar el precio en psql y volver a leerlo:

   ```bash
   docker compose exec db psql -U shop -d shop -c "UPDATE products SET price_cents = 1 WHERE id = 1"
   ```

   ```bash
   curl -s http://localhost:8000/orders/1
   ```

   El pedido sigue diciendo 89900. El catálogo ya dice 1.
4. Pedir más unidades de las que hay: `409` con el detalle, y el stock **intacto**. Con dos líneas, una
   servible y otra no, no se mueve ninguna: el pedido es todo o nada.
5. La carrera de la sesión 14: dos carritos con la última unidad, pagando a la vez. Uno recibe `201` y el
   otro `409`, y el stock acaba en 0, nunca en −1. Lo consigue `SELECT ... FOR UPDATE` en `create_order`.
6. En el navegador: añadir desde el catálogo, `+` / `−` / `Remove` en el carrito, comprar y ver la
   confirmación. El carrito sobrevive a recargar la página, porque el token está en `localStorage`.

> **Todavía no hay usuarios.** Cada pedido se asigna al mismo cliente de prueba, definido en
> [`backend/app/config.py`](backend/app/config.py) como `PLACEHOLDER_CUSTOMER_EMAIL`. Por eso `POST /orders`
> no lleva cuerpo: los precios, el total y el comprador los decide el servidor. El registro, la
> autenticación y la asignación real del pedido llegan en el checkpoint siguiente.

### cp3 · Registro y acceso

1. Abrir [`models.py`](backend/app/models.py) y buscar dónde se guarda la contraseña. **No está.** Hay una
   columna `password_hash` y ningún sitio donde quepa una contraseña: eso no es un olvido, es el diseño.
2. Registrarse en la pantalla y mirar después la tabla en psql. Lo que hay es `scrypt$<sal>$<hash>`:

   ```bash
   docker compose exec db psql -U shop -d shop -c "SELECT email, left(password_hash, 30) FROM users"
   ```

   Registrar a dos personas **con la misma contraseña** y comparar: los hashes son distintos, porque cada
   uno lleva su propia sal. Por eso una tabla de hashes precalculados no sirve de nada.
3. Equivocarse de contraseña, y luego probar con un email que no existe. **El mensaje es el mismo**:
   *"Invalid email or password"*. Si dijera "ese email no está registrado", el formulario de acceso sería
   una forma de averiguar quién compra aquí. Y tardan lo mismo, porque el servidor hace el trabajo de
   comprobar el hash también cuando no hay usuario.
4. La contraseña en el navegador, con las herramientas de desarrollo abiertas:
   - `type="password"`, y el botón **Show** para verla cuando hace falta.
   - Si el campo estuviera controlado por React, la contraseña acabaría en el atributo `value` del HTML, y
     cualquier cosa que serialice el DOM se la llevaría en claro. Por eso el campo es **no controlado** y se
     lee del elemento al enviar. Se puede comprobar en la consola: `$0.getAttribute('value')` da `null`.
   - `autocomplete="username"` y `autocomplete="current-password"` / `"new-password"`: es lo que hace que un
     gestor de contraseñas guarde y rellene bien, y que el navegador no meta la contraseña vieja en el campo
     de la nueva.
   - Aviso de **Caps Lock**, que es la causa más común de que una contraseña correcta sea rechazada.
5. Cerrar sesión y mirar la tabla `sessions`: la fila **se ha borrado**. Olvidar el token solo en el
   navegador dejaría al token vivo 24 horas para quien lo hubiera copiado.
6. Una sesión caducada: la fila sigue existiendo y aun así el token ya no vale, porque lo que manda es la
   fecha, no la existencia de la fila.

### cp3 · Direcciones de envío y facturación

Cada persona tiene **una dirección de envío y una de facturación**, y se editan en *My account*. El tipo
de dirección es una **columna** de la propia fila, `is_billing`, no una fila en otra tabla de tipos.

7. Guardar las dos direcciones y mirar la tabla: dos filas, una con `is_billing = f` y otra con `t`.

   ```bash
   docker compose exec db psql -U shop -d shop -c "SELECT id, user_id, is_billing, street, city FROM addresses"
   ```

8. Cambiar la dirección de envío y volver a mirar: **la misma fila, con el `id` de antes**. No aparece una
   segunda. Es lo que hace `PUT /me/addresses/shipping`, que fija lo que esa dirección *es*.
9. Intentar meter a mano una segunda dirección de facturación para la misma persona: la base de datos la
   rechaza, porque la regla vive ahí y no en Python.

   ```bash
   docker compose exec db psql -U shop -d shop -c "INSERT INTO addresses (user_id, is_billing, recipient_name, street, city, postal_code) VALUES (1, true, 'X', 'X', 'X', 'X')"
   ```

10. `PUT /me/addresses/home` responde `422` sin que corra nada nuestro: los dos únicos valores posibles
    están declarados en el tipo de la ruta, y salen también en `/docs`.
11. **El `id` de una dirección no aparece en ninguna ruta.** Todo se resuelve desde la sesión, así que no
    hay ningún número que cambiar para llegar a la dirección de otra persona.

> **Decisión distinta a la del plan.** `PLAN.md` §6.1 estudia justo este diseño (una tabla de direcciones
> con su tipo) y lo descarta en favor de direcciones sin tipo cuyo papel se asigna en el pedido. Aquí se
> ha seguido la otra opción a propósito. Lo que cuesta se ve en el botón *"Copy from shipping"*: usar la
> misma dirección para las dos cosas guarda las mismas líneas dos veces.

### cp3 · El pedido recuerda a dónde se envió

Las direcciones **dejan de editarse**. Cambiar una retira la fila que estaba en uso y escribe otra, así
que la fila a la que apunta un pedido nunca cambia por debajo. Es la lección del precio congelado de
`order_items`, alcanzada por el otro camino: allí copiando el valor, aquí apuntando a una fila que no se
puede modificar.

12. **La demostración**: con sesión iniciada, el carrito muestra *"Shipping to"* con la dirección de
    envío. Comprar, y después **mudarse** cambiando la dirección en *My account*. Volver al pedido: sigue
    diciendo la dirección antigua. La cuenta muestra la nueva.
13. Mirar la tabla: la fila vieja sigue ahí, retirada, y el pedido apunta a ella.

    ```bash
    docker compose exec db psql -U shop -d shop -c "SELECT id, is_active, street, city FROM addresses ORDER BY id"
    ```

    ```bash
    docker compose exec db psql -U shop -d shop -c "SELECT id, shipping_address_id FROM orders"
    ```

14. Lo que mantiene el orden es un **índice único parcial**: único sobre `(user_id, is_billing)` pero
    **solo** `WHERE is_active`. Cada persona tiene como mucho una de cada en uso y todas las retiradas que
    haga falta. Probar a meter una segunda activa a mano y ver cómo la base de datos la rechaza.
15. `is_active` **no sale en la API**. Que alguien siga usando una dirección es asunto suyo; el pedido
    apunta a una fila concreta y eso no le afecta.
16. La dirección **no se envía desde el navegador**: el servidor la busca a partir del token. Un cliente
    que pudiera nombrar un `id` de dirección sería un cliente capaz de nombrar la de otra persona.
17. El `downgrade` de `003b` fue el segundo que autogenerate no pudo escribir bien: el esquema anterior
    solo admite una dirección por persona y tipo, y para entonces ya hay retiradas. La versión corregida
    borra las retiradas primero **y dice que eso destruye información**, porque el esquema viejo no tiene
    dónde guardarla.

### cp3 · No hay pedidos anónimos

Un pedido pertenece a alguien y solo esa persona puede verlo. Los pedidos aparecen en *My account*.

18. **Dos agujeros que se encontraron probando la API, no leyendo el código.** Antes de este paso,
    `POST /orders` sin token respondía `201`, y peor: `GET /orders/5` **sin token** respondía `200` con el
    correo y la calle del cliente. Cualquiera podía leer todos los pedidos de la tienda contando ids.
    Ahora:

    ```bash
    curl -i -X POST http://localhost:8000/orders -H "X-Cart-Token: TOKEN"
    ```

    Responde `401`. Y el pedido de otra persona responde **`404`, no `403`**: un `403` confirmaría que el
    pedido 42 existe, y eso basta para contar los pedidos del negocio.
19. Un pedido sin dirección también se rechaza, con `409`: tiene que saber a dónde va. En la pantalla el
    botón está deshabilitado antes de llegar ahí, pero la comprobación que manda es la del servidor.
20. **Lo interesante de la revisión `003c` es lo que NO hace.** No pone `user_id` como `NOT NULL`, porque
    los pedidos anteriores a esta regla no tienen dueño y las únicas salidas serían inventarle uno o
    borrar pedidos de verdad. En su lugar añade la regla como `CHECK ... NOT VALID`:

    ```sql
    ALTER TABLE orders ADD CONSTRAINT ck_orders_user_id_required CHECK (user_id IS NOT NULL) NOT VALID;
    ```

    PostgreSQL la aplica a **todo lo que se escriba a partir de ahora** y no revisa las filas que ya
    estaban. Es la misma técnica con la que se añade una restricción a una tabla enorme sin bloquearla
    durante un recorrido completo; después, cuando las filas viejas están resueltas, se valida con una
    línea: `VALIDATE CONSTRAINT`. Se puede ver funcionando:

    ```bash
    docker compose exec db psql -U shop -d shop -c "INSERT INTO orders (customer_email, total_cents) VALUES ('x@x.com', 100)"
    ```

21. `customer_email` se mantiene aunque ya se sepa quién compra: guarda el correo **del día del pedido**,
    congelado como el precio y la dirección. Cambiar el correo de la cuenta el año que viene no debe
    reescribir a dónde se confirmó un pedido antiguo.

## Fuera de alcance

Se dejan fuera a propósito (no se implementan):

- Pasarela de pago (un pedido nace ya en estado `paid`)
- Roles y permisos
- Imágenes de producción (los contenedores de la aplicación arrancan los servidores de desarrollo)
- CI (los tests del cp4 se ejecutan a mano antes de cada tag)
- Observabilidad
- Subir imágenes a través de la API (se colocan a mano en `data/images/`)
