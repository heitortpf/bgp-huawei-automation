import uvicorn
from api.app import app
from bgp.db import init_db

if __name__ == "__main__":
    init_db()
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)
