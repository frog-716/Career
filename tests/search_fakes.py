"""Explicit offline Research SearchProvider doubles for integration tests."""


class FakeSearchProvider:
    def __init__(self, results, *, on_search=None):
        self.results = results
        self.on_search = on_search
        self.calls = []

    def search(self, query):
        self.calls.append(query)
        if self.on_search:
            self.on_search(query)
        if callable(self.results):
            return self.results(query)
        if isinstance(self.results, BaseException):
            raise self.results
        return self.results
