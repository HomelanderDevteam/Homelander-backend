from rest_framework import status
from rest_framework.exceptions import APIException


class InvalidCredentials(APIException):
    status_code = status.HTTP_401_UNAUTHORIZED
    default_detail = "Invalid phone number, email or password."
    default_code = "invalid_credentials"


class AccountDisabled(APIException):
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = "This account has been deactivated. Please contact support."
    default_code = "account_disabled"


class DuplicateAccount(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "An account with these details already exists."
    default_code = "duplicate_account"

class KYCAlreadyActive(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "You already have a KYC submission that is pending or approved."
    default_code = "kyc_already_active"
