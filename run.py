import os

from app import create_app
from app.scheduler import start_scheduler

app = create_app()

if __name__ == "__main__":
    debug = True
    # With the auto-reloader on, Flask starts two processes; only the one that actually serves
    # requests has WERKZEUG_RUN_MAIN set, so start the scheduler there and nowhere else.
    if not debug or os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        start_scheduler(app)
    app.run(debug=debug, port=5000)
