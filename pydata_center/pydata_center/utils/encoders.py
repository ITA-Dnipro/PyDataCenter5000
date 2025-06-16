import json
from dataclasses import asdict, is_dataclass


class DataclassJSONEncoder(json.JSONEncoder):
    """Ensures Python dataclasses are JSON serializable."""
    def default(self, obj):
        if is_dataclass(obj):
            return asdict(obj)
        return super().default(obj)
