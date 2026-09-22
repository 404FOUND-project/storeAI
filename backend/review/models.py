from django.db import models
from store.models import Store

class Review(models.Model):
    store = models.ForeignKey(
        Store, 
        on_delete=models.CASCADE,
        related_name='reviews'
    )

    content = models.TextField()

    # 별점
    rating = models.DecimalField(
        max_digits=2, 
        decimal_places=1, 
        null=True,
        blank=True
    )

    # AI 분석 결과: positive, negative, neutral
    sentiment = models.CharField(
        max_length=10,
        blank=True
    )

    # AI가 뽑은 키워드
    keywords = models.JSONField(
        blank=True,
        null=True
    )

    # 실제 리뷰 작성일
    reviewed_at = models.DateTimeField(
        null=True,
        blank=True
    )

    create_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Review for {self.store.name} - {self.id}"
