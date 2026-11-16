from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView

from . import services
from .serializers import WaitlistJoinSerializer


class WaitlistThrottle(AnonRateThrottle):
    scope = "waitlist"

    def get_rate(self):
        return "10/hour"  # per IP address; defined here so no settings change is needed


class WaitlistView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [WaitlistThrottle]

    @extend_schema(
        request=WaitlistJoinSerializer,
        responses={201: OpenApiResponse(description="On the waitlist")},
        tags=["Waitlist"],
        summary="Join the waitlist",
        description="Always returns 201 for a valid request, including when the email was already "
                    "on the list, so the endpoint can't be used to check who has signed up.",
    )
    def post(self, request):
        serializer = WaitlistJoinSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.join_waitlist(**serializer.validated_data)
        return Response({"detail": "You're on the waitlist."}, status=status.HTTP_201_CREATED)
