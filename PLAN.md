# Plan de implementación · Tienda didáctica (React + FastAPI + SQLAlchemy + PostgreSQL)

Este documento es la única fuente de requisitos para quien implemente el código (modelo o
persona). Se construye **checkpoint a checkpoint, en orden**, sin adelantar tablas, endpoints
ni pantallas de checkpoints posteriores. Cada checkpoint termina con un commit y un tag de Git.

| Tag | Revisión Alembic | Qué se enseña |
|---|---|---|
| `cp1-catalog` | `001_products` | Una tabla bien hecha, un endpoint paginado, un listado que carga más al hacer scroll |
| `cp2-cart` | `002_cart_and_orders` | Carrito (mutable, efímero) frente a pedido (inmutable, precio congelado) |
| `cp3-users` | `003_users_and_addresses` | Usuario, dirección de envío y de facturación, registro y login |
| `cp4-price-history` | `004_price_history` | Un histórico que la base de datos rellena sola con un trigger en el `UPDATE` |

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
- Cuando el usuario **no puede tocar** un recurso (una dirección que no es suya), el servicio lanza `PermissionError("...")` y la ruta lo convierte en `403`.
- Autenticación fallida: la dependencia de la ruta lanza `HTTPException(401, ...)` directamente.

Solo excepciones de Python. El servicio sigue sin saber nada de HTTP.

### 0.3 Todo el código en inglés

Sin excepciones: identificadores SQL, Python y TypeScript, comentarios, mensajes de error de
la API, textos de pantalla, datos de arranque, mensajes de commit y tags. El castellano
queda solo para este `PLAN.md` y para el `README.md` de clase.

### 0.4 Convenciones del curso que se mantienen

1. **Importes en céntimos enteros** (`price_cents`, `total_cents`). Nunca `float`.
2. **Errores de la API siempre `{"detail": "..."}`** con el código HTTP correcto y el dato que falló en el mensaje.
3. **Todo lo que afecta a dinero o stock se calcula en el servidor.** Del cliente solo llegan ids y cantidades.
4. **Nombres SQL y JSON en `snake_case`**: tablas en plural, PK `id`, FK `<singular>_id`, fechas `created_at`. Python en `snake_case`, TypeScript en `camelCase`, componentes en `PascalCase`.
5. **Fuera de alcance** (nota en el README, no se implementa): pasarela de pago, roles, Docker de la app, CI, observabilidad, tests automáticos. Un pedido nace en estado `paid`.

---

## 1. Stack

| Capa | Elección |
|---|---|
| Base de datos | PostgreSQL 16 (`postgres:16-alpine`), único servicio de `docker-compose.yml` |
| Backend | Python 3.12 · FastAPI · SQLAlchemy 2.0 (estilo `Mapped`) · Alembic · `psycopg[binary]` 3 · uvicorn · `pydantic[email]` · `python-dotenv` |
| Frontend | Vite · React 18 · TypeScript · `react-router-dom` (desde cp2) · un `styles.css` |

**Fuente de verdad del esquema: los modelos SQLAlchemy.** Alembic genera las migraciones
comparándolos con la base de datos (`--autogenerate`), y a mano se añade lo que
autogenerate no ve: datos de arranque, la función y el trigger del cp4. Es el flujo real de
un proyecto con SQLAlchemy y es lo que se enseña.

---

## 2. Estructura del repositorio

```
shop/
├── README.md                 # (castellano) arranque, checkpoints, qué queda fuera
├── docker-compose.yml        # solo el servicio db; sin scripts de inicialización
├── .env.example
├── backend/
│   ├── requirements.txt
│   ├── alembic.ini
│   ├── alembic/
│   │   ├── env.py            # lee DATABASE_URL del entorno; target_metadata = Base.metadata
│   │   ├── script.py.mako
│   │   └── versions/
│   │       ├── 001_products.py               # cp1
│   │       ├── 002_cart_and_orders.py        # cp2
│   │       ├── 003_users_and_addresses.py    # cp3
│   │       └── 004_price_history.py          # cp4
│   └── app/
│       ├── main.py           # FastAPI, CORS, include_router, GET /health
│       ├── db.py             # engine, SessionLocal, get_db()
│       ├── models.py         # M: una clase por tabla
│       ├── schemas.py        # esquemas Pydantic de ENTRADA
│       ├── services.py       # C: reglas de negocio, funciones con Session
│       ├── security.py       # cp3: hash_password, verify_password
│       └── routes/           # V: products.py, cart.py, orders.py, users.py
└── frontend/
    ├── package.json · vite.config.ts · tsconfig.json · index.html
    └── src/
        ├── api.ts            # request<T>() y una función por endpoint
        ├── useData.ts        # hook de carga con el tipo State<T>
        ├── format.ts         # formatPrice, formatDate
        ├── styles.css
        ├── main.tsx · App.tsx
        ├── components/       # Header, ProductCard, PriceHistory (cp4)
        └── pages/            # Catalog, ProductDetail, Cart, OrderConfirmation, Auth, Account
```

