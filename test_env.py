from app.core.config import settings

print("Checking DHAN credentials...")
print(f"Client ID: {settings.DHAN_MASTER_CLIENT_ID[:10]}..." if settings.DHAN_MASTER_CLIENT_ID else "❌ Not set")
print(f"Access Token: {settings.DHAN_MASTER_ACCESS_TOKEN[:20]}..." if settings.DHAN_MASTER_ACCESS_TOKEN else "❌ Not set")