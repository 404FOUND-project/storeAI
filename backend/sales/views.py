from datetime import timedelta

from django.db.models import Sum
from django.db.models.functions import TruncDate
from django.utils import timezone

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from store.models import Store
from .models import Sales


class SalesSummaryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        store = Store.objects.filter(owner=request.user).first()

        if store is None:
            return Response(
                {'detail': '등록된 매장이 없습니다.'},
                status=404
            )

        now = timezone.localtime()
        today = now.date()

        sales = Sales.objects.filter(store=store)

        today_sales = sales.filter(sold_at__date=today)

        today_total = today_sales.aggregate(
            total=Sum('total_amount')
        )['total'] or 0

        today_count = today_sales.count()

        average_amount = (
            round(today_total / today_count)
            if today_count else 0
        )

        seven_days_ago = today - timedelta(days=6)

        weekly_sales = (
            sales.filter(
                sold_at__date__gte=seven_days_ago,
                sold_at__date__lte=today,
            )
            .annotate(date=TruncDate('sold_at'))
            .values('date')
            .annotate(total=Sum('total_amount'))
            .order_by('date')
        )

        weekly_data = [
            {
                'date': item['date'].isoformat(),
                'total': item['total'],
            }
            for item in weekly_sales
        ]

        return Response({
            'store_name': store.name,
            'today_total': today_total,
            'today_count': today_count,
            'average_amount': average_amount,
            'weekly_sales': weekly_data,
        })