from django.db import models
from store.models import Store, Menu

class Review(models.Model):
    store = models.ForeignKey(
        Store, 
        on_delete=models.CASCADE,
        related_name='reviews'
    )

    class Source(models.TextChoices):
        NAVER_API = "NAVER_API", "네이버 블로그 검색 API"
        DUMMY = "DUMMY", "더미(테스트) 데이터"

    class Category(models.TextChoices):
        TASTE = "TASTE", "맛"
        PRICE = "PRICE", "가격"
        AMOUNT = "AMOUNT", "양"
        SERVICE = "SERVICE", "서비스"
        ATMOSPHERE = "ATMOSPHERE", "분위기"
        ETC = "ETC", "기타"

    # 리뷰 내용 (NAVER_API는 블로그 글 '제목'만 저장, 본문 아님)
    content = models.TextField()

    # 관련 메뉴 (없으면 매장 전체 리뷰)
    menu = models.ForeignKey(
        Menu, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='reviews'
    )
    category = models.CharField(max_length=10, choices=Category.choices, blank=True)
    source = models.CharField(max_length=10, choices=Source.choices, default=Source.DUMMY)
    # 네이버 블로그 글 링크 / 블로그명 (NAVER_API일 때만)
    url = models.URLField(max_length=500, blank=True)
    blogger_name = models.CharField(max_length=100, blank=True)

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
