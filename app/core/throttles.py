from rest_framework.throttling import UserRateThrottle


class LikeRateThrottle(UserRateThrottle):
    scope = "like"


class FollowRateThrottle(UserRateThrottle):
    scope = "follow"