Git: rama `main`, commits en inglés, un tag anotado al cerrar cada checkpoint.

---

## 3. Base común (antes del checkpoint 1)

**`docker-compose.yml`** — servicio `db`: `postgres:16-alpine`, `POSTGRES_USER=shop`,
`POSTGRES_DB=shop`, contraseña desde `${POSTGRES_PASSWORD:?POSTGRES_PASSWORD missing in .env}`,
volumen con nombre, healthcheck `pg_isready`, puerto `5432:5432` (comentario: solo desarrollo).
**Sin** `docker-entrypoint-initdb.d`: el esquema lo gestiona Alembic.

**`.env.example`**:
```
POSTGRES_PASSWORD=shop
DATABASE_URL=postgresql+psycopg://shop:shop@localhost:5432/shop
```

**`app/db.py`**:
```python
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

def get_db():
    with SessionLocal() as db:
        yield db
```
En cada ruta: `db: Session = Depends(get_db)`. El `commit` lo hace el servicio, porque el
servicio es quien sabe qué operaciones forman una unidad (sesión 13).

**`app/models.py`** — solo `class Base(DeclarativeBase): pass` de momento.

**Alembic** — `alembic init alembic` dentro de `backend/`, y en `env.py`:
- `config.set_main_option("sqlalchemy.url", os.environ["DATABASE_URL"])` tras cargar `.env`.
- `from app.models import Base` y `target_metadata = Base.metadata`.
- `compare_type=True` en `context.configure`.

Cómo se crea cada revisión (el mismo comando en los cuatro checkpoints):
```bash
alembic revision --autogenerate --rev-id 001_products -m "products"
```
El `--rev-id` legible es deliberado: permite moverse entre checkpoints con la base de datos
sin tocar Git, y en clase se ve el esquema crecer y encoger:
```bash
alembic upgrade head
```
```bash
alembic downgrade 001_products
```
Comentario en el README: Alembic guarda en la tabla `alembic_version` qué revisión está
aplicada. Es el `schema_migrations` de la sesión 15, hecho por la herramienta de verdad.

**`app/main.py`** — `FastAPI(title="Shop API")`, `CORSMiddleware` con
`allow_origins=["http://localhost:5173"]`, `allow_methods=["*"]`, `allow_headers=["*"]`,
`GET /health` → `{"status": "ok"}`, y un `include_router` por fichero de `routes/`.

**Frontend base**:
- `api.ts`: `BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8000"` y `request<T>(path, options?)`: hace `fetch`; si la respuesta no es `ok`, lanza el objeto `{ status, detail }`; fallo de red → `{ status: 0, detail: "Could not reach the server" }`. Todas las llamadas pasan por aquí.
- `useData.ts`: `type State<T> = { phase: "loading" } | { phase: "ready"; data: T } | { phase: "error"; status: number; detail: string }`, con la cancelación de peticiones obsoletas de la sesión 16.
- `format.ts`: `formatPrice(cents)` → `"€899.00"` con `Intl.NumberFormat("en-IE", { style: "currency", currency: "EUR" })`; `formatDate(iso)`.
- `styles.css`: rejilla de tarjetas, cabecera, tabla.

**README** (castellano) — arranque:
```bash
docker compose up -d
cd backend && python -m venv .venv && .venv/Scripts/activate && pip install -r requirements.txt && alembic upgrade head && uvicorn app.main:app --reload
cd frontend && npm install && npm run dev
```

**Hecho cuando**: `GET /health` responde, `alembic current` no da error (sin revisiones aún),
Vite muestra la página vacía. Commit `Base: compose, Alembic, FastAPI and Vite skeleton`.

---

## 4. Checkpoint 1 · Catálogo (`cp1-catalog`)

### 4.1 Modelo

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
    category: Mapped[str] = mapped_column(String(50), index=True)   # every listing filters by it
    price_cents: Mapped[int]                                          # cents, never float
    stock: Mapped[int] = mapped_column(server_default="0")
    image_url: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

Los `CheckConstraint` con nombre y los `server_default` van en el modelo a propósito: así
autogenerate los lleva a la migración y la regla vive en la base de datos, no en el código.

