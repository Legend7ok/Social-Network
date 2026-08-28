from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework.views import APIView
from rest_framework.response import Response

from apps.images.models import Image
from apps.actions.models import Action
from apps.actions.utils import create_action
from core.throttles import LikeRateThrottle
from .serializers import LikeSerializer


class ImageLikeView(APIView):
    throttle_classes = [LikeRateThrottle]

    @extend_schema(request=LikeSerializer, responses={200: None})
    def post(self, request, pk):
        image = get_object_or_404(Image, pk=pk)
        serializer = LikeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        action = serializer.validated_data["action"]
        if action == "like":
            image.users_like.add(request.user)
            # Liking your own picture is allowed, but announcing it is not: the
            # followers who already saw "uploaded image" would get the same
            # picture again as "likes".
            if image.user_id != request.user.id:
                create_action(request.user, Action.Verb.LIKED_IMAGE, image)
        else:
            image.users_like.remove(request.user)

        return Response({"status": "ok"})
