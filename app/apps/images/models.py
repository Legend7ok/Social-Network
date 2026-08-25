from django.conf import settings
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVector, SearchVectorField
from django.db import models
from django.urls import reverse
from django.utils.text import slugify


class Image(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name="images", on_delete=models.CASCADE
    )
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, blank=True, allow_unicode=True)
    url = models.URLField(max_length=2000)
    image = models.ImageField(upload_to="images/%Y/%m/%d", null=True, blank=True)
    # Why the file never arrived, in words meant for the person who bookmarked
    # it. Empty while a download is still on its way and once it succeeds, so
    # the three states read off the two columns: file, error, neither.
    download_error = models.CharField(max_length=200, blank=True)
    description = models.TextField(blank=True)
    created = models.DateTimeField(auto_now_add=True)
    # Set by ImageEditForm only, so background saves of the row (the file
    # download finishing, for one) do not mark a fresh image as edited.
    edited_at = models.DateTimeField(null=True, blank=True)
    users_like = models.ManyToManyField(
        settings.AUTH_USER_MODEL, related_name="images_liked", blank=True
    )
    total_likes = models.PositiveIntegerField(default=0)
    # Views are counted in Redis and flushed here periodically; this column is
    # the durable source of truth and what the ranking page sorts by.
    total_views = models.PositiveIntegerField(default=0)
    # A generated column keeps the vector in sync even when rows are written
    # outside the model (bulk updates, data migrations, admin actions).
    search_vector = models.GeneratedField(
        expression=SearchVector("title", weight="A", config="english")
        + SearchVector("description", weight="B", config="english"),
        output_field=SearchVectorField(),
        db_persist=True,
    )

    class Meta:
        indexes = [
            models.Index(fields=["-created"]),
            models.Index(fields=["-total_likes"]),
            models.Index(fields=["-total_views"]),
            GinIndex(fields=["search_vector"], name="image_search_vector_gin"),
        ]
        ordering = ["-created"]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        self.slug = slugify(self.title, allow_unicode=True) or "image"
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("images:detail", args=[self.id, self.slug])
