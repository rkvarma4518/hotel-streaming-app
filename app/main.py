"""Hotel booking site + API. Every search/view/booking is published as an event.

Producer  -> Azure Event Hub (partition key = hotel/city)
Consumer  -> reads the hub and updates stats + live feed (Server-Sent Events)
No EVENTHUB_CONNECTION_STRING -> "local" mode: same code path, no Azure needed.
"""
import asyncio
import json
import os
import random
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from azure.eventhub import EventData
from azure.eventhub.aio import EventHubConsumerClient, EventHubProducerClient
from fastapi import Body, FastAPI, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from .data import GUEST_NAMES, HOTELS, MEALS

CONN = os.environ.get("EVENTHUB_CONNECTION_STRING")  # must include EntityPath (event hub name)
MODE = "eventhub" if CONN else "local"

# ---- In-memory read model (rebuilt from the stream; resets on restart) ----
stats = {"total": 0, "byType": {}, "bookingsByHotel": {}, "revenue": 0, "searchesByCity": {}}
recent: list[dict] = []
bookings: list[dict] = []
clients: set[asyncio.Queue] = set()
producer: EventHubProducerClient | None = None

ALL_ROOMS = [{**r, "hotelId": h["id"]} for h in HOTELS for r in h["rooms"]]
HOTEL_BY_ID = {h["id"]: h for h in HOTELS}


def from_price(h):
    return min(r["price"] for r in h["rooms"])


# ---- CONSUMER SIDE: every event, wherever it came from, is handled here ----
def handle_event(ev: dict, partition_id=None, offset=None):
    etype = ev.get("type", "Unknown")
    stats["total"] += 1
    stats["byType"][etype] = stats["byType"].get(etype, 0) + 1
    if etype == "BookingCreated":
        hid = ev.get("hotelId", "unknown")
        stats["bookingsByHotel"][hid] = stats["bookingsByHotel"].get(hid, 0) + 1
        stats["revenue"] += ev.get("total") or 0
        bookings.insert(0, ev)
        del bookings[100:]
    if etype == "SearchPerformed":
        c = ev.get("city")
        stats["searchesByCity"][c] = stats["searchesByCity"].get(c, 0) + 1
    item = {**ev, "partition": partition_id if partition_id is not None else "-",
            "offset": offset if offset is not None else "-"}
    recent.insert(0, item)
    del recent[50:]
    for q in clients:
        q.put_nowait({"event": item, "stats": stats})


async def on_event(partition_context, event):
    # Called by the Event Hubs SDK for each event it reads from a partition.
    handle_event(json.loads(event.body_as_str()), partition_context.partition_id, event.offset)


async def run_consumer():
    # '$Default' consumer group. No checkpoint store, so we start from the newest events.
    # Add Blob checkpointing (azure-eventhub-checkpointstoreblobaio) as a next exercise.
    consumer = EventHubConsumerClient.from_connection_string(CONN, consumer_group="$Default")
    async with consumer:
        await consumer.receive(on_event=on_event, starting_position="@latest")


# ---- PRODUCER SIDE ----
async def publish(type_: str, **payload) -> dict:
    ev = {"id": str(uuid.uuid4()), "type": type_, "ts": datetime.now(timezone.utc).isoformat(), **payload}
    if MODE == "local":
        asyncio.get_running_loop().call_soon(handle_event, ev)
        return ev
    # partition_key: events with the same key always land in the same partition
    key = str(ev.get("hotelId") or ev.get("city") or ev["id"])
    batch = await producer.create_batch(partition_key=key)
    batch.add(EventData(json.dumps(ev)))
    await producer.send_batch(batch)
    return ev


_bg_tasks: set = set()


def fire_and_forget(coro):
    """Schedule a publish without awaiting it. Must be called from the event loop thread."""
    task = asyncio.create_task(coro)
    _bg_tasks.add(task)  # strong ref: asyncio only keeps weak refs to tasks

    def _done(t: asyncio.Task):
        _bg_tasks.discard(t)
        if not t.cancelled() and t.exception():
            print("publish error:", t.exception())

    task.add_done_callback(_done)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global producer
    tasks = []
    if MODE == "eventhub":
        producer = EventHubProducerClient.from_connection_string(CONN)
        tasks.append(asyncio.create_task(run_consumer()))
    print(f"Hotel streaming lab running (mode: {MODE})")
    yield
    for t in tasks:
        t.cancel()
    if producer:
        await producer.close()


app = FastAPI(title="Stay & Stream hotel API", lifespan=lifespan)


def bad(msg, code=400):
    return JSONResponse({"error": msg}, status_code=code)


# ---- REST API (interactive docs at /docs) ----
@app.get("/api/health")
def health():
    return {"ok": True, "mode": MODE}


