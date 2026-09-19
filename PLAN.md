# Plan de implementación · Tienda didáctica (React + FastAPI + SQLAlchemy + PostgreSQL)

Este documento es la única fuente de requisitos para quien implemente el código (modelo o
persona). Se construye **checkpoint a checkpoint, en orden**, sin adelantar tablas, endpoints
ni pantallas de checkpoints posteriores. Cada checkpoint termina con un commit y un tag de Git.

| Tag | Revisiones Alembic | Qué se enseña |
|---|---|---|
| `cp1-catalog` | `001_products` … `001d_categories_contract` | Una tabla bien hecha, un endpoint paginado, un listado que carga al hacer scroll, ficheros estáticos y un cambio de modelo en dos mitades (EXPAND-CONTRACT) |
| `cp2-cart` | `002_cart_and_orders` | Carrito (mutable, efímero) frente a pedido (inmutable, precio congelado) |
| `cp3-users` | `003_users` … `003c_orders_user` | Registro, acceso, sesiones, direcciones con histórico y el pedido que sabe de quién es y a dónde va |
| **`cp4-tests`** | **ninguna** | **Convertir en tests todo lo que hasta ahora se comprobaba a mano, en tres capas** |
| `cp5-price-history` | `004_price_history` | Un histórico que la base de datos rellena sola con un trigger en el `UPDATE` |

> **cp4 es el único checkpoint sin migración.** No toca el esquema: no añade
> funcionalidad, la sujeta. Es deliberado que llegue **después** de tres checkpoints de
> comprobaciones manuales, porque así los tests no se inventan: ya están escritos en los
> «Hecho cuando» de cp1, cp2 y cp3, solo hay que pasarlos a código.

---

## 0. Reglas del juego

### 0.1 Arquitectura: MVC en tres capas, y nada más

| Capa | Fichero | Qué contiene | Qué NO contiene |
|---|---|---|---|
| Modelo | `app/models.py` | Una clase SQLAlchemy por tabla. Columnas, restricciones, relaciones | Lógica de negocio |
| Servicios | `app/services.py` | Las reglas de negocio como funciones que reciben una `Session` de SQLAlchemy | Nada de HTTP: ni códigos, ni `HTTPException`, ni JSON |
| Rutas | `app/routes/*.py` | Traducción HTTP ↔ servicios: lee la petición, llama al servicio, convierte el resultado a diccionario, elige el código | Reglas de negocio |

Y una regla para las clases: **solo existen las que el framework necesita**. Modelos
SQLAlchemy (una por tabla) y esquemas Pydantic **de entrada** (uno por cuerpo de petición).
Ninguna otra: ni excepciones propias, ni esquemas de salida, ni componentes de clase en React.

### 0.2 Errores sin excepciones propias

- Cuando algo **no existe**, el servicio devuelve `None` y la ruta lo convierte en `HTTPException(404, "Product 999 not found")`.
- Cuando una **regla de negocio** se rompe (stock insuficiente, carrito vacío), el servicio lanza `ValueError("...")` con el mensaje final y la ruta lo convierte en `HTTPException(409, str(e))`.
- Autenticación fallida o ausente: la dependencia de la ruta lanza `HTTPException(401, ...)`.
- **Un recurso de otra persona no se responde con 403, sino con 404**, con el mismo texto que si no existiera. Un 403 confirmaría que el pedido 42 existe, y eso basta para contar los pedidos del negocio pidiendo un número tras otro.

Solo excepciones de Python. El servicio sigue sin saber nada de HTTP.

### 0.3 Todo el código en inglés

Sin excepciones: identificadores SQL, Python y TypeScript, comentarios, mensajes de error de
la API, textos de pantalla, datos de arranque, mensajes de commit y tags. El castellano
queda solo para este `PLAN.md` y para el `README.md` de clase.

### 0.4 Convenciones del curso que se mantienen

1. **Importes en céntimos enteros** (`price_cents`, `total_cents`). Nunca `float`.
2. **Errores de la API siempre `{"detail": "..."}`** con el código HTTP correcto y el dato que falló en el mensaje.
3. **Todo lo que afecta a dinero, stock o identidad se calcula en el servidor.** Del cliente solo llegan ids de producto y cantidades. Nunca un precio, un total, un id de dirección ni un id de usuario.
4. **Nombres SQL y JSON en `snake_case`**: tablas en plural, PK `id`, FK `<singular>_id`, fechas `created_at`. Python en `snake_case`, TypeScript en `camelCase`, componentes en `PascalCase`.
5. **Las claves foráneas y las restricciones llevan nombre propio.** Si no, PostgreSQL inventa uno y el `downgrade` no sabe qué borrar; Alembic avisa de esto por escrito y hay que leerlo.

### 0.5 Lo que se guarda congelado, y por qué

Es el hilo que recorre la tienda entera y aparece en tres checkpoints distintos:

| Dato | Dónde se congela | Cómo |
|---|---|---|
| Precio | `order_items.price_cents` (cp2) | **Copiando el valor** al hacer el pedido |
| Dirección | `orders.shipping_address_id` (cp3) | **Apuntando a una fila que ya no se modifica**: cambiar de dirección escribe una nueva y retira la vieja |
| Correo del comprador | `orders.customer_email` (cp3) | Copiando el valor, aunque el usuario ya se conozca |

Dos técnicas para el mismo problema, y merece la pena contrastarlas en clase: copiar el
valor es más simple y no depende de nadie; apuntar a una fila inmutable no duplica datos y
permite recuperar la dirección completa, pero obliga a que nada la edite nunca.

### 0.6 Fuera de alcance

Se dejan fuera a propósito (nota en el README, no se implementa): pasarela de pago, roles y
permisos, imágenes de producción (los contenedores arrancan servidores de desarrollo), CI,
observabilidad y subida de imágenes por la API. Un pedido nace en estado `paid`.

> Los **tests automáticos estaban en esta lista y han salido de ella**: son el checkpoint 4.

---

## 1. Stack

| Capa | Elección |
|---|---|
| Base de datos | PostgreSQL 16 (`postgres:16-alpine`), con los datos en un bind mount visible (`./data/postgres`) |
| Backend | Python 3.12 · FastAPI · SQLAlchemy 2.0 (estilo `Mapped`) · Alembic · `psycopg[binary]` 3 · uvicorn · `pydantic[email]` · `python-dotenv` |
| Frontend | Vite · React 18 · TypeScript · `react-router-dom` (desde cp2) · un `styles.css` |
| Contenedores | Un único `docker-compose.yml` con **todos** los servicios: `db`, `backend` (`python:3.12-slim`) y `frontend` (`node:22-alpine`) |
| Tests (cp4) | `pytest` · `httpx2` (lo que mueve el `TestClient` de FastAPI, y el cliente de los de extremo a extremo) en el backend · `vitest` + `@testing-library/react` sobre `jsdom` en el frontend |

**Fuente de verdad del esquema: los modelos SQLAlchemy.** Alembic genera las migraciones
comparándolos con la base de datos (`--autogenerate`), y a mano se añade lo que
autogenerate no ve. Es el flujo real de un proyecto con SQLAlchemy y es lo que se enseña.

### 1.1 La frase que vertebra el curso

> **`--autogenerate` compara esquemas, no datos.**

Sabe escribir `CREATE TABLE` y `ALTER TABLE` porque las tablas están en los modelos. No sabe
que tu tabla tiene filas, ni de dónde sacar un dato que falta, ni escribir un `INSERT`, ni ver
una función o un trigger. De ahí salen **todas** las partes escritas a mano del proyecto, y los
tres `downgrade` que generó mal y hubo que corregir (§10).

---

## 2. Estructura del repositorio

