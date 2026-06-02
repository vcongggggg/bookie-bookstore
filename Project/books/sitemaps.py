from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from .models import Book, Category


class StaticViewSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.6

    def items(self):
        return ["home", "book_list", "ebook_list", "category_list", "about", "contact"]

    def location(self, item):
        return reverse(item)


class BookSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.8

    def items(self):
        return Book.objects.all().order_by("id")

    def lastmod(self, obj):
        return obj.created_at

    def location(self, obj):
        return reverse("book_detail", args=[obj.pk])


class CategorySitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.7

    def items(self):
        return Category.objects.all().order_by("id")

    def location(self, obj):
        return reverse("category_detail", args=[obj.pk])
