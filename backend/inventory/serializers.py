from rest_framework import serializers

from .models import Inventory
from .stock_services import expiry_status, stock_status


class InventorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Inventory
        fields = ["id", "ingredient_name", "quantity", "unit", "expiration_date", "update_at"]
        read_only_fields = ["id", "update_at"]

    def validate_quantity(self, value):
        if value < 0:
            raise serializers.ValidationError("재고량은 0 이상이어야 합니다.")
        return value

    def to_representation(self, instance):
        data = super().to_representation(instance)
        per_day = self.context.get("usage", {}).get(instance.id)
        days_left, state = stock_status(instance.quantity, per_day)
        exp_days, exp_state = expiry_status(instance.expiration_date)
        data.update({
            "daily_usage": round(float(per_day), 2) if per_day else None,
            "days_left": round(days_left, 1) if days_left is not None else None,
            "stock_status": state,            # danger / low / ok / no_usage
            "days_to_expiry": exp_days,
            "expiry_status": exp_state,       # expired / expiring / ok / none
        })
        return data
