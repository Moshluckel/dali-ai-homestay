import os
import re
import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import httpx
import qrcode
from io import BytesIO
from fastapi import FastAPI, HTTPException, Request, Query
from fastapi.responses import FileResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = Path(os.getenv("DATABASE_PATH", str(BASE_DIR / "data" / "demo.db"))).expanduser()

app = FastAPI(title="大理民宿 AI 在地管家 V0", version="0.1.0")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = db()
    cur = conn.cursor()

    cur.executescript("""
    CREATE TABLE IF NOT EXISTS hotels (
      id TEXT PRIMARY KEY,
      name TEXT NOT NULL,
      short_name TEXT NOT NULL,
      address TEXT,
      longitude REAL,
      latitude REAL,
      frontdesk_contact TEXT,
      created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS hotel_faqs (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      hotel_id TEXT NOT NULL,
      intent TEXT NOT NULL,
      keywords TEXT NOT NULL,
      question TEXT NOT NULL,
      answer TEXT NOT NULL,
      risk_level TEXT DEFAULT 'low',
      updated_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS pois (
      id TEXT PRIMARY KEY,
      name TEXT NOT NULL,
      category TEXT NOT NULL,
      longitude REAL,
      latitude REAL,
      avg_price INTEGER,
      tags TEXT,
      why TEXT,
      hours TEXT,
      verified_at TEXT,
      source TEXT,
      active INTEGER DEFAULT 1
    );

    CREATE TABLE IF NOT EXISTS hotel_pois (
      hotel_id TEXT NOT NULL,
      poi_id TEXT NOT NULL,
      priority INTEGER DEFAULT 0,
      note TEXT,
      PRIMARY KEY(hotel_id, poi_id)
    );

    CREATE TABLE IF NOT EXISTS experiences (
      id TEXT PRIMARY KEY,
      hotel_id TEXT,
      name TEXT NOT NULL,
      category TEXT NOT NULL,
      price_text TEXT,
      duration_text TEXT,
      suitable_for TEXT,
      why TEXT,
      booking_text TEXT,
      active INTEGER DEFAULT 1
    );

    CREATE TABLE IF NOT EXISTS conversations (
      id TEXT PRIMARY KEY,
      hotel_id TEXT NOT NULL,
      session_id TEXT NOT NULL,
      created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS messages (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      conversation_id TEXT NOT NULL,
      role TEXT NOT NULL,
      content TEXT NOT NULL,
      intent TEXT,
      source_type TEXT,
      confidence REAL,
      created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS handoff_tickets (
      id TEXT PRIMARY KEY,
      hotel_id TEXT NOT NULL,
      conversation_id TEXT NOT NULL,
      reason TEXT NOT NULL,
      status TEXT DEFAULT 'open',
      created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS events (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      hotel_id TEXT NOT NULL,
      session_id TEXT,
      event_name TEXT NOT NULL,
      payload TEXT,
      created_at TEXT NOT NULL
    );
    """)

    existing = cur.execute("SELECT COUNT(*) AS n FROM hotels").fetchone()["n"]
    if existing == 0:
        cur.execute(
            "INSERT INTO hotels VALUES (?,?,?,?,?,?,?,?)",
            (
                "hotel_demo",
                "大理龙龛 · 有风小院（Demo）",
                "有风小院",
                "云南省大理市龙龛片区（虚拟演示地址）",
                100.2265,
                25.6720,
                "前台微信 / 电话请由真实门店配置",
                now_iso(),
            ),
        )

        faqs = [
            ("wifi", "wifi,无线网,网络,密码", "Wi-Fi 密码是什么？", "房间 Wi-Fi：YOUFENG-GUEST，密码：dali2026。"),
            ("breakfast", "早餐,早饭,吃早饭", "早餐几点？", "早餐时间是 07:30–10:00，在一楼公共用餐区。"),
            ("checkout", "退房,几点退房,离店", "几点退房？", "标准退房时间是 12:00。延迟退房需要前台根据当天房态确认。"),
            ("checkin", "入住,几点入住,提前入住", "几点可以入住？", "标准入住时间是 14:00。提前入住需要前台根据当天房态确认。"),
            ("parking", "停车,停车场,车停哪里", "可以停车吗？", "可停车。住客请使用小院合作停车点，步行约3分钟；具体入口建议到店前联系前台确认。"),
            ("laundry", "洗衣,洗衣机,烘干", "可以洗衣服吗？", "二楼公共区有住客洗衣机，建议使用时间 08:00–22:00。"),
            ("pet", "宠物,狗,猫,带狗,带猫", "可以带宠物吗？", "可接待小型宠物，但必须提前与前台确认，并遵守公共区域管理要求。"),
            ("luggage", "行李,寄存,存行李", "可以寄存行李吗？", "退房当天可免费短时寄存行李；贵重物品请随身携带。"),
        ]
        for intent, kws, q, a in faqs:
            cur.execute(
                """INSERT INTO hotel_faqs
                (hotel_id,intent,keywords,question,answer,risk_level,updated_at)
                VALUES (?,?,?,?,?,'low',?)""",
                ("hotel_demo", intent, kws, q, a, now_iso()),
            )

        pois = [
            ("poi_cafe_1", "海边慢咖啡（Demo）", "咖啡", 100.2320, 25.6740, 55,
             "安静,情侣,独处,下雨可,洱海", "离龙龛较近，适合两个人坐下来聊天，不需要专门跑远路。", "09:00–22:00",
             "2026-09-01", "Demo人工核实"),
            ("poi_food_1", "山下云南小馆（Demo）", "云南菜", 100.2245, 25.6700, 85,
             "两人,家庭,不辣可,晚餐", "菜品比较适合第一次来云南的客人，口味选择比较稳妥。", "11:00–21:30",
             "2026-09-02", "Demo人工核实"),
            ("poi_bar_1", "风下小酒馆（Demo）", "酒吧", 100.2288, 25.6688, 90,
             "安静,两人,聊天,夜间", "体量小、偏聊天型，不是热闹蹦迪路线。", "18:00–23:30",
             "2026-09-02", "Demo人工核实"),
            ("poi_walk_1", "龙龛洱海散步段（Demo）", "散步", 100.2330, 25.6750, 0,
             "免费,傍晚,情侣,老人", "距离近，时间不充裕时比跨城打卡更合适。", "全天",
             "2026-09-03", "Demo人工核实"),
        ]
        cur.executemany(
            "INSERT INTO pois VALUES (?,?,?,?,?,?,?,?,?,?,?,1)",
            pois,
        )
        for poi in pois:
            cur.execute(
                "INSERT INTO hotel_pois(hotel_id,poi_id,priority,note) VALUES (?,?,?,?)",
                ("hotel_demo", poi[0], 10, "Demo推荐"),
            )

        experiences = [
            ("exp_dye", "hotel_demo", "把我们的故事染进大理（Demo）", "非遗共创", "¥399 / 双人", "约2小时",
             "情侣,纪念日,第一次来大理", "先通过AI梳理两个人的故事，再在线下完成个性化扎染体验。", "点击后联系体验顾问预约", 1),
            ("exp_ride", "hotel_demo", "洱海轻骑行（Demo）", "户外", "¥199 / 人", "约3小时",
             "朋友,情侣,轻户外", "路线强度较低，适合第一次体验洱海骑行。", "点击后联系合作方确认天气和名额", 1),
            ("exp_photo", "hotel_demo", "苍洱纪念跟拍（Demo）", "摄影", "¥399 起", "约1.5小时",
             "情侣,亲子,独行", "适合想留下一组自然旅行照片的住客。", "点击后联系摄影师确认档期", 1),
        ]
        cur.executemany(
            """INSERT INTO experiences
            (id,hotel_id,name,category,price_text,duration_text,suitable_for,why,booking_text,active)
            VALUES (?,?,?,?,?,?,?,?,?,?)""",
            experiences,
        )

    conn.commit()
    conn.close()


