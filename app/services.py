"""
services.py - service layer: Create, Read, Update and Delete operations (slide 67).

Owner: Member B (Database)

The routers (HTTP) call these services; the services talk to the database
through SQLAlchemy. Each class has one responsibility:
    UserService       users (register, look up)
    CategoryService   expense categories
    ExpenseService    a user's expenses
    BudgetService     a user's monthly budgets
    RuleService       keyword rules for auto-categorization

Every expense/budget/rule method takes `user_id`, so one user can never
read or change another user's data.
"""
from datetime import date  # tipo fecha (sin hora)

from sqlalchemy import func, select  # func = funciones SQL (lower, sum...); select = construye consultas SELECT
from sqlalchemy.orm import Session  # tipo de la sesión de base de datos

from . import models, schemas  # modelos ORM (tablas) y schemas Pydantic (datos de entrada)
from .auth import AuthService  # para hashear la contraseña al crear un usuario
from .categorizer import DEFAULT_RULES, Categorizer, Rule, normalize  # reglas por defecto y el motor de categorización

DEFAULT_CATEGORIES = [  # categorías iniciales: (nombre, color para los gráficos)
    ("Food", "#f97316"),  # comida
    ("Transit", "#0ea5e9"),  # transporte
    ("Utilities", "#8b5cf6"),  # servicios: luz, internet, teléfono
    ("Rent", "#ef4444"),  # alquiler
    ("Shopping", "#ec4899"),  # compras
    ("Health", "#22c55e"),  # salud
    ("Entertainment", "#eab308"),  # entretenimiento
    ("Other", "#64748b"),  # otros: se usa cuando ninguna regla coincide
]  # fin de la lista


def month_range(month: str) -> tuple[date, date]:  # convierte "2026-11" en (2026-11-01, 2026-12-01); el fin es exclusivo
    year, mon = (int(part) for part in month.split("-"))  # separa año y mes y los convierte a enteros
    start = date(year, mon, 1)  # primer día del mes
    end = date(year + 1, 1, 1) if mon == 12 else date(year, mon + 1, 1)  # primer día del mes siguiente (diciembre pasa al año siguiente)
    return start, end  # devuelve el rango [inicio, fin)


class UserService:  # operaciones sobre la tabla users
    @staticmethod  # se llama sin crear un objeto: UserService.get_by_username(...)
    def get_by_username(db: Session, username: str):  # busca un usuario por su nombre de usuario
        return db.scalar(select(models.User).where(models.User.username == username))  # SELECT ... WHERE username = ?; devuelve el usuario o None

    @staticmethod  # método estático
    def get_by_email(db: Session, email: str):  # busca un usuario por email
        return db.scalar(select(models.User).where(models.User.email == email))  # SELECT ... WHERE email = ?; devuelve el usuario o None

    @staticmethod  # método estático
    def create(db: Session, data: schemas.UserCreate) -> models.User:  # crea un usuario a partir de los datos validados
        user = models.User(  # crea el objeto Python que será una fila de users
            username=data.username,  # nombre de usuario
            email=data.email.lower(),  # email en minúsculas, para que "Ana@X.de" y "ana@x.de" sean el mismo
            password_hash=AuthService.hash_password(data.password),  # solo se guarda el hash, nunca la contraseña
            phone_number=data.phone_number or None,  # teléfono opcional; un texto vacío se guarda como NULL
        )  # fin del objeto
        db.add(user)  # lo prepara para insertarlo (INSERT pendiente)
        db.commit()  # confirma la transacción: la fila queda guardada en PostgreSQL
        db.refresh(user)  # recarga el objeto para obtener el user_id generado por la base
        return user  # devuelve el usuario creado


class CategoryService:  # operaciones sobre la tabla categories
    @staticmethod  # método estático
    def seed_defaults(db: Session) -> None:  # inserta las categorías por defecto una sola vez
        if db.scalar(select(models.Category).limit(1)) is None:  # si la tabla está vacía
            db.add_all(models.Category(name=n, color=c) for n, c in DEFAULT_CATEGORIES)  # prepara una fila por categoría
            db.commit()  # las guarda

    @staticmethod  # método estático
    def list_all(db: Session):  # devuelve todas las categorías
        return db.scalars(select(models.Category).order_by(models.Category.name)).all()  # SELECT ... ORDER BY name

    @staticmethod  # método estático
    def get(db: Session, category_id: int):  # busca una categoría por su clave primaria
        return db.get(models.Category, category_id)  # devuelve la categoría o None

    @staticmethod  # método estático
    def get_by_name(db: Session, name: str):  # busca una categoría por nombre, sin distinguir mayúsculas
        return db.scalar(select(models.Category).where(models.Category.name.ilike(name)))  # ILIKE = comparación sin mayúsculas/minúsculas

    @staticmethod  # método estático
    def create(db: Session, data: schemas.CategoryCreate) -> models.Category:  # crea una categoría nueva
        category = models.Category(name=data.name.strip(), color=data.color)  # objeto con el nombre sin espacios sobrantes
        db.add(category)  # INSERT pendiente
        db.commit()  # lo guarda
        db.refresh(category)  # obtiene el category_id generado
        return category  # devuelve la categoría creada


