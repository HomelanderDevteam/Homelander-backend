
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenRefreshView
from rest_framework.parsers import FormParser, MultiPartParser

from . import selectors, services
from .serializers import (
    AuthResponseSerializer,
    ChangePasswordSerializer,
    LoginSerializer,
    GoogleAuthSerializer,
    LogoutSerializer,
    ProfileUpdateSerializer,
    RegisterSerializer,
    TokenPairSerializer,
    UserSerializer,
    KYCSubmissionSerializer,
    KYCSubmitSerializer,
)


TAG = ["Authentication"]


class PublicAPIView(APIView):
    """Endpoints that do not need a login.

    authentication_classes is empty on purpose: if the app sends an old or expired token
    to login/register, the request must still work instead of failing with a token error.
    """

    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]


class RegisterView(PublicAPIView):
    throttle_scope = "register"

    @extend_schema(request=RegisterSerializer, responses={201: AuthResponseSerializer}, tags=TAG,
                   summary="Create an account", description="Creates the account and logs the user in.")
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        user = services.register_user(
            first_name=data["first_name"],
            last_name=data["last_name"],
            email=data["email"],
            phone_number=data.get("phone_number"),
            password=data["password"],
        )

        tokens = services.issue_tokens_for_user(user)

        return Response(
            {
                "user": UserSerializer(user).data,
                **tokens,
            },
            status=status.HTTP_201_CREATED,
        )



class LoginView(PublicAPIView):
    throttle_scope = "login"

    @extend_schema(
        request=LoginSerializer,
        responses={200: AuthResponseSerializer},
        tags=TAG,
        summary="Log in with email and password",
    )
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user, tokens = services.login_user(
            **serializer.validated_data
        )

        return Response(
            {
                "user": UserSerializer(user).data,
                **tokens,
            },
            status=status.HTTP_200_OK,
        )


class GoogleAuthView(PublicAPIView):
    throttle_scope = "google"

    @extend_schema(
        request=GoogleAuthSerializer,
        responses={200: AuthResponseSerializer},
        tags=TAG,
        summary="Sign up or log in with Google",
        description=(
            "Authenticates a Google account using its verified email. "
            "A phone number is optional."
        ),
    )
    def post(self, request):
        serializer = GoogleAuthSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data

        user, tokens = services.google_authenticate(
            token=data["id_token"],
            phone_number=data.get("phone_number"),
        )

        return Response(
            {
                "user": UserSerializer(user).data,
                **tokens,
            },
            status=status.HTTP_200_OK,
        )


class RefreshView(TokenRefreshView):
    """Exchange a refresh token for a new access token (and a new refresh token)."""

    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "refresh"

    @extend_schema(tags=TAG, summary="Get a new access token",
                   description="The old refresh token stops working; store the new one that comes back.")
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class LogoutView(PublicAPIView):
    """Needs only the refresh token, so users can still log out after their access token expired."""

    @extend_schema(request=LogoutSerializer, responses={200: OpenApiResponse(description="Logged out")}, tags=TAG,
                   summary="Log out (blacklists the refresh token)")
    def post(self, request):
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.logout_user(refresh_token=serializer.validated_data["refresh"])
        return Response({"detail": "Logged out."}, status=status.HTTP_200_OK)


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: UserSerializer}, tags=TAG, summary="Get my profile")
    def get(self, request):
        return Response(UserSerializer(request.user).data)

    @extend_schema(request=ProfileUpdateSerializer, responses={200: UserSerializer}, tags=TAG,
                   summary="Update my profile", description="Only first name, last name and email can be changed.")
    def patch(self, request):
        serializer = ProfileUpdateSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        user = services.update_profile(user=request.user, **serializer.validated_data)
        return Response(UserSerializer(user).data)


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "password"

    @extend_schema(request=ChangePasswordSerializer, responses={200: TokenPairSerializer}, tags=TAG,
                   summary="Change my password",
                   description="Signs the user out of every device and returns fresh tokens for this one.")
    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        tokens = services.change_password(user=request.user, new_password=serializer.validated_data["new_password"])
        return Response(tokens, status=status.HTTP_200_OK)

class KYCView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    @extend_schema(responses={200: KYCSubmissionSerializer}, tags=TAG,
                   summary="Get my latest KYC submission",
                   description="Returns status NOT_SUBMITTED if the user has never submitted.")
    def get(self, request):
        submission = selectors.get_latest_kyc(request.user)
        if submission is None:
            return Response({"status": "NOT_SUBMITTED"})
        return Response(KYCSubmissionSerializer(submission).data)

    @extend_schema(request={"multipart/form-data": KYCSubmitSerializer},
                   responses={201: KYCSubmissionSerializer}, tags=TAG,
                   summary="Submit KYC documents")
    def post(self, request):
        serializer = KYCSubmitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        submission = services.submit_kyc(
            user=request.user, documents=list(zip(data["document_types"], data["documents"]))
        )
        return Response(KYCSubmissionSerializer(submission).data, status=status.HTTP_201_CREATED)
