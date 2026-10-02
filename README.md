# Stay & Stream: hotel booking site for learning Azure Event Hubs / Kafka (Python)

A working hotel website (search by location, view hotels, choose room, meal plan and nights, confirm). Behind the scenes every search, hotel view and booking is published as an **event**; a consumer reads the stream and powers a developer dashboard.

```
Browser/API ──► Producer ──► Azure Event Hub (2 partitions) ──► Consumer ──► stats + live feed (SSE)
```

Stack: Python 3.12, FastAPI, `azure-eventhub`. Without an Event Hub connection string the app runs in **local mode** (same code path, no Azure needed).

## Run locally
```bash
python -m venv .venv && source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 3000
```
- Hotel site: http://localhost:3000
- Live event stream (developer view): http://localhost:3000/learn.html
- Interactive API docs: http://localhost:3000/docs

To use a real Event Hub locally: `export EVENTHUB_CONNECTION_STRING="Endpoint=sb://...;EntityPath=hotel-events"`.

## API
```bash
curl "localhost:3000/api/hotels?q=nashik"
curl -X POST localhost:3000/api/bookings -H 'Content-Type: application/json' \
  -d '{"roomId":"h3-r1","guest":"Asha","email":"a@b.c","checkIn":"2026-11-01","nights":3,"guests":2,"meal":"half"}'
curl -X POST "localhost:3000/api/simulate?count=50"
curl -X POST localhost:3000/api/events -H 'Content-Type: application/json' -d '{"type":"Custom","note":"hello"}'
curl localhost:3000/api/stats
```
Also: `GET /api/hotels/{id}`, `GET /api/meals`, `GET /api/bookings`, `GET /api/health`, `GET /api/stream` (SSE).

## Deploy to Azure (GitHub Actions + Bicep)
1. `az ad sp create-for-rbac --name hotel-lab-gh --role Contributor --scopes /subscriptions/<SUB_ID> --sdk-auth` and copy the JSON.
2. GitHub: *Settings → Secrets and variables → Actions* → secret `AZURE_CREDENTIALS` with that JSON.
3. Push to `main`. The workflow deploys `infra/main.bicep` (Event Hubs + free **F1** App Service on Python 3.12), then your code. App Service installs `requirements.txt` during deployment (first deploy takes a few minutes).

Cost: App Service F1 is free. Event Hubs has no free tier; Basic is about $0.015 per hour (~$11/month) while it exists. Delete when done: `az group delete -n rg-hotel-streaming-lab --yes`.

## Concepts to explore
1. **Partitions & keys:** the feed shows `[p0]`/`[p1]`; bookings for the same hotel share a partition.
2. **Consumer groups:** Basic has only `$Default`; use Standard to add more.
3. **Checkpoints:** add `azure-eventhub-checkpointstoreblobaio` so the consumer resumes after a restart.
4. **Kafka:** set `eventHubSku` to `Standard`, then run `examples/kafka_consumer.py`.
5. **Next:** Azure Functions trigger, Stream Analytics, Event Hubs Capture.
