"""Messages from the monitor to the person, kept until read; sent onwards by Amazon SNS when a topic is configured."""
from __future__ import annotations

import sqlite3

from app import credentials
from app.agent.models import new_id, now_iso
from app.agent.store import DB, _LOCK


def _conn() -> sqlite3.Connection:
    DB.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB, check_same_thread=False); c.row_factory = sqlite3.Row
    c.execute("create table if not exists notifications (id text primary key, user_id text, kind text, text text, detail text, created_utc text, read_utc text, delivered text)")
    return c


def publish(user_id: str, kind: str, text: str, detail: str = "") -> dict:
    row = {"id": new_id("ntf"), "user_id": user_id, "kind": kind, "text": text, "detail": detail, "created_utc": now_iso(), "read_utc": None, "delivered": _deliver(user_id, text)}
    with _LOCK, _conn() as c:
        c.execute("insert into notifications values (?,?,?,?,?,?,?,?)", tuple(row.values()))
    return row


def _deliver(user_id: str, text: str) -> str:
    """SNS when SNS_TOPIC_ARN is set in .env (subscribe a phone or an app there); otherwise in-app only."""
    topic = credentials.load("SNS_TOPIC_ARN")
    if not topic:
        return "in-app"
    try:
        import boto3
        region = credentials.load("SNS_REGION") or credentials.load("AWS_REGION") or "us-west-2"
        boto3.client("sns", region_name=region, aws_access_key_id=credentials.load("AWS_ACCESS_KEY_ID"), aws_secret_access_key=credentials.load("AWS_SECRET_ACCESS_KEY")).publish(TopicArn=topic, Message=text, Subject="TrafficTwin"[:100], MessageAttributes={"user": {"DataType": "String", "StringValue": user_id}})
        return "sns"
    except Exception as exc:                            # noqa: BLE001 - in-app delivery still stands
        return f"sns-failed: {type(exc).__name__}"


def list_for(user_id: str, limit: int = 50) -> list[dict]:
    with _conn() as c:
        return [dict(r) for r in c.execute("select * from notifications where user_id=? order by created_utc desc limit ?", (user_id, limit)).fetchall()]


def mark_read(user_id: str, ids: list[str] | None = None) -> int:
    with _LOCK, _conn() as c:
        if ids:
            return sum(c.execute("update notifications set read_utc=? where user_id=? and id=? and read_utc is null", (now_iso(), user_id, i)).rowcount for i in ids)
        return c.execute("update notifications set read_utc=? where user_id=? and read_utc is null", (now_iso(), user_id)).rowcount
