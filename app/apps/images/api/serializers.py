from rest_framework import serializers


class LikeSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=["like", "unlike"])
