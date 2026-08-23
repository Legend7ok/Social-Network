from django.contrib.postgres.search import SearchQuery, SearchRank, TrigramSimilarity
from django.db.models import F, Q
from django.db.models.functions import Greatest

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
        # The id breaks ties: without it equal ranks may come back in a
        # different order per page and rows would repeat or go missing.
        .order_by("-rank", "-created", "-pk")
    )


def search_users(query):
    # Rows are picked by the trigram lookups, which the GIN index serves; the
    # similarity is then computed only for those rows, to rank them.
    return (
        public_users()
        .filter(
            Q(username__trigram_similar=query)
            | Q(first_name__trigram_similar=query)
            | Q(last_name__trigram_similar=query)
        )
        .annotate(
            similarity=Greatest(
                TrigramSimilarity("username", query),
                TrigramSimilarity("first_name", query),
                TrigramSimilarity("last_name", query),
            )
        )
        .order_by("-similarity", "first_name", "last_name", "pk")
    )
