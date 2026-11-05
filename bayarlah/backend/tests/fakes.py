"""In-memory stand-ins for Supabase and Redis.

Unlike chained MagicMocks, these actually store rows, apply filters and enforce
the same uniqueness/check constraints as the real schema, so tests assert on
resulting *state* instead of on how the code happened to call the client. That
is what catches bugs like `.single()` raising where `if not data` was expected.
"""
import copy
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

from postgrest.exceptions import APIError

ACTIVE = ("manual", "pending", "verified")


def _pg_error(code: str, message: str) -> APIError:
    return APIError({"message": message, "code": code, "hint": None, "details": None})


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Resp:
    def __init__(self, data):
        self.data = data


class Query:
    def __init__(self, db: "FakeDB", table: str):
        self.db, self.table = db, table
        self.op = "select"
        self.payload = None
        self.on_conflict: str | None = None
        self.filters: list[tuple[str, str, object]] = []
        self._limit: int | None = None
        self._order: tuple[str, bool] | None = None

    # builders -----------------------------------------------------------
    def select(self, *_a, **_k):
        return self

    def eq(self, col, val):
        self.filters.append(("eq", col, val))
        return self

    def neq(self, col, val):
        self.filters.append(("neq", col, val))
        return self

    def in_(self, col, vals):
        self.filters.append(("in", col, list(vals)))
        return self

    def limit(self, n):
        self._limit = n
        return self

    def order(self, col, desc=False):
        self._order = (col, desc)
        return self

    def insert(self, rows):
        self.op, self.payload = "insert", rows
        return self

    def update(self, values):
        self.op, self.payload = "update", values
        return self

    def delete(self):
        self.op = "delete"
        return self

    def upsert(self, row, on_conflict=None):
        self.op, self.payload, self.on_conflict = "upsert", row, on_conflict
        return self

    # execution ----------------------------------------------------------
    def _matches(self, row: dict) -> bool:
        for kind, col, val in self.filters:
            if kind == "eq" and str(row.get(col)) != str(val):
                return False
            if kind == "neq" and str(row.get(col)) == str(val):
                return False
            if kind == "in" and str(row.get(col)) not in {str(v) for v in val}:
                return False
        return True

    def execute(self) -> Resp:
        self.db.calls.append((self.table, self.op))
        rows = self.db.tables.setdefault(self.table, [])

        if self.op == "select":
            out = [copy.deepcopy(r) for r in rows if self._matches(r)]
            if self._order:
                col, desc = self._order
                out.sort(key=lambda r: str(r.get(col)), reverse=desc)
            return Resp(out[: self._limit] if self._limit else out)

        if self.op == "insert":
            batch = self.payload if isinstance(self.payload, list) else [self.payload]
            if self.table in self.db.fail_inserts:
                raise _pg_error("XX000", f"forced failure inserting into {self.table}")
            inserted = [self.db.insert_row(self.table, r) for r in batch]
            return Resp(copy.deepcopy(inserted))

        if self.op == "upsert":
            key = self.on_conflict or "id"
            existing = next((r for r in rows if r.get(key) == self.payload.get(key)), None)
            if existing:
                existing.update(self.payload)
                return Resp([copy.deepcopy(existing)])
            return Resp([copy.deepcopy(self.db.insert_row(self.table, self.payload))])

        if self.op == "update":
            hit = [r for r in rows if self._matches(r)]
            for r in hit:
                r.update(self.payload)
            return Resp(copy.deepcopy(hit))

        if self.op == "delete":
            hit = [r for r in rows if self._matches(r)]
            self.db.tables[self.table] = [r for r in rows if r not in hit]
            return Resp(copy.deepcopy(hit))

        raise AssertionError(f"unsupported op {self.op}")


class FakeBucket:
    def __init__(self, db: "FakeDB", name: str):
        self.db, self.name = db, name

    def upload(self, path, data, options=None):
        store = self.db.objects.setdefault(self.name, {})
        if path in store and (options or {}).get("upsert") != "true":
            raise RuntimeError("Duplicate")
        if self.name in self.db.fail_uploads:
            raise RuntimeError("storage down")
        store[path] = {"data": data, "options": options or {}}

    def remove(self, paths):
        for p in paths:
            self.db.objects.get(self.name, {}).pop(p, None)

    def get_public_url(self, path):
        return f"https://test.supabase.co/storage/v1/object/public/{self.name}/{path}"


