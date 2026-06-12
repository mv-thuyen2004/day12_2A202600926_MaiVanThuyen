# Deployment Information

## Public URL
https://production-agent-28ld.onrender.com/

## Platform
Render

## Test Commands

### Health Check
```bash
curl https://production-agent-28ld.onrender.com/health
# Expected: {"status": "ok", ...}
```

### API Test (with authentication)
```bash
curl -X POST https://production-agent-28ld.onrender.com/ask \
  -H "X-API-Key: secret-key-123" \
  -H "Content-Type: application/json" \
  -d "{\"user_id\": \"test_user\", \"question\": \"What is Docker?\"}"
```

### Rate Limiting Test (Spam requests to trigger 429)
```bash
for i in {1..12}; do
  curl -s -X POST https://production-agent-28ld.onrender.com/ask \
    -H "X-API-Key: secret-key-123" \
    -H "Content-Type: application/json" \
    -d "{\"user_id\": \"test_user\", \"question\": \"test $i\"}"
  echo ""
done
# Should eventually return: {"detail": "Rate limit exceeded: 10 req/min"}
```

## Environment Variables Set
- `PORT`
- `REDIS_URL`
- `AGENT_API_KEY`
- `ENVIRONMENT`
- `RATE_LIMIT_PER_MINUTE`
- `DAILY_BUDGET_USD`

## Screenshots
- [Deployment dashboard](screenshots/deployment_railway.png)