class ExpenseService:  # operaciones sobre la tabla expenses
    @staticmethod  # método estático
    def list_for_user(db: Session, user_id: int, month: str | None = None, category_id: int | None = None):  # gastos de un usuario, con filtros opcionales
        query = select(models.Expense).where(models.Expense.user_id == user_id)  # solo los gastos de ESTE usuario
        if month:  # si se pidió un mes
            start, end = month_range(month)  # calcula el rango de fechas del mes
            query = query.where(models.Expense.expense_date >= start, models.Expense.expense_date < end)  # filtra por ese rango
        if category_id:  # si se pidió una categoría
            query = query.where(models.Expense.category_id == category_id)  # filtra por esa categoría
        query = query.order_by(models.Expense.expense_date.desc(), models.Expense.created_at.desc())  # más recientes primero; created_at desempata
        return db.scalars(query).all()  # ejecuta la consulta y devuelve la lista

    @staticmethod  # método estático
    def get(db: Session, expense_id: int):  # busca un gasto por su clave primaria, sea de quien sea
        return db.get(models.Expense, expense_id)  # devuelve el gasto o None; el router decide si es 404 o 403

    @staticmethod  # método estático
    def create(db: Session, user_id: int, data: schemas.ExpenseCreate, source: str = "manual") -> models.Expense:  # crea un gasto
        expense = models.Expense(user_id=user_id, source=source, **data.model_dump())  # objeto con dueño, origen (manual/import) y los datos validados
        db.add(expense)  # INSERT pendiente
        db.commit()  # lo guarda
        db.refresh(expense)  # obtiene expense_id y created_at
        return expense  # devuelve el gasto creado

    @staticmethod  # método estático
    def update(db: Session, expense: models.Expense, data: schemas.ExpenseUpdate) -> models.Expense:  # modifica un gasto existente
        for field, value in data.model_dump().items():  # recorre cada campo enviado (monto, descripción, fecha, categoría)
            setattr(expense, field, value)  # asigna el valor nuevo al objeto; SQLAlchemy detecta el cambio
        db.commit()  # ejecuta el UPDATE
        db.refresh(expense)  # recarga los valores guardados
        return expense  # devuelve el gasto actualizado

    @staticmethod  # método estático
    def delete(db: Session, expense: models.Expense) -> None:  # borra un gasto
        db.delete(expense)  # DELETE pendiente
        db.commit()  # lo ejecuta

    @staticmethod  # método estático
    def existing_keys(db: Session, user_id: int, start: date, end: date) -> set[tuple]:  # huellas de gastos ya guardados, para detectar duplicados al importar
        rows = db.execute(  # ejecuta una consulta que devuelve solo 3 columnas
            select(models.Expense.expense_date, models.Expense.amount, func.lower(models.Expense.description))  # fecha, monto, descripción en minúsculas
            .where(  # condiciones
                models.Expense.user_id == user_id,  # solo del usuario
                models.Expense.expense_date >= start,  # desde la fecha inicial
                models.Expense.expense_date <= end,  # hasta la fecha final (incluida)
            )  # fin de las condiciones
        ).all()  # trae todas las filas
        return {(d, round(a, 2), text) for d, a, text in rows}  # conjunto de tuplas: buscar en él es muy rápido


class BudgetService:  # operaciones sobre la tabla budgets
    @staticmethod  # método estático
    def list_for_month(db: Session, user_id: int, month: str):  # presupuestos de un usuario en un mes
        query = select(models.Budget).where(  # SELECT ... WHERE
            models.Budget.user_id == user_id, models.Budget.period_month == month  # del usuario y del mes pedido
        )  # fin de la consulta
        return db.scalars(query).all()  # ejecuta y devuelve la lista

    @staticmethod  # método estático
    def upsert(db: Session, user_id: int, data: schemas.BudgetCreate) -> models.Budget:  # crea el presupuesto, o actualiza el límite si ya existe ("upsert")
        existing = db.scalar(  # busca si ya hay uno para el mismo usuario + mes + categoría
            select(models.Budget).where(  # SELECT ... WHERE
                models.Budget.user_id == user_id,  # mismo usuario
                models.Budget.period_month == data.period_month,  # mismo mes
                models.Budget.category_id.is_(None)  # presupuesto general (sin categoría): se compara con IS NULL...
                if data.category_id is None  # ...cuando no se envió categoría
                else models.Budget.category_id == data.category_id,  # si no, misma categoría
            )  # fin de las condiciones
        )  # fin de la búsqueda
        if existing:  # ya existía
            existing.limit_amount = data.limit_amount  # solo cambia el límite
            budget = existing  # trabajamos con el existente
        else:  # no existía
            budget = models.Budget(user_id=user_id, **data.model_dump())  # crea uno nuevo
            db.add(budget)  # INSERT pendiente
        db.commit()  # guarda (INSERT o UPDATE)
        db.refresh(budget)  # recarga los valores guardados
        return budget  # devuelve el presupuesto

    @staticmethod  # método estático
    def get(db: Session, budget_id: int):  # busca un presupuesto por su clave primaria, sea de quien sea
        return db.get(models.Budget, budget_id)  # devuelve el presupuesto o None; el router decide si es 404 o 403

    @staticmethod  # método estático
    def delete(db: Session, budget: models.Budget) -> None:  # borra un presupuesto
        db.delete(budget)  # DELETE pendiente
        db.commit()  # lo ejecuta


