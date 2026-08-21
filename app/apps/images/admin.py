from django.contrib import admin
from .models import Image


@admin.register(Image)
class ImageAdmin(admin.ModelAdmin):
    list_display = ["title", "user", "total_likes", "total_views", "created"]
    list_filter = ["created"]
    list_select_related = ["user"]
    search_fields = ["title", "description", "user__username"]
    date_hierarchy = "created"
    raw_id_fields = ["user", "users_like"]
    # Counters are maintained by signals and the flush task, the slug follows
    # the title, and the timestamps are set automatically: editing any of them
    # by hand would only drift from reality.
    readonly_fields = [
        "slug",
        "total_likes",
        "total_views",
        "created",
        "updated",
        "edited_at",
    ]
