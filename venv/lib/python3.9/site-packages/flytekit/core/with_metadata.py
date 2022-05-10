from typing import Any, Dict


class FlyteMetadata:
    def __init__(self, data: Dict[str, Any]):
        self._data = data

    @property
    def data(self):
        return self._data
