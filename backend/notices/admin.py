from django.contrib import admin

from .models import Notice


@admin.register(Notice)
class NoticeAdmin(admin.ModelAdmin):
    list_display = ['id', 'title', 'author', 'created_at', 'updated_at']
    search_fields = ['title', 'content']
    readonly_fields = ['author', 'created_at', 'updated_at']

    def save_model(self, request, obj, form, change):
        # 관리자 화면 신규 작성자 지정
        if not change:
            obj.author = request.user
        super().save_model(request, obj, form, change)