### 4.2 Revisión `001_products`

`alembic revision --autogenerate --rev-id 001_products -m "products"` genera el
`create_table` con las restricciones y el índice. Se revisa que el DDL resultante sea:

```sql
CREATE TABLE products (
    id          INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    name        VARCHAR(200) NOT NULL,
    description TEXT         NOT NULL DEFAULT '',
    category    VARCHAR(50)  NOT NULL,
    price_cents INTEGER      NOT NULL CONSTRAINT ck_products_price_cents CHECK (price_cents >= 0),
    stock       INTEGER      NOT NULL DEFAULT 0 CONSTRAINT ck_products_stock CHECK (stock >= 0),
    image_url   TEXT         NOT NULL,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT now()
);
CREATE INDEX ix_products_category ON products (category);
```

**A mano**, al final de `upgrade()`, los datos de arranque con `op.execute("""INSERT INTO
products (...) VALUES ...""")`: **36 productos**, 5 categorías (`laptops`, `monitors`,
`peripherals`, `storage`, `networking`), precios entre 999 y 149900 céntimos, **4 con
`stock = 0`**, imagen `https://picsum.photos/seed/product-<n>/400/300`. El `downgrade()`
autogenerado (`drop_table`) ya se lleva los datos.

Comentarios en inglés en el fichero de la revisión, encima del bloque que corresponda: qué
parte la generó Alembic y qué parte se añadió a mano, y por qué (autogenerate compara
esquemas, no datos).

### 4.3 Servicios

```python
def get_product(db: Session, product_id: int) -> Product | None
def list_products(db: Session, category: str | None, cursor: int, limit: int) -> tuple[list[Product], int | None]
```
`list_products` hace paginación **keyset**: `select(Product).where(Product.id > cursor)`,
filtro opcional por categoría, `order_by(Product.id).limit(limit + 1)`. Se pide una fila de
más para saber si hay página siguiente sin una segunda consulta: si llegan `limit + 1`,
`next_cursor` es el `id` de la última que se devuelve; si no, `None`. Se listan todos los
productos, con stock o sin él.

### 4.4 Ruta `routes/products.py`

Una función de conversión, que es la decisión de "qué expone la API":
```python
def product_to_dict(p: Product) -> dict:
    return {"id": p.id, "name": p.name, "description": p.description, "category": p.category,
            "price_cents": p.price_cents, "stock": p.stock, "image_url": p.image_url}
```
(`created_at` no sale: no hace falta en pantalla. Es una decisión, no un volcado de la tabla.)

| Ruta | Parámetros | Respuesta |
|---|---|---|
| `GET /products` | `category?`, `limit` = `Query(12, ge=1, le=100)`, `cursor` = `Query(0, ge=0)` | `200 {"items": [...], "next_cursor": <int o null>}` |
| `GET /products/{product_id}` | — | `200` producto · `404 {"detail": "Product 999 not found"}` |

### 4.5 Frontend

- `api.ts`: `type Product = {...}`, `listProducts({ category?, cursor? })`, `getProduct(id)`.
- `pages/Catalog.tsx`: estado `items`, `nextCursor`, `loading`, `category`. Un `<div ref={sentinel} />` al final de la rejilla con un `IntersectionObserver`: cuando entra en pantalla, hay `nextCursor` y no está cargando, pide la siguiente página y **concatena**. Cambiar de categoría vacía la lista. Vacío: `"No products in this category."`.
- `components/ProductCard.tsx`: `<img loading="lazy" width="400" height="300">`, nombre, precio, etiqueta `"Out of stock"` si `stock === 0`.
- Sin router todavía: `App.tsx` = `Header` + `Catalog`.

Dos mecanismos de carga perezosa, y se explican por separado: `loading="lazy"` retrasa
**las imágenes**; el `IntersectionObserver` retrasa **la petición de la página siguiente**.

### 4.6 Hecho cuando

- `alembic current` muestra `001_products (head)`; `\d products` en psql coincide con el DDL de 4.2.
- `GET /products?limit=5` da 5 y un `next_cursor`; con ese cursor, los 5 siguientes sin solapar; la última página da `null`.
- `GET /products/999` → 404 con `detail`.
- En el navegador: 12 tarjetas, al bajar 12 más, luego las últimas 12; tres peticiones en la pestaña Red.
- Tag `cp1-catalog`.

---

## 5. Checkpoint 2 · Carrito y pedido (`cp2-cart`)

### 5.1 Modelos