init_db()


class ChatRequest(BaseModel):
    hotel_id: str = "hotel_demo"
    session_id: Optional[str] = None
    message: str


class EventRequest(BaseModel):
    hotel_id: str = "hotel_demo"
    session_id: Optional[str] = None
    event_name: str
    payload: dict = {}


SENSITIVE_TERMS = [
    "退款", "赔偿", "免单", "投诉", "报警", "警察", "受伤", "医院", "急救",
    "过敏", "丢失", "丢了", "失窃", "被偷", "被盗", "房费争议", "免费升级",
    "赔钱", "事故", "打架"
]

LOCAL_TERMS = ["附近", "推荐", "咖啡", "吃", "餐厅", "酒吧", "喝酒", "散步", "去哪", "怎么玩"]
EXPERIENCE_TERMS = ["体验", "扎染", "非遗", "骑行", "旅拍", "跟拍", "特别", "活动"]
ROUTE_TERMS = ["怎么去", "多久", "多远", "步行", "路线"]


def contains_any(text, terms):
    t = text.lower()
    return any(term.lower() in t for term in terms)


def get_or_create_conversation(conn, hotel_id, session_id):
    row = conn.execute(
        "SELECT * FROM conversations WHERE hotel_id=? AND session_id=? ORDER BY created_at DESC LIMIT 1",
        (hotel_id, session_id),
    ).fetchone()
    if row:
        return row["id"]
    cid = str(uuid.uuid4())
    conn.execute(
        "INSERT INTO conversations(id,hotel_id,session_id,created_at) VALUES (?,?,?,?)",
        (cid, hotel_id, session_id, now_iso()),
    )
    return cid


