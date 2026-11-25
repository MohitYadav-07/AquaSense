import pymysql
from pymysql.cursors import DictCursor
from config import DB


def conn():
    return pymysql.connect(cursorclass=DictCursor, **DB)


def query(sql, args=None, one=False):
    with conn() as c, c.cursor() as cur:
        cur.execute(sql, args or ())
        return cur.fetchone() if one else cur.fetchall()


def execute(sql, args=None):
    with conn() as c, c.cursor() as cur:
        cur.execute(sql, args or ())
        return cur.lastrowid