class RuleService:  # operaciones sobre la tabla category_rules (palabras clave del categorizador)
    @staticmethod  # método estático
    def seed_defaults(db: Session) -> None:  # inserta las reglas incluidas (user_id = NULL) una sola vez
        if db.scalar(select(models.CategoryRule).where(models.CategoryRule.user_id.is_(None)).limit(1)):  # si ya hay reglas incluidas
            return  # no hace nada
        categories = {c.name: c.category_id for c in CategoryService.list_all(db)}  # diccionario nombre -> id de categoría
        for category_name, keywords in DEFAULT_RULES.items():  # recorre cada categoría y sus palabras clave
            if category_name in categories:  # solo si la categoría existe
                db.add_all(  # prepara una fila por palabra clave
                    models.CategoryRule(user_id=None, category_id=categories[category_name], keyword=k)  # regla incluida (sin dueño)
                    for k in keywords  # una por cada palabra
                )  # fin de add_all
        db.commit()  # guarda todas las reglas

    @staticmethod  # método estático
    def list_for_user(db: Session, user_id: int):  # reglas incluidas + reglas propias del usuario
        query = (  # construye la consulta
            select(models.CategoryRule)  # SELECT de reglas
            .where((models.CategoryRule.user_id.is_(None)) | (models.CategoryRule.user_id == user_id))  # incluidas (NULL) O del usuario
            .order_by(models.CategoryRule.user_id.is_(None), models.CategoryRule.keyword)  # primero las del usuario, luego por palabra
        )  # fin de la consulta
        return db.scalars(query).all()  # ejecuta y devuelve la lista

    @staticmethod  # método estático
    def get_user_rule(db: Session, user_id: int, keyword: str):  # busca una regla propia del usuario por palabra clave
        return db.scalar(  # devuelve la regla o None
            select(models.CategoryRule).where(  # SELECT ... WHERE
                models.CategoryRule.user_id == user_id, models.CategoryRule.keyword == keyword  # mismo usuario y misma palabra
            )  # fin de las condiciones
        )  # fin de la consulta

    @staticmethod  # método estático
    def save_user_rule(db: Session, user_id: int, keyword: str, category_id: int, commit: bool = True):  # crea la regla del usuario o la reasigna a otra categoría
        keyword = normalize(keyword)  # normaliza: minúsculas, umlauts escritos, sin puntuación
        rule = RuleService.get_user_rule(db, user_id, keyword)  # ¿ya existe esa regla?
        if rule:  # sí existe
            rule.category_id = category_id  # solo cambia la categoría
        else:  # no existe
            rule = models.CategoryRule(user_id=user_id, keyword=keyword, category_id=category_id)  # crea la regla nueva
            db.add(rule)  # INSERT pendiente
        if commit:  # caso normal: guardar ahora
            db.commit()  # guarda
            db.refresh(rule)  # recarga la regla guardada
        else:  # durante una importación: se guarda todo junto al final
            db.flush()  # envía el cambio sin confirmar, para que una segunda regla igual en el mismo lote la encuentre
        return rule  # devuelve la regla

    @staticmethod  # método estático
    def delete(db: Session, rule: models.CategoryRule) -> None:  # borra una regla
        db.delete(rule)  # DELETE pendiente
        db.commit()  # lo ejecuta

    @staticmethod  # método estático
    def build_categorizer(db: Session, user_id: int) -> Categorizer:  # arma el categorizador con las reglas de este usuario
        rules = [Rule(r.keyword, r.category_id, r.user_id is not None) for r in RuleService.list_for_user(db, user_id)]  # convierte cada fila en un objeto Rule (marca si es propia)
        return Categorizer(rules)  # devuelve el motor listo para categorizar descripciones
