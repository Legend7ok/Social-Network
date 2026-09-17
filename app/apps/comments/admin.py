from django.contrib import admin
from django.utils.text import Truncator

from .models import Comment


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ["preview", "user", "image", "created", "removed_at"]
    list_filter = [("removed_at", admin.EmptyFieldListFilter), "created"]
    list_select_related = ["user", "image"]
    search_fields = ["body", "user__username"]
    date_hierarchy = "created"
    raw_id_fields = ["user", "image", "parent", "removed_by"]
    readonly_fields = ["created"]
    ordering = ["-created"]

    @admin.display(description="comment")
    def preview(self, comment):
        return Truncator(comment.body).chars(80)