```
tienda/
├── README.md                 # (castellano) arranque, configuración, checkpoints, demos
├── PLAN.md                   # (castellano) este documento
├── docker-compose.yml        # todos los servicios; sin scripts de inicialización
├── .env.example
├── data/
│   ├── postgres/             # datos de PostgreSQL (bind mount); NO se sube a Git
│   └── images/               # imágenes de los productos; SÍ se sube (dato de arranque)
├── backend/
│   ├── Dockerfile · .dockerignore · requirements.txt · alembic.ini
│   ├── alembic/
│   │   ├── env.py            # lee DATABASE_URL del entorno; target_metadata = Base.metadata
│   │   └── versions/         # 001… 001d (cp1), 002 (cp2), 003… 003c (cp3), 004 (cp5)
│   ├── app/
│   │   ├── main.py           # FastAPI, CORS, include_router, GET /health, StaticFiles
│   │   ├── config.py         # TODO lo que se lee del entorno, en un solo sitio
│   │   ├── db.py             # engine, SessionLocal, get_db()
│   │   ├── models.py         # M: una clase por tabla
│   │   ├── schemas.py        # esquemas Pydantic de ENTRADA
│   │   ├── services.py       # C: reglas de negocio, funciones con Session
│   │   ├── security.py       # hash_password, verify_password
│   │   └── routes/           # V: products, categories, cart, orders, users, shared
│   ├── tests/                # cp4: servicios y API, en proceso
│   └── requirements-dev.txt · pytest.ini
├── e2e/                      # cp4: la tienda levantada, solo HTTP y SQL. NO importa app
└── frontend/
    ├── Dockerfile · .dockerignore · package.json · vite.config.ts · tsconfig.json
    └── src/
        ├── api.ts            # request<T>() y una función por endpoint
        ├── useData.ts        # hook de carga con el tipo State<T>
        ├── cart.tsx          # CartProvider / useCart
        ├── session.tsx       # SessionProvider / useSession
        ├── format.ts · styles.css · main.tsx · App.tsx
        ├── setupTests.ts     # cp4: doble de IntersectionObserver, que jsdom no trae
        ├── components/       # *.test.tsx junto al componente que prueban
        └── pages/
```

Git: rama `main`, commits en inglés, un tag anotado al cerrar cada checkpoint.

---

## 3. Base común (antes del checkpoint 1)

**`docker-compose.yml`** — **todos los servicios que hay que levantar para que la aplicación
funcione**, no solo la base de datos. Es una regla del curso (§9.9): cuando un checkpoint
necesite un servicio nuevo, se añade a este mismo fichero en ese mismo checkpoint, con su
healthcheck y su `depends_on`. En la base son tres, y arrancan en este orden:

- `db`: `postgres:16-alpine`, healthcheck `pg_isready`, puerto `5432:5432` (solo desarrollo).
  Los datos en un **bind mount**, `./data/postgres`, para que se vea dónde se guardan.
  Consecuencia que va al README: **`docker compose down -v` ya no borra la base de datos**,
  porque `-v` solo elimina volúmenes con nombre; para empezar de cero se borra la carpeta.
  **Sin** `docker-entrypoint-initdb.d`: el esquema lo gestiona Alembic.
- `backend`: `build: ./backend`. `DATABASE_URL` con el host `db` (el nombre del servicio).
  Al arrancar ejecuta `alembic upgrade head` y después uvicorn. `depends_on` `db` en estado
  `service_healthy`; healthcheck contra `GET /health`.
- `frontend`: `build: ./frontend`, servidor de desarrollo de Vite en `5173:5173`.

El código va dentro de las imágenes (sin recarga en caliente). Para desarrollar con recarga
se levanta solo la base de datos con `docker compose up -d db`.

**`app/config.py`** — todo lo que se lee del entorno, en un solo fichero, para que la
respuesta a *«¿qué hay que configurar para desplegar esto?»* sea un fichero y no un `grep`:
`DATABASE_URL`, `CORS_ORIGINS` (lista separada por comas, por defecto el servidor de Vite) e
`IMAGES_DIR`.

**`app/db.py`** — `engine`, `SessionLocal`, y `get_db()` que abre una sesión por petición.
El `commit` lo hace el servicio, porque el servicio es quien sabe qué operaciones forman una
unidad (sesión 13).

**Alembic** — `alembic init alembic` dentro de `backend/`, y en `env.py`: la URL desde
`os.environ["DATABASE_URL"]`, `target_metadata = Base.metadata` y `compare_type=True`. En
`alembic.ini`, `file_template = %%(rev)s` para que `--rev-id 001_products` produzca
`versions/001_products.py`. El `--rev-id` legible permite mover **la base de datos** entre
checkpoints sin tocar Git.

**Frontend base**:
- `api.ts`: `request<T>(path, options?)`. Un solo sitio donde se añaden las cabeceras
  (`X-Cart-Token` desde cp2, `Authorization` desde cp3), se traduce el error a
  `{ status, detail }`, se trata el `204` sin cuerpo y se tira un token que el servidor
  rechaza con un `401`.
- `useData.ts`: `State<T>` (`loading` | `ready` | `error`) con la cancelación de respuestas
  obsoletas de la sesión 16.
- `format.ts`: `formatPrice(cents)` con `Intl.NumberFormat("en-IE")`; `formatDate(iso)`.

**Hecho cuando**: `docker compose up --build` desde cero deja los tres servicios `healthy`,
`GET /health` responde y Vite muestra la página vacía.
Commit `Base: compose, Alembic, FastAPI and Vite skeleton`.

---

## 4. Checkpoint 1 · Catálogo (`cp1-catalog`)

Cinco revisiones, y cada una enseña una cosa distinta sobre migraciones.

### 4.1 `001_products` · Una tabla con las reglas dentro

```python
class Product(Base):
    __tablename__ = "products"
    __table_args__ = (
        CheckConstraint("price_cents >= 0", name="ck_products_price_cents"),
        CheckConstraint("stock >= 0", name="ck_products_stock"),
    )
    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, server_default="")
    category: Mapped[str] = mapped_column(String(50), index=True)
    price_cents: Mapped[int]
    stock: Mapped[int] = mapped_column(server_default="0")
    image_url: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

Los `CheckConstraint` con nombre van en el modelo a propósito: así autogenerate los lleva a
la migración y **la regla vive en la base de datos**, que la protege por todos los caminos
—scripts, `psql`, la importación que alguien monte en dos años— y no solo por el del servicio.

**A mano**, al final del `upgrade()`: los datos de arranque con `op.execute("INSERT ...")`,
36 productos, 5 categorías (`laptops`, `monitors`, `peripherals`, `storage`, `networking`),
precios entre 999 y 149900 céntimos, 4 con `stock = 0`. Es la primera vez que aparece la frase
de §1.1: autogenerate creó la tabla y no puede crear los datos.

### 4.2 `001a` y `001b` · Migraciones que solo cambian datos

Las imágenes pasan de un sitio externo a ficheros servidos por la propia API
(`001a`, a `.svg` generados) y después a fotografías reales (`001b`, a `.jpg`). **El esquema
no cambia en ninguna de las dos**: `image_url` sigue siendo un `TEXT`. Autogenerate habría
generado un fichero vacío, así que las dos están escritas enteras a mano, con su `downgrade`.

Las imágenes se sirven con `StaticFiles` montado en `/images`, desde `data/images`, que es un
bind mount de solo lectura. Y la decisión que se explica en clase:

| Dónde | Qué hay | Por qué |
|---|---|---|
| Base de datos | `/images/product-1.jpg` | Ruta **relativa**: la misma fila vale en `localhost` y en producción |
| Respuesta de la API | `http://localhost:8000/images/product-1.jpg` | Dirección **completa**, construida con la dirección por la que llegó la petición |
| Frontend | `<img src={product.image_url}>` | No sabe nada de esto, y no debe saberlo |

