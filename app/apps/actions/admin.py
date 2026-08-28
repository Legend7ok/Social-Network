from django.contrib import admin
from .models import Action


@admin.register(Action)
class ActionAdmin(admin.ModelAdmin):
    list_display = ["user", "verb", "target", "created"]
    list_filter = ["created"]
    search_fields = ["verb"]
    list_select_related = ["user"]

    def get_queryset(self, request):
        # The target hangs off a generic relation, so the changelist fetches it
        # one row at a time unless it is asked for in advance.
        return super().get_queryset(request).prefetch_related("target")
