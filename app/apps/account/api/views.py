from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response

from apps.account.models import Contact
from apps.account.selectors import public_users
from apps.actions.models import Action
from apps.actions.utils import create_action
from core.throttles import FollowRateThrottle
from .serializers import FollowSerializer


class UserFollowView(APIView):
    throttle_classes = [FollowRateThrottle]

    @extend_schema(request=FollowSerializer, responses={200: None})
    def post(self, request, pk):
        # Service accounts are hidden everywhere else, so there is nothing to
        # follow here either.
        user = get_object_or_404(public_users(), pk=pk)
        if user == request.user:
            return Response(
                {"error": "You cannot follow yourself."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = FollowSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        action = serializer.validated_data["action"]
        if action == "follow":
            Contact.objects.get_or_create(
                user_from=request.user.profile, user_to=user.profile
            )
            create_action(request.user, Action.Verb.FOLLOWED_USER, user)
        else:
            Contact.objects.filter(
                user_from=request.user.profile, user_to=user.profile
            ).delete()

        return Response({"status": "ok"})