`data/images` **sí** se sube a Git: es un dato de arranque igual que los productos. Si no
estuviera, la migración nombraría ficheros que nadie tendría (§10, demo de cp1).

### 4.3 `001c` y `001d` · Las categorías, en dos mitades (EXPAND-CONTRACT)

La categoría era texto repetido en cada producto; pasa a ser una tabla `categories` con
`products.category_id`. **El cambio se parte en dos migraciones, y esa es la lección**:

| Revisión | Qué hace | ¿Rompe el código que ya corre? |
|---|---|---|
| `001c_categories_expand` | Crea `categories`, la llena leyendo `SELECT DISTINCT` de los propios productos, y añade `category_id` **anulable** | **No.** La columna de texto sigue ahí y sigue siendo la que se lee |
| `001d_categories_contract` | Pone `category_id` obligatoria y **borra** la columna de texto | **Sí.** Todo lo que aún leyera `products.category` deja de funcionar |

Entre las dos hay un hueco: ahí se despliega el código nuevo y se comprueba que nadie usa la
columna vieja. Hacerlo en una sola migración significa un instante, durante el despliegue, en
que la base de datos ya cambió y el código no. Eso es una tienda caída.

Dos cosas que autogenerate no hizo bien y hay que corregir a mano:
1. La clave foránea sin nombre (avisa por escrito: *«constraint name is None; this directive will fail as rendered»*).
2. El `downgrade` de CONTRACT: genera `add_column` con `NOT NULL` y sin valor por defecto sobre una tabla con 36 filas, que PostgreSQL rechaza. El correcto son tres pasos: columna anulable, rellenarla siguiendo la clave foránea, y solo entonces exigir `NOT NULL`.

**La API no cambia**: `GET /products` sigue enviando `"category": "laptops"`, leído ahora de
la fila relacionada, y el filtro sigue siendo por nombre. El contrato con el navegador es
independiente del esquema. Lo que sí es nuevo es `GET /categories`, que el frontend usa para
pintar los botones en vez de llevar la lista escrita a mano.

Y una trampa del ORM que se mide, no se adivina: leer `product.category.name` de cada
producto son **N+1 consultas**. Se arregla con `joinedload(Product.category)` y se comprueba
contando consultas (§7.2).

### 4.4 Servicios y rutas

```python
def list_categories(db) -> list[Category]
def get_product(db, product_id) -> Product | None
def list_products(db, category: str | None, cursor: int, limit: int) -> tuple[list[Product], int | None]
```

`list_products` hace paginación **keyset**: `where(Product.id > cursor)`, filtro opcional por
nombre de categoría (con `join`), `order_by(Product.id).limit(limit + 1)`. Se pide una fila de
más para saber si hay página siguiente sin una segunda consulta ni un `COUNT(*)`.

| Ruta | Parámetros | Respuesta |
|---|---|---|
| `GET /products` | `category?`, `limit` = `Query(12, ge=1, le=100)`, `cursor` = `Query(0, ge=0)` | `200 {"items": [...], "next_cursor": <int o null>}` |
| `GET /products/{product_id}` | — | `200` producto · `404 {"detail": "Product 999 not found"}` |
| `GET /categories` | — | `200 [{"id": 1, "name": "laptops"}]`, sin paginar: son cinco |

`product_to_dict` es la decisión de «qué expone la API», no un volcado de la tabla:
`created_at` no sale, y `category` sale como nombre.

### 4.5 Frontend

- `pages/Catalog.tsx`: estado `items`, `nextCursor`, `loading`, `category`. Un
  `<div ref={sentinel} />` al final de la rejilla con un `IntersectionObserver`: cuando entra
  en pantalla, pide la página siguiente y **concatena**. Cambiar de categoría vacía la lista.
  Un contador `generation` descarta la respuesta que llega tarde para la categoría anterior.
- Las categorías se cargan con `useData` (una carga que **sustituye**), los productos no
  (cada página se **añade**). El contraste está en una sola pantalla y se comenta.
- `components/ProductCard.tsx`: `<img loading="lazy" width="400" height="300">`, nombre,
  precio, etiqueta `"Out of stock"` si `stock === 0`.
- `components/ProductModal.tsx`: al pinchar una tarjeta se abre el detalle con imagen,
  descripción, precio y el estado del stock. Es un `<dialog>` **nativo** con `showModal()`,
  para que el navegador ponga el fondo, el cierre con `Esc`, el foco atrapado y la vuelta del
  foco a la tarjeta. **No pide nada al servidor**: la descripción ya venía en el listado.

Dos mecanismos de carga perezosa, y se explican por separado: `loading="lazy"` retrasa **las
imágenes**; el `IntersectionObserver` retrasa **la petición de la página siguiente**.

### 4.6 Hecho cuando

- `alembic current` muestra `001d_categories_contract (head)`.
- `GET /products?limit=5` da 5 y un `next_cursor`; con ese cursor, los 5 siguientes sin solapar; la última página da `null`.
- `GET /products/999` → 404 con `detail`.
- En el navegador: 12 tarjetas, al bajar 12 más, luego las últimas 12; tres peticiones en la pestaña Red. Pinchar una tarjeta abre el detalle sin ninguna petición nueva.
- Una fila nueva en `categories` aparece como un botón más sin tocar código.
- Tag `cp1-catalog`.

---

## 5. Checkpoint 2 · Carrito y pedido (`cp2-cart`)

### 5.1 Modelos

```python
class Cart(Base):
    __tablename__ = "carts"
    # El identificador ES el token: aleatorio y largo. Con un número secuencial,
    # cambiarlo en el navegador enseñaría el carrito de otra persona.
    token: Mapped[str] = mapped_column(Text, primary_key=True)
    created_at: ...
    items: Mapped[list["CartItem"]] = relationship(back_populates="cart", cascade="all, delete-orphan")

class CartItem(Base):
    __tablename__ = "cart_items"
    __table_args__ = (CheckConstraint("quantity > 0", name="ck_cart_items_quantity"),)
    # Clave primaria compuesta: una fila por producto y carrito, sin duplicados posibles.
    cart_token: Mapped[str] = mapped_column(ForeignKey("carts.token", ondelete="CASCADE", name=...), primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", name=...), primary_key=True)
    quantity: Mapped[int]
    # Fíjate en lo que NO está: un precio. El carrito enseña el precio de HOY.

class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (CheckConstraint("total_cents >= 0", name="ck_orders_total_cents"),)
    id, customer_email, status (server_default "paid"), total_cents, created_at, items

class OrderItem(Base):
    __tablename__ = "order_items"
    __table_args__ = (CheckConstraint("quantity > 0", name="ck_order_items_quantity"),)
    order_id, product_id  # clave primaria compuesta
    quantity: Mapped[int]
    # Y aquí SÍ hay precio: el del momento de la compra.
    price_cents: Mapped[int]
```

El contraste `CartItem` sin precio / `OrderItem` con precio es **la** lección del checkpoint.

### 5.2 `002_cart_and_orders`

Todo sale de autogenerate; **nada a mano**, y también eso se comenta: esta migración solo crea
tablas vacías, y vacío es el estado inicial correcto para un carrito y para un pedido.

### 5.3 Esquemas de entrada y servicios

```python
class QuantityIn(BaseModel):
    quantity: int = Field(ge=1)   # cantidad cero no existe: quitar una línea es DELETE
```

```python
def create_cart(db) -> Cart                                   # token = secrets.token_urlsafe(32)
def get_cart(db, token) -> Cart | None                        # carga líneas y productos de golpe
def set_cart_item(db, cart, product_id, quantity) -> Cart | None
def remove_cart_item(db, cart, product_id) -> bool
def cart_total_cents(cart) -> int
def create_order(db, cart, user) -> Order                     # el `user` llega en cp3
def get_order(db, order_id, user) -> Order | None
```

