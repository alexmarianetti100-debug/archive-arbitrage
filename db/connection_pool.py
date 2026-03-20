"""
Database Connection Pool for SQLite

Provides connection pooling with:
- Singleton pattern (one pool per process)
- Context manager for transactions
- Connection health checks
- Automatic reconnection
- Thread-safe operations
- Performance metrics
"""

import logging
import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Optional, List, Dict, Any, Generator

logger = logging.getLogger("db_pool")

DEFAULT_DB_PATH = Path(__file__).parent.parent / "data" / "archive.db"
DEFAULT_POOL_SIZE = 5
DEFAULT_TIMEOUT = 30.0


class PooledConnection:
    """
    Wrapper for sqlite3.Connection that returns to pool on close().
    """
    def __init__(self, conn: sqlite3.Connection, pool: 'ConnectionPool'):
        self._conn = conn
        self._pool = pool
        self._closed = False
    
    def __getattr__(self, name):
        """Delegate all other attributes to the real connection."""
        return getattr(self._conn, name)
    
    def close(self):
        """Return connection to pool instead of closing."""
        if not self._closed:
            self._pool._return_connection(self._conn)
            self._closed = True
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


class ConnectionPool:
    """
    Thread-safe SQLite connection pool.
    
    Usage:
        pool = ConnectionPool()
        
        # Get connection
        with pool.connection() as conn:
            cursor = conn.execute("SELECT * FROM items")
            
        # Transaction
        with pool.transaction() as conn:
            conn.execute("INSERT INTO items ...")
            conn.commit()
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls, *args, **kwargs):
        """Singleton pattern - one pool per process."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, db_path: Optional[Path] = None, pool_size: int = DEFAULT_POOL_SIZE):
        if self._initialized:
            return
        
        self.db_path = db_path or DEFAULT_DB_PATH
        self.pool_size = pool_size
        self._pool: List[sqlite3.Connection] = []
        self._in_use: set = set()
        self._pool_lock = threading.Lock()
        self._condition = threading.Condition(self._pool_lock)
        self._initialized = True
        self._metrics = {
            "connections_created": 0,
            "connections_reused": 0,
            "connections_closed": 0,
            "transactions": 0,
            "errors": 0,
        }
        
        # Ensure directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Initialize pool
        self._initialize_pool()
        
        logger.info(f"Connection pool initialized: {pool_size} connections")
    
    def _initialize_pool(self):
        """Create initial pool of connections."""
        for _ in range(self.pool_size):
            conn = self._create_connection()
            if conn:
                self._pool.append(conn)
    
    def _create_connection(self) -> Optional[sqlite3.Connection]:
        """Create a new database connection with optimal settings."""
        try:
            conn = sqlite3.connect(
                str(self.db_path),
                timeout=DEFAULT_TIMEOUT,
                check_same_thread=False,  # Allow sharing across threads
            )
            conn.row_factory = sqlite3.Row
            
            # Performance optimizations
            conn.execute("PRAGMA journal_mode=WAL")  # Write-ahead logging
            conn.execute("PRAGMA foreign_keys=ON")   # Enforce foreign keys
            conn.execute("PRAGMA synchronous=NORMAL") # Balance safety/speed
            conn.execute("PRAGMA cache_size=10000")   # 10MB cache
            conn.execute("PRAGMA temp_store=MEMORY")  # Temp tables in memory
            
            self._metrics["connections_created"] += 1
            return conn
            
        except Exception as e:
            logger.error(f"Failed to create connection: {e}")
            self._metrics["errors"] += 1
            return None
    
    def _is_connection_healthy(self, conn: sqlite3.Connection) -> bool:
        """Check if a connection is still valid."""
        try:
            conn.execute("SELECT 1")
            return True
        except:
            return False
    
    def _get_connection(self, wrap: bool = True) -> sqlite3.Connection:
        """Get a connection from the pool (blocks if none available)."""
        with self._condition:
            # Wait for available connection
            while not self._pool:
                self._condition.wait(timeout=DEFAULT_TIMEOUT)
                if not self._pool:
                    # Timeout - create emergency connection
                    logger.warning("Pool exhausted, creating emergency connection")
                    conn = self._create_connection()
                    if wrap:
                        return PooledConnection(conn, self)
                    return conn
            
            # Get connection from pool
            conn = self._pool.pop()
            
            # Check health
            if not self._is_connection_healthy(conn):
                logger.debug("Connection unhealthy, recreating")
                conn.close()
                conn = self._create_connection()
            
            self._in_use.add(id(conn))
            self._metrics["connections_reused"] += 1
            
            if wrap:
                return PooledConnection(conn, self)
            return conn
    
    def _return_connection(self, conn: sqlite3.Connection):
        """Return a connection to the pool."""
        with self._condition:
            self._in_use.discard(id(conn))
            
            if self._is_connection_healthy(conn):
                self._pool.append(conn)
            else:
                logger.debug("Discarding unhealthy connection")
                try:
                    conn.close()
                    self._metrics["connections_closed"] += 1
                except:
                    pass
            
            self._condition.notify()
    
    @contextmanager
    def connection(self) -> Generator[sqlite3.Connection, None, None]:
        """
        Context manager for database connections.
        
        Usage:
            with pool.connection() as conn:
                cursor = conn.execute("SELECT * FROM items")
                rows = cursor.fetchall()
        """
        conn = None
        try:
            conn = self._get_connection(wrap=False)
            yield conn
        finally:
            if conn:
                self._return_connection(conn)
    
    @contextmanager
    def transaction(self) -> Generator[sqlite3.Connection, None, None]:
        """
        Context manager for database transactions.
        Auto-commits on success, rolls back on exception.
        
        Usage:
            with pool.transaction() as conn:
                conn.execute("INSERT INTO items ...")
                # Auto-committed if no exception
        """
        conn = None
        try:
            conn = self._get_connection(wrap=False)
            conn.execute("BEGIN")
            yield conn
            conn.commit()
            self._metrics["transactions"] += 1
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Transaction failed: {e}")
            raise
        finally:
            if conn:
                self._return_connection(conn)
    
    def execute(self, query: str, params: tuple = ()) -> List[sqlite3.Row]:
        """
        Execute a query and return results.
        Convenience method for simple queries.
        """
        with self.connection() as conn:
            cursor = conn.execute(query, params)
            return cursor.fetchall()
    
    def execute_many(self, query: str, params_list: List[tuple]) -> int:
        """
        Execute a query multiple times (batch insert/update).
        Returns number of rows affected.
        """
        with self.transaction() as conn:
            cursor = conn.executemany(query, params_list)
            return cursor.rowcount
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get connection pool metrics."""
        with self._pool_lock:
            return {
                **self._metrics,
                "pool_size": self.pool_size,
                "available": len(self._pool),
                "in_use": len(self._in_use),
                "db_path": str(self.db_path),
            }
    
    def close_all(self):
        """Close all connections in the pool."""
        with self._pool_lock:
            for conn in self._pool:
                try:
                    conn.close()
                    self._metrics["connections_closed"] += 1
                except:
                    pass
            self._pool.clear()
            self._in_use.clear()
        
        logger.info("All connections closed")
    
    def __del__(self):
        """Cleanup on destruction."""
        if hasattr(self, '_pool'):
            self.close_all()


# Convenience functions for backward compatibility

def get_db_connection() -> sqlite3.Connection:
    """
    Get a database connection (for backward compatibility).
    
    NOTE: This creates a new connection each time. 
    Use ConnectionPool for better performance.
    """
    pool = ConnectionPool()
    # Return a connection that won't be managed by pool
    # This is for code that manages its own connections
    return pool._create_connection()


@contextmanager
def db_transaction():
    """Context manager for database transactions."""
    pool = ConnectionPool()
    with pool.transaction() as conn:
        yield conn


@contextmanager
def db_connection():
    """Context manager for database connections."""
    pool = ConnectionPool()
    with pool.connection() as conn:
        yield conn


# Initialize pool on module load
_pool = None

def init_pool(db_path: Optional[Path] = None, pool_size: int = DEFAULT_POOL_SIZE):
    """Initialize the connection pool."""
    global _pool
    _pool = ConnectionPool(db_path, pool_size)
    return _pool


def get_pool() -> ConnectionPool:
    """Get the connection pool instance."""
    global _pool
    if _pool is None:
        _pool = ConnectionPool()
    return _pool
