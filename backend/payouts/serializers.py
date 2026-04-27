"""
DRF Serializers for the payout engine.
"""

from rest_framework import serializers
from .models import Merchant, LedgerEntry, BankAccount, Payout
from .services import compute_merchant_balance


class BankAccountSerializer(serializers.ModelSerializer):
    display_name = serializers.SerializerMethodField()

    class Meta:
        model = BankAccount
        fields = [
            'id', 'account_number', 'ifsc_code',
            'account_holder_name', 'display_name', 'created_at',
        ]

    def get_display_name(self, obj):
        masked = 'X' * (len(obj.account_number) - 4) + obj.account_number[-4:]
        return f"{obj.account_holder_name} - {masked}"


class MerchantSerializer(serializers.ModelSerializer):
    """Merchant with computed balance fields (derived from ledger)."""
    total_balance_paise = serializers.SerializerMethodField()
    held_balance_paise = serializers.SerializerMethodField()
    available_balance_paise = serializers.SerializerMethodField()
    bank_accounts = BankAccountSerializer(many=True, read_only=True)

    class Meta:
        model = Merchant
        fields = [
            'id', 'name', 'email', 'created_at',
            'total_balance_paise', 'held_balance_paise',
            'available_balance_paise', 'bank_accounts',
        ]

    def get_total_balance_paise(self, obj):
        return self._get_balance(obj)['total_balance_paise']

    def get_held_balance_paise(self, obj):
        return self._get_balance(obj)['held_balance_paise']

    def get_available_balance_paise(self, obj):
        return self._get_balance(obj)['available_balance_paise']

    def _get_balance(self, obj):
        # Cache balance computation per serialization to avoid repeated queries
        if not hasattr(obj, '_cached_balance'):
            obj._cached_balance = compute_merchant_balance(obj.id)
        return obj._cached_balance


class LedgerEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = LedgerEntry
        fields = [
            'id', 'merchant', 'entry_type', 'amount_paise',
            'description', 'reference_id', 'created_at',
        ]


class PayoutSerializer(serializers.ModelSerializer):
    bank_account_display = serializers.SerializerMethodField()

    class Meta:
        model = Payout
        fields = [
            'id', 'merchant', 'bank_account', 'bank_account_display',
            'amount_paise', 'status', 'attempts', 'idempotency_key',
            'created_at', 'updated_at', 'processed_at',
        ]

    def get_bank_account_display(self, obj):
        return str(obj.bank_account)


class PayoutRequestSerializer(serializers.Serializer):
    """Validates incoming payout request body."""
    merchant_id = serializers.UUIDField()
    amount_paise = serializers.IntegerField(min_value=100)  # Min 1 INR
    bank_account_id = serializers.UUIDField()
