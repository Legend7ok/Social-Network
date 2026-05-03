from rest_framework import serializers


class FollowSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=["follow", "unfollow"])
