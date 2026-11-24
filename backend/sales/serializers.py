
from rest_framework import serializers
from .models import Sales, SalesItem


class SalesItemSerializer(serializers.ModelSerializer):
    menu_name = serializers.CharField(
        source='menu.name',
        read_only=True
    )

    class Meta:
        model = SalesItem
        fields = [
            'id',
            'menu',
            'menu_name',
            'quantity',
            'unit_price',
        ]


class SalesSerializer(serializers.ModelSerializer):
    items = SalesItemSerializer(many=True, read_only=True)

    class Meta:
        model = Sales
        fields = [
            'id',
            'sold_at',
            'total_amount',
            'items',
        ]