```python
class Cart(Base):
    __tablename__ = "carts"
    # The identifier IS the token: random and long. With a sequential number,
    # changing it in the browser would show someone else's cart.
    token: Mapped[str] = mapped_column(Text, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    items: Mapped[list["CartItem"]] = relationship(back_populates="cart", cascade="all, delete-orphan")

class CartItem(Base):
    __tablename__ = "cart_items"
    __table_args__ = (CheckConstraint("quantity > 0", name="ck_cart_items_quantity"),)
    # Composite primary key: one row per product per cart, no duplicates possible.
    cart_token: Mapped[str] = mapped_column(ForeignKey("carts.token", ondelete="CASCADE"), primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), primary_key=True)
    quantity: Mapped[int]
    # Note what is NOT here: a price. The cart shows TODAY's price, read from products.
    cart: Mapped["Cart"] = relationship(back_populates="items")
    product: Mapped["Product"] = relationship()

class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (CheckConstraint("total_cents >= 0", name="ck_orders_total_cents"),)
    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    customer_email: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(20), server_default="paid")
    total_cents: Mapped[int]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    items: Mapped[list["OrderItem"]] = relationship(back_populates="order", cascade="all, delete-orphan")

class OrderItem(Base):
    __tablename__ = "order_items"
    __table_args__ = (CheckConstraint("quantity > 0", name="ck_order_items_quantity"),)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), primary_key=True)
    quantity: Mapped[int]
    # And here there IS a price: the price at purchase time. If the product
    # goes up tomorrow, today's order must not change.
    price_cents: Mapped[int]
    order: Mapped["Order"] = relationship(back_populates="items")
    product: Mapped["Product"] = relationship()
```

El contraste `CartItem` sin precio / `OrderItem` con precio es **la** lección del checkpoint.

### 5.2 Revisión `002_cart_and_orders`

`alembic revision --autogenerate --rev-id 002_cart_and_orders -m "cart and orders"`. Todo
sale de autogenerate; nada a mano. Revisar que aparecen las cuatro tablas, las claves
compuestas, los `ON DELETE CASCADE` y los `CHECK`.

### 5.3 Esquemas de entrada (`schemas.py`)

```python
class QuantityIn(BaseModel):
    quantity: int = Field(ge=1)

class OrderIn(BaseModel):
    customer_email: EmailStr
```

### 5.4 Servicios

```python
def create_cart(db) -> Cart                                   # token = secrets.token_urlsafe(32)
def get_cart(db, token: str) -> Cart | None
def set_cart_item(db, cart: Cart, product_id: int, quantity: int) -> Cart | None
def remove_cart_item(db, cart: Cart, product_id: int) -> bool  # False if the product was not in the cart
def cart_total_cents(cart: Cart) -> int                       # sum(item.product.price_cents * item.quantity)
def create_order(db, cart: Cart, customer_email: str) -> Order
def get_order(db, order_id: int) -> Order | None
```

- `set_cart_item`: `None` si el producto no existe; `ValueError("Insufficient stock for 27\" Monitor: 0 left, 3 requested")` si `quantity > product.stock` (respuesta inmediata al usuario; **la comprobación que vale es la del checkout**); si no, UPSERT con `sqlalchemy.dialects.postgresql.insert(...).on_conflict_do_update(...)`. `commit`.
- `create_order`, **una sola transacción**, en este orden:
  1. Sin líneas → `ValueError("The cart is empty")`.
  2. Cargar los productos de todas las líneas con `with_for_update()`: dos compradores a por la última unidad no pasan los dos (la carrera de la sesión 14).
  3. Validar **todas** las líneas contra el stock; una falla → `ValueError` y no se ha tocado nada.
  4. Solo entonces: descontar stock, crear `Order` con `total_cents` calculado aquí, crear cada `OrderItem` con `price_cents = product.price_cents` (el precio de hoy, congelado), borrar el carrito. `commit`.

### 5.5 Rutas `routes/cart.py` y `routes/orders.py`

El token del carrito viaja en la cabecera `X-Cart-Token`. Dependencia `current_cart(db,
x_cart_token: str = Header())` → `get_cart` o `HTTPException(404, "Cart not found")`.
Conversión `cart_to_dict(cart)` con `items: [{product_id, name, image_url, price_cents,
quantity, subtotal_cents}]` y `total_cents`; `order_to_dict(order)` con `items:
[{product_id, name, quantity, price_cents}]`.