- `set_cart_item`: `None` si el producto no existe; `ValueError("Insufficient stock for 27\" Monitor: 0 left, 3 requested")` si `quantity > product.stock` (respuesta inmediata al usuario; **la comprobación que vale es la del checkout**); si no, UPSERT con `on_conflict_do_update`.
- `create_order`, **una sola transacción**, en este orden:
  1. Sin líneas → `ValueError("The cart is empty")`.
  2. Cargar los productos con `with_for_update()` **y `order_by(Product.id)`**: lo primero impide que dos compradores pasen a la vez por la última unidad (sesión 14); lo segundo hace que todos los checkouts tomen los bloqueos en el mismo orden, que es lo que evita que se bloqueen entre ellos.
  3. Validar **todas** las líneas contra el stock; una falla → `ValueError` y no se ha tocado nada.
  4. Solo entonces: descontar stock, crear `Order` con `total_cents` calculado aquí, crear cada `OrderItem` con `price_cents = product.price_cents`, borrar el carrito. `commit`.

### 5.4 Rutas

El token del carrito viaja en la cabecera `X-Cart-Token`, nunca en la ruta: una dirección que
aparece en la barra del navegador acaba pegada en un chat, y entonces es el carrito de otro.

| Ruta | Cabecera / cuerpo | Respuesta |
|---|---|---|
| `POST /cart` | — | `201` carrito vacío |
| `GET /cart` | `X-Cart-Token` | `200` carrito · `404` |
| `PUT /cart/items/{product_id}` | `X-Cart-Token` · `QuantityIn` | `200` carrito · `404` producto o carrito · `409` stock |
| `DELETE /cart/items/{product_id}` | `X-Cart-Token` | `200` carrito · `404 "Product 7 is not in the cart"` |
| `POST /orders` | `X-Cart-Token` · **sin cuerpo** | `201` pedido, cabecera `Location` · `409` carrito vacío o stock |
| `GET /orders/{order_id}` | — | `200` pedido · `404 "Order 42 not found"` |

`PUT` **fija** la cantidad (idempotente: repetirlo por un reintento no duplica) y `DELETE`
quita la línea: cada verbo hace lo que su nombre dice, que es la lección de la sesión 11.

`POST /orders` **no lleva cuerpo**: no hay nada que el cliente deba decidir. Precios, total y
comprador los pone el servidor.

### 5.5 Frontend

- `react-router-dom` con rutas `/`, `/cart`, `/orders/:id`. **No hay `/products/:id`**: el detalle es el modal de cp1, y la tienda mantiene una sola forma de enseñar un producto.
- El carrito vive en un `CartProvider` (`src/cart.tsx`) y todas las pantallas lo leen con `useCart`, para que nadie guarde una segunda copia que se desincronice. Lo que se pinta es **siempre la última respuesta del servidor**, nunca un total calculado en el navegador.
- Token en `localStorage["cart_token"]`; al arrancar, `GET /cart` y si da 404 se borra. El carrito **se crea al añadir el primer producto**, no al cargar la página: quien solo mira no deja una fila en la base de datos.
- `Header`: enlace `Cart (n)`. `ProductCard` y el modal: botón `"Add to cart"` (deshabilitado sin stock).
- `pages/Cart.tsx`: tabla con `−` / `+`, `"Remove"`, subtotal, total y `"Place order"`.
- Lo que el carrito no pueda hacer se enseña en **un solo aviso** sobre la página, porque añadir desde el catálogo y pagar desde el carrito fallan igual.

### 5.6 Hecho cuando

- Por curl: `POST /cart` → `PUT` → `PUT` → `DELETE` → `GET /cart` → `POST /orders` → `GET /orders/1`. El stock baja.
- `PUT` dos veces con la misma cantidad deja el carrito igual.
- `UPDATE products SET price_cents = 1 WHERE id = 1;` tras el pedido: `GET /orders/1` mantiene el precio original.
- Pedido con una línea servible y otra sin stock → 409 y **ningún** stock cambia, y el carrito sigue ahí.
- Dos carritos con la última unidad pagando a la vez → un `201`, un `409`, y stock final 0, nunca −1.
- Tag `cp2-cart`.

---

## 6. Checkpoint 3 · Usuarios, direcciones y el dueño del pedido (`cp3-users`)

### 6.1 `003_users` · La cuenta

```python
class User(Base):
    __tablename__ = "users"
    id, email (String(200), unique), password_hash (Text), full_name, created_at

class UserSession(Base):        # "Session" chocaría con sqlalchemy.orm.Session
    __tablename__ = "sessions"
    token: Mapped[str] = mapped_column(Text, primary_key=True)   # misma idea que el carrito
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE", name=...), index=True)
    expires_at: Mapped[datetime]   # una sesión eterna es una contraseña que nunca caduca
```

**La tabla tiene `password_hash` y no tiene ningún sitio donde quepa una contraseña.** Eso no
es un olvido, es el diseño, y es lo primero que se enseña al abrir el fichero.

`security.py`, solo librería estándar: `hash_password` con `hashlib.scrypt` y sal de
`os.urandom(16)` por usuario, guardado como `"scrypt$<sal_hex>$<hash_hex>"` para que el
algoritmo viaje con la fila y se pueda reconocer el día que cambie; `verify_password` con
`hmac.compare_digest`, que no delata por el tiempo cuánto acertó el intento. Comentario: en
producción, `bcrypt` o `argon2`.

Tres cosas que la respuesta **no** debe revelar, y las tres se comprueban:
1. `password_hash` no sale en ninguna respuesta de la API, nunca.
2. Acceso fallido: **el mismo mensaje** (`"Invalid email or password"`) exista o no el email.
3. Y **el mismo tiempo**: si el email no existe se hace igualmente el trabajo de hasheo contra un hash de descarte, porque si no, «este correo no está registrado» se contesta antes y eso basta para averiguar quién compra aquí.

`register_user` deja que decida la restricción `unique` y captura `IntegrityError`, en vez de
preguntar antes: entre la pregunta y el `INSERT` hay un hueco en el que dos personas pasan.

| Ruta | Cuerpo / cabecera | Respuesta |
|---|---|---|
| `POST /users` | `UserIn` (email, password ≥ 8, full_name) | `201` usuario · `409` email ya registrado |
| `POST /login` | `LoginIn` | `200 {"token": "..."}` · `401` |
| `POST /logout` | Bearer | `204`, y **borra la fila**: el token deja de valer en todas partes, no solo en ese navegador |
| `GET /me` | Bearer | `200` usuario · `401` |

### 6.2 `003a` y `003b` · Direcciones con histórico

**La decisión de modelado.** El tipo de dirección es una **columna** de la propia fila,
`is_billing`, y no una fila en otra tabla de tipos: dos tipos fijos que el código tiene que
conocer igualmente no justifican un `join`. Una tabla aparte se ganaría el sueldo si los tipos
llevaran datos propios o se pudieran añadir sin desplegar.

Y la segunda decisión, que resuelve lo mismo que el precio congelado: **las direcciones no se
editan**. Cambiar una retira la fila en uso y escribe otra.

```python
class Address(Base):
    __tablename__ = "addresses"
    __table_args__ = (
        # Único ÍNDICE PARCIAL: única sobre (user_id, is_billing) pero solo WHERE is_active.
        # Una de cada en uso, y todas las retiradas que hagan falta.
        Index("uq_addresses_one_active", "user_id", "is_billing",
              unique=True, postgresql_where=text("is_active")),
    )
    id, user_id (FK ondelete CASCADE, index)
    is_billing: Mapped[bool]   # el tipo, como columna
    is_active: Mapped[bool]    # la que se usa ahora
    recipient_name, street, city, postal_code, country (String(2), ISO 3166-1)
```