@app.get("/api/meals")
def meals():
    return MEALS


@app.get("/api/hotels")
async def search_hotels(q: str = Query(""), city: str = Query(""), maxPrice: float = Query(float("inf"))):
    term = (q or city).strip().lower()
    result = [{**h, "fromPrice": from_price(h)} for h in HOTELS
              if (not term or term in h["city"].lower() or term in h["name"].lower())
              and from_price(h) <= maxPrice]
    if term:
        fire_and_forget(publish("SearchPerformed", city=term, results=len(result)))
    return result


@app.get("/api/hotels/{hotel_id}")
async def get_hotel(hotel_id: str):
    h = HOTEL_BY_ID.get(hotel_id)
    if not h:
        return bad("Hotel not found", 404)
    fire_and_forget(publish("HotelViewed", hotelId=h["id"], hotelName=h["name"]))
    return h


@app.post("/api/bookings", status_code=201)
async def create_booking(body: dict = Body(...)):
    room = next((r for r in ALL_ROOMS if r["id"] == body.get("roomId")), None)
    plan = next((m for m in MEALS if m["id"] == body.get("meal", "none")), None)
    guest = body.get("guest")
    if not room or not plan or not guest:
        return bad("roomId, guest and a valid meal plan are required")
    hotel = HOTEL_BY_ID[room["hotelId"]]
    try:
        nights = max(1, min(30, int(body.get("nights") or 1)))
        guests = max(1, min(6, int(body.get("guests") or 1)))
    except (TypeError, ValueError):
        return bad("nights and guests must be numbers")
    room_total, meal_total = room["price"] * nights, plan["price"] * guests * nights
    try:
        ev = await publish("BookingCreated", hotelId=hotel["id"], hotelName=hotel["name"], city=hotel["city"],
                           roomId=room["id"], roomType=room["type"], guest=guest, email=body.get("email"),
                           checkIn=body.get("checkIn"), nights=nights, guests=guests, meal=plan["id"],
                           roomTotal=room_total, mealTotal=meal_total, total=room_total + meal_total)
    except Exception as e:  # noqa: BLE001
        print("booking error:", e)
        return bad("Could not place booking", 500)
    return {"bookingId": ev["id"], "hotelName": hotel["name"], "roomType": room["type"],
            "checkIn": body.get("checkIn"), "nights": nights, "guests": guests, "meal": plan["name"],
            "roomTotal": room_total, "mealTotal": meal_total, "total": room_total + meal_total}


@app.get("/api/bookings")
def list_bookings():
    return bookings


@app.post("/api/events", status_code=202)
async def publish_custom(body: dict = Body(...)):
    """Publish any custom event: great for experimenting with the raw stream."""
    type_ = body.pop("type", None)
    if not type_:
        return bad("type is required")
    return await publish(type_, **body)


@app.post("/api/simulate", status_code=202)
async def simulate(count: int = Query(20, ge=1, le=200)):
    for _ in range(count):
        room = random.choice(ALL_ROOMS)
        hotel = HOTEL_BY_ID[room["hotelId"]]
        r = random.random()
        if r < 0.4:
            await publish("SearchPerformed", city=random.choice(HOTELS)["city"].lower())
        elif r < 0.7:
            await publish("HotelViewed", hotelId=hotel["id"], hotelName=hotel["name"])
        else:
            nights, guests = random.randint(1, 4), random.randint(1, 3)
            plan = random.choice(MEALS)
            rt, mt = room["price"] * nights, plan["price"] * guests * nights
            await publish("BookingCreated", hotelId=hotel["id"], hotelName=hotel["name"], city=hotel["city"],
                          roomId=room["id"], roomType=room["type"], guest=random.choice(GUEST_NAMES),
                          nights=nights, guests=guests, meal=plan["id"], roomTotal=rt, mealTotal=mt, total=rt + mt)
    return {"sent": count}


@app.get("/api/stats")
def get_stats():
    return {"mode": MODE, **stats}


@app.get("/api/stream")
async def stream(request: Request):
    """Server-Sent Events feed used by /learn.html."""
    q: asyncio.Queue = asyncio.Queue()
    clients.add(q)

    async def gen():
        try:
            yield f"data: {json.dumps({'snapshot': recent, 'stats': stats, 'mode': MODE})}\n\n"
            while not await request.is_disconnected():
                try:
                    msg = await asyncio.wait_for(q.get(), timeout=15)
                    yield f"data: {json.dumps(msg)}\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            clients.discard(q)

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# Static website (must be mounted last so it doesn't shadow /api routes)
app.mount("/", StaticFiles(directory=Path(__file__).parent.parent / "public", html=True), name="site")
