from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response

from apps.account.models import Contact
from apps.actions.utils import create_action
from .serializers import FollowSerializer

User = get_user_model()


class UserFollowView(APIView):
    def post(self, request, pk):
        user = get_object_or_404(User, pk=pk, is_active=True)
        serializer = FollowSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        action = serializer.validated_data["action"]
        if action == "follow":
            Contact.objects.get_or_create(
                user_from=request.user.profile, user_to=user.profile
            )
            create_action(request.user, "is following", user)
        else:
            Contact.objects.filter(
                user_from=request.user.profile, user_to=user.profile
            ).delete()

        return Response({"status": "ok"})