`is_active` **no sale en la API**: que alguien siga usando una dirección es asunto suyo, y al
pedido no le afecta. «Borrar» una dirección la retira, no borra la fila, porque un pedido
puede apuntar a ella.

| Ruta | Respuesta |
|---|---|
| `GET /me/addresses` | `200` solo las que están en uso |
| `PUT /me/addresses/{kind}` | `kind` es un `Literal["shipping","billing"]`, así que FastAPI rechaza cualquier otra cosa con `422` antes de que corra nada nuestro |
| `DELETE /me/addresses/{kind}` | `204` · `404` si no había ninguna en uso |

**El `id` de una dirección no aparece en ninguna ruta.** Todo se resuelve desde la sesión, así
que no hay número que cambiar para llegar a la dirección de otra persona.

El `downgrade` de `003b` es el segundo que autogenerate escribe mal: el esquema anterior solo
admite una dirección por persona y tipo, y para entonces ya hay retiradas. La versión
corregida borra las retiradas primero **y dice que eso destruye información**, porque el
esquema viejo no tiene dónde guardarla.

### 6.3 `003c_orders_user` · El pedido tiene dueño

**No hay pedidos anónimos.** `POST /orders` y toda lectura de pedidos exigen sesión, y un
pedido de otra persona responde `404` (§0.2). Un pedido sin dirección de envío también se
rechaza, con `409`: tiene que saber a dónde va.

`orders` gana `user_id` y `shipping_address_id`, y lo interesante de la revisión es **lo que
no hace**: no pone `user_id` como `NOT NULL`, porque los pedidos anteriores a esta regla no
tienen dueño y las únicas salidas serían inventarle uno o borrar pedidos de verdad. En su
lugar:

```sql
ALTER TABLE orders ADD CONSTRAINT ck_orders_user_id_required
CHECK (user_id IS NOT NULL) NOT VALID;
```

`NOT VALID` la aplica a **todo lo que se escriba a partir de ahora** y no revisa lo que ya
estaba. Es además la técnica con la que se añade una restricción a una tabla enorme sin
bloquearla durante un recorrido completo, y se valida después con `VALIDATE CONSTRAINT`.
Alembic no autogenera restricciones `CHECK`, así que esta va a mano.

`customer_email` se mantiene aunque el usuario ya se conozca: congela el correo del día del
pedido (§0.5).

### 6.4 Frontend

- Segundo contexto, `src/session.tsx` (`SessionProvider` / `useSession`): `user`, `addresses`, `signIn`, `register`, `signOut`, `saveAddress`, `removeAddress`. Token en `localStorage["auth_token"]`; `request` añade `Authorization: Bearer` si existe y lo borra ante un `401`.
- Las direcciones viven en la sesión, no en la página: la cuenta y el carrito las necesitan y dos copias se desincronizarían.
- `components/AccountMenu.tsx`: un **botón desplegable** en la cabecera, con `aria-expanded` y `aria-haspopup`, que se cierra con `Esc`, al pinchar fuera y al elegir una opción.
- `pages/Auth.tsx`: los dos formularios, acceso y registro, en la misma página; cuál se muestra va en la dirección. Registrarse inicia sesión.
- `components/PasswordField.tsx` — **todo lo que hoy es estándar para una contraseña**, en un sitio:
  - El campo es **no controlado**. Un `<input value={...}>` controlado hace que React escriba el texto en el **atributo** `value` del DOM, y entonces cualquier cosa que serialice el DOM (un grabador de sesión, un informe de error, una extensión) se lleva la contraseña en claro. Se lee del elemento al enviar y se borra después. No pasa nunca por el estado de React.
  - Enmascarada por defecto, con botón **Show/Hide** (`type="button"`, `aria-pressed`).
  - `autocomplete="username"` en el correo y `"current-password"` / `"new-password"` en la contraseña: es lo que hace que un gestor guarde y rellene bien.
  - Aviso de **Caps Lock**, sin corrector ni autocorrección, y tipografía monoespaciada.
  - Un `<form>` de verdad, y la contraseña en el cuerpo de un `POST`, nunca en la URL.
- `pages/Account.tsx`: datos, los dos formularios de dirección (con un botón *«Copy from shipping»*, que es donde se ve lo que cuesta guardar el tipo en la fila: usar la misma dirección para las dos cosas guarda las mismas líneas dos veces) y **la lista de pedidos**.
- `pages/Cart.tsx`: con sesión, enseña la dirección a la que va el pedido; sin sesión o sin dirección, el botón se deshabilita y dice cuál de las dos cosas falta.

### 6.5 Hecho cuando

- Registro, acceso, `GET /me`, cerrar sesión y ver que la fila de `sessions` desapareció.
- Contraseña incorrecta y email inexistente: mismo mensaje y mismo tiempo.
- Dos usuarios con la misma contraseña tienen hashes distintos.
- Pedido hecho, luego cambiar la dirección: el pedido sigue enseñando la antigua y la cuenta la nueva.
- `POST /orders` sin token → 401. Pedido de otra persona → 404. Pedido sin dirección → 409.
- La cuenta lista los pedidos propios y solo los propios.
- Tag `cp3-users`.

---

## 7. Checkpoint 4 · Tests (`cp4-tests`)

**Sin migración.** Este checkpoint no añade funcionalidad: la sujeta.

### 7.1 La regla: qué se testea y qué no

> **Se testea lo que se rompería en silencio.**

No es una cifra de cobertura. Un porcentaje objetivo hace que la gente escriba tests de
*getters* para subirlo, y esos tests no han encontrado un fallo en su vida.

| Se testea | No se testea |
|---|---|
| Las reglas que hemos escrito nosotros: stock, precios, propiedad, paginación | Que SQLAlchemy sepa hacer un `SELECT` |
| Lo que falla **sin dar error**: un N+1, una contraseña en el DOM, un pedido que cambia de precio | Que Pydantic valide un email (tiene sus propios tests) |
| Lo que solo se ve al concurrir o al migrar hacia atrás | El CSS, los textos exactos, el color de un botón |
| Los códigos HTTP que documenta §0.2, porque son el contrato | Funciones de una línea que solo devuelven un campo |

Y la fuente de la lista de tests no hay que inventarla: **son los «Hecho cuando» de cp1, cp2 y
cp3**, que hasta ahora se comprobaban a mano una y otra vez.

### 7.2 Backend: de comprobación manual a test

| Viene de | Test | Qué protege |
|---|---|---|
| cp1 | Dos páginas seguidas con `cursor` no se solapan ni se saltan filas; la última da `next_cursor: null` | La paginación keyset |
| cp1 | `GET /products/999` → 404 con `detail` | El contrato de errores |
| cp1 | Filtrar por nombre de categoría sigue funcionando | Que el cambio de esquema no rompió la API |
| cp1 | **Contar consultas**: una página de 12 productos con sus categorías es **1** consulta | El N+1, que es invisible leyendo el código |
| cp2 | `PUT` dos veces con la misma cantidad deja el carrito igual | La idempotencia |
| cp2 | Pedir más unidades de las que hay → 409 y stock intacto | La regla de stock |
| cp2 | Cambiar el precio después del pedido: el pedido no cambia | **El precio congelado** |
| cp2 | Pedido con una línea servible y otra sin stock → 409 y **ningún** stock se mueve | Todo o nada |
| cp2 | Dos compradores a la vez por la última unidad → un 201, un 409, stock 0 | La carrera (§7.5) |
| cp3 | Email desconocido y contraseña incorrecta dan el mismo mensaje | No revelar quién está registrado |
| cp3 | Ninguna respuesta de la API contiene `password_hash` ni la contraseña | Que el hash no se escape |
| cp3 | Dos usuarios con la misma contraseña tienen hashes distintos | La sal |
| cp3 | Una sesión caducada da 401 aunque su fila exista | Que manda la fecha, no la fila |
| cp3 | `POST /orders` sin token → 401; el pedido de otro → **404**, no 403 | Que no haya pedidos anónimos ni ajenos |
| cp3 | Guardar una dirección crea una fila nueva y el pedido sigue apuntando a la vieja | **La dirección congelada** |
| cp3 | Una segunda dirección activa del mismo tipo es rechazada | El índice parcial |

