from django.db import models
from django.conf import settings
from django.utils.text import slugify
from django.urls import reverse


class Image(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name="images", on_delete=models.CASCADE
    )
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, blank=True, allow_unicode=True)
    url = models.URLField(max_length=2000)
    image = models.ImageField(upload_to="images/%Y/%m/%d", null=True, blank=True)
    description = models.TextField(blank=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    users_like = models.ManyToManyField(
        settings.AUTH_USER_MODEL, related_name="images_liked", blank=True
    )
    total_likes = models.PositiveIntegerField(default=0)
    # Views are counted in Redis and flushed here periodically; this column is
    # the durable source of truth and what the ranking page sorts by.
    total_views = models.PositiveIntegerField(default=0)

    class Meta:
        indexes = [
            models.Index(fields=["-created"]),
            models.Index(fields=["-total_likes"]),
            models.Index(fields=["-total_views"]),
        ]
        ordering = ["-created"]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        self.slug = slugify(self.title, allow_unicode=True) or "image"
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("images:detail", args=[self.id, self.slug])
