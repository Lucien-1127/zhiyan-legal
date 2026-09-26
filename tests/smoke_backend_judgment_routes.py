import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / 'backend'))
import main  # noqa: E402

paths = {getattr(route, 'path', '') for route in main.app.routes}
assert '/api/judgments/status' in paths
assert '/api/judgments/search' in paths
print('BACKEND_JUDGMENT_ROUTES_PASS')
