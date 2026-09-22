from django.conf import settings
from django.db import models


class Notice(models.Model):
    title = models.CharField(max_length=200)
    content = models.TextField()
    # 작성자 삭제 시 공지 유지
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='notices',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        # 최신순 정렬
        ordering = ['-created_at', '-id']
        verbose_name = '공지사항'
        verbose_name_plural = '공지사항'

    def __str__(self):
        return self.title