def log_message(conn, conversation_id, role, content, intent=None, source_type=None, confidence=None):
    conn.execute(
        """INSERT INTO messages
        (conversation_id,role,content,intent,source_type,confidence,created_at)
        VALUES (?,?,?,?,?,?,?)""",
        (conversation_id, role, content, intent, source_type, confidence, now_iso()),
    )


def faq_match(conn, hotel_id, message):
    rows = conn.execute("SELECT * FROM hotel_faqs WHERE hotel_id=?", (hotel_id,)).fetchall()
    scored = []
    lower = message.lower()
    for row in rows:
        keywords = [k.strip().lower() for k in row["keywords"].split(",") if k.strip()]
        score = sum(1 for kw in keywords if kw in lower)
        if score:
            scored.append((score, row))
    if not scored:
        return None
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[0][1]


def find_matching_poi(conn, hotel_id, message):
    rows = conn.execute(
        """SELECT p.* FROM pois p
        JOIN hotel_pois hp ON hp.poi_id=p.id
        WHERE hp.hotel_id=? AND p.active=1
        ORDER BY hp.priority DESC""",
        (hotel_id,),
    ).fetchall()

    # If the user names a POI, return it first.
    for row in rows:
        if row["name"].replace("（Demo）", "") in message or row["name"] in message:
            return [row]

    category_words = {
        "咖啡": ["咖啡"],
        "云南菜": ["吃", "餐厅", "饭", "云南菜"],
        "酒吧": ["酒吧", "喝酒", "小酒馆"],
        "散步": ["散步", "走走", "洱海", "海边"],
    }
    matched = []
    for row in rows:
        words = category_words.get(row["category"], [])
        if any(w in message for w in words):
            matched.append(row)
    return matched[:3] if matched else rows[:3]


async def amap_walking(hotel, poi):
    key = os.getenv("AMAP_WEB_KEY")
    if not key or hotel["longitude"] is None or poi["longitude"] is None:
        return None
    params = {
        "key": key,
        "origin": f'{hotel["longitude"]},{hotel["latitude"]}',
        "destination": f'{poi["longitude"]},{poi["latitude"]}',
        "show_fields": "cost",
    }
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            r = await client.get("https://restapi.amap.com/v5/direction/walking", params=params)
            data = r.json()
        if data.get("status") != "1":
            return None
        paths = data.get("route", {}).get("paths", [])
        if not paths:
            return None
        p = paths[0]
        distance = int(float(p.get("distance", 0)))
        duration = None
        # Different AMap versions may expose cost.duration.
        cost = p.get("cost") or {}
        if cost.get("duration"):
            duration = int(float(cost["duration"]))
        return {"distance_m": distance, "duration_s": duration}
    except Exception:
        return None