| Ruta | Cabecera / cuerpo | Respuesta |
|---|---|---|
| `POST /cart` | — | `201` carrito vacío |
| `GET /cart` | `X-Cart-Token` | `200` carrito · `404` |
| `PUT /cart/items/{product_id}` | `X-Cart-Token` · `QuantityIn` | `200` carrito · `404` producto o carrito · `409` stock |
| `DELETE /cart/items/{product_id}` | `X-Cart-Token` | `200` carrito · `404 "Product 7 is not in the cart"` |
| `POST /orders` | `X-Cart-Token` · `OrderIn` | `201` pedido, cabecera `Location: /orders/{id}` · `404` carrito · `409` carrito vacío o stock |
| `GET /orders/{order_id}` | — | `200` pedido · `404 "Order 42 not found"` |

`PUT` fija la cantidad (idempotente: repetir por un reintento no duplica) y `DELETE` quita la
línea: cada verbo hace lo que su nombre dice, que es la lección de la sesión 11.

### 5.6 Frontend

- `react-router-dom` con rutas `/`, `/products/:id`, `/cart`, `/orders/:id`.
- El carrito vive en `App.tsx` como estado y se reparte con un `createContext` (`CartContext`: `cart`, `setQuantity(productId, quantity)`, `removeItem(productId)`, `placeOrder(email)`). Token en `localStorage["cart_token"]`; al arrancar, `GET /cart` y si da 404 se borra el token. Si no hay carrito al añadir, primero `POST /cart`. Lo que se pinta es siempre la última respuesta del backend.
- `Header`: enlace `Cart (n)`.
- `ProductCard` y `pages/ProductDetail.tsx`: botón `"Add to cart"` (deshabilitado sin stock) = `setQuantity(id, current + 1)`.
- `pages/Cart.tsx`: tabla con `−` / `+` (`setQuantity`), botón `"Remove"` (`removeItem`, que llama al `DELETE`), subtotal, total, campo email, botón `"Place order"`. El `409` se enseña con su `detail`. Vacío: `"Your cart is empty"`.
- `pages/OrderConfirmation.tsx`: `useData(() => getOrder(id))`.

### 5.7 Hecho cuando

- Por curl: `POST /cart` → `PUT /cart/items/1 {quantity: 2}` → `PUT /cart/items/3 {quantity: 1}` → `DELETE /cart/items/3` → `GET /cart` (una línea) → `POST /orders` → `GET /orders/1`. Stock del producto 1 baja en 2.
- Pedido con una línea servible y otra sin stock → 409 y **ningún** stock cambia.
- `UPDATE products SET price_cents = 1 WHERE id = 1;` tras el pedido: `GET /orders/1` mantiene el precio original.
- `alembic downgrade 001_products` deja solo `products` con sus datos; `alembic upgrade head` vuelve.
- Tag `cp2-cart`.

---

## 6. Checkpoint 3 · Usuarios y direcciones (`cp3-users`)

### 6.1 La decisión de modelado

Tres formas de modelar envío y facturación, y solo una escala:

1. Columnas en `users` (`shipping_street`, `billing_street`, …): duplica campos y limita a una de cada. Descartada.
2. Tabla `addresses` con `kind IN ('shipping','billing')`: el caso más común, *"la misma para las dos"*, obliga a duplicar la fila. Descartada.
3. **Tabla `addresses` sin tipo. Envío y facturación son *roles* que se asignan en el pedido** con dos FK en `orders`. "La misma para las dos" = las dos FK apuntan a la misma fila. Elegida.

Y la misma lección que con el precio: si el usuario edita su dirección un año después, el
pedido antiguo no debe cambiar. Solución más simple: **las direcciones no se editan** (no hay
endpoint de edición; se crea otra).

### 6.2 Modelos

```python
class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    email: Mapped[str] = mapped_column(String(200), unique=True)
    password_hash: Mapped[str] = mapped_column(Text)     # never the password; never reversible
    full_name: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    addresses: Mapped[list["Address"]] = relationship(back_populates="user", cascade="all, delete-orphan")

class UserSession(Base):            # "Session" would clash with sqlalchemy.orm.Session
    __tablename__ = "sessions"
    # Same idea as carts: a random token identifies the session.
    token: Mapped[str] = mapped_column(Text, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    user: Mapped["User"] = relationship()

class Address(Base):
    __tablename__ = "addresses"
    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    recipient_name: Mapped[str] = mapped_column(String(200))
    street: Mapped[str] = mapped_column(String(200))
    city: Mapped[str] = mapped_column(String(100))
    postal_code: Mapped[str] = mapped_column(String(20))
    country: Mapped[str] = mapped_column(String(2), server_default="ES")   # ISO 3166-1
    user: Mapped["User"] = relationship(back_populates="addresses")
```

