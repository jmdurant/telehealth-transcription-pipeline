#!/usr/bin/env python3
"""
Health check endpoint for Real-Time Clinical Assistant
"""
import asyncio
import json
from datetime import datetime
from aiohttp import web
import logging

logger = logging.getLogger(__name__)

async def health_check(request):
    """Health check endpoint"""
    try:
        # You could add more sophisticated health checks here
        # e.g., check Parakeet connectivity, database health, etc.
        
        health_status = {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "service": "realtime-clinical-assistant",
            "version": "1.0.0"
        }
        
        return web.json_response(health_status)
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return web.json_response(
            {"status": "unhealthy", "error": str(e)},
            status=500
        )

async def create_health_server():
    """Create HTTP health check server"""
    app = web.Application()
    app.router.add_get('/health', health_check)
    
    runner = web.AppRunner(app)
    await runner.setup()
    
    site = web.TCPSite(runner, '0.0.0.0', 8092)  # Different port for health checks
    await site.start()
    
    logger.info("Health check server started on port 8092")

if __name__ == "__main__":
    asyncio.run(create_health_server())