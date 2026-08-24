def feed_cache_key(user_id):
    """Shared by the view that fills the feed cache and the signal that drops
    it, so a typo cannot silently break invalidation."""
    return f"feed_{user_id}"
