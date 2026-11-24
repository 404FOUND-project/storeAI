"""네이버 블로그 검색 API로 매장 관련 글 '제목/URL'만 수집 (본문·실제 고객 의견 아님).
사용: python manage.py collect_naver_reviews --store-id 1 [--query "키워드"] [--display 30]
"""
import html
import os
import re
from datetime import datetime

import json
import urllib.error
import urllib.parse
import urllib.request
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from review.models import Review
from store.models import Store

API_URL = os.environ.get("NAVER_API_URL", "https://naverapihub.apigw.ntruss.com/search/v1/blog")


class Command(BaseCommand):
    help = "네이버 블로그 검색 결과(제목/URL)를 Review(source=NAVER_API)로 저장"

    def add_arguments(self, parser):
        parser.add_argument("--store-id", type=int, required=True)
        parser.add_argument("--query", default="")
        parser.add_argument("--display", type=int, default=30)

    def handle(self, *args, **o):
        cid, sec = os.environ.get("NAVER_CLIENT_ID"), os.environ.get("NAVER_CLIENT_SECRET")
        if not cid or not sec:
            raise CommandError(".env에 NAVER_CLIENT_ID / NAVER_CLIENT_SECRET이 없습니다.")
        try:
            store = Store.objects.get(pk=o["store_id"])
        except Store.DoesNotExist:
            raise CommandError("해당 store-id 매장이 없습니다.")
        query = o["query"] or store.name
        qs = urllib.parse.urlencode({"query": query, "display": min(o["display"], 100), "sort": "date"})
        req = urllib.request.Request(
            f"{API_URL}?{qs}",
            headers={"X-NCP-APIGW-API-KEY-ID": cid, "X-NCP-APIGW-API-KEY": sec},
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                items = json.loads(r.read().decode("utf-8")).get("items", [])
        except (urllib.error.URLError, ValueError) as e:
            raise CommandError(f"네이버 API 호출 실패: {e}")
        if not items:
            self.stdout.write(f"'{query}' 검색 결과가 없습니다.")
            return
        new = 0
        for it in items:
            url = it.get("link", "")
            if Review.objects.filter(store=store, source="NAVER_API", url=url).exists():
                continue
            title = html.unescape(re.sub(r"<[^>]+>", "", it.get("title", "")))
            posted = None
            try:
                posted = timezone.make_aware(datetime.strptime(it.get("postdate", ""), "%Y%m%d"))
            except ValueError:
                pass
            Review.objects.create(
                store=store, content=title, source="NAVER_API", url=url,
                blogger_name=it.get("bloggername", ""), reviewed_at=posted,
                keywords={"query": query},
            )
            new += 1
        self.stdout.write(self.style.SUCCESS(f"'{query}': {len(items)}건 중 {new}건 새로 저장"))