async def llm_fallback(conn, hotel_id, message):
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        return None

    hotel = conn.execute("SELECT * FROM hotels WHERE id=?", (hotel_id,)).fetchone()
    faqs = conn.execute(
        "SELECT question,answer FROM hotel_faqs WHERE hotel_id=? LIMIT 50", (hotel_id,)
    ).fetchall()
    pois = conn.execute(
        """SELECT p.name,p.category,p.avg_price,p.tags,p.why,p.hours,p.verified_at
        FROM pois p JOIN hotel_pois hp ON hp.poi_id=p.id
        WHERE hp.hotel_id=? AND p.active=1 LIMIT 20""", (hotel_id,)
    ).fetchall()

    context = {
        "hotel": dict(hotel) if hotel else {},
        "hotel_facts": [dict(x) for x in faqs],
        "verified_pois": [dict(x) for x in pois],
    }

    system = """你是大理一家精品住宿的住客服务助手。
准确性高于一切。只允许使用提供的酒店事实和已核实POI。
涉及退款、赔偿、投诉、失窃、医疗、安全事故、房费争议、经济承诺时，必须要求工作人员介入。
不知道就明确说不能确认，不得猜测。
一次最多推荐3个地点，回答尽量控制在180字以内，语气自然。"""

    payload = {
        "model": os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash"),
        "messages": [
            {"role": "system", "content": system},
            {"role": "system", "content": "可信上下文：" + json.dumps(context, ensure_ascii=False)},
            {"role": "user", "content": message},
        ],
        "temperature": 0.2,
    }

    base = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.post(
                f"{base}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json=payload,
            )
            r.raise_for_status()
            data = r.json()
        return data["choices"][0]["message"]["content"].strip()
    except Exception:
        return None


@app.get("/")
def root():
    return RedirectResponse("/guest")



@app.get("/qr")
def qr_page():
    return FileResponse(BASE_DIR / "static" / "qr.html")


@app.get("/api/qr")
def qr_png(request: Request, target: str = Query(default="")):
    """
    Generate a QR code PNG.
    If target is omitted, it points to this deployment's /guest page.
    """
    if not target:
        forwarded_proto = request.headers.get("x-forwarded-proto")
        scheme = forwarded_proto or request.url.scheme
        host = request.headers.get("host", request.url.netloc)
        target = f"{scheme}://{host}/guest"
    img = qrcode.make(target)
    buf = BytesIO()
    img.save(buf, format="PNG")
    return Response(content=buf.getvalue(), media_type="image/png")


@app.get("/guest")
def guest_page():
    return FileResponse(BASE_DIR / "static" / "guest.html")


@app.get("/admin")
def admin_page():
    return FileResponse(BASE_DIR / "static" / "admin.html")


