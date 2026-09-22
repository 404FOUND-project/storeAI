from rest_framework import serializers

from .models import Notice


class NoticeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notice
        fields = ['id', 'title', 'content', 'author', 'created_at', 'updated_at']
        # 작성자·시간 임의 변경 차단
        read_only_fields = ['id', 'author', 'created_at', 'updated_at']
