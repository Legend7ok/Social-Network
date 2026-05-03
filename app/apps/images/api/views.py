from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response

from apps.images.models import Image
from apps.actions.utils import create_action
from .serializers import LikeSerializer


class ImageLikeView(APIView):
    def post(self, request, pk):
        image = get_object_or_404(Image, pk=pk)
        serializer = LikeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        action = serializer.validated_data["action"]
        if action == "like":
            image.users_like.add(request.user)
            create_action(request.user, "likes", image)
        else:
            image.users_like.remove(request.user)

        return Response({"status": "ok"})