@app.get("/api/hotel/{hotel_id}")
def get_hotel(hotel_id: str):
    conn = db()
    row = conn.execute("SELECT * FROM hotels WHERE id=?", (hotel_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, "hotel not found")
    return dict(row)


@app.post("/api/event")
def record_event(req: EventRequest):
    conn = db()
    conn.execute(
        "INSERT INTO events(hotel_id,session_id,event_name,payload,created_at) VALUES (?,?,?,?,?)",
        (req.hotel_id, req.session_id, req.event_name, json.dumps(req.payload, ensure_ascii=False), now_iso()),
    )
    conn.commit()
    conn.close()
    return {"ok": True}


@app.post("/api/chat")
async def chat(req: ChatRequest):
    message = req.message.strip()
    if not message:
        raise HTTPException(400, "message is empty")

    session_id = req.session_id or str(uuid.uuid4())
    conn = db()
    hotel = conn.execute("SELECT * FROM hotels WHERE id=?", (req.hotel_id,)).fetchone()
    if not hotel:
        conn.close()
        raise HTTPException(404, "hotel not found")

    cid = get_or_create_conversation(conn, req.hotel_id, session_id)
    log_message(conn, cid, "user", message)

    # 1. Hard safety handoff
    if contains_any(message, SENSITIVE_TERMS):
        ticket_id = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO handoff_tickets(id,hotel_id,conversation_id,reason,status,created_at) VALUES (?,?,?,?,?,?)",
            (ticket_id, req.hotel_id, cid, message[:200], "open", now_iso()),
        )
        answer = "这个问题需要工作人员亲自确认，我不能代表民宿做退款、赔偿或责任判断。我已经建议转前台处理；如果涉及人身安全，请优先联系当地紧急服务。"
        log_message(conn, cid, "assistant", answer, "handoff", "safety_rule", 1.0)
        conn.execute(
            "INSERT INTO events(hotel_id,session_id,event_name,payload,created_at) VALUES (?,?,?,?,?)",
            (req.hotel_id, session_id, "handoff_created", json.dumps({"ticket_id": ticket_id}), now_iso()),
        )
        conn.commit()
        conn.close()
        return {
            "session_id": session_id,
            "text": answer,
            "intent": "handoff",
            "source_type": "safety_rule",
            "confidence": 1.0,
            "handoff": True,
            "cards": [],
        }

    # 2. Exact hotel facts
    match = faq_match(conn, req.hotel_id, message)
    if match:
        answer = match["answer"]
        log_message(conn, cid, "assistant", answer, match["intent"], "hotel_fact", 0.98)
        conn.execute(
            "INSERT INTO events(hotel_id,session_id,event_name,payload,created_at) VALUES (?,?,?,?,?)",
            (req.hotel_id, session_id, "faq_answered", json.dumps({"intent": match["intent"]}), now_iso()),
        )
        conn.commit()
        conn.close()
        return {
            "session_id": session_id,
            "text": answer,
            "intent": match["intent"],
            "source_type": "hotel_fact",
            "confidence": 0.98,
            "handoff": False,
            "cards": [],
        }

    # 3. Experience recommendation
    if contains_any(message, EXPERIENCE_TERMS):
        rows = conn.execute(
            "SELECT * FROM experiences WHERE (hotel_id=? OR hotel_id IS NULL) AND active=1 LIMIT 3",
            (req.hotel_id,),
        ).fetchall()
        cards = [
            {
                "type": "experience",
                "id": r["id"],
                "title": r["name"],
                "meta": f'{r["price_text"]} · {r["duration_text"]}',
                "description": r["why"],
                "cta": "咨询预约",
            }
            for r in rows
        ]
        answer = "如果你不想只打卡，我更建议从下面这些体验里选一个。第一版我只放少量我们核实过、能够真实联系到人的项目："
        log_message(conn, cid, "assistant", answer, "experience", "experience_db", 0.95)
        conn.execute(
            "INSERT INTO events(hotel_id,session_id,event_name,payload,created_at) VALUES (?,?,?,?,?)",
            (req.hotel_id, session_id, "experience_recommended", "{}", now_iso()),
        )
        conn.commit()
        conn.close()
        return {
            "session_id": session_id,
            "text": answer,
            "intent": "experience",
            "source_type": "experience_db",
            "confidence": 0.95,
            "handoff": False,
            "cards": cards,
        }

    # 4. Local recommendation and optional route
    if contains_any(message, LOCAL_TERMS + ROUTE_TERMS):
        rows = find_matching_poi(conn, req.hotel_id, message)
        cards = []
        route_text = None
        for r in rows[:3]:
            card = {
                "type": "poi",
                "id": r["id"],
                "title": r["name"],
                "meta": f'{r["category"]} · 人均约¥{r["avg_price"]}' if r["avg_price"] else r["category"],
                "description": r["why"],
                "hours": r["hours"],
                "verified_at": r["verified_at"],
                "cta": "查看/导航",
            }
            if contains_any(message, ROUTE_TERMS) and len(rows) == 1:
                route = await amap_walking(hotel, r)
                if route:
                    mins = round(route["duration_s"] / 60) if route.get("duration_s") else None
                    distance = route["distance_m"]
                    card["route"] = f"步行约 {mins} 分钟 · {distance} 米" if mins else f"步行约 {distance} 米"
                    route_text = card["route"]
            cards.append(card)

        if route_text:
            answer = f"从民宿出发，实时路线查询结果是：{route_text}。下面是目的地信息："
        else:
            answer = "我先从民宿核实过的本地清单里给你少量推荐，不用为了网红点专门跑很远。"
        log_message(conn, cid, "assistant", answer, "local_recommendation", "verified_poi_db", 0.92)
        conn.execute(
            "INSERT INTO events(hotel_id,session_id,event_name,payload,created_at) VALUES (?,?,?,?,?)",
            (req.hotel_id, session_id, "poi_recommended", json.dumps({"count": len(cards)}), now_iso()),
        )
        conn.commit()
        conn.close()
        return {
            "session_id": session_id,
            "text": answer,
            "intent": "local_recommendation",
            "source_type": "verified_poi_db",
            "confidence": 0.92,
            "handoff": False,
            "cards": cards,
        }

    # 5. Constrained LLM fallback
    llm_text = await llm_fallback(conn, req.hotel_id, message)
    if llm_text:
        answer = llm_text
        source_type = "llm_with_verified_context"
        confidence = 0.72
        handoff = False
    else:
        answer = "这个问题我目前没有足够可靠的信息，先不猜。你可以换个问法，或者让前台帮你确认。"
        source_type = "safe_fallback"
        confidence = 0.35
        handoff = True

    log_message(conn, cid, "assistant", answer, "fallback", source_type, confidence)
    conn.commit()
    conn.close()
    return {
        "session_id": session_id,
        "text": answer,
        "intent": "fallback",
        "source_type": source_type,
        "confidence": confidence,
        "handoff": handoff,
        "cards": [],
    }


