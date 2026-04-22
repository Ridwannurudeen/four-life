"""Run the FOUR-LIFE API server."""

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "agent.api:app",
        host="0.0.0.0",
        port=8030,
        reload=False,
        log_level="info",
        # Trust X-Forwarded-For / X-Forwarded-Proto from the local nginx only.
        # Without this `request.client.host` is always 127.0.0.1 (the nginx
        # upstream) and every caller shares the same rate-limit bucket. Only
        # the loopback reverse proxy is permitted to set these headers.
        proxy_headers=True,
        forwarded_allow_ips="127.0.0.1",
    )
