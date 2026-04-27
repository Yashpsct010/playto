"""
URL configuration for the payouts API.
"""

from django.urls import path
from . import views

urlpatterns = [
    # Merchants
    path('merchants/', views.MerchantListView.as_view(), name='merchant-list'),
    path('merchants/<uuid:id>/', views.MerchantDetailView.as_view(), name='merchant-detail'),
    path(
        'merchants/<uuid:merchant_id>/ledger/',
        views.LedgerEntryListView.as_view(),
        name='merchant-ledger',
    ),

    # Payouts
    path('payouts/', views.PayoutCreateView.as_view(), name='payout-create'),
    path('payouts/list/', views.PayoutListView.as_view(), name='payout-list'),
    path('payouts/<uuid:id>/', views.PayoutDetailView.as_view(), name='payout-detail'),
]
