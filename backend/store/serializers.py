from rest_framework import serializers

from .models import Menu, Store


class MyStoreSerializer(serializers.ModelSerializer):
    """사장님 본인 매장 조회·수정용. (소유자, 원본 ID, 데이터 구분은 수정 불가)"""

    class Meta:
        model = Store
        fields = [
            "id", "name", "address", "phone", "business_number",
            "latitude", "longitude", "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class MenuSerializer(serializers.ModelSerializer):
    class Meta:
        model = Menu
        fields = ["id", "pos_code", "name", "category", "price", "cost", "is_active"]
        read_only_fields = ["id"]

    def validate_price(self, value):
        if value <= 0:
            raise serializers.ValidationError("가격은 0보다 커야 합니다.")
        return value