Y en `Order`, tres columnas nuevas, **todas nullable** (la compra anónima del cp2 sigue
igual; ningún pedido existente cambia):
```python
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    shipping_address_id: Mapped[int | None] = mapped_column(ForeignKey("addresses.id"))
    billing_address_id: Mapped[int | None] = mapped_column(ForeignKey("addresses.id"))
    shipping_address: Mapped["Address | None"] = relationship(foreign_keys=[shipping_address_id])
    billing_address: Mapped["Address | None"] = relationship(foreign_keys=[billing_address_id])
```

### 6.3 Revisión `003_users_and_addresses`

Autogenerate: tres `create_table` y tres `add_column` sobre `orders`. Nada a mano. En clase
se señala que las columnas nuevas son nullable y que por eso el cambio es seguro (sesión 15,
EXPAND).

### 6.4 Esquemas de entrada

```python
class UserIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str = Field(min_length=1)

class LoginIn(BaseModel):
    email: EmailStr
    password: str

class AddressIn(BaseModel):
    recipient_name: str = Field(min_length=1)
    street: str = Field(min_length=1)
    city: str = Field(min_length=1)
    postal_code: str = Field(min_length=1)
    country: str = Field(default="ES", min_length=2, max_length=2)
```
`OrderIn` cambia: `customer_email: EmailStr | None = None`, `shipping_address_id: int | None = None`,
`billing_address_id: int | None = None`.

### 6.5 `security.py` y servicios

`security.py`, solo librería estándar: `hash_password(plain)` con `hashlib.scrypt` y sal de
`os.urandom(16)`, guardado como `"scrypt$<salt_hex>$<hash_hex>"`; `verify_password(plain,
stored)` con `hmac.compare_digest`. Comentario: en producción `bcrypt` o `argon2`.

Servicios nuevos:
```python
def register_user(db, email, password, full_name) -> User | None   # None if the email is taken (IntegrityError caught, not checked beforehand)
def login(db, email, password) -> UserSession | None               # None on any failure; 24 h expiry
def get_user_by_session(db, token) -> User | None                  # None if missing or expired
def create_address(db, user, data: AddressIn) -> Address
```
`create_order(db, cart, customer_email, user=None, shipping_address_id=None, billing_address_id=None)`:
con usuario, el email es el suyo; cada dirección indicada **debe ser suya**, si no
`PermissionError("Address 7 does not belong to you")`; sin `billing_address_id` se usa la de
envío. Sin usuario, igual que en cp2 (y entonces `customer_email` es obligatorio: si falta,
`ValueError("customer_email is required for guest checkout")`).

### 6.6 Rutas `routes/users.py` y cambios en `orders.py`

Dependencias: `current_user(db, authorization: str = Header())` → usuario o
`HTTPException(401, "Invalid or expired token")`; `optional_user` devuelve `None` sin cabecera.
Conversión `user_to_dict` (sin `password_hash`, con `addresses`) y `address_to_dict`.

| Ruta | Cuerpo / cabecera | Respuesta |
|---|---|---|
| `POST /users` | `UserIn` | `201` usuario · `409 "Email ana@example.com is already registered"` |
| `POST /login` | `LoginIn` | `200 {"token": "..."}` · `401 "Invalid email or password"` (mismo mensaje exista o no el email) |
| `GET /me` | Bearer | `200` usuario con `addresses` · `401` |
| `POST /me/addresses` | Bearer · `AddressIn` | `201` dirección · `401` |
| `POST /orders` (cambia) | `X-Cart-Token` · Bearer opcional · `OrderIn` | igual que cp2 · `403` dirección ajena |
| `GET /orders/{id}` (cambia) | — | añade `shipping_address` y `billing_address` (objetos o `null`) |

### 6.7 Frontend

- Segundo `createContext` (`SessionContext`: `user`, `login`, `register`, `logout`); token en `localStorage["auth_token"]`; `request` añade `Authorization: Bearer` si existe; un `401` borra el token.
- `pages/Auth.tsx`: los dos formularios, registro y login, en la misma página. Registrar = `POST /users` y login automático.
- `pages/Account.tsx`: datos del usuario, lista de direcciones, formulario `"New address"`.
- `pages/Cart.tsx`: con sesión, desaparece el email y aparece un `<select>` `"Shipping address"` y una casilla `"Use the same address for billing"` (marcada por defecto; al desmarcarla, un segundo `<select>`). Sin direcciones: `"Add an address in your account first"` con enlace. Sin sesión: igual que en cp2.
- `Header`: `"Sign in"` o `"Hi, Ana · My account · Sign out"`.

### 6.8 Hecho cuando

