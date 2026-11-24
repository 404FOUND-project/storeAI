from django.shortcuts import get_object_or_404

from .models import Store


def get_my_store(request, store_id):
    """본인 소유 매장만 접근 가능 (관리자는 모든 매장). 남의 매장은 404."""
    qs = Store.objects.all() if request.user.is_staff else Store.objects.filter(owner=request.user)
    return get_object_or_404(qs, pk=store_id)
