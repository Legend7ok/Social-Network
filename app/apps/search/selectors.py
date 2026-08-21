from django.contrib.postgres.search import SearchQuery, SearchRank, TrigramSimilarity
from django.db.models import Count, F, IntegerField, OuterRef, Q, Subquery, Sum
from django.db.models.functions import Coalesce, Greatest

from apps.account.selectors import public_users
from apps.images.models import Image


def search_images(query):
    # websearch parses the way people already type ("red rose" -or blue) and
    # never raises on malformed input, unlike the plain tsquery syntax.
    search_query = SearchQuery(query, search_type="websearch", config="english")
    return (
        Image.objects.filter(search_vector=search_query)
        .annotate(rank=SearchRank(F("search_vector"), search_query))
        .select_related("user", "user__profile")
        .order_by("-rank", "-created")
    )


def search_users(query):
    likes_per_user = (
        Image.objects.filter(user=OuterRef("pk"))
        .values("user")
        .annotate(total=Sum("total_likes"))
        .values("total")
    )
    # Rows are picked by the trigram lookups, which the GIN index serves; the
    # similarity is then computed only for those rows, to rank them.
    return (
        public_users()
        .filter(
            Q(username__trigram_similar=query)
            | Q(first_name__trigram_similar=query)
            | Q(last_name__trigram_similar=query)
        )
        .select_related("profile")
        .annotate(
            similarity=Greatest(
                TrigramSimilarity("username", query),
                TrigramSimilarity("first_name", query),
                TrigramSimilarity("last_name", query),
            ),
            images_count=Count("images", distinct=True),
            followers_count=Count("profile__followers", distinct=True),
            total_likes=Coalesce(
                Subquery(likes_per_user, output_field=IntegerField()), 0
            ),
        )
        .order_by("-similarity", "first_name", "last_name")
    )