### 7.3 Herramientas y estructura

```
backend/
├── requirements-dev.txt       # pytest, httpx
└── tests/
    ├── conftest.py            # fixtures: base de datos, sesión, cliente, usuario con dirección
    ├── test_catalog.py
    ├── test_cart.py
    ├── test_orders.py
    ├── test_auth.py
    ├── test_addresses.py
    ├── test_concurrency.py    # el que necesita dos conexiones de verdad
    └── test_migrations.py     # el que necesita su propia base de datos
```

Los tests de la API van contra el `TestClient` de FastAPI (que por debajo es `httpx`), no
contra un servidor levantado: es más rápido y no depende de que nadie arranque nada.

### 7.4 La base de datos de tests

Una base **aparte**, `shop_test`, nunca la de desarrollo: un test que borra una tabla no puede
llevarse por delante los datos con los que se está dando clase.

- Una vez por sesión de pytest: crear la base si no existe y `alembic upgrade head`. Así los tests corren contra **el esquema que producen las migraciones**, no contra uno creado con `create_all`, que es una forma silenciosa de que las migraciones dejen de ser ciertas.
- Por test: abrir una transacción y hacer **rollback** al terminar. Cada test empieza con los mismos 36 productos y sin usuarios, y no hay que borrar nada a mano.
- Los datos de arranque (los 36 productos) vienen de la propia migración, así que no hay que duplicarlos en un fixture.

Dos excepciones que hay que explicar, porque son justo los casos donde el truco del rollback
no sirve:

### 7.5 El test de concurrencia

Dos compradores a por la última unidad tienen que estar en **dos transacciones de verdad**, con
dos conexiones, y confirmando. Si todo el test vive dentro de una transacción que se deshace,
no hay concurrencia que medir: sería una sola transacción hablando consigo misma.

Así que este test crea sus datos, los **confirma**, lanza los dos checkouts, comprueba que
hay exactamente un `201` y un `409` y que el stock acaba en 0, y limpia lo suyo al final.

### 7.6 El test de migraciones, que es el más rentable

Sobre una base vacía y propia:

1. `alembic upgrade head` — todas las revisiones aplican en orden.
2. `alembic downgrade base` — **todas deshacen**.
3. `alembic upgrade head` otra vez.
4. Y con datos dentro: bajar un escalón y volver a subirlo, comprobando que lo que tenía que sobrevivir sobrevivió.

Este test solo habría tardado unos segundos en escribirse y **habría cazado los tres fallos de
`downgrade` que aparecieron a mano** (§10). Merece decirlo en clase tal cual: el test más
aburrido del proyecto es el que más ha encontrado.

Además, un test que corre `alembic revision --autogenerate` y comprueba que **no genera nada**:
si alguien cambia un modelo y se olvida de la migración, salta aquí y no en producción.

### 7.7 Frontend: pocos y elegidos

Con `vitest` y `@testing-library/react`. Se prueba **comportamiento**, nunca la forma:

1. **`PasswordField` no deja la contraseña en el DOM.** Escribir en el campo y comprobar que `input.getAttribute("value")` es `null` y que la contraseña no aparece en `document.body.innerHTML`. Este test existe porque ese fallo **fue real** y solo se vio mirando el HTML.
2. **`Catalog` concatena páginas y descarta la respuesta obsoleta.** Con el `fetch` simulado: pedir la página 2 y ver que se añade a la 1; cambiar de categoría con una respuesta lenta en vuelo y ver que la lenta no pinta nada.
3. **El botón de comprar está deshabilitado sin sesión o sin dirección**, y dice cuál falta.

No se prueban `formatPrice` ni el `Header`: no tienen ninguna forma de romperse en silencio.

### 7.8 De extremo a extremo: pocos, y sin navegador

Una tercera capa, en `e2e/`, contra la tienda **realmente levantada**. Solo HTTP y SQL: no se automatiza
un navegador. Lo que se gana con un navegador —que los componentes reaccionen— ya lo cubre §7.7; lo que
**solo** se puede ver con todo encendido es que las piezas estén conectadas, y para eso basta con hablar
por la red.

La regla que las hace distintas, y hay que decirla en voz alta:

> **Ninguno importa la aplicación.** Ni un solo `from app import ...`.

Un test que importa el código que prueba puede pasar mientras los contenedores están mal conectados, las
migraciones no se han ejecutado o el CORS apunta a otra dirección.

Qué cazan que las otras dos capas no pueden:

- Que el **CORS** nombre la dirección desde la que se sirve el frontend de verdad. Bien en el fichero y
  mal en el entorno es una tienda que a `curl` le parece perfecta y en un navegador no funciona.
- Que la petición **OPTIONS** previa al `PUT` se conteste; si no, no se puede añadir nada al carrito.
- Que las **imágenes** que la API promete se puedan descargar: el volumen está montado de verdad.
- Que las **migraciones** se hayan aplicado en la base real al arrancar.
- Que el **frontend** se esté sirviendo.

Escriben en la base de datos de desarrollo, porque es la que usa la tienda. Así que traen **su propio
producto y su propio cliente**, y se los llevan al terminar: el stock de los 36 de siempre no se toca.
Si no hay nada levantado se **saltan** con un mensaje que lo explica; pero un backend que responde con el
frontend caído es media tienda desplegada, y eso **falla**.

### 7.9 La pirámide, con los números de este proyecto

| Capa | Cuántos | Qué prueba | Cuando falla |
|---|---|---|---|
| Backend | 128 | Las reglas | Rápido, y señala la línea |
| Frontend | 24 | Lo que se rompe en silencio | Rápido |
| Extremo a extremo | 15 | Que las piezas encajan | Lento, y dice «algo falla» sin decir dónde |

Al subir en la tabla los tests son más lentos, más frágiles y más vagos al fallar. Por eso arriba hay
quince y no doscientos: **solo sube lo que no se puede comprobar más abajo**. Es el argumento de la
sesión 7 con cifras propias en vez de con un dibujo.

### 7.10 Cómo se ejecutan

```bash
cd backend && .venv/Scripts/activate && pytest -q
```

```bash
cd frontend && npm test
```

```bash
docker compose up -d && cd e2e && ../backend/.venv/Scripts/python -m pytest
```

Y en el README, la razón de que no haya CI: está fuera de alcance (§0.6), así que los tests
se ejecutan a mano antes de cada tag. La regla §9.5 pasa a incluirlos.

### 7.11 Hecho cuando

- `pytest` pasa entero, desde una base `shop_test` que no existía.
- Cada uno de los «Hecho cuando» de cp1, cp2 y cp3 tiene un test que lo comprueba.
- **La prueba de la prueba**: estropear a propósito una regla (quitar el `joinedload`, quitar el `with_for_update`, devolver 403 en vez de 404, hacer que `save_address` haga `UPDATE`) hace fallar exactamente un test, y el mensaje dice cuál es el problema. Un test que no falla al romper lo que vigila no vigila nada.
- `npm test` pasa los tres tests del frontend.
- Tag `cp4-tests`.

---

## 8. Checkpoint 5 · Histórico de precios con trigger (`cp5-price-history`)

### 8.1 La idea

Si el histórico lo escribe la aplicación, cualquier cambio de precio que no pase por ella (un
`UPDATE` en psql, un script, otro sistema) se lo salta. Aquí la garantía se mueve **a la base
de datos**: da igual por dónde cambie el precio. Y es la última vuelta de tuerca a §1.1,
porque Alembic **no ve funciones ni triggers**.

