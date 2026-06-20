from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.core.cache import cache
from .models import Book, Rating, OrderItem, Category

@receiver([post_save, post_delete], sender=Book)
@receiver([post_save, post_delete], sender=Rating)
@receiver([post_save, post_delete], sender=OrderItem)
@receiver([post_save, post_delete], sender=Category)
def clear_book_catalog_caches(sender, **kwargs):
    # Clear popular and top rated books caches
    try:
        cache.delete_pattern("popular_books_*")
        cache.delete_pattern("top_rated_books_*")
    except AttributeError:
        # Fallback if delete_pattern is not supported (e.g. LocMemCache)
        for limit in [8, 12, 15, 20]:
            cache.delete(f"popular_books_{limit}")
            cache.delete(f"top_rated_books_{limit}")
            
    # Clear category list cache
    cache.delete("category_list_cache")
