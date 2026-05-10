from app.core.config import settings

print(f"QDRANT_END_POINT: {settings.QDRANT_END_POINT}")
print(f"QDRANT_API_KEY: {'[SET]' if settings.QDRANT_API_KEY else '[NOT SET]'}")
