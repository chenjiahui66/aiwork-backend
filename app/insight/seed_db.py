"""
演示数据库 — 首次启动时自动建表 + 灌种子数据。
放一个 SQLite 文件,放几张典型的企业表:
- sales: 销售记录(时间/产品/金额/区域/销售员)
- products: 产品库
- employees: 员工(部门/职级/入职时间/薪资)
- user_activity: 用户活跃(时间/事件类型/用户ID)

业务无关,只是给 AI 一些真实查询可玩。
"""
import logging
import random
from datetime import datetime, timedelta
from pathlib import Path

from app.core.config import settings

logger = logging.getLogger(__name__)

DB_PATH = settings.data_path / "demo.db"


def get_schema_description() -> str:
    """给 LLM 用的表结构描述 — 必须是干净、可读的文本"""
    return """
## 数据库 Schema (SQLite)

### 表 1: products (产品表)
- id INTEGER PRIMARY KEY
- name TEXT (产品名,如"AI 写作助手")
- category TEXT (分类,如"productivity"/"communication"/"data"/"creative")
- price REAL (单价,元)
- launch_date TEXT (上线日期, ISO 格式)

示例数据:
1 | AI 写作助手 | productivity | 299.0 | 2024-03-15
2 | 智能问答 | productivity | 399.0 | 2024-01-10
3 | 数据洞察 | data | 599.0 | 2024-06-01
4 | 翻译助手 | communication | 199.0 | 2024-04-20

### 表 2: sales (销售记录)
- id INTEGER PRIMARY KEY
- product_id INTEGER (关联 products.id)
- sale_date TEXT (销售日期, ISO 格式)
- amount INTEGER (销售数量)
- total_price REAL (总金额 = amount * products.price)
- region TEXT (区域: 华东/华北/华南/西部/东北)
- sales_person TEXT (销售员姓名)

示例数据:
100 多条 2024 年至今的销售记录

### 表 3: employees (员工表)
- id INTEGER PRIMARY KEY
- name TEXT
- department TEXT (部门: 研发/产品/销售/市场/HR/财务)
- level TEXT (职级: P1-P10)
- hire_date TEXT (入职日期)
- salary REAL (月薪,元)

示例数据:
50 个员工

### 表 4: user_activity (用户活跃事件)
- id INTEGER PRIMARY KEY
- user_id INTEGER
- event TEXT (事件: login/chat/upload/export/share)
- event_date TEXT (日期)
- duration_seconds INTEGER (停留时长)

示例数据:
约 500 条 2024 年事件

## 提示
- 所有日期都是 TEXT, ISO 格式 'YYYY-MM-DD'
- 总金额 = amount * products.price(可计算,也可直接读 sales.total_price)
- 关联查询用 products.id = sales.product_id
"""


def _ensure_seed():
    """如果数据库没建过,就建表 + 灌数据"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    import sqlite3
    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()

    # 1. products
    cur.execute("""
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        category TEXT,
        price REAL,
        launch_date TEXT
    )
    """)
    # 2. sales
    cur.execute("""
    CREATE TABLE IF NOT EXISTS sales (
        id INTEGER PRIMARY KEY,
        product_id INTEGER,
        sale_date TEXT,
        amount INTEGER,
        total_price REAL,
        region TEXT,
        sales_person TEXT
    )
    """)
    # 3. employees
    cur.execute("""
    CREATE TABLE IF NOT EXISTS employees (
        id INTEGER PRIMARY KEY,
        name TEXT,
        department TEXT,
        level TEXT,
        hire_date TEXT,
        salary REAL
    )
    """)
    # 4. user_activity
    cur.execute("""
    CREATE TABLE IF NOT EXISTS user_activity (
        id INTEGER PRIMARY KEY,
        user_id INTEGER,
        event TEXT,
        event_date TEXT,
        duration_seconds INTEGER
    )
    """)

    # 检查 products 是不是空的,空就灌种子
    cur.execute("SELECT COUNT(*) FROM products")
    if cur.fetchone()[0] > 0:
        conn.close()
        logger.info("演示数据库已存在, 跳过灌种子: %s", DB_PATH)
        return

    random.seed(42)
    # ---- products ----
    products = [
        (1, "AI 写作助手", "productivity", 299.0, "2024-03-15"),
        (2, "智能问答", "productivity", 399.0, "2024-01-10"),
        (3, "数据洞察", "data", 599.0, "2024-06-01"),
        (4, "翻译助手", "communication", 199.0, "2024-04-20"),
        (5, "会议助手", "productivity", 349.0, "2024-05-08"),
        (6, "HR 助手", "productivity", 259.0, "2024-07-12"),
        (7, "AI 设计助手", "creative", 459.0, "2024-08-22"),
    ]
    cur.executemany("INSERT INTO products VALUES (?,?,?,?,?)", products)

    # ---- sales ----
    regions = ["华东", "华北", "华南", "西部", "东北"]
    sales_persons = ["张明", "李娜", "王芳", "刘强", "陈静", "赵磊", "周婷", "吴昊"]
    sales = []
    sale_id = 1
    for month in range(1, 13):  # 1-12 月
        for _ in range(random.randint(8, 15)):
            p = random.choice(products)
            amount = random.randint(1, 20)
            region = random.choice(regions)
            sp = random.choice(sales_persons)
            date = f"2024-{month:02d}-{random.randint(1, 28):02d}"
            sales.append((
                sale_id, p[0], date, amount, amount * p[3], region, sp
            ))
            sale_id += 1
    cur.executemany("INSERT INTO sales VALUES (?,?,?,?,?,?,?)", sales)

    # ---- employees ----
    departments = ["研发", "产品", "销售", "市场", "HR", "财务"]
    levels = ["P3", "P4", "P5", "P6", "P7", "P8"]
    surnames = "张王李赵陈刘杨黄周吴徐孙马朱胡郭高林何"
    givens = "明远娜静强磊军洋勇艳杰娟涛明超秀英霞平平刚桂英"
    emps = []
    for i in range(1, 51):
        name = random.choice(surnames) + random.choice(givens) + random.choice(givens)
        dept = random.choice(departments)
        level = random.choice(levels)
        year = random.randint(2018, 2024)
        month = random.randint(1, 12)
        hire = f"{year}-{month:02d}-{random.randint(1, 28):02d}"
        salary = random.randint(8000, 50000)
        emps.append((i, name, dept, level, hire, salary))
    cur.executemany("INSERT INTO employees VALUES (?,?,?,?,?,?)", emps)

    # ---- user_activity ----
    events = ["login", "chat", "upload", "export", "share"]
    activities = []
    for i in range(1, 501):
        uid = random.randint(1, 100)
        ev = random.choice(events)
        month = random.randint(1, 12)
        date = f"2024-{month:02d}-{random.randint(1, 28):02d}"
        dur = random.randint(5, 600)
        activities.append((i, uid, ev, date, dur))
    cur.executemany("INSERT INTO user_activity VALUES (?,?,?,?,?)", activities)

    conn.commit()
    conn.close()
    logger.info(
        "✅ 演示数据库已创建: %s (products=%d, sales=%d, employees=%d, activity=%d)",
        DB_PATH, len(products), len(sales), len(emps), len(activities),
    )


def get_connection():
    """给上层用的连接工厂 — 只读模式"""
    import sqlite3
    if not DB_PATH.exists():
        _ensure_seed()
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    return conn