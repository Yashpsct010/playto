"""
API Views for the payout engine.

Key view: PayoutCreateView handles the POST /api/v1/payouts/ endpoint with
full idempotency support via the Idempotency-Key header.
"""

import logging
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Merchant, LedgerEntry, Payout
from .serializers import (
    MerchantSerializer,
    LedgerEntrySerializer,
    PayoutSerializer,
    PayoutRequestSerializer,
)
from .services import (
    create_payout,
    check_idempotency,
    InsufficientBalance,
    InvalidBankAccount,
)

logger = logging.getLogger(__name__)


class MerchantListView(generics.ListAPIView):
    """List all merchants with their computed balances."""
    queryset = Merchant.objects.all()
    serializer_class = MerchantSerializer
    pagination_class = None  # Return all merchants (we only have 2-3)


class MerchantDetailView(generics.RetrieveAPIView):
    """Get a single merchant with computed balances and bank accounts."""
    queryset = Merchant.objects.all()
    serializer_class = MerchantSerializer
    lookup_field = 'id'


class LedgerEntryListView(generics.ListAPIView):
    """
    List ledger entries for a merchant.
    Supports filtering by entry_type via query param.
    """
    serializer_class = LedgerEntrySerializer

    def get_queryset(self):
        merchant_id = self.kwargs['merchant_id']
        queryset = LedgerEntry.objects.filter(merchant_id=merchant_id)

        entry_type = self.request.query_params.get('entry_type')
        if entry_type:
            queryset = queryset.filter(entry_type=entry_type.upper())

        return queryset


class PayoutCreateView(APIView):
    """
    POST /api/v1/payouts/

    Create a payout request with idempotency support.

    Headers:
        Idempotency-Key: <merchant-supplied UUID> (REQUIRED)

    Body:
        {
            "merchant_id": "<uuid>",
            "amount_paise": 500000,
            "bank_account_id": "<uuid>"
        }

    Idempotency behavior:
    - First call: creates payout, returns 201
    - Second call with same key + same merchant: returns cached 201 response
    - Keys are scoped per merchant and expire after 24 hours
    """

    def post(self, request):
        # 1. Validate Idempotency-Key header
        idempotency_key = request.headers.get('Idempotency-Key')
        if not idempotency_key:
            return Response(
                {'error': 'Idempotency-Key header is required'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 2. Validate request body
        serializer = PayoutRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {'error': 'Invalid request', 'details': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        merchant_id = serializer.validated_data['merchant_id']
        amount_paise = serializer.validated_data['amount_paise']
        bank_account_id = serializer.validated_data['bank_account_id']

        # 3. Check idempotency — return cached response if key was seen before
        cached = check_idempotency(merchant_id, idempotency_key)
        if cached is not None:
            response_status, response_body = cached
            logger.info(
                f"Idempotency hit for merchant {merchant_id}, "
                f"key {idempotency_key}"
            )
            return Response(response_body, status=response_status)

        # 4. Create the payout (with concurrency protection)
        try:
            status_code, response_data = create_payout(
                merchant_id=merchant_id,
                amount_paise=amount_paise,
                bank_account_id=bank_account_id,
                idempotency_key=idempotency_key,
            )
            return Response(response_data, status=status_code)

        except InsufficientBalance as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except InvalidBankAccount as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Merchant.DoesNotExist:
            return Response(
                {'error': f'Merchant {merchant_id} not found'},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            logger.exception(f"Unexpected error creating payout: {e}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class PayoutListView(generics.ListAPIView):
    """
    List payouts, optionally filtered by merchant_id query param.
    Used by the dashboard to show payout history with live status.
    """
    serializer_class = PayoutSerializer

    def get_queryset(self):
        queryset = Payout.objects.all()
        merchant_id = self.request.query_params.get('merchant')
        if merchant_id:
            queryset = queryset.filter(merchant_id=merchant_id)
        return queryset


class PayoutDetailView(generics.RetrieveAPIView):
    """Get a single payout's details and current status."""
    queryset = Payout.objects.all()
    serializer_class = PayoutSerializer
    lookup_field = 'id'
