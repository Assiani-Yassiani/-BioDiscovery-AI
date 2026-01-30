"""
Multi-Level Cache System for BioDiscovery AI
Architecture v2.1

Cache Levels:
- Level 1: Embeddings Cache (permanent)
- Level 2: Results Cache (TTL: 1 hour)
- Level 3: LLM Response Cache (permanent)
"""

import logging
import hashlib
import json
import time
from typing import Any, Optional, Dict
from functools import lru_cache
from collections import OrderedDict
import threading

logger = logging.getLogger(__name__)


class LRUCache:
    """Thread-safe LRU Cache with optional TTL."""
    
    def __init__(self, max_size: int = 10000, default_ttl: Optional[int] = None):
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._cache: OrderedDict = OrderedDict()
        self._timestamps: Dict[str, float] = {}
        self._ttls: Dict[str, Optional[int]] = {}
        self._lock = threading.RLock()
        
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        with self._lock:
            if key not in self._cache:
                return None
            
            # Check TTL
            ttl = self._ttls.get(key)
            if ttl is not None:
                age = time.time() - self._timestamps.get(key, 0)
                if age > ttl:
                    self._remove(key)
                    return None
            
            # Move to end (most recently used)
            self._cache.move_to_end(key)
            return self._cache[key]
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set value in cache."""
        with self._lock:
            # Remove if exists
            if key in self._cache:
                self._remove(key)
            
            # Evict oldest if at capacity
            while len(self._cache) >= self.max_size:
                oldest_key = next(iter(self._cache))
                self._remove(oldest_key)
            
            # Add new entry
            self._cache[key] = value
            self._timestamps[key] = time.time()
            self._ttls[key] = ttl if ttl is not None else self.default_ttl
    
    def _remove(self, key: str) -> None:
        """Remove key from cache."""
        self._cache.pop(key, None)
        self._timestamps.pop(key, None)
        self._ttls.pop(key, None)
    
    def clear(self) -> None:
        """Clear all cache."""
        with self._lock:
            self._cache.clear()
            self._timestamps.clear()
            self._ttls.clear()
    
    def stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self._lock:
            return {
                "size": len(self._cache),
                "max_size": self.max_size,
                "default_ttl": self.default_ttl,
            }


class MultiLevelCache:
    """
    Multi-level cache system for BioDiscovery AI.
    
    Levels:
    - embeddings: Permanent cache for vector embeddings
    - results: 1-hour TTL cache for search results
    - llm: Permanent cache for LLM responses
    """
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._initialized = True
        
        # Level 1: Embeddings (permanent, large)
        self.embeddings = LRUCache(max_size=10000, default_ttl=None)
        
        # Level 2: Results (1 hour TTL)
        self.results = LRUCache(max_size=1000, default_ttl=3600)
        
        # Level 3: LLM responses (permanent, smaller)
        self.llm = LRUCache(max_size=500, default_ttl=None)
        
        # Stats
        self._hits = {"embeddings": 0, "results": 0, "llm": 0}
        self._misses = {"embeddings": 0, "results": 0, "llm": 0}
        
        logger.info("MultiLevelCache initialized")
    
    def get(self, key: str, level: str = "results") -> Optional[Any]:
        """Get from specific cache level."""
        cache = self._get_cache(level)
        value = cache.get(key)
        
        if value is not None:
            self._hits[level] = self._hits.get(level, 0) + 1
        else:
            self._misses[level] = self._misses.get(level, 0) + 1
        
        return value
    
    def set(self, key: str, value: Any, level: str = "results", ttl: Optional[int] = None) -> None:
        """Set in specific cache level."""
        cache = self._get_cache(level)
        cache.set(key, value, ttl)
    
    def _get_cache(self, level: str) -> LRUCache:
        """Get cache by level name."""
        if level == "embeddings":
            return self.embeddings
        elif level == "results":
            return self.results
        elif level == "llm":
            return self.llm
        else:
            return self.results  # default
    
    def get_embedding(self, content_hash: str) -> Optional[Any]:
        """Shortcut for embedding cache."""
        return self.get(f"emb:{content_hash}", "embeddings")
    
    def set_embedding(self, content_hash: str, value: Any) -> None:
        """Shortcut for embedding cache."""
        self.set(f"emb:{content_hash}", value, "embeddings")
    
    def get_results(self, query_hash: str) -> Optional[Any]:
        """Shortcut for results cache."""
        return self.get(f"res:{query_hash}", "results")
    
    def set_results(self, query_hash: str, value: Any) -> None:
        """Shortcut for results cache."""
        self.set(f"res:{query_hash}", value, "results", ttl=3600)
    
    def get_llm(self, prompt_hash: str) -> Optional[Any]:
        """Shortcut for LLM cache."""
        return self.get(f"llm:{prompt_hash}", "llm")
    
    def set_llm(self, prompt_hash: str, value: Any) -> None:
        """Shortcut for LLM cache."""
        self.set(f"llm:{prompt_hash}", value, "llm")
    
    def stats(self) -> Dict[str, Any]:
        """Get all cache statistics."""
        return {
            "embeddings": {
                **self.embeddings.stats(),
                "hits": self._hits.get("embeddings", 0),
                "misses": self._misses.get("embeddings", 0),
            },
            "results": {
                **self.results.stats(),
                "hits": self._hits.get("results", 0),
                "misses": self._misses.get("results", 0),
            },
            "llm": {
                **self.llm.stats(),
                "hits": self._hits.get("llm", 0),
                "misses": self._misses.get("llm", 0),
            },
        }
    
    def clear_all(self) -> None:
        """Clear all caches."""
        self.embeddings.clear()
        self.results.clear()
        self.llm.clear()
        logger.info("All caches cleared")


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def hash_content(content: str) -> str:
    """Generate hash for content."""
    return hashlib.sha256(content.encode()).hexdigest()[:16]


def hash_dict(d: Dict) -> str:
    """Generate hash for dictionary."""
    return hashlib.sha256(json.dumps(d, sort_keys=True).encode()).hexdigest()[:16]


# ============================================================
# SINGLETON ACCESSOR
# ============================================================

_cache_instance: Optional[MultiLevelCache] = None


def get_cache() -> MultiLevelCache:
    """Get singleton cache instance."""
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = MultiLevelCache()
    return _cache_instance