### 8.2 Modelo

```python
class ProductPriceHistory(Base):
    __tablename__ = "product_price_history"
    __table_args__ = (Index("ix_product_price_history_product", "product_id", "changed_at"),)
    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE", name=...))
    previous_price_cents: Mapped[int]
    price_cents: Mapped[int]
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

Se guarda el precio anterior y el nuevo porque una fila registra **una transición**; así no
hace falta una fila inicial artificial.

### 8.3 Revisiones `004_price_history` y `004a_price_trigger`

**Dos revisiones y no una.** La tabla se hizo primero y sola: `004` crea `product_price_history`
y su índice, y **nada la escribe todavía**. Dejar ese hueco a la vista es lo que convierte
"¿quién rellena esto?" en una pregunta de clase. Cuando llegó el trigger, `004` ya estaba
aplicada, y editar una migración aplicada es justo lo que §10 dice que no se hace nunca.

`004` salió **entera de autogenerate**, por segunda vez en el proyecto tras `002`, y por el
mismo motivo: solo crea una tabla vacía. Tampoco apareció el aviso `constraint name is None`,
porque esta vez la clave foránea lleva su nombre puesto en el modelo.

`004a` es lo contrario: **cada línea escrita a mano**, y lo que produjo `--autogenerate`
es la lección del checkpoint:

```python
def upgrade() -> None:
    pass    # <- esto es todo. Ni error, ni aviso.