- Registro, login, `GET /me`, dos direcciones, pedido con envío y facturación distintas; `GET /orders/{id}` trae las dos.
- Pedido con la dirección de otro usuario → 403. Pedido sin token → sigue funcionando.
- Mismo email dos veces → 409. Contraseña incorrecta → 401 con el mismo mensaje que un email inexistente.
- Tag `cp3-users`.

---

## 7. Checkpoint 4 · Histórico de precios con trigger (`cp4-price-history`)

### 7.1 La idea

Si el histórico lo escribe la aplicación, cualquier cambio de precio que no pase por ella (un
`UPDATE` en psql, un script, otro sistema) se lo salta. Aquí la garantía se mueve **a la
base de datos**: da igual por dónde cambie el precio. Y es también la primera vez que
autogenerate **no basta**: Alembic no ve funciones ni triggers.

### 7.2 Modelo

```python
class PriceHistory(Base):
    __tablename__ = "price_history"
    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"))
    previous_price_cents: Mapped[int]
    price_cents: Mapped[int]
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (Index("ix_price_history_product", "product_id", "changed_at"),)
```
Y en `Product`: `price_history: Mapped[list["PriceHistory"]] = relationship(order_by="PriceHistory.changed_at", cascade="all, delete-orphan")`.

Se guarda el precio anterior y el nuevo porque una fila registra **una transición**; así no
hace falta una fila inicial artificial.

### 7.3 Revisión `004_price_history`

Autogenerate crea la tabla y el índice. **A mano**, después, en `upgrade()`:

```python
op.execute("""
-- The function: WHAT to do. OLD and NEW are the row before and after the UPDATE.
CREATE FUNCTION record_price_change() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    INSERT INTO price_history (product_id, previous_price_cents, price_cents)
    VALUES (NEW.id, OLD.price_cents, NEW.price_cents);
    RETURN NEW;
END;
$$;
""")
op.execute("""
-- The trigger: WHEN to do it. Only when price_cents changes, and only if it is really different.
CREATE TRIGGER trg_products_price_change
AFTER UPDATE OF price_cents ON products
FOR EACH ROW
WHEN (OLD.price_cents IS DISTINCT FROM NEW.price_cents)
EXECUTE FUNCTION record_price_change();
""")
# Three price changes from the migration itself: the history does not start empty,
# and it proves the trigger works without the application doing anything.
op.execute("UPDATE products SET price_cents = 84900 WHERE id = 1")
op.execute("UPDATE products SET price_cents = 79900 WHERE id = 1")
op.execute("UPDATE products SET price_cents = 2299  WHERE id = 3")
```

Y en `downgrade()`, **antes** del `drop_table` autogenerado:
```python
op.execute("DROP TRIGGER trg_products_price_change ON products")
op.execute("DROP FUNCTION record_price_change()")
```
Punto de clase: sin estas dos líneas el `downgrade` falla, porque el trigger sigue apuntando
a una tabla que ya no existe. Es lo que autogenerate no sabe.

### 7.4 Servicios y rutas

```python
def list_price_history(db, product_id) -> list[PriceHistory] | None   # None if the product does not exist
def change_price(db, product_id, price_cents) -> Product | None
```
`change_price` asigna `product.price_cents = price_cents` y hace `commit`. **No escribe en
`price_history`**: ese es el punto. Un producto inexistente devuelve `None` (404), no lista
vacía: dos situaciones distintas, dos respuestas distintas.

Esquema de entrada: `class PriceIn(BaseModel): price_cents: int = Field(ge=0)`.

| Ruta | Cuerpo | Respuesta |
|---|---|---|
| `GET /products/{id}/price-history` | — | `200 [{changed_at, previous_price_cents, price_cents}]` del más antiguo al más reciente; `200 []` si nunca cambió · `404` |
| `PATCH /products/{id}` | `PriceIn` | `200` producto · `404` |

`PATCH` sin autenticación (los roles quedan fuera del curso; comentario en la ruta).

### 7.5 Frontend

- `components/PriceHistory.tsx`: `useData(() => getPriceHistory(id))`; vacío → `"This product has not changed price yet."`; tabla `Date · Before · After`. Se monta en `ProductDetail` debajo de la ficha.

### 7.6 Hecho cuando

- En psql: `UPDATE products SET price_cents = 74900 WHERE id = 1;` → fila nueva en `price_history`. El mismo `UPDATE` otra vez → nada. `UPDATE ... SET stock = 99` → nada.
- `PATCH /products/1 {"price_cents": 69900}` → una fila más; `GET /products/1/price-history` en orden.
- `GET /products/999/price-history` → 404; producto sin cambios → `200 []`.
- `alembic downgrade 003_users_and_addresses` funciona (trigger y función se van) y `upgrade head` vuelve a crear los tres cambios de precio.
- Tag `cp4-price-history`.

