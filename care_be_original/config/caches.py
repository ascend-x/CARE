import fnmatch

from django.core.cache.backends import dummy, locmem
from django.core.cache.backends.base import DEFAULT_TIMEOUT


class DummyCache(dummy.DummyCache):
    def set(self, key, value, timeout=DEFAULT_TIMEOUT, version=None, nx=None):
        super().set(key, value, timeout, version)
        # mimic the behavior of django_redis with setnx, for tests
        return True

    def delete_pattern(self, pattern, version=None, itersize=None):
        """No-op for DummyCache — nothing is cached."""
        pass


class LocMemCache(locmem.LocMemCache):
    def set(self, key, value, timeout=DEFAULT_TIMEOUT, version=None, nx=None):
        super().set(key, value, timeout, version)
        # mimic the behavior of django_redis with setnx, for tests
        return True

    def delete_pattern(self, pattern, version=None, itersize=None):
        """
        Mimic django_redis's delete_pattern for LocMemCache.
        Deletes all keys matching the given glob-style pattern.
        """
        key = self.make_key(pattern, version=version)
        key = key.replace("*", "")  # strip wildcard for prefix matching

        with self._lock:
            keys_to_delete = [
                k for k in self._cache
                if k.startswith(key) or fnmatch.fnmatch(k, pattern)
            ]
        for k in keys_to_delete:
            try:
                self.delete(k)
            except Exception:
                pass