```

Un trigger no está en los modelos ni es algo que Alembic compare, así que no hay nada que
decir. **No es el esquema que compara ni los datos que ignora: es una tercera categoría que
no sabe que existe.**

A mano, en `upgrade()`:

```python
op.execute("""
-- La función: QUÉ hacer. OLD y NEW son la fila antes y después del UPDATE.
CREATE FUNCTION record_price_change() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    INSERT INTO product_price_history (product_id, previous_price_cents, price_cents)
    VALUES (NEW.id, OLD.price_cents, NEW.price_cents);
    RETURN NEW;
END;
$$;
""")
op.execute("""
-- El trigger: CUÁNDO hacerlo. Solo al cambiar price_cents, y solo si de verdad cambia.
CREATE TRIGGER trg_products_price_change
AFTER UPDATE OF price_cents ON products
FOR EACH ROW
WHEN (OLD.price_cents IS DISTINCT FROM NEW.price_cents)
EXECUTE FUNCTION record_price_change();
""")
```

Los tres calificadores se ganan su sitio: `AFTER` registra solo lo confirmado, `OF price_cents`
evita que reponer stock escriba en el histórico de **precios**, y el `WHEN` evita que guardar
el mismo precio cuente como cambio. `IS DISTINCT FROM` y no `<>`, que con nulos responde
`NULL` y dejaría agujeros el día que la columna admita nulos.

**PENDIENTE DE DECIDIR:** el plan traía tres `UPDATE` de precio desde la propia migración,
para que el histórico no empezara vacío. No se han hecho. A favor: la pantalla del §8.4
tiene algo que enseñar sin que nadie toque nada. En contra: es una migración cambiando
precios del catálogo. Sin ellos, los 36 productos empiezan con histórico vacío.

Y en `downgrade()`:

```python
op.execute("DROP TRIGGER trg_products_price_change ON products")
op.execute("DROP FUNCTION record_price_change()")
```

El trigger **antes** que la función, porque PostgreSQL se niega a borrar una función de la
que algo depende.

**El punto de clase, corregido después de reproducirlo.** Este plan decía que sin esas dos
líneas el `downgrade` *falla*. **No falla.** Las dos revisiones se deshacen informando de
éxito, la tabla desaparece y el trigger y la función se quedan vivos. El fallo llega
después, en otro momento y a otra persona, con el primer cambio de precio:

```
ERROR:  relation "product_price_history" does not exist
CONTEXT:  PL/pgSQL function record_price_change() line 3
```

Y la tienda sigue **leyendo** perfectamente, así que el catálogo parece sano y solo se rompe
al escribir un precio. Es el cuarto `downgrade` roto del proyecto y el único que no se
anuncia: no es una migración rota, es una mina.

El test de §7.6 sí lo caza, y **falla en el `upgrade` siguiente** con
`DuplicateFunction: function "record_price_change" already exists` — el sitio donde algo
explota no es el sitio donde está el error.

### 8.3b Que `--autogenerate` sí vea el trigger: `alembic_utils`

Sin ayuda, la comprobación de deriva de §7.6 contesta `[]` **con el trigger puesto y con el
trigger borrado a mano**: no es silencio, es una aprobación. Con `alembic-utils==0.8.8`, la
función y el trigger se declaran en `alembic/env.py` como `PGFunction` y `PGTrigger` y se
registran con `register_entities()`. A partir de ahí autogenerate emite
`create_entity` / `replace_entity` / `drop_entity`, y el `downgrade` que escribe solo pone el
trigger antes que la función — el fallo de arriba, resuelto por defecto.

Instalarlo **rompió** el test de deriva (`KeyError: 'include_schemas'`): su comparador queda
registrado para todo el proceso y ese test llamaba a `compare_metadata()` sin esa opción.
Añadirla es también la mejora, porque desde entonces la comprobación cubre las entidades.

Aviso: las declaraciones viven en `env.py`, que ejecuta migraciones al importarlo, así que
nadie más puede importarlo. El test solo las ve porque su fixture ha ejecutado `env.py`
antes en el mismo proceso — funciona por accidente. Sacarlas a un módulo propio lo haría
explícito.

### 8.4 Servicios, rutas y frontend

```python
def list_price_history(db, product_id) -> list[ProductPriceHistory] | None   # None si el producto no existe
```

Un producto inexistente devuelve `None` (404), no lista vacía: dos situaciones distintas,
dos respuestas distintas. Elegir el código de estado es decidir **qué puede distinguir
quien llama** — y en §6 se tomó la decisión contraria a propósito, porque allí no
queríamos que distinguiera "no es tuyo" de "no existe".

| Ruta | Cuerpo | Respuesta |
|---|---|---|
| `GET /products/{id}/price-history` | — | `200 [{changed_at, previous_price_cents, price_cents}]`, del más antiguo al más reciente; `200 []` si nunca cambió · `404` |

**Y ninguna ruta más. Decisión tomada: el precio no se cambia por el API.**

Este plan traía un `PATCH /products/{id}` y un servicio `change_price`. No entran, y el
motivo no es falta de tiempo: **esta tienda no tiene interfaz de gestión de productos**. El
catálogo se administra contra la base de datos, y eso convierte el API en un API de *venta*,
solo de lectura sobre el catálogo.

La consecuencia es la que sostiene todo el checkpoint, y conviene decirla así en clase:

> Con la gestión hecha contra la base de datos, **ningún cambio de precio pasa jamás por la
> aplicación**. Un histórico escrito en Python no se perdería "algunos" cambios: no
> registraría **ninguno**. El trigger deja de ser la opción elegante y pasa a ser la única
> que existe.

De paso desaparece la deuda que el plan iba a contraer: ya no hay un endpoint que cambie
precios sin autenticación mientras `POST /orders` exige sesión.

`components/PriceHistory.tsx`: `useData(() => getPriceHistory(id))`; vacío →
`"This product has not changed price yet."`; tabla `Date · Before · After`. Se monta en el
modal de detalle, debajo de la descripción.

### 8.5 Tests que añade (cp4 ya existe, así que llegan con él)

- Un `UPDATE` del precio en SQL directo, **sin pasar por la aplicación**, crea una fila.
  Con la gestión hecha contra la base de datos, esto no es un caso raro: es el único caso.
- El mismo precio otra vez no crea ninguna. Un `UPDATE` del stock tampoco.
- El histórico se lee en orden aunque dos cambios compartan `changed_at`, porque `now()` es
  el inicio de la **transacción** y el desempate lo pone el `id`.
- El `downgrade` de `004a` funciona (que es donde el test de §7.6 gana su sueldo).

### 8.6 Hecho cuando

- En psql: `UPDATE products SET price_cents = 74900 WHERE id = 1;` → fila nueva. El mismo `UPDATE` otra vez → nada. `UPDATE ... SET stock = 99` → nada.
- `GET /products/999/price-history` → 404; producto sin cambios → `200 []`.
- `alembic downgrade 003c_orders_user` funciona (trigger y función se van, en ese orden) y `upgrade head` los devuelve.
- `--autogenerate` con el trigger borrado a mano genera `create_entity`; con todo en su sitio, una migración vacía.
- Ninguna ruta cambia un precio: el catálogo se administra contra la base de datos.
- Tag `cp5-price-history`.

---

## 9. Orden de trabajo y reglas de implementación

1. Sección 3 (base común). Comprobar `/health`, `alembic current` y Vite. Commit.
2. Para cada checkpoint: modelos → `alembic revision --autogenerate --rev-id ...` → **leer** lo generado y completar a mano → `alembic upgrade head` → esquemas de entrada → servicios → rutas → probar con curl → frontend → README → commit → tag.
3. **Leer la salida de Alembic**, no solo mirar si terminó. Los avisos aparecen entre diez líneas de `INFO` y todo el mundo se los salta; uno de los tres fallos del proyecto estaba escrito ahí.
4. Antes de cada tag: `docker compose down`, borrar `data/postgres` y `docker compose up -d --build` deja todos los servicios `healthy` y aplica las revisiones desde cero; y `alembic downgrade base && alembic upgrade head` también.
5. Antes de cada tag, **desde cp4**: `pytest` y `npm test` pasan enteros.
6. Antes de cada tag: `alembic revision --autogenerate -m "check"` sobre la base al día **no genera ningún cambio**. Borrar el fichero vacío que genera.
7. No adelantar nada de un checkpoint posterior.
8. **Revisión de clases antes de cada tag**: en `backend/app` solo hay clases en `models.py` (una por tabla, más `Base`) y en `schemas.py` (una por cuerpo de petición). En `frontend/src`, `grep -rn "class " frontend/src` no debe devolver nada.
9. **Revisión de idioma antes de cada tag**: `grep -rniE "producto|carrito|pedido|usuario|direccion|precio|sesion" backend/app backend/alembic/versions frontend/src` no debe devolver nada.
10. **Todos los servicios, en `docker-compose.yml`**: si un checkpoint introduce un servicio nuevo, se añade en ese mismo checkpoint con su healthcheck, su `depends_on` y, si guarda datos, su bind mount visible (y esa carpeta en `.gitignore`). Nadie debe tener que arrancar nada aparte.
11. **Probar la API, no solo la pantalla.** Los dos agujeros de seguridad del proyecto (crear pedidos sin sesión y leer el pedido de cualquiera) se encontraron llamando a la API con `curl`, no leyendo el código ni mirando el navegador.

---

## 10. Guion de demo por checkpoint

**cp1** — `models.py` y la revisión `001` lado a lado: qué generó Alembic y qué se añadió a
mano. `\d products` en psql. `GET /products?limit=5` dos veces con el cursor. Navegador con la
pestaña Red: bajar, ver las tres peticiones y las imágenes llegando; pinchar una tarjeta y ver
que el detalle **no pide nada**. Insertar una categoría en psql y ver aparecer el botón. Y las
revisiones `001c`/`001d` abiertas juntas: dónde está el hueco entre EXPAND y CONTRACT.

**cp2** — `CartItem` sin precio y `OrderItem` con precio, lado a lado. Hacer un pedido,
cambiar el precio en psql, volver a `GET /orders/1`. Pedir más unidades de las que hay: 409 y
stock intacto. `PUT` dos veces: mismo resultado. Y la carrera, que necesita dos terminales.

**cp3** — Registrar y mirar `password_hash` en psql; registrar a dos personas con la misma
contraseña y comparar. Equivocarse de contraseña y probar un email que no existe: mismo
mensaje. En el navegador, con las herramientas abiertas: escribir en el campo de contraseña y
comprobar que no está en el HTML. Comprar, **mudarse**, y volver al pedido. Y pedir el pedido
de otra persona: 404.

**cp4** — Ejecutar `pytest` una vez. Y después **romper cosas a propósito** delante de la
clase, que es la parte que se recuerda: quitar el `joinedload` y ver fallar el test de
consultas; quitar el `with_for_update` y ver fallar el de concurrencia; cambiar un 404 por un
403 y ver fallar el de propiedad. Un test que no falla al romper lo que vigila no vigila nada.

**cp5** — psql y `product_price_history` en otra ventana. `UPDATE` del precio: fila nueva. Mismo
precio: nada. `UPDATE` del stock: nada. Preguntar: ¿dónde está el código de Python que ha
escrito esa fila? No hay. Abrir la revisión `004`: la parte que Alembic no pudo generar.

### 10.1 Los tres `downgrade` que autogenerate escribió mal

Se reproducen en vivo, y valen para toda la sección de migraciones:

| Revisión | Lo que generó | Por qué no puede funcionar |
|---|---|---|
| `001d_categories_contract` | `add_column` con `NOT NULL` y sin valor por defecto | La tabla ya tiene 36 filas y no hay nada que poner en ellas |
| `003b_address_history` | Restaurar la restricción `UNIQUE(user_id, is_billing)` | Para entonces ya hay direcciones retiradas: la clave está duplicada |
| `004_price_history` | `drop_table` a secas | El trigger seguiría apuntando a una tabla que ya no existe |

Y los tres tienen la misma causa: **autogenerate compara esquemas, no datos**.

---

## 11. Decisiones que se pueden cambiar sin rehacer el plan

| Decisión tomada | Alternativa | Qué cambia |
|---|---|---|
| Sesión en tabla `sessions` | Token firmado con HMAC (sesión 9) | `security.py` gana `create_token`/`verify_token`; desaparece `UserSession` |
| Tipo de dirección como columna `is_billing` | Direcciones sin tipo, con el papel asignado en el pedido con dos FK | Desaparece la duplicación al usar la misma para las dos cosas; el pedido gana `billing_address_id` |
| El pedido apunta a la dirección | Copiar las líneas de la dirección dentro del pedido | Las direcciones podrían volver a editarse; el pedido deja de poder enseñar la dirección completa relacionada |
| Sin compra anónima | Permitirla con `customer_email` | `user_id` vuelve a ser opcional y el `CHECK` se retira |
| Datos de arranque dentro de la revisión `001` | Un `seed.py` con la `Session` de SQLAlchemy | El README añade `python seed.py`; los tests tendrían que llamarlo |
| Textos de pantalla en inglés | Castellano (el código sigue en inglés) | Solo las cadenas de los componentes |
| Moneda `en-IE` (`€899.00`) | `es-ES` (`899,00 €`) | Un argumento en `formatPrice` |
| Token de carrito en cabecera + `localStorage` | Cookie `HttpOnly` (sesión 18) | CORS con credenciales y `Set-Cookie` en `POST /cart` |
| Contenedores con servidores de desarrollo | Imágenes de producción: `vite build` servido por nginx | Un `Dockerfile` de varias etapas; la migración como paso propio del despliegue |
| Datos de PostgreSQL en un bind mount | Volumen con nombre | `down -v` vuelve a borrar la base de datos y los datos dejan de verse |
| Sin cobertura mínima en los tests | `pytest --cov` con un umbral | Una cifra que cumplir, y tests escritos para subirla |