---

## 8. Orden de trabajo y reglas de implementación

1. Sección 3 (base común). Comprobar `/health`, `alembic current` y Vite. Commit.
2. Para cada checkpoint: modelos → `alembic revision --autogenerate --rev-id ...` → revisar y completar a mano la revisión → `alembic upgrade head` → esquemas de entrada → servicios → rutas → probar con curl → frontend → README → commit → tag.
3. Antes de cada tag: `docker compose down -v && docker compose up -d && alembic upgrade head` aplica todas las revisiones desde cero sin error, y `alembic downgrade base && alembic upgrade head` también.
4. Antes de cada tag: `alembic revision --autogenerate -m "check"` sobre la base al día **no genera ningún cambio** (los modelos y la base coinciden). Borrar el fichero vacío que genera.
5. No adelantar nada de un checkpoint posterior.
6. **Revisión de clases antes de cada tag**: en `backend/app` solo hay clases en `models.py` (una por tabla, más `Base`) y en `schemas.py` (una por cuerpo de petición). `grep -rn "^class " backend/app` no debe listar ningún otro fichero. En `frontend/src`, `grep -rn "class " frontend/src` no debe devolver nada.
7. **Revisión de idioma antes de cada tag**: `grep -rniE "producto|carrito|pedido|usuario|direccion|precio|sesion" backend/app backend/alembic/versions frontend/src` no debe devolver nada.
8. El README final (castellano) tiene: arranque, los comandos de Alembic para moverse entre checkpoints, tabla de checkpoints con su tag y su revisión, el guion de demo de la sección 9 y la lista de lo que queda fuera.

---

## 9. Guion de demo por checkpoint

**cp1** — Abrir `models.py` y la revisión `001` lado a lado: qué generó Alembic y qué se
añadió a mano. `\d products` en psql. `GET /products?limit=5` dos veces con el cursor.
Navegador con la pestaña Red abierta: bajar, ver las tres peticiones y las imágenes llegando.

**cp2** — `CartItem` sin precio y `OrderItem` con precio, lado a lado. Hacer un pedido,
cambiar el precio en psql, volver a `GET /orders/1`. Pedir más unidades de las que hay: 409
y stock intacto. `PUT` dos veces: mismo resultado. `DELETE` de una línea y `GET /cart`.
`alembic downgrade 001_products` y `upgrade head`: el esquema encoge y vuelve a crecer.

**cp3** — Pizarra: las tres formas de modelar envío/facturación y por qué gana la tercera.
Registrar, mirar `password_hash` en psql. Enseñar que `sessions` y `carts` son la misma
idea. Pedir con la dirección de otro usuario: 403. Pedir sin sesión: sigue funcionando.

**cp4** — psql y `price_history` en otra ventana. `UPDATE` del precio: fila nueva. Mismo
precio: nada. `UPDATE` del stock: nada. Preguntar: ¿dónde está el código de Python que ha
escrito esa fila? No hay. Abrir la revisión `004`: la parte que Alembic no pudo generar, y
el `downgrade` que falla si se olvidan el trigger y la función.

---

## 10. Decisiones que se pueden cambiar sin rehacer el plan

| Decisión tomada | Alternativa | Qué cambia |
|---|---|---|
| Sin tests automáticos | Un `tests/test_smoke.py` con `TestClient`, un test por checkpoint | `pytest` y `httpx` en `requirements.txt`; una base `shop_test` |
| Sesión en tabla `sessions` | Token firmado con HMAC (sesión 9) | `security.py` gana `create_token`/`verify_token`; desaparece `UserSession` |
| Datos de arranque dentro de la revisión `001` | Un `seed.py` con la `Session` de SQLAlchemy | Se quita el `op.execute` de la revisión; el README añade `python seed.py` |
| Textos de pantalla en inglés | Castellano (el código sigue en inglés) | Solo las cadenas de los componentes |
| Moneda `en-IE` (`€899.00`) | `es-ES` (`899,00 €`) | Un argumento en `formatPrice` |
| Token de carrito en cabecera + `localStorage` | Cookie `HttpOnly` (sesión 18) | CORS con credenciales y `Set-Cookie` en `POST /cart` |
| Imágenes de `picsum.photos` | Carpeta estática servida por FastAPI (sin internet) | `image_url` relativa y `StaticFiles` en `main.py` |