@app.get("/api/admin/stats/{hotel_id}")
def stats(hotel_id: str):
    conn = db()
    sessions = conn.execute(
        "SELECT COUNT(DISTINCT session_id) AS n FROM conversations WHERE hotel_id=?", (hotel_id,)
    ).fetchone()["n"]
    user_msgs = conn.execute(
        """SELECT COUNT(*) AS n FROM messages m
        JOIN conversations c ON c.id=m.conversation_id
        WHERE c.hotel_id=? AND m.role='user'""", (hotel_id,)
    ).fetchone()["n"]
    handoffs = conn.execute(
        "SELECT COUNT(*) AS n FROM handoff_tickets WHERE hotel_id=?", (hotel_id,)
    ).fetchone()["n"]
    faq_answers = conn.execute(
        """SELECT COUNT(*) AS n FROM messages m
        JOIN conversations c ON c.id=m.conversation_id
        WHERE c.hotel_id=? AND m.role='assistant' AND m.source_type='hotel_fact'""", (hotel_id,)
    ).fetchone()["n"]
    poi_recs = conn.execute(
        "SELECT COUNT(*) AS n FROM events WHERE hotel_id=? AND event_name='poi_recommended'", (hotel_id,)
    ).fetchone()["n"]
    exp_recs = conn.execute(
        "SELECT COUNT(*) AS n FROM events WHERE hotel_id=? AND event_name='experience_recommended'", (hotel_id,)
    ).fetchone()["n"]
    conn.close()
    return {
        "sessions": sessions,
        "user_messages": user_msgs,
        "faq_answers": faq_answers,
        "handoffs": handoffs,
        "poi_recommendations": poi_recs,
        "experience_recommendations": exp_recs,
    }


@app.get("/api/admin/faqs/{hotel_id}")
def list_faqs(hotel_id: str):
    conn = db()
    rows = conn.execute(
        "SELECT id,intent,question,answer,updated_at FROM hotel_faqs WHERE hotel_id=? ORDER BY id",
        (hotel_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.get("/api/admin/messages/{hotel_id}")
def recent_messages(hotel_id: str):
    conn = db()
    rows = conn.execute(
        """SELECT m.role,m.content,m.intent,m.source_type,m.created_at
        FROM messages m
        JOIN conversations c ON c.id=m.conversation_id
        WHERE c.hotel_id=?
        ORDER BY m.id DESC LIMIT 20""",
        (hotel_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