class FakeDB:
    DEFAULTS = {
        "bills": lambda: {"status": "active", "game_mode": "equal", "emoji_tag": "🍽️",
                          "receipt_url": None, "payment_details": {}, "created_at": _now()},
        "participants": lambda: {"is_organiser": False, "created_at": _now()},
        "payments": lambda: {"status": "confirmed", "gateway_status": "manual",
                             "confirmed_at": _now(), "gateway_ref": None},
        "game_results": lambda: {"is_locked": True, "played_at": _now()},
    }

    def __init__(self):
        self.tables: dict[str, list[dict]] = {}
        self.objects: dict[str, dict[str, dict]] = {}
        self.tokens: dict[str, SimpleNamespace] = {}
        self.calls: list[tuple[str, str]] = []
        self.fail_inserts: set[str] = set()
        self.fail_uploads: set[str] = set()
        self.auth = SimpleNamespace(get_user=self._get_user)
        self.storage = SimpleNamespace(from_=lambda name: FakeBucket(self, name))

    # supabase surface ---------------------------------------------------
    def table(self, name: str) -> Query:
        return Query(self, name)

    def _get_user(self, token: str):
        if token not in self.tokens:
            raise RuntimeError("invalid JWT")
        return SimpleNamespace(user=self.tokens[token])

    # constraint-aware insert -------------------------------------------
    def insert_row(self, table: str, row: dict) -> dict:
        new = {"id": str(uuid.uuid4()), **self.DEFAULTS.get(table, lambda: {})(), **copy.deepcopy(row)}
        rows = self.tables.setdefault(table, [])
        if table == "payments":
            if new.get("amount") is not None and float(new["amount"]) <= 0:
                raise _pg_error("23514", "payments_amount_positive")
            if new["gateway_status"] in ACTIVE and any(
                r["participant_id"] == new["participant_id"] and r["bill_id"] == new["bill_id"]
                and r["gateway_status"] in ACTIVE for r in rows
            ):
                raise _pg_error("23505", "payments_one_live_per_participant")
        if table == "game_results" and any(r["bill_id"] == new["bill_id"] for r in rows):
            raise _pg_error("23505", "game_results_one_per_bill")
        if table == "push_tokens" and new.get("user_id") and any(
            r.get("user_id") == new["user_id"] for r in rows
        ):
            raise _pg_error("23505", "push_tokens_user_id_key")
        rows.append(new)
        return new

    # test helpers --------------------------------------------------------
    def add_user(self, user_id: str) -> dict:
        self.tokens[f"tok-{user_id}"] = SimpleNamespace(id=user_id)
        return {"Authorization": f"Bearer tok-{user_id}"}

    def seed_bill(self, organiser_id: str, total="60.00", names=("Ali", "Siti", "Raj"),
                  phones=("60123456789", "60198765432", "60111111111"), **bill_fields) -> dict:
        n = len(names)
        per = round(float(total) / n, 2)
        bill = self.insert_row("bills", {
            "organiser_id": organiser_id, "title": "Mamak", "total_amount": float(total),
            "per_person": per, **bill_fields})
        parts = [self.insert_row("participants", {
            "bill_id": bill["id"], "name": nm, "phone": phones[i], "amount_owed": per})
            for i, nm in enumerate(names)]
        return {"bill": bill, "participants": parts}

    def rows(self, table: str, **where) -> list[dict]:
        return [r for r in self.tables.get(table, [])
                if all(str(r.get(k)) == str(v) for k, v in where.items())]


class FakeRedis:
    def __init__(self):
        self.d: dict[str, str] = {}
        self.ttl: dict[str, int] = {}

    async def get(self, k): return self.d.get(k)
    async def exists(self, k): return 1 if k in self.d else 0
    async def delete(self, *keys):
        for k in keys:
            self.d.pop(k, None)

    async def set(self, k, v, ex=None, nx=False):
        if nx and k in self.d:
            return None  # redis-py returns None when NX loses
        self.d[k] = v
        if ex:
            self.ttl[k] = ex
        return True

    async def incr(self, k):
        self.d[k] = str(int(self.d.get(k, "0")) + 1)
        return int(self.d[k])

    async def expire(self, k, seconds):
        self.ttl[k] = seconds

    async def aclose(self):
        pass
